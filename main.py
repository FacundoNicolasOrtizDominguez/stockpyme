"""
main.py — Punto de entrada de STOCKPYME
=======================================
Modos de funcionamiento (ver backend/config.py y «Configuración de red» en el menú Sesión):

  • local    : una sola PC con su base (como siempre).
  • servidor : esta PC guarda la base, atiende a las demás cajas por red local y además
               se puede usar como una caja más.
  • cliente  : esta PC no tiene base: usa la del servidor.

Flujo de arranque:
  1. (Solo instalado, primera vez) asistente de configuración de red.
  2. Cliente: comprobar conexión con el servidor.
     Local/servidor: migración de BD, creación de tablas y, en servidor, abrir el puerto de red.
  3. Primer uso: si no hay ningún usuario, se pide crear el administrador.
  4. Pantalla de login → ventana principal → (cerrar sesión vuelve al login).

Modo demo (solo desarrollo): STOCKPYME_DEMO=1 crea los usuarios admin / vendedor / repositor.
"""

import datetime
import os
import secrets
import sys
import traceback
import tkinter as tk
from tkinter import simpledialog, messagebox

from backend.config import (
    MODO, TOKEN, SERVIDOR_BIND, SERVIDOR_PUERTO, DATA_DIR, hay_config_local, guardar_config_local,
)
from backend.base_datos.conexion import crear_base_datos
from backend.base_datos.migracion import migrar, crear_tablas_extra
import backend.modelos.producto
import backend.modelos.usuario
import backend.modelos.venta
import backend.modelos.proveedor
import backend.modelos.movimiento_stock   # registra el modelo en Base

from backend.red.errores import ErrorRed
from interfaz.login import VentanaLogin
from interfaz.ventana_principal import VentanaPrincipal


LOG_ERRORES = os.path.join(DATA_DIR, "error.log")


def _guardar_error(texto):
    """El programa instalado no tiene consola: los errores se guardan en un archivo."""
    try:
        with open(LOG_ERRORES, "a", encoding="utf-8") as f:
            f.write(f"\n=== {datetime.datetime.now():%Y-%m-%d %H:%M:%S} ===\n{texto}")
    except OSError:
        pass


def _avisar_error(texto, parent=None):
    try:
        messagebox.showerror(
            "STOCKPYME — error inesperado",
            f"{texto[-1400:]}\n\nEl detalle completo quedó guardado en:\n{LOG_ERRORES}",
            parent=parent)
    except Exception:
        pass


def main():
    root = tk.Tk()
    root.withdraw()

    # Cualquier error dentro de una ventana se guarda y se muestra (antes se perdía en silencio)
    def _error_en_ventana(exc, val, tb):
        texto = "".join(traceback.format_exception(exc, val, tb))
        _guardar_error(texto)
        _avisar_error(texto)
    root.report_callback_exception = _error_en_ventana

    # 1) Instalado y sin configurar: preguntar cómo va a funcionar esta PC
    if getattr(sys, "frozen", False) and not hay_config_local():
        if not _asistente_inicial(root):
            root.destroy()
            return

    servidor = None
    try:
        # 2) Preparar datos / conexión según el modo
        if MODO == "cliente":
            if not _conectar_a_servidor(root):
                root.destroy()
                return
        else:
            migrar()
            crear_base_datos()
            crear_tablas_extra()
            if MODO == "servidor":
                servidor = _iniciar_servidor(root)

        # 3) Primer uso
        if not _asegurar_usuario_inicial(root):
            root.destroy()
            return

        # 4) Login y ventana principal
        while True:
            login = VentanaLogin(root)
            root.wait_window(login)

            if login.usuario_autenticado is None:
                if login.reabrir_por_tema:
                    continue    # cambió el tema en el login → se vuelve a abrir con el tema nuevo
                break           # cerró el login sin autenticarse

            while True:
                app = VentanaPrincipal(login.usuario_autenticado, root)
                root.wait_window(app)
                if not app.reabrir_por_tema:
                    break       # (si cambió el tema, se rehace la ventana con el mismo usuario)

            if not app.cerrar_sesion_solicitado:
                break   # eligió "Salir" → cerrar todo
            # cerrar_sesion_solicitado == True → vuelve al login sin reiniciar
    except ErrorRed as e:
        messagebox.showerror("Sin conexión con el servidor", str(e), parent=root)
    finally:
        if servidor is not None:
            try:
                servidor.detener()
            except Exception:
                pass
        try:
            root.destroy()
        except tk.TclError:
            pass


# ----------------------------------------------------------------------
# RED
# ----------------------------------------------------------------------

def _asistente_inicial(root):
    """Primera vez del programa instalado. Devuelve False si hay que cerrar (config guardada)."""
    from interfaz.ventana_configuracion import VentanaConfiguracion
    ventana = VentanaConfiguracion(root, inicial=True)
    root.wait_window(ventana)
    if ventana.guardado:
        return False        # ya se avisó "volvé a abrir el programa"
    return True             # canceló: sigue en modo "una sola PC" sin guardar nada


def _conectar_a_servidor(root):
    """Comprueba el servidor; permite reintentar o revisar la configuración."""
    from backend.base_datos import repositorios
    cliente = repositorios._cliente_red
    while True:
        try:
            cliente.ping()
            return True
        except ErrorRed as e:
            if messagebox.askretrycancel("Sin conexión con el servidor",
                                         f"{e}\n\n¿Reintentar?", parent=root):
                continue
            if messagebox.askyesno("Configuración de red",
                                   "¿Querés revisar la configuración de red de esta caja?", parent=root):
                from interfaz.ventana_configuracion import VentanaConfiguracion
                root.wait_window(VentanaConfiguracion(root))
            return False


def _iniciar_servidor(root):
    """Abre el puerto de red para las demás cajas. Si falla, esta PC sigue andando sola."""
    from backend.red.servidor import ServidorRed
    from backend.red.registro import construir_registro

    token = TOKEN
    if not token:
        token = secrets.token_urlsafe(12)
        guardar_config_local({"token": token})
    try:
        return ServidorRed(construir_registro(), SERVIDOR_BIND, SERVIDOR_PUERTO, token).iniciar_en_hilo()
    except OSError as e:
        messagebox.showwarning(
            "Servidor de red",
            f"No se pudo abrir el puerto {SERVIDOR_PUERTO} ({e}).\n\n"
            "Seguramente otro programa lo está usando (¿ya hay un STOCKPYME abierto?).\n"
            "Esta PC funciona igual, pero las otras cajas no van a poder conectarse.",
            parent=root)
        return None


# ----------------------------------------------------------------------
# PRIMER USO
# ----------------------------------------------------------------------

def _asegurar_usuario_inicial(root):
    """
    Si la base no tiene usuarios (primer uso en un comercio nuevo), pide crear el
    administrador. Devuelve False si el usuario cancela.
    """
    from backend.base_datos.repositorios import listar_usuarios, buscar_usuario, crear_usuario

    if os.environ.get("STOCKPYME_DEMO") == "1":
        demo = (("admin", "admin123", "administrador"),
                ("vendedor", "venta123", "vendedor"),
                ("repositor", "repo123", "repositor"))
        for nombre, clave, rol in demo:
            if buscar_usuario(nombre) is None:
                crear_usuario(nombre, clave, rol)
                print(f"[demo] Usuario '{nombre}' creado")
        return True

    if listar_usuarios():
        return True

    messagebox.showinfo(
        "Primer uso",
        "Bienvenido a STOCKPYME.\n\nNo hay usuarios cargados todavía: "
        "vamos a crear el administrador del comercio.",
        parent=root,
    )
    nombre = simpledialog.askstring("Administrador", "Nombre de usuario (mín. 3 caracteres):", parent=root)
    if nombre is None:
        return False

    while True:
        clave = simpledialog.askstring("Administrador", "Contraseña (mín. 6 caracteres):",
                                       show="*", parent=root)
        if clave is None:
            return False
        if len(clave) < 6:
            messagebox.showwarning("Contraseña corta", "Usá al menos 6 caracteres.", parent=root)
            continue
        repetida = simpledialog.askstring("Administrador", "Repetí la contraseña:", show="*", parent=root)
        if repetida is None:
            return False
        if repetida != clave:
            messagebox.showwarning("No coinciden", "Las contraseñas no coinciden.", parent=root)
            continue
        break

    try:
        creado = crear_usuario(nombre, clave, "administrador")
    except ValueError as e:
        messagebox.showerror("Dato inválido", str(e), parent=root)
        return _asegurar_usuario_inicial(root)
    if creado is None:
        messagebox.showerror("Error", "No se pudo crear el administrador.", parent=root)
        return False
    return True


if __name__ == "__main__":
    try:
        main()
    except Exception:
        _texto = traceback.format_exc()
        _guardar_error(_texto)
        try:
            _r = tk.Tk()
            _r.withdraw()
            _avisar_error(_texto, _r)
            _r.destroy()
        except Exception:
            pass
        raise SystemExit(1)
