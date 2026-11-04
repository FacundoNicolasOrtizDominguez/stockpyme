"""
servidor.py — Servidor de red de STOCKPYME (PC servidor del comercio).

Es una API JSON mínima sobre HTTP, solo con la librería estándar de Python:

    GET  /ping   → comprueba que el servidor responde y el token es correcto
    POST /rpc    → {"fn": "...", "args": [...], "kwargs": {...}} ejecuta UNA función de la lista
                   blanca (registro.py) y devuelve {"ok": true, "resultado": ...} o
                   {"ok": false, "error": {...}}

Seguridad (pensada para una red local de comercio):
  • Toda llamada exige el token compartido en la cabecera X-Token.
  • Solo se ejecutan funciones de la lista blanca.
  • Las contraseñas viajan en HTTP sin cifrar dentro de la red local: no exponer el puerto
    a Internet.

Cada pedido corre en su propio hilo; la base resuelve la concurrencia con transacciones
BEGIN IMMEDIATE (ver transacciones.py).
"""
import hmac
import json
import logging
import threading
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote

from backend.config import fijar_pdv_del_hilo
from backend.red.serializacion import a_json, desde_json

PROTOCOLO = 1
MAX_CUERPO = 5 * 1024 * 1024        # 5 MB por pedido

log = logging.getLogger("stockpyme.servidor")


def _datos_del_error(exc):
    """Atributos que el cliente necesita para reconstruir los errores de stock."""
    extra = {}
    for attr in ("producto_id", "nombre", "disponible", "pedido", "esperado", "actual"):
        if hasattr(exc, attr):
            extra[attr] = getattr(exc, attr)
    return {"tipo": type(exc).__name__, "mensaje": str(exc), "datos": extra}


def _crear_handler(registro, token):
    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, formato, *args):        # silenciar el log por defecto de http.server
            log.debug("%s - %s", self.address_string(), formato % args)

        # ---- utilidades
        def _responder(self, codigo, payload):
            cuerpo = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(codigo)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(cuerpo)))
            self.end_headers()
            self.wfile.write(cuerpo)

        def _autorizado(self):
            enviado = self.headers.get("X-Token", "")
            if token and hmac.compare_digest(enviado.encode(), token.encode()):
                return True
            self._responder(401, {"ok": False, "error": {"tipo": "ErrorAutenticacion",
                                                         "mensaje": "Token inválido."}})
            return False

        # ---- rutas
        def do_GET(self):
            if self.path != "/ping":
                return self._responder(404, {"ok": False, "error": {"tipo": "NoEncontrado", "mensaje": "Ruta inexistente."}})
            if not self._autorizado():
                return
            self._responder(200, {"ok": True, "protocolo": PROTOCOLO, "app": "STOCKPYME"})

        def do_POST(self):
            if self.path != "/rpc":
                return self._responder(404, {"ok": False, "error": {"tipo": "NoEncontrado", "mensaje": "Ruta inexistente."}})
            if not self._autorizado():
                return
            try:
                largo = int(self.headers.get("Content-Length", "0"))
                if largo <= 0 or largo > MAX_CUERPO:
                    return self._responder(400, {"ok": False, "error": {"tipo": "PedidoInvalido", "mensaje": "Tamaño de pedido inválido."}})
                pedido = json.loads(self.rfile.read(largo).decode("utf-8"))
                nombre = pedido["fn"]
                funcion = registro.get(nombre)
                if funcion is None:
                    return self._responder(404, {"ok": False, "error": {"tipo": "FuncionDesconocida", "mensaje": f"Función no disponible: {nombre}"}})
                args = desde_json(pedido.get("args", []))
                kwargs = desde_json(pedido.get("kwargs", {}))
            except (ValueError, KeyError, TypeError) as e:
                return self._responder(400, {"ok": False, "error": {"tipo": "PedidoInvalido", "mensaje": str(e)}})

            # El PDV de la caja que pide: las ventas/movimientos se guardan con SU nombre.
            fijar_pdv_del_hilo(unquote(self.headers.get("X-PDV", "")) or None)
            try:
                resultado = funcion(*args, **kwargs)
                self._responder(200, {"ok": True, "resultado": a_json(resultado)})
            except Exception as exc:                       # el error vuelve al cliente, no tumba el servidor
                if not isinstance(exc, ValueError):
                    log.error("Error en %s:\n%s", nombre, traceback.format_exc())
                self._responder(200, {"ok": False, "error": _datos_del_error(exc)})
            finally:
                fijar_pdv_del_hilo(None)

    return Handler


class ServidorRed:
    def __init__(self, registro, host, puerto, token):
        if not token:
            raise ValueError("El servidor necesita un token de acceso.")
        self.httpd = ThreadingHTTPServer((host, puerto), _crear_handler(registro, token))
        self.httpd.daemon_threads = True
        self._hilo = None

    @property
    def puerto(self):
        return self.httpd.server_address[1]

    def iniciar_en_hilo(self):
        self._hilo = threading.Thread(target=self.httpd.serve_forever, name="stockpyme-servidor", daemon=True)
        self._hilo.start()
        return self

    def servir_para_siempre(self):
        self.httpd.serve_forever()

    def detener(self):
        self.httpd.shutdown()
        self.httpd.server_close()
