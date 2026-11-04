"""
Pruebas de: idempotencia de ventas, fijar/ajustar stock atómicos con movimiento y
las métricas del piloto (§2.3). No requieren SQLAlchemy ni interfaz gráfica.
"""
import threading
import unittest

from tests.test_transacciones import BaseTest, _q
from backend.base_datos.transacciones import (
    registrar_venta_atomica, ajustar_stock_atomico, fijar_stock_atomico,
    ConflictoStockError, StockInsuficienteError,
)
from backend.base_datos.metricas import (
    registrar_tiempo_manual, registrar_conteo_fisico, resumen_metricas, datos_metricas,
)


class TestIdempotenciaYDuracion(BaseTest):
    def test_mismo_op_id_no_vende_dos_veces(self):
        it = [self.item(1, "Pan", 100, 2)]
        v1 = registrar_venta_atomica(1, 200.0, "Efectivo", it, op_id="abc123", db_path=self.db)
        v2 = registrar_venta_atomica(1, 200.0, "Efectivo", it, op_id="abc123", db_path=self.db)
        self.assertFalse(v1.ya_registrada)
        self.assertTrue(v2.ya_registrada)
        self.assertEqual(v1.id, v2.id)
        self.assertEqual(_q(self.db, "SELECT stock FROM productos WHERE id=1")[0][0], 8)   # descontó UNA vez
        self.assertEqual(_q(self.db, "SELECT COUNT(*) FROM ventas")[0][0], 1)

    def test_op_id_distintos_son_ventas_distintas(self):
        it = [self.item(1, "Pan", 100, 1)]
        registrar_venta_atomica(1, 100.0, "Efectivo", it, op_id="a", db_path=self.db)
        registrar_venta_atomica(1, 100.0, "Efectivo", it, op_id="b", db_path=self.db)
        self.assertEqual(_q(self.db, "SELECT COUNT(*) FROM ventas")[0][0], 2)

    def test_reintentos_concurrentes_con_mismo_op_id(self):
        resultados = []
        def reintentar():
            resultados.append(registrar_venta_atomica(
                1, 100.0, "Efectivo", [self.item(1, "Pan", 100, 1)], op_id="mismo", db_path=self.db))
        hs = [threading.Thread(target=reintentar) for _ in range(5)]
        [h.start() for h in hs]; [h.join() for h in hs]
        self.assertEqual(len({r.id for r in resultados}), 1)
        self.assertEqual(sum(1 for r in resultados if not r.ya_registrada), 1)
        self.assertEqual(_q(self.db, "SELECT stock FROM productos WHERE id=1")[0][0], 9)

    def test_guarda_duracion(self):
        v = registrar_venta_atomica(1, 100.0, "Efectivo", [self.item(1, "Pan", 100, 1)],
                                    duracion_seg=12.5, db_path=self.db)
        self.assertEqual(_q(self.db, "SELECT duracion_seg FROM ventas WHERE id=?", (v.id,))[0][0], 12.5)


class TestStockAtomico(BaseTest):
    def test_ajuste_con_movimiento_en_la_misma_transaccion(self):
        nuevo = ajustar_stock_atomico(1, +5, usuario_id=1, tipo="entrada", descripcion="Reposición", db_path=self.db)
        self.assertEqual(nuevo, 15)
        self.assertEqual(_q(self.db, "SELECT cantidad,tipo,descripcion FROM movimientos_stock")[0],
                         (5, "entrada", "Reposición"))

    def test_ajuste_rechazado_no_deja_movimiento(self):
        with self.assertRaises(StockInsuficienteError):
            ajustar_stock_atomico(2, -50, usuario_id=1, tipo="ajuste", db_path=self.db)
        self.assertEqual(_q(self.db, "SELECT COUNT(*) FROM movimientos_stock")[0][0], 0)

    def test_fijar_stock_ok_y_movimiento_por_diferencia(self):
        self.assertEqual(fijar_stock_atomico(1, 4, esperado=10, usuario_id=1, tipo="ajuste", db_path=self.db), 4)
        self.assertEqual(_q(self.db, "SELECT cantidad FROM movimientos_stock")[0][0], -6)

    def test_fijar_stock_detecta_cambio_de_otra_caja(self):
        # La pantalla mostraba 10; otra caja vendió 3 → ahora hay 7. Fijar "esperando 10" debe fallar.
        registrar_venta_atomica(1, 300.0, "Efectivo", [self.item(1, "Pan", 100, 3)], db_path=self.db)
        with self.assertRaises(ConflictoStockError) as ctx:
            fijar_stock_atomico(1, 20, esperado=10, db_path=self.db)
        self.assertEqual((ctx.exception.esperado, ctx.exception.actual), (10, 7))
        self.assertEqual(_q(self.db, "SELECT stock FROM productos WHERE id=1")[0][0], 7)  # no se pisó

    def test_fijar_stock_negativo_y_producto_inexistente(self):
        with self.assertRaises(ValueError):
            fijar_stock_atomico(1, -1, db_path=self.db)
        self.assertIsNone(fijar_stock_atomico(99, 5, db_path=self.db))


class TestEventosYAlertas(BaseTest):
    def test_alerta_al_cruzar_el_minimo(self):
        # Pan: stock 10, mínimo 2. Vender 8 → queda 2 (== mínimo) → alerta
        registrar_venta_atomica(1, 800.0, "Efectivo", [self.item(1, "Pan", 100, 8)], db_path=self.db)
        self.assertEqual(_q(self.db, "SELECT tipo FROM eventos_stock WHERE producto_id=1"), [("alerta",)])

    def test_quiebre_con_alerta_previa(self):
        registrar_venta_atomica(1, 800.0, "Efectivo", [self.item(1, "Pan", 100, 8)], db_path=self.db)   # alerta
        registrar_venta_atomica(1, 200.0, "Efectivo", [self.item(1, "Pan", 100, 2)], db_path=self.db)   # quiebre
        q = _q(self.db, "SELECT alertado_antes FROM eventos_stock WHERE tipo='quiebre'")
        self.assertEqual(q, [(1,)])

    def test_quiebre_sin_alerta_previa_por_salto_directo(self):
        # Pan 10, mínimo 2: vender 10 de golpe pasa de "normal" a 0 sin alerta anterior
        registrar_venta_atomica(1, 1000.0, "Efectivo", [self.item(1, "Pan", 100, 10)], db_path=self.db)
        self.assertEqual(_q(self.db, "SELECT alertado_antes FROM eventos_stock WHERE tipo='quiebre'"), [(0,)])


class TestMetricasPiloto(BaseTest):
    def _conteo(self, momento, fisico_pan, fisico_medialuna, **kw):
        return registrar_conteo_fisico(
            momento, [{"producto_id": 1, "stock_fisico": fisico_pan},
                      {"producto_id": 2, "stock_fisico": fisico_medialuna}], db_path=self.db, **kw)

    def test_todo_pendiente_al_inicio(self):
        r = resumen_metricas(self.db)
        self.assertEqual([r["desfase"]["estado"], r["tiempo"]["estado"], r["alertas"]["estado"]],
                         ["pendiente"] * 3)
        self.assertFalse(r["exito_piloto"])

    # ---- 1. desfase
    def test_desfase_reduccion_80_cumple(self):
        self._conteo("inicio", 0, 0)        # sistema 10 y 3 → desfase 10+3 = 13
        self._conteo("fin", 9, 3)           # sistema 10 y 3 → desfase 1 → reducción 92 %
        d = resumen_metricas(self.db)["desfase"]
        self.assertEqual((d["base"]["unidades"], d["final"]["unidades"]), (13, 1))
        self.assertEqual(d["estado"], "cumple")
        self.assertAlmostEqual(d["reduccion_pct"], (13 - 1) / 13 * 100)

    def test_desfase_reduccion_insuficiente_no_cumple(self):
        self._conteo("inicio", 0, 0)        # 13
        self._conteo("fin", 5, 3)           # 5 → reducción 61 %
        self.assertEqual(resumen_metricas(self.db)["desfase"]["estado"], "no_cumple")

    def test_conteo_no_toca_el_stock_salvo_que_se_pida(self):
        self._conteo("inicio", 4, 1)
        self.assertEqual(_q(self.db, "SELECT stock FROM productos ORDER BY id"), [(10,), (3,)])
        r = self._conteo("control", 4, 1, ajustar_stock=True)
        self.assertEqual(r["desfase_total"], 6 + 2)
        self.assertEqual(_q(self.db, "SELECT stock FROM productos ORDER BY id"), [(4,), (1,)])
        self.assertEqual(_q(self.db, "SELECT COUNT(*) FROM movimientos_stock WHERE tipo='ajuste'")[0][0], 2)

    def test_conteo_validaciones(self):
        with self.assertRaises(ValueError):
            registrar_conteo_fisico("otro", [{"producto_id": 1, "stock_fisico": 1}], db_path=self.db)
        with self.assertRaises(ValueError):
            registrar_conteo_fisico("inicio", [], db_path=self.db)
        with self.assertRaises(ValueError):
            registrar_conteo_fisico("inicio", [{"producto_id": 1, "stock_fisico": -2}], db_path=self.db)

    # ---- 2. tiempos
    def test_tiempos_cumple_con_muestra_completa(self):
        for _ in range(10):
            registrar_tiempo_manual(60, db_path=self.db)
        # (ventas reales con duración) – usamos el stock del Pan, que alcanza justo para 10
        for _ in range(10):
            registrar_venta_atomica(1, 100.0, "Efectivo", [self.item(1, "Pan", 100, 1)],
                                    duracion_seg=30, db_path=self.db)
        t = resumen_metricas(self.db)["tiempo"]
        self.assertEqual((t["n_manual"], t["n_sistema"]), (10, 10))
        self.assertAlmostEqual(t["reduccion_pct"], 50.0)
        self.assertEqual(t["estado"], "cumple")

    def test_tiempos_muestra_incompleta_es_provisorio(self):
        registrar_tiempo_manual(60, db_path=self.db)
        registrar_venta_atomica(1, 100.0, "Efectivo", [self.item(1, "Pan", 100, 1)], duracion_seg=10, db_path=self.db)
        t = resumen_metricas(self.db)["tiempo"]
        self.assertEqual(t["estado"], "pendiente")
        self.assertIn("Provisorio", t["detalle"])

    def test_tiempos_no_cumple_si_mejora_poco(self):
        for _ in range(10):
            registrar_tiempo_manual(60, db_path=self.db)
        for _ in range(10):
            registrar_venta_atomica(1, 100.0, "Efectivo", [self.item(1, "Pan", 100, 1)],
                                    duracion_seg=55, db_path=self.db)       # solo 8 % menos
        self.assertEqual(resumen_metricas(self.db)["tiempo"]["estado"], "no_cumple")

    def test_tiempo_manual_invalido(self):
        with self.assertRaises(ValueError):
            registrar_tiempo_manual(0, db_path=self.db)

    # ---- 3. alertas
    def test_alertas_cumple_si_todos_los_quiebres_tuvieron_alerta(self):
        registrar_venta_atomica(1, 800.0, "Efectivo", [self.item(1, "Pan", 100, 8)], db_path=self.db)
        registrar_venta_atomica(1, 200.0, "Efectivo", [self.item(1, "Pan", 100, 2)], db_path=self.db)
        a = resumen_metricas(self.db)["alertas"]
        self.assertEqual((a["quiebres"], a["con_alerta_previa"], a["cumplimiento_pct"]), (1, 1, 100.0))
        self.assertEqual(a["estado"], "cumple")

    def test_alertas_no_cumple_si_hubo_quiebre_sin_aviso(self):
        registrar_venta_atomica(1, 1000.0, "Efectivo", [self.item(1, "Pan", 100, 10)], db_path=self.db)
        self.assertEqual(resumen_metricas(self.db)["alertas"]["estado"], "no_cumple")

    def test_alertas_cumple_si_hay_alertas_y_ningun_quiebre(self):
        registrar_venta_atomica(1, 800.0, "Efectivo", [self.item(1, "Pan", 100, 8)], db_path=self.db)
        self.assertEqual(resumen_metricas(self.db)["alertas"]["estado"], "cumple")

    # ---- éxito global + datos para exportar
    def test_exito_global_y_datos_para_exportar(self):
        self._conteo("inicio", 0, 0); self._conteo("fin", 10, 3)       # desfase 13 → 0
        for _ in range(10):
            registrar_tiempo_manual(60, db_path=self.db)
        for _ in range(7):
            registrar_venta_atomica(1, 100.0, "Efectivo", [self.item(1, "Pan", 100, 1)], duracion_seg=20, db_path=self.db)
        for _ in range(3):
            registrar_venta_atomica(1, 50.0, "Efectivo", [self.item(2, "Medialuna", 50, 1)], duracion_seg=20, db_path=self.db)
        # Pan queda en 3 (> mínimo 2) y Medialuna en 0 con alerta previa? Medialuna 3→2 (alerta) →1 →0 (quiebre alertado)
        r = resumen_metricas(self.db)
        self.assertEqual(r["desfase"]["estado"], "cumple")
        self.assertEqual(r["tiempo"]["estado"], "cumple")
        self.assertEqual(r["alertas"]["estado"], "cumple")
        self.assertTrue(r["exito_piloto"])
        d = datos_metricas(self.db)
        self.assertEqual(len(d["tiempos_manual"]), 10)
        self.assertEqual(len(d["tiempos_sistema"]), 10)
        self.assertEqual(len(d["conteos"]), 4)
        self.assertTrue(any(e["tipo"] == "quiebre" for e in d["eventos"]))


class TestMigracionDesdeVersionAnterior(unittest.TestCase):
    """La base de prueba de la versión previa ya tiene `pdv` pero no duracion_seg / op_id / métricas."""

    def test_migra_sin_perder_datos(self):
        import os, shutil, sqlite3, tempfile
        from backend.base_datos.migracion import migrar
        d = tempfile.mkdtemp()
        db = os.path.join(d, "previa.db")
        try:
            con = sqlite3.connect(db)
            con.executescript("""
                CREATE TABLE productos (id INTEGER PRIMARY KEY, nombre TEXT, categoria TEXT, precio FLOAT,
                    stock INTEGER, stock_minimo INTEGER, activo BOOLEAN);
                CREATE TABLE usuarios (id INTEGER PRIMARY KEY, nombre_usuario TEXT, password TEXT, rol TEXT, activo BOOLEAN);
                CREATE TABLE ventas (id INTEGER PRIMARY KEY, usuario_id INTEGER, total FLOAT,
                    medio_pago TEXT, fecha TEXT, pdv TEXT);
                CREATE TABLE items_venta (id INTEGER PRIMARY KEY AUTOINCREMENT, venta_id INTEGER, producto_id INTEGER,
                    nombre TEXT, precio REAL, cantidad INTEGER, subtotal REAL);
                CREATE TABLE movimientos_stock (id INTEGER PRIMARY KEY AUTOINCREMENT, producto_id INTEGER NOT NULL,
                    usuario_id INTEGER, cantidad INTEGER NOT NULL, tipo TEXT NOT NULL, descripcion TEXT,
                    fecha TEXT, pdv TEXT);
                INSERT INTO ventas VALUES (1, 1, 50.0, 'Efectivo', '2026-10-02 10:00:00', 'Caja 1');
            """)
            con.commit(); con.close()
            migrar(db); migrar(db)
            cols = {r[1] for r in _q(db, "PRAGMA table_info(ventas)")}
            self.assertTrue({"duracion_seg", "op_id"} <= cols)
            tablas = {r[0] for r in _q(db, "SELECT name FROM sqlite_master WHERE type='table'")}
            self.assertTrue({"conteos_fisicos", "tiempos_venta_manual", "eventos_stock"} <= tablas)
            self.assertEqual(_q(db, "SELECT total, pdv FROM ventas")[0], (50.0, "Caja 1"))
            # y el índice anti-duplicados quedó creado
            self.assertIn("ux_ventas_op_id", {r[0] for r in _q(db, "SELECT name FROM sqlite_master WHERE type='index'")})
        finally:
            shutil.rmtree(d, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
