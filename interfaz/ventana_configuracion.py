"""
interfaz/ventana_configuracion.py
=================================
Configuración de red del comercio, pensada para quien instala (sin editar archivos):

  • Una sola PC          → todo en esta PC (como siempre).
  • Servidor del comercio → esta PC guarda la base y atiende a las demás cajas.
  • Caja conectada        → esta PC usa la base del servidor (hay que indicar su dirección y la clave).

Guarda en config_local.json; los cambios se aplican al volver a abrir el programa.
"""

import secrets
import socket
import tkinter as tk
from tkinter import messagebox

from backend.config import (
    MODO, PDV_NOMBRE, SERVIDOR_HOST, SERVIDOR_PUERTO, TOKEN, guardar_config_local,
)
from interfaz import tema as T

FONT = ("Courier New", 10)
FONT_BTN = ("Courier New", 10, "bold")


def _ips_locales():
    """Direcciones IP de esta PC en la red (para decirle al instalador qué poner en las cajas)."""
    ips = set()
    try:
        for ip in socket.gethostbyname_ex(socket.gethostname())[2]:
            if not ip.startswith("127."):
                ips.add(ip)
    except OSError:
        pass
    return sorted(ips) or ["(no se pudo detectar)"]


class VentanaConfiguracion(tk.Toplevel):
    def __init__(self, parent, al_guardar=None, inicial=False):
        super().__init__(parent)
        self.al_guardar = al_guardar
        self.guardado = False
        self.title("🌐 Configuración de red" + (" — primer uso" if inicial else ""))
        self.configure(bg=T.BG)
        self.resizable(False, False)

        tk.Label(self, text="Configuración de red", font=("Courier New", 14, "bold"),
                 bg=T.BG, fg=T.ACCENT, pady=8).pack()
        if inicial:
            tk.Label(self, text="Elegí cómo va a funcionar esta PC en el comercio.",
                     font=FONT, bg=T.BG, fg=T.FG).pack()

        cuerpo = tk.Frame(self, bg=T.BG, padx=20, pady=10)
        cuerpo.pack()

        # Nombre de esta caja
        tk.Label(cuerpo, text="Nombre de esta caja / sucursal:", font=FONT, bg=T.BG, fg=T.FG
                 ).grid(row=0, column=0, sticky="w", pady=(0, 2))
        self.var_pdv = tk.StringVar(value=PDV_NOMBRE)
        self._entry(cuerpo, self.var_pdv, 32).grid(row=1, column=0, sticky="w", pady=(0, 10))

        # Modo
        self.var_modo = tk.StringVar(value=MODO)
        for valor, texto in (
            ("local", "Una sola PC (todo en esta computadora)"),
            ("servidor", "SERVIDOR del comercio (guarda la base y atiende a las otras cajas)"),
            ("cliente", "CAJA conectada a un servidor"),
        ):
            tk.Radiobutton(cuerpo, text=texto, value=valor, variable=self.var_modo,
                           command=self._actualizar_campos, font=FONT, bg=T.BG, fg=T.FG,
                           selectcolor=T.CARD, activebackground=T.BG, activeforeground=T.FG,
                           anchor="w").grid(sticky="w")

        # Datos de conexión
        self.marco = tk.Frame(cuerpo, bg=T.CARD, padx=12, pady=10)
        self.marco.grid(sticky="we", pady=12)
        self.var_host = tk.StringVar(value=SERVIDOR_HOST if SERVIDOR_HOST != "127.0.0.1" else "")
        self.var_puerto = tk.StringVar(value=str(SERVIDOR_PUERTO))
        self.var_token = tk.StringVar(value=TOKEN)

        self.lbl_host = tk.Label(self.marco, text="Dirección del servidor (IP):", font=FONT, bg=T.CARD, fg=T.FG)
        self.ent_host = self._entry(self.marco, self.var_host, 22)
        self.lbl_puerto = tk.Label(self.marco, text="Puerto:", font=FONT, bg=T.CARD, fg=T.FG)
        self.ent_puerto = self._entry(self.marco, self.var_puerto, 8)
        self.lbl_token = tk.Label(self.marco, text="Clave de acceso:", font=FONT, bg=T.CARD, fg=T.FG)
        self.ent_token = self._entry(self.marco, self.var_token, 34)
        self.lbl_ayuda = tk.Label(self.marco, text="", font=("Courier New", 9), bg=T.CARD, fg=T.MUTED,
                                  justify="left", wraplength=470)
        self.btn_probar = tk.Button(self.marco, text="🔌 Probar conexión", font=FONT_BTN, bg=T.ACCENT,
                                    fg=T.BG, relief="flat", cursor="hand2", padx=10, pady=4,
                                    command=self._probar)

        fila = tk.Frame(self, bg=T.BG)
        fila.pack(pady=(4, 14))
        tk.Button(fila, text="💾 Guardar", font=FONT_BTN, bg=T.GREEN, fg=T.BG, relief="flat",
                  cursor="hand2", padx=14, pady=6, command=self._guardar).pack(side="left", padx=6)
        tk.Button(fila, text="Cancelar", font=FONT_BTN, bg=T.CARD, fg=T.FG, relief="flat",
                  cursor="hand2", padx=14, pady=6, command=self.destroy).pack(side="left", padx=6)

        self._actualizar_campos()

        # Si la ventana "madre" está oculta (arranque del programa), NO hay que atarse a ella:
        # Tk esconde también a la ventana hija y el programa parecería no abrir.
        try:
            if parent.winfo_viewable():
                self.transient(parent)
        except tk.TclError:
            pass
        self.update_idletasks()
        x = (self.winfo_screenwidth() - self.winfo_width()) // 2
        y = (self.winfo_screenheight() - self.winfo_height()) // 3
        self.geometry(f"+{x}+{y}")
        self.deiconify()
        self.lift()
        self.focus_force()
        try:
            self.wait_visibility()     # tomar el foco recién cuando ya se ve
            self.grab_set()
        except tk.TclError:
            pass

    @staticmethod
    def _entry(parent, var, ancho):
        return tk.Entry(parent, textvariable=var, width=ancho, font=FONT, bg=T.BG, fg=T.FG,
                        insertbackground=T.FG, relief="flat")

    def _actualizar_campos(self):
        for w in (self.lbl_host, self.ent_host, self.lbl_puerto, self.ent_puerto,
                  self.lbl_token, self.ent_token, self.lbl_ayuda, self.btn_probar):
            w.grid_forget()
        modo = self.var_modo.get()
        if modo == "local":
            self.marco.grid_remove()
            return
        self.marco.grid()
        if modo == "servidor":
            self.lbl_puerto.grid(row=0, column=0, sticky="w")
            self.ent_puerto.grid(row=0, column=1, sticky="w", padx=8, pady=3, ipady=2)
            self.lbl_token.grid(row=1, column=0, sticky="w")
            self.ent_token.grid(row=1, column=1, sticky="w", padx=8, pady=3, ipady=2)
            if not self.var_token.get().strip():
                self.var_token.set(secrets.token_urlsafe(12))
            self.lbl_ayuda.config(
                text="En cada caja, elegí «CAJA conectada» y cargá estos datos:\n"
                     f"  • Dirección (IP) de este servidor: {', '.join(_ips_locales())}\n"
                     "  • El mismo puerto y la misma clave de acceso.\n"
                     "Esta PC debe quedar encendida mientras se vende, y Windows tiene que "
                     "permitir el puerto en el firewall.")
            self.lbl_ayuda.grid(row=2, column=0, columnspan=2, sticky="w", pady=(6, 0))
        else:
            self.lbl_host.grid(row=0, column=0, sticky="w")
            self.ent_host.grid(row=0, column=1, sticky="w", padx=8, pady=3, ipady=2)
            self.lbl_puerto.grid(row=1, column=0, sticky="w")
            self.ent_puerto.grid(row=1, column=1, sticky="w", padx=8, pady=3, ipady=2)
            self.lbl_token.grid(row=2, column=0, sticky="w")
            self.ent_token.grid(row=2, column=1, sticky="w", padx=8, pady=3, ipady=2)
            self.btn_probar.grid(row=3, column=0, columnspan=2, pady=(8, 0))
            self.lbl_ayuda.config(text="Pedí estos datos a quien configuró el servidor.")
            self.lbl_ayuda.grid(row=4, column=0, columnspan=2, sticky="w", pady=(6, 0))

    def _leer_puerto(self):
        try:
            p = int(self.var_puerto.get().strip())
            if not 1024 <= p <= 65535:
                raise ValueError
            return p
        except ValueError:
            messagebox.showerror("Puerto inválido", "Ingresá un número entre 1024 y 65535.", parent=self)
            return None

    def _probar(self):
        puerto = self._leer_puerto()
        if puerto is None:
            return
        host, token = self.var_host.get().strip(), self.var_token.get().strip()
        if not host or not token:
            messagebox.showwarning("Faltan datos", "Completá la dirección y la clave.", parent=self)
            return
        from backend.red.cliente import ClienteRed
        from backend.red.errores import ErrorRed
        try:
            ClienteRed(host, puerto, token, self.var_pdv.get().strip(), timeout=5).ping()
        except ErrorRed as e:
            messagebox.showerror("No se pudo conectar", str(e), parent=self)
            return
        messagebox.showinfo("✅ Conexión correcta", "El servidor respondió y la clave es correcta.", parent=self)

    def _guardar(self):
        pdv = self.var_pdv.get().strip()
        if not pdv:
            messagebox.showwarning("Falta el nombre", "Indicá un nombre para esta caja.", parent=self)
            return
        modo = self.var_modo.get()
        cambios = {"pdv": pdv, "modo": modo}
        if modo != "local":
            puerto = self._leer_puerto()
            token = self.var_token.get().strip()
            if puerto is None:
                return
            if not token:
                messagebox.showwarning("Falta la clave", "Indicá la clave de acceso.", parent=self)
                return
            cambios.update(servidor_puerto=puerto, token=token)
            if modo == "cliente":
                host = self.var_host.get().strip()
                if not host:
                    messagebox.showwarning("Falta la dirección", "Indicá la IP del servidor.", parent=self)
                    return
                cambios["servidor_host"] = host
        try:
            guardar_config_local(cambios)
        except OSError as e:
            messagebox.showerror("No se pudo guardar", str(e), parent=self)
            return
        self.guardado = True
        messagebox.showinfo("Guardado",
                            "Configuración guardada.\nCerrá y volvé a abrir STOCKPYME para aplicarla.",
                            parent=self)
        if self.al_guardar:
            self.al_guardar()
        self.destroy()
