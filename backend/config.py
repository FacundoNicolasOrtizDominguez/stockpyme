# ==============================
# CONFIGURACIÓN GENERAL
# ==============================
import json
import os
import sys
import threading

NOMBRE_SISTEMA = "STOCKPYME — Sistema de Stock y Ventas"


def _directorio_datos():
    """
    Carpeta donde viven la base de datos, tickets y config local.
    - Corriendo con `python main.py`: la raíz del proyecto.
    - Empaquetado (PyInstaller): %LOCALAPPDATA%/StockPyME (siempre escribible,
      a diferencia de C:/Program Files).
    """
    if getattr(sys, "frozen", False):
        base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
        carpeta = os.path.join(base, "StockPyME")
    else:
        carpeta = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    os.makedirs(carpeta, exist_ok=True)
    return carpeta


DATA_DIR = _directorio_datos()


def _leer_config_local():
    """
    Lee DATA_DIR/config_local.json (opcional). Ejemplo:
        {"pdv": "Caja 2", "db_path": "\\\\\\\\SERVIDOR\\\\stockpyme\\\\stock_ventas.db"}
    """
    ruta = os.path.join(DATA_DIR, "config_local.json")
    try:
        with open(ruta, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


_LOCAL = _leer_config_local()

# ── Modo de red ──────────────────────────────────────────────────────
#   "local"    : una sola PC, con su propia base (comportamiento original).
#   "servidor" : esta PC guarda la base y atiende a las demás cajas por red local
#                (además se puede usar como una caja más).
#   "cliente"  : esta PC NO tiene base; usa la del servidor (SERVIDOR_HOST:PUERTO).
MODO = (os.environ.get("STOCKPYME_MODO") or _LOCAL.get("modo") or "local").strip().lower()
if MODO not in ("local", "servidor", "cliente"):
    MODO = "local"
SERVIDOR_HOST = (os.environ.get("STOCKPYME_SERVIDOR") or _LOCAL.get("servidor_host") or "127.0.0.1").strip()
SERVIDOR_PUERTO = int(os.environ.get("STOCKPYME_PUERTO") or _LOCAL.get("servidor_puerto") or 8765)
SERVIDOR_BIND = "0.0.0.0"          # el servidor escucha en todas las interfaces de la red local
TOKEN = (os.environ.get("STOCKPYME_TOKEN") or _LOCAL.get("token") or "").strip()

# Punto de venta (caja/sucursal) de ESTA PC. Prioridad: variable de entorno >
# config_local.json > valor por defecto.
PDV_NOMBRE = (os.environ.get("STOCKPYME_PDV") or _LOCAL.get("pdv") or "Caja 1").strip()

def pdv_actual():
    """
    PDV con el que se registran las operaciones. En el servidor, mientras atiende
    el pedido de una caja remota, es el PDV de ESA caja (lo fija el hilo del pedido);
    en cualquier otro caso es el PDV de esta PC.
    """
    return getattr(_contexto, "pdv", None) or PDV_NOMBRE


def fijar_pdv_del_hilo(pdv):
    _contexto.pdv = pdv


_contexto = threading.local()


def hay_config_local():
    return os.path.exists(os.path.join(DATA_DIR, "config_local.json"))


def guardar_config_local(cambios):
    """Mezcla `cambios` en config_local.json. Los cambios se aplican al reiniciar la app."""
    actual = _leer_config_local()
    actual.update(cambios)
    ruta = os.path.join(DATA_DIR, "config_local.json")
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(actual, f, ensure_ascii=False, indent=2)
    return ruta


# Base de datos (ruta ABSOLUTA; puede apuntar a una carpeta compartida de la red local)
DB_PATH = os.path.abspath(
    os.environ.get("STOCKPYME_DB")
    or _LOCAL.get("db_path")
    or os.path.join(DATA_DIR, "stock_ventas.db")
)
NOMBRE_BD = DB_PATH  # alias: el código viejo importa NOMBRE_BD

# URL para SQLAlchemy (barras normales para que funcione también en Windows)
DATABASE_URL = "sqlite:///" + DB_PATH.replace("\\", "/")

# Mostrar el SQL generado en consola (solo para depurar)
SQL_ECHO = os.environ.get("STOCKPYME_SQL_ECHO") == "1"

# Carpeta de tickets PDF
TICKETS_DIR = os.path.join(DATA_DIR, "tickets")

# IVA
IVA = 0.21

# Stock mínimo
STOCK_MINIMO_DEFAULT = 5

# Roles
ROLES_VALIDOS = ("administrador", "vendedor", "repositor")
