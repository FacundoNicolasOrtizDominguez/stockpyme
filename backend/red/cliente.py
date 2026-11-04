"""
cliente.py — Cliente de red de STOCKPYME (cajas que NO tienen la base).

instalar_proxies_remotos(namespace) reemplaza, dentro de `repositorios`, cada función de la
lista blanca por una que ejecuta la misma función en el servidor. Así las ventanas siguen
llamando a las mismas funciones de siempre y reciben los mismos tipos de objetos.

Notas:
  • Se ignora el proxy del sistema (la red local no debe pasar por un proxy).
  • Solo las funciones de lectura se reintentan automáticamente. Las que escriben NO:
    para ventas se usa `op_id`, que evita duplicados si hay que repetir el pedido a mano.
"""
import json
import socket
import urllib.error
import urllib.request
from urllib.parse import quote

from backend.config import SERVIDOR_HOST, SERVIDOR_PUERTO, TOKEN, PDV_NOMBRE
from backend.red.errores import ErrorConexion, ErrorAutenticacionRed, ErrorRed
from backend.red.registro import FUNCIONES_PUBLICAS, es_solo_lectura
from backend.red.serializacion import a_json, desde_json


class ClienteRed:
    def __init__(self, host, puerto, token, pdv, clases=None, timeout=10):
        self.base = f"http://{host}:{puerto}"
        self.token = token
        self.pdv = pdv
        self.clases = clases or {}
        self.timeout = timeout
        self._opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    # ---- transporte
    def _enviar(self, req):
        try:
            with self._opener.open(req, timeout=self.timeout) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code == 401:
                raise ErrorAutenticacionRed(
                    "El servidor rechazó el token de acceso. Revisá la configuración de red.") from None
            try:
                return json.loads(e.read().decode("utf-8"))
            except Exception:
                raise ErrorRed(f"El servidor respondió con un error HTTP {e.code}.") from None
        except (urllib.error.URLError, socket.timeout, ConnectionError, OSError) as e:
            raise ErrorConexion(
                f"No se pudo comunicar con el servidor ({self.base}). "
                f"Verificá que la PC servidor esté encendida y en la misma red. ({e})") from None

    def _cabeceras(self):
        return {"Content-Type": "application/json; charset=utf-8",
                "X-Token": self.token, "X-PDV": quote(self.pdv or "")}

    def ping(self):
        req = urllib.request.Request(self.base + "/ping", headers=self._cabeceras(), method="GET")
        datos = self._enviar(req)
        if not datos.get("ok"):
            raise ErrorRed("El servidor no respondió correctamente.")
        return datos

    def llamar(self, nombre, *args, **kwargs):
        cuerpo = json.dumps({"fn": nombre, "args": a_json(args), "kwargs": a_json(kwargs)},
                            ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(self.base + "/rpc", data=cuerpo,
                                     headers=self._cabeceras(), method="POST")
        intentos = 2 if es_solo_lectura(nombre) else 1
        for n in range(intentos):
            try:
                datos = self._enviar(req)
                break
            except ErrorConexion:
                if n == intentos - 1:
                    raise
        if datos.get("ok"):
            return desde_json(datos["resultado"], self.clases)
        raise reconstruir_error(datos.get("error", {}))


def reconstruir_error(err):
    """Vuelve a crear, en la caja, la misma excepción que ocurrió en el servidor."""
    from backend.base_datos.transacciones import (
        StockInsuficienteError, ProductoInexistenteError, ConflictoStockError,
    )
    tipo, msg, d = err.get("tipo"), err.get("mensaje", "Error del servidor."), err.get("datos", {})
    try:
        if tipo == "StockInsuficienteError":
            return StockInsuficienteError(d["producto_id"], d["nombre"], d["disponible"], d["pedido"])
        if tipo == "ProductoInexistenteError":
            return ProductoInexistenteError(d["producto_id"])
        if tipo == "ConflictoStockError":
            return ConflictoStockError(d["producto_id"], d["nombre"], d["esperado"], d["actual"])
    except KeyError:
        pass
    if tipo == "ValueError":
        return ValueError(msg)
    if tipo == "ErrorAutenticacion":
        return ErrorAutenticacionRed(msg)
    return ErrorRed(f"Error en el servidor: {msg}")


def _clases_del_modelo():
    """Clases para reconstruir los objetos recibidos (modelos + resultado de venta)."""
    from backend.modelos.producto import Producto
    from backend.modelos.usuario import Usuario
    from backend.modelos.venta import Venta, ItemVenta
    from backend.modelos.proveedor import Proveedor
    from backend.modelos.movimiento_stock import MovimientoStock
    from backend.base_datos.transacciones import VentaRegistrada
    return {c.__name__: c for c in (Producto, Usuario, Venta, ItemVenta, Proveedor,
                                    MovimientoStock, VentaRegistrada)}


def crear_cliente_desde_config():
    return ClienteRed(SERVIDOR_HOST, SERVIDOR_PUERTO, TOKEN, PDV_NOMBRE, _clases_del_modelo())


def instalar_proxies_remotos(namespace, cliente=None):
    """Reemplaza en `namespace` cada función de la lista blanca por su versión remota."""
    cliente = cliente or crear_cliente_desde_config()
    namespace["_cliente_red"] = cliente

    def hacer_proxy(nombre):
        def proxy(*args, **kwargs):
            return cliente.llamar(nombre, *args, **kwargs)
        proxy.__name__ = nombre
        proxy.__doc__ = f"(remota) {nombre} ejecutada en el servidor."
        return proxy

    for nombre in FUNCIONES_PUBLICAS:
        namespace[nombre] = hacer_proxy(nombre)
    return cliente
