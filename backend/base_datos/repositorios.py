"""
repositorios.py — Punto de acceso a los datos que usa TODA la interfaz.

Según el modo de red (backend/config.py → MODO):

  • "local" / "servidor": las funciones trabajan directamente sobre la base de esta PC
    (implementación en repositorios_local.py).
  • "cliente": las mismas funciones se ejecutan en el servidor por la red local
    (backend/red/cliente.py) y devuelven los mismos tipos de objetos.

Así las ventanas no cambian: siguen haciendo `from ...repositorios import listar_productos`.
"""
from backend.config import MODO
from backend.base_datos.repositorios_local import *          # noqa: F401,F403

if MODO == "cliente":
    from backend.red.cliente import instalar_proxies_remotos
    instalar_proxies_remotos(globals())
