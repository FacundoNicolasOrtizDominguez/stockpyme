"""
Pruebas de la capa de red: serialización, servidor HTTP real en 127.0.0.1, cliente,
errores, token, PDV por caja y varias cajas vendiendo a la vez a través de la red.
No requieren SQLAlchemy.
"""
import functools
import logging
import threading
import unittest
from datetime import datetime, date

from tests.test_transacciones import BaseTest, _q
from backend.base_datos import transacciones as tx
from backend.base_datos import metricas as mt
from backend.base_datos.transacciones import VentaRegistrada, StockInsuficienteError, ConflictoStockError
from backend.red.serializacion import a_json, desde_json
from backend.red.servidor import ServidorRed
from backend.red.cliente import ClienteRed
from backend.red.errores import ErrorConexion, ErrorAutenticacionRed, ErrorRed
from backend.config import pdv_actual, PDV_NOMBRE

TOKEN = "token-de-prueba"
logging.getLogger("stockpyme.servidor").setLevel(logging.CRITICAL)   # el error de prueba es a propósito


# ---------- objetos falsos que imitan a los del modelo (sin SQLAlchemy) ----------
class FalsoItem:
    _sa_instance_state = object()
    id = nombre = cantidad = venta = None      # como los atributos mapeados de un modelo real
    def __init__(self, **kw):
        self.__dict__.update(kw)

class FalsaVenta:
    _sa_instance_state = object()
    id = items = usuario = fecha = total = None
    def __init__(self, **kw):
        self.__dict__.update(kw)

class FalsoUsuario:
    _sa_instance_state = object()
    id = nombre_usuario = rol = password = None
    def __init__(self, **kw):
        self.__dict__.update(kw)


class TestSerializacion(unittest.TestCase):
    def test_fechas_tuplas_y_dicts(self):
        original = {"dt": datetime(2026, 10, 2, 9, 5, 7, 123456), "d": date(2026, 10, 2),
                    "t": (1, 2), "n": None, "ok": True}
        r = desde_json(a_json(original))
        self.assertEqual(r["dt"], original["dt"])
        self.assertEqual(r["d"], original["d"])
        self.assertEqual(r["t"], [1, 2])

    def test_objeto_del_modelo_sin_password_y_sin_ciclos(self):
        u = FalsoUsuario(id=1, nombre_usuario="ana", rol="vendedor", password="$2b$HASH")
        venta = FalsaVenta(id=5, total=300.0, fecha=datetime(2026, 1, 1, 10, 0), usuario=u)
        item = FalsoItem(id=9, nombre="Pan", cantidad=3, venta=venta)       # ciclo: item → venta
        venta.items = [item]
        js = a_json(venta)
        self.assertNotIn("password", js["usuario"])
        self.assertNotIn("venta", js["items"][0])                           # ciclo cortado
        self.assertNotIn("$2b$HASH", str(js))

        clases = {"FalsaVenta": FalsaVenta, "FalsoItem": FalsoItem, "FalsoUsuario": FalsoUsuario}
        v2 = desde_json(js, clases)
        self.assertIsInstance(v2, FalsaVenta)
        self.assertEqual((v2.id, v2.total, v2.fecha), (5, 300.0, datetime(2026, 1, 1, 10, 0)))
        self.assertEqual(v2.items[0].nombre, "Pan")
        self.assertEqual(v2.usuario.nombre_usuario, "ana")
        self.assertIsNone(v2.usuario.password)

    def test_dataclass_ida_y_vuelta(self):
        v = VentaRegistrada(3, "2026-10-02 10:00:00", 100.0, "Efectivo", "Caja 2",
                            [{"id": 1, "nombre": "Pan", "stock": 2, "stock_minimo": 2}], False)
        v2 = desde_json(a_json(v), {"VentaRegistrada": VentaRegistrada})
        self.assertEqual(v, v2)

    def test_tipo_desconocido_falla(self):
        with self.assertRaises(TypeError):
            desde_json({"__tipo__": "Raro"}, {})

    def test_objeto_no_serializable(self):
        with self.assertRaises(TypeError):
            a_json(object())


class BaseRed(BaseTest):
    """Levanta un servidor real con funciones que usan la base temporal del test."""

    def setUp(self):
        super().setUp()
        db = self.db
        self.registro = {
            "registrar_venta_atomica": functools.partial(tx.registrar_venta_atomica, db_path=db),
            "ajustar_stock": functools.partial(tx.ajustar_stock_atomico, db_path=db),
            "fijar_stock": functools.partial(tx.fijar_stock_atomico, db_path=db),
            "resumen_por_pdv": functools.partial(tx.resumen_por_pdv, db_path=db),
            "ultimas_ventas": functools.partial(tx.ultimas_ventas, db_path=db),
            "resumen_metricas": functools.partial(mt.resumen_metricas, db_path=db),
            "registrar_tiempo_manual": functools.partial(mt.registrar_tiempo_manual, db_path=db),
            "pdv_del_hilo": lambda: pdv_actual(),
            "falla": lambda: 1 / 0,
        }
        self.servidor = ServidorRed(self.registro, "127.0.0.1", 0, TOKEN).iniciar_en_hilo()
        self.addCleanup(self.servidor.detener)

    def cliente(self, pdv="Caja 2", token=TOKEN, puerto=None):
        return ClienteRed("127.0.0.1", puerto or self.servidor.puerto, token, pdv,
                          clases={"VentaRegistrada": VentaRegistrada}, timeout=5)


class TestServidorYCliente(BaseRed):
    def test_ping_y_token(self):
        self.assertTrue(self.cliente().ping()["ok"])
        with self.assertRaises(ErrorAutenticacionRed):
            self.cliente(token="incorrecto").ping()
        with self.assertRaises(ErrorAutenticacionRed):
            self.cliente(token="").llamar("pdv_del_hilo")

    def test_servidor_apagado_da_error_de_conexion(self):
        puerto = self.servidor.puerto
        self.servidor.detener()
        with self.assertRaises(ErrorConexion):
            self.cliente(puerto=puerto).ping()

    def test_funcion_fuera_de_la_lista_blanca(self):
        with self.assertRaises(ErrorRed):
            self.cliente().llamar("os_system", "calc")

    def test_venta_remota_guarda_el_pdv_de_la_caja(self):
        v = self.cliente("Sucursal Ñandú").llamar(
            "registrar_venta_atomica", 1, 300.0, "Efectivo", [self.item(1, "Pan", 100, 3)])
        self.assertIsInstance(v, VentaRegistrada)
        self.assertEqual(v.pdv, "Sucursal Ñandú")                 # acentos incluidos
        self.assertEqual(_q(self.db, "SELECT pdv FROM ventas WHERE id=?", (v.id,))[0][0], "Sucursal Ñandú")
        self.assertEqual(_q(self.db, "SELECT stock FROM productos WHERE id=1")[0][0], 7)

    def test_el_pdv_del_hilo_se_limpia_entre_pedidos(self):
        self.assertEqual(self.cliente("Caja 7").llamar("pdv_del_hilo"), "Caja 7")
        self.assertEqual(self.cliente("").llamar("pdv_del_hilo"), PDV_NOMBRE)

    def test_stock_insuficiente_llega_como_la_misma_excepcion(self):
        with self.assertRaises(StockInsuficienteError) as ctx:
            self.cliente().llamar("registrar_venta_atomica", 1, 1.0, "Efectivo",
                                  [self.item(2, "Medialuna", 50, 99)])
        e = ctx.exception
        self.assertEqual((e.nombre, e.disponible, e.pedido, e.producto_id), ("Medialuna", 3, 99, 2))
        self.assertEqual(_q(self.db, "SELECT COUNT(*) FROM ventas")[0][0], 0)

    def test_conflicto_de_stock_llega_como_excepcion(self):
        self.cliente().llamar("registrar_venta_atomica", 1, 300.0, "Efectivo", [self.item(1, "Pan", 100, 3)])
        with self.assertRaises(ConflictoStockError) as ctx:
            self.cliente().llamar("fijar_stock", 1, 50, esperado=10)
        self.assertEqual((ctx.exception.esperado, ctx.exception.actual), (10, 7))

    def test_valueerror_y_errores_inesperados(self):
        with self.assertRaises(ValueError):
            self.cliente().llamar("registrar_venta_atomica", 1, 10, "Efectivo", [])
        with self.assertRaises(ErrorRed):                          # ZeroDivisionError en el servidor
            self.cliente().llamar("falla")
        self.assertTrue(self.cliente().ping()["ok"])               # el servidor sigue vivo

    def test_fechas_como_argumento_y_resultado_estructurado(self):
        c1, c2 = self.cliente("Caja 1"), self.cliente("Caja 2")
        c1.llamar("registrar_venta_atomica", 1, 100.0, "Efectivo", [self.item(1, "Pan", 100, 1)])
        c2.llamar("registrar_venta_atomica", 1, 200.0, "Débito", [self.item(1, "Pan", 100, 2)])
        r = c1.llamar("resumen_por_pdv", date.today(), date.today())
        self.assertEqual({x["pdv"]: x["total"] for x in r}, {"Caja 1": 100.0, "Caja 2": 200.0})
        self.assertEqual(len(c1.llamar("ultimas_ventas", 10)), 2)

    def test_op_id_reintento_por_la_red_no_duplica(self):
        c = self.cliente()
        args = (1, 100.0, "Efectivo", [self.item(1, "Pan", 100, 1)])
        v1 = c.llamar("registrar_venta_atomica", *args, op_id="venta-xyz")
        v2 = c.llamar("registrar_venta_atomica", *args, op_id="venta-xyz")
        self.assertTrue(v2.ya_registrada)
        self.assertEqual(v1.id, v2.id)
        self.assertEqual(_q(self.db, "SELECT stock FROM productos WHERE id=1")[0][0], 9)

    def test_metricas_por_la_red(self):
        c = self.cliente()
        c.llamar("registrar_tiempo_manual", 45.0, nota="prueba")
        r = c.llamar("resumen_metricas")
        self.assertEqual(r["tiempo"]["n_manual"], 1)
        self.assertEqual(r["tiempo"]["estado"], "pendiente")


class TestConcurrenciaPorRed(BaseRed):
    def test_3_cajas_remotas_venden_el_mismo_sku(self):
        exitos, rechazos, errores = [], [], []
        lock = threading.Lock()
        barrera = threading.Barrier(3)

        def caja(n):
            c = self.cliente(f"Caja {n}")
            barrera.wait()
            for _ in range(8):
                try:
                    c.llamar("registrar_venta_atomica", 1, 100.0, "Efectivo", [self.item(1, "Pan", 100, 1)])
                    with lock: exitos.append(n)
                except StockInsuficienteError:
                    with lock: rechazos.append(n)
                except Exception as e:
                    with lock: errores.append(repr(e))

        hs = [threading.Thread(target=caja, args=(n,)) for n in (1, 2, 3)]
        [h.start() for h in hs]; [h.join() for h in hs]
        self.assertEqual(errores, [])
        self.assertEqual(len(exitos), 10)                           # stock 10, 24 intentos
        self.assertEqual(len(rechazos), 14)
        self.assertEqual(_q(self.db, "SELECT stock FROM productos WHERE id=1")[0][0], 0)
        self.assertEqual(_q(self.db, "SELECT COUNT(*) FROM ventas")[0][0], 10)
        pdvs = {r[0] for r in _q(self.db, "SELECT DISTINCT pdv FROM ventas")}
        self.assertTrue(pdvs <= {"Caja 1", "Caja 2", "Caja 3"})


class TestProxiesRemotos(BaseRed):
    """instalar_proxies_remotos reemplaza las funciones del repositorio por llamadas al servidor."""

    def test_los_proxies_ejecutan_en_el_servidor(self):
        from backend.red.cliente import instalar_proxies_remotos
        from backend.red.registro import FUNCIONES_PUBLICAS
        espacio = {"registrar_venta_atomica": "original", "listar_productos": "original"}
        cliente = self.cliente("Caja 9")
        instalar_proxies_remotos(espacio, cliente)

        self.assertEqual(set(FUNCIONES_PUBLICAS) <= set(espacio), True)      # reemplazó todas
        self.assertIs(espacio["_cliente_red"], cliente)
        self.assertNotEqual(espacio["registrar_venta_atomica"], "original")

        v = espacio["registrar_venta_atomica"](1, 100.0, "Efectivo", [self.item(1, "Pan", 100, 1)])
        self.assertEqual((v.pdv, _q(self.db, "SELECT stock FROM productos WHERE id=1")[0][0]), ("Caja 9", 9))
        self.assertEqual(espacio["resumen_metricas"]()["tiempo"]["estado"], "pendiente")

    def test_lectura_se_reintenta_una_vez_y_escritura_no(self):
        from backend.red.registro import es_solo_lectura
        for nombre in ("listar_productos", "buscar_usuario", "resumen_hoy", "ultimas_ventas", "datos_metricas"):
            self.assertTrue(es_solo_lectura(nombre), nombre)
        for nombre in ("registrar_venta_atomica", "ajustar_stock", "crear_usuario", "verificar_credenciales"):
            self.assertFalse(es_solo_lectura(nombre), nombre)


if __name__ == "__main__":
    unittest.main()
