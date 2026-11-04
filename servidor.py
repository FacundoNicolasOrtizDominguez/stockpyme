"""
servidor.py — Servidor de STOCKPYME SIN ventanas (para una PC dedicada, o para pruebas).

    python servidor.py                 # puerto por defecto (8765)
    python servidor.py --puerto 9000

Usa la misma base y el mismo config_local.json que la aplicación. Mientras esté corriendo,
las cajas configuradas como «CAJA conectada» se conectan a esta PC. El primer administrador
se crea desde la primera caja que se abra (el programa lo pide solo).

Las cajas necesitan: la IP que se muestra acá, el puerto y la clave de acceso.
"""
import argparse
import logging
import secrets
import socket

from backend.config import SERVIDOR_BIND, SERVIDOR_PUERTO, TOKEN, DB_PATH, guardar_config_local
from backend.base_datos.conexion import crear_base_datos
from backend.base_datos.migracion import migrar, crear_tablas_extra
import backend.modelos.producto
import backend.modelos.usuario
import backend.modelos.venta
import backend.modelos.proveedor
import backend.modelos.movimiento_stock   # registra los modelos en Base
from backend.red.servidor import ServidorRed
from backend.red.registro import construir_registro


def _ips():
    try:
        return sorted({ip for ip in socket.gethostbyname_ex(socket.gethostname())[2]
                       if not ip.startswith("127.")}) or ["(no detectada)"]
    except OSError:
        return ["(no detectada)"]


def main():
    ap = argparse.ArgumentParser(description="Servidor de red de STOCKPYME")
    ap.add_argument("--puerto", type=int, default=SERVIDOR_PUERTO)
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    migrar()
    crear_base_datos()
    crear_tablas_extra()

    token = TOKEN
    if not token:
        token = secrets.token_urlsafe(12)
        guardar_config_local({"token": token})

    servidor = ServidorRed(construir_registro(), SERVIDOR_BIND, args.puerto, token)
    print("=" * 62)
    print(" STOCKPYME — servidor de red en marcha")
    print(f"  Base de datos : {DB_PATH}")
    print(f"  IP de esta PC : {', '.join(_ips())}")
    print(f"  Puerto        : {args.puerto}")
    print(f"  Clave         : {token}")
    print(" Dejá esta ventana abierta. Ctrl+C para detener.")
    print("=" * 62)
    try:
        servidor.servir_para_siempre()
    except KeyboardInterrupt:
        print("\nServidor detenido.")
    finally:
        servidor.detener()


if __name__ == "__main__":
    main()
