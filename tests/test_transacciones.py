"""
Pruebas de venta atómica y concurrencia (riesgo R01 del informe).
No requieren SQLAlchemy ni la interfaz gráfica.

Ejecutar desde la raíz del proyecto:
    python -m unittest discover -s tests -v
"""
import os
import shutil
import sqlite3
import tempfile
import threading
import unittest
from datetime import date

from backend.base_datos.migracion import migrar
from backend.base_datos.transacciones import (
    registrar_venta_atomica, ajustar_stock_atomico, resumen_por_pdv, ultimas_ventas,
    StockInsuficienteError, ProductoInexistenteError,
)

# Esquema "viejo" (sin columna pdv), igual al de la base real del proyecto
ESQUEMA_VIEJO = """
CREATE TABLE productos (id INTEGER PRIMARY KEY, nombre VARCHAR NOT NULL, categoria VARCHAR NOT NULL,
    precio FLOAT NOT NULL, stock INTEGER, stock_minimo INTEGER, activo BOOLEAN);
CREATE TABLE usuarios (id INTEGER PRIMARY KEY, nombre_usuario VARCHAR NOT NULL UNIQUE,
    password VARCHAR NOT NULL, rol VARCHAR NOT NULL, activo BOOLEAN);
CREATE TABLE ventas (id INTEGER PRIMARY KEY, usuario_id INTEGER, total FLOAT,
    medio_pago TEXT DEFAULT 'Efectivo', fecha TEXT);
CREATE TABLE items_venta (id INTEGER PRIMARY KEY AUTOINCREMENT, venta_id INTEGER, producto_id INTEGER,
    nombre TEXT, precio REAL, cantidad INTEGER, subtotal REAL);
CREATE TABLE movimientos_stock (id INTEGER PRIMARY KEY AUTOINCREMENT, producto_id INTEGER NOT NULL,
    usuario_id INTEGER, cantidad INTEGER NOT NULL, tipo TEXT NOT NULL, descripcion TEXT DEFAULT '',
    fecha TEXT DEFAULT (datetime('now')));
"""


def _q(ruta, sql, params=()):
    con = sqlite3.connect(ruta)
    try:
        return con.execute(sql, params).fetchall()
    finally:
        con.close()


class BaseTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.db = os.path.join(self.dir, "t.db")
        con = sqlite3.connect(self.db)
        con.executescript(ESQUEMA_VIEJO)
        con.execute("INSERT INTO usuarios VALUES (1,'cajero','x','vendedor',1)")
        con.execute("INSERT INTO productos VALUES (1,'Pan','Panadería',100,10,2,1)")
        con.execute("INSERT INTO productos VALUES (2,'Medialuna','Panadería',50,3,2,1)")
        con.commit()
        con.close()
        migrar(self.db)

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def item(self, pid, nombre, precio, cant):
        return {"id": pid, "nombre": nombre, "precio": precio, "cantidad": cant}


class TestMigracion(BaseTest):
    def test_agrega_pdv_y_es_idempotente(self):
        cols = {r[1] for r in _q(self.db, "PRAGMA table_info(ventas)")}
        self.assertIn("pdv", cols)
        cols = {r[1] for r in _q(self.db, "PRAGMA table_info(movimientos_stock)")}
        self.assertIn("pdv", cols)
        migrar(self.db)  # segunda corrida no debe fallar ni duplicar nada
        migrar(self.db)

    def test_ventas_viejas_quedan_con_pdv(self):
        # Base "vieja" (antes de la migración) con una venta ya cargada
        vieja = os.path.join(self.dir, "vieja.db")
        con = sqlite3.connect(vieja)
        con.executescript(ESQUEMA_VIEJO)
        con.execute("INSERT INTO ventas (usuario_id,total,fecha) VALUES (1,10,'2026-01-01 10:00:00')")
        con.commit(); con.close()
        migrar(vieja)
        self.assertEqual(_q(vieja, "SELECT COUNT(*) FROM ventas WHERE pdv IS NULL")[0][0], 0)
        self.assertEqual(_q(vieja, "SELECT COUNT(*) FROM ventas")[0][0], 1)  # no se perdió la venta


class TestVentaAtomica(BaseTest):
    def test_venta_ok_descuenta_y_registra_todo(self):
        v = registrar_venta_atomica(1, 300.0, "Efectivo", [self.item(1, "Pan", 100, 3)],
                                    pdv="Caja 2", db_path=self.db)
        self.assertEqual(_q(self.db, "SELECT stock FROM productos WHERE id=1")[0][0], 7)
        self.assertEqual(_q(self.db, "SELECT pdv,total FROM ventas WHERE id=?", (v.id,))[0], ("Caja 2", 300.0))
        self.assertEqual(_q(self.db, "SELECT cantidad,subtotal FROM items_venta WHERE venta_id=?", (v.id,))[0], (3, 300.0))
        mov = _q(self.db, "SELECT cantidad,tipo,pdv FROM movimientos_stock WHERE producto_id=1")
        self.assertEqual(mov, [(-3, "venta", "Caja 2")])

    def test_stock_insuficiente_hace_rollback_de_todo(self):
        # 2 ítems: el primero alcanza, el segundo no -> no debe quedar NADA registrado
        with self.assertRaises(StockInsuficienteError) as ctx:
            registrar_venta_atomica(1, 999.0, "Efectivo",
                                    [self.item(1, "Pan", 100, 5), self.item(2, "Medialuna", 50, 99)],
                                    db_path=self.db)
        self.assertEqual(ctx.exception.disponible, 3)
        self.assertEqual(_q(self.db, "SELECT stock FROM productos WHERE id=1")[0][0], 10)  # no se descontó
        self.assertEqual(_q(self.db, "SELECT COUNT(*) FROM ventas")[0][0], 0)
        self.assertEqual(_q(self.db, "SELECT COUNT(*) FROM items_venta")[0][0], 0)
        self.assertEqual(_q(self.db, "SELECT COUNT(*) FROM movimientos_stock")[0][0], 0)

    def test_mismo_producto_en_dos_lineas_no_sobrevende(self):
        with self.assertRaises(StockInsuficienteError):
            registrar_venta_atomica(1, 1.0, "Efectivo",
                                    [self.item(1, "Pan", 100, 6), self.item(1, "Pan", 100, 6)],
                                    db_path=self.db)
        self.assertEqual(_q(self.db, "SELECT stock FROM productos WHERE id=1")[0][0], 10)

    def test_producto_inexistente(self):
        with self.assertRaises(ProductoInexistenteError):
            registrar_venta_atomica(1, 1.0, "Efectivo", [self.item(99, "Fantasma", 1, 1)], db_path=self.db)
        self.assertEqual(_q(self.db, "SELECT COUNT(*) FROM ventas")[0][0], 0)

    def test_validaciones(self):
        with self.assertRaises(ValueError):
            registrar_venta_atomica(1, 10, "Efectivo", [], db_path=self.db)
        with self.assertRaises(ValueError):
            registrar_venta_atomica(1, -5, "Efectivo", [self.item(1, "Pan", 1, 1)], db_path=self.db)
        with self.assertRaises(ValueError):
            registrar_venta_atomica(1, 5, "Efectivo", [self.item(1, "Pan", 1, 0)], db_path=self.db)

    def test_alerta_de_stock_bajo_tras_la_venta(self):
        v = registrar_venta_atomica(1, 800.0, "Efectivo", [self.item(1, "Pan", 100, 8)], db_path=self.db)
        self.assertEqual([a["nombre"] for a in v.alertas_stock], ["Pan"])  # quedó en 2 == mínimo


class TestConcurrencia(BaseTest):
    def _correr_cajas(self, n_cajas, intentos_por_caja):
        exitos, rechazos, errores = [], [], []
        lock = threading.Lock()
        barrera = threading.Barrier(n_cajas)

        def caja(n):
            barrera.wait()  # arrancan todas juntas
            for _ in range(intentos_por_caja):
                try:
                    registrar_venta_atomica(1, 100.0, "Efectivo", [self.item(1, "Pan", 100, 1)],
                                            pdv=f"Caja {n}", db_path=self.db)
                    with lock: exitos.append(n)
                except StockInsuficienteError:
                    with lock: rechazos.append(n)
                except Exception as e:  # cualquier otra cosa (p. ej. "database is locked") es un fallo
                    with lock: errores.append(repr(e))

        hilos = [threading.Thread(target=caja, args=(n,)) for n in range(1, n_cajas + 1)]
        for h in hilos: h.start()
        for h in hilos: h.join()
        return exitos, rechazos, errores

    def test_3_cajas_venden_el_mismo_sku_sin_inconsistencias(self):
        # stock 10, 3 cajas x 8 intentos = 24 intentos -> exactamente 10 deben salir bien
        exitos, rechazos, errores = self._correr_cajas(3, 8)
        self.assertEqual(errores, [])
        self.assertEqual(len(exitos), 10)
        self.assertEqual(len(rechazos), 14)
        self.assertEqual(_q(self.db, "SELECT stock FROM productos WHERE id=1")[0][0], 0)   # nunca negativo
        self.assertEqual(_q(self.db, "SELECT COUNT(*) FROM ventas")[0][0], 10)
        self.assertEqual(_q(self.db, "SELECT COALESCE(SUM(cantidad),0) FROM items_venta")[0][0], 10)
        self.assertEqual(_q(self.db, "SELECT COALESCE(SUM(cantidad),0) FROM movimientos_stock")[0][0], -10)

    def test_latencia_por_venta_menor_a_2_segundos(self):
        # Contingencia de R01: si los bloqueos generan latencia > 2 s hay que replantear
        import time
        t0 = time.perf_counter()
        self._correr_cajas(3, 3)
        promedio = (time.perf_counter() - t0) / 9
        self.assertLess(promedio, 2.0)

    def test_ajuste_manual_concurrente_con_ventas(self):
        # Una caja vende mientras el repositor suma stock: ninguna operación se pierde
        def vender():
            for _ in range(5):
                registrar_venta_atomica(1, 100.0, "Efectivo", [self.item(1, "Pan", 100, 1)], db_path=self.db)
        def reponer():
            for _ in range(5):
                ajustar_stock_atomico(1, +2, db_path=self.db)
        hs = [threading.Thread(target=vender), threading.Thread(target=reponer)]
        for h in hs: h.start()
        for h in hs: h.join()
        self.assertEqual(_q(self.db, "SELECT stock FROM productos WHERE id=1")[0][0], 10 - 5 + 10)


class TestAjusteYConsolidacion(BaseTest):
    def test_ajuste_no_permite_negativo(self):
        with self.assertRaises(StockInsuficienteError):
            ajustar_stock_atomico(2, -50, db_path=self.db)
        self.assertEqual(_q(self.db, "SELECT stock FROM productos WHERE id=2")[0][0], 3)

    def test_ajuste_producto_inexistente_devuelve_none(self):
        self.assertIsNone(ajustar_stock_atomico(99, 1, db_path=self.db))

    def test_resumen_por_pdv(self):
        registrar_venta_atomica(1, 100.0, "Efectivo", [self.item(1, "Pan", 100, 1)], pdv="Caja 1", db_path=self.db)
        registrar_venta_atomica(1, 200.0, "Débito", [self.item(1, "Pan", 100, 2)], pdv="Caja 2", db_path=self.db)
        registrar_venta_atomica(1, 50.0, "Efectivo", [self.item(2, "Medialuna", 50, 1)], pdv="Caja 2", db_path=self.db)
        r = resumen_por_pdv(date.today(), date.today(), db_path=self.db)
        self.assertEqual(r[0], {"pdv": "Caja 2", "cantidad_ventas": 2, "total": 250.0})
        self.assertEqual(r[1], {"pdv": "Caja 1", "cantidad_ventas": 1, "total": 100.0})
        self.assertEqual(len(ultimas_ventas(10, db_path=self.db)), 3)


if __name__ == "__main__":
    unittest.main()
