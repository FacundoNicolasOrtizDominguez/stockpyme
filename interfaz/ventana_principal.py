# ============================================================
# VENTANA PRINCIPAL
# Sistema de Control de Stock y Ventas
# ============================================================

import tkinter as tk
from tkinter import messagebox

from backend.config import NOMBRE_SISTEMA, ROLES_VALIDOS, PDV_NOMBRE, MODO, SERVIDOR_HOST
from interfaz import tema as T


class VentanaPrincipal(tk.Toplevel):
    """
    Ventana principal de la aplicación.
    Ahora es Toplevel (no Tk) para poder volver al login sin destruir root.
    cerrar_sesion_solicitado indica si se debe volver al login.
    """

    def __init__(self, usuario, master=None):
        super().__init__(master)
        self.usuario = usuario
        self.cerrar_sesion_solicitado = False
        # True si se cerró solo para volver a abrirse con otro tema (lo usa main.py)
        self.reabrir_por_tema = False
        self._var_tema = tk.StringVar(value=T.actual)

        T.configurar_ttk(self)

        _etiqueta_red = {"servidor": " [SERVIDOR]", "cliente": f" [→ {SERVIDOR_HOST}]"}.get(MODO, "")
        self.title(f"{NOMBRE_SISTEMA} — {PDV_NOMBRE}{_etiqueta_red} — {usuario.nombre_usuario} ({usuario.rol})")
        self.geometry("780x560")
        self.minsize(640, 460)
        self.configure(bg=T.BG)

        # Al cerrar con la X, equivale a "Salir"
        self.protocol("WM_DELETE_WINDOW", self._salir)

        self._construir_menu()
        self._construir_ui()
        self._centrar_ventana()

        if self.usuario.rol in ("administrador", "repositor"):
            self.after(600, self._verificar_alertas_inicio)

        # Mostrar notificaciones pendientes al admin
        if self.usuario.rol == "administrador":
            self.after(900, self._verificar_notificaciones_admin)

        self.focus_force()

    # ------------------------------------------------------------------
    # MENÚ NATIVO
    # ------------------------------------------------------------------

    def _construir_menu(self):
        barra = tk.Menu(self, bg=T.CARD, fg=T.FG,
                        activebackground=T.ACCENT)

        menu_sesion = tk.Menu(barra, tearoff=0, bg=T.CARD, fg=T.FG)
        menu_sesion.add_command(label="Cerrar sesión", command=self._cerrar_sesion)

        menu_tema = tk.Menu(menu_sesion, tearoff=0, bg=T.CARD, fg=T.FG,
                            activebackground=T.ACCENT, activeforeground=T.ON_ACCENT,
                            selectcolor=T.ACCENT)
        for nombre in T.ORDEN:
            menu_tema.add_radiobutton(label=T.NOMBRES[nombre], value=nombre,
                                      variable=self._var_tema,
                                      command=lambda n=nombre: self._cambiar_tema(n))
        menu_sesion.add_cascade(label="Tema", menu=menu_tema)
        if self.usuario.rol == "administrador":
            menu_sesion.add_command(label="Configuración de red…", command=self._abrir_configuracion)
        menu_sesion.add_separator()
        menu_sesion.add_command(label="Salir del sistema", command=self._salir)
        barra.add_cascade(label="Sesión", menu=menu_sesion)

        # Ventas — solo administrador y vendedor (NO repositor)
        if self.usuario.rol in ("administrador", "vendedor"):
            menu_ventas = tk.Menu(barra, tearoff=0, bg=T.CARD, fg=T.FG)
            menu_ventas.add_command(label="Registrar venta", command=self._abrir_venta)
            barra.add_cascade(label="Ventas", menu=menu_ventas)

        if self.usuario.rol in ("administrador", "repositor"):
            menu_stock = tk.Menu(barra, tearoff=0, bg=T.CARD, fg=T.FG)
            menu_stock.add_command(label="Ver stock actual", command=self._abrir_stock)
            menu_stock.add_command(label="Alertas de stock mínimo", command=self._abrir_alertas)
            if self.usuario.rol == "administrador":
                menu_stock.add_command(label="Historial de movimientos", command=self._abrir_movimientos)
            if self.usuario.rol == "repositor":
                menu_stock.add_command(label="📢 Avisar al Admin", command=self._ventana_notificar_admin)
            barra.add_cascade(label="Stock", menu=menu_stock)

        if self.usuario.rol == "administrador":
            menu_reportes = tk.Menu(barra, tearoff=0, bg=T.CARD, fg=T.FG)
            menu_reportes.add_command(label="Reporte de ventas", command=self._abrir_reportes)
            menu_reportes.add_command(label="Consolidación de PDV", command=self._abrir_consolidacion)
            menu_reportes.add_command(label="Métricas del piloto", command=self._abrir_metricas)
            barra.add_cascade(label="Reportes", menu=menu_reportes)

            menu_admin = tk.Menu(barra, tearoff=0, bg=T.CARD, fg=T.FG)
            menu_admin.add_command(label="Gestión de productos", command=self._abrir_admin)
            menu_admin.add_command(label="Gestión de usuarios", command=self._abrir_admin)
            barra.add_cascade(label="Administración", menu=menu_admin)

        self.config(menu=barra)

    # ------------------------------------------------------------------
    # DASHBOARD
    # ------------------------------------------------------------------

    def _construir_ui(self):
        # Encabezado
        frame_header = tk.Frame(self, bg=T.PANEL, pady=14)
        frame_header.pack(fill="x")

        tk.Label(
            frame_header,
            text=f"📦 {NOMBRE_SISTEMA}",
            font=("Courier New", 18, "bold"),
            bg=T.PANEL, fg=T.ACCENT,
        ).pack()

        tk.Label(
            frame_header,
            text=f"Bienvenido, {self.usuario.nombre_usuario}  •  Rol: {self.usuario.rol.upper()}",
            font=("Courier New", 9),
            bg=T.PANEL, fg=T.MUTED,
        ).pack(pady=(2, 0))

        # Banner alerta stock
        self.frame_alerta = tk.Frame(self, bg=T.ALERT_BG, cursor="hand2")
        self.lbl_alerta = tk.Label(
            self.frame_alerta, text="",
            font=("Courier New", 10, "bold"),
            bg=T.ALERT_BG, fg=T.RED, pady=7
        )
        self.lbl_alerta.pack(expand=True)
        self.frame_alerta.bind("<Button-1>", lambda e: self._abrir_alertas())
        self.lbl_alerta.bind("<Button-1>", lambda e: self._abrir_alertas())

        # ── DASHBOARD de resumen (solo admin y repositor) ──────────────
        if self.usuario.rol in ("administrador", "repositor"):
            self.frame_dashboard = tk.Frame(self, bg=T.BG)
            self.frame_dashboard.pack(fill="x", padx=20, pady=(10, 0))
            self._construir_dashboard()

        # Botones de acceso rápido
        frame_botones = tk.Frame(self, bg=T.BG)
        frame_botones.pack(expand=True)

        botones = self._obtener_botones_por_rol()
        for i, (icono, texto, comando) in enumerate(botones):
            col = i % 3
            row = i // 3
            self._crear_boton_card(frame_botones, icono, texto, comando).grid(
                row=row, column=col, padx=14, pady=12, sticky="nsew"
            )
        for c in range(3):
            frame_botones.grid_columnconfigure(c, weight=1)

        # Pie
        tk.Label(
            self,
            text="STOCKPYME — Universidad del Aconcagua — 2026",
            font=("Courier New", 8),
            bg=T.BG, fg=T.FAINT,
        ).pack(side="bottom", pady=6)

    def _construir_dashboard(self):
        """Tarjetas de resumen: ventas de hoy, productos críticos."""
        try:
            from backend.base_datos.repositorios import resumen_hoy
            datos = resumen_hoy()
        except Exception:
            datos = {"total_vendido_hoy": 0.0, "cantidad_ventas_hoy": 0, "productos_stock_critico": 0}

        tarjetas = [
            ("💰", "Vendido hoy", f"${datos['total_vendido_hoy']:,.2f}", T.GREEN),
            ("🛒", "Ventas hoy",  str(datos["cantidad_ventas_hoy"]),     T.BLUE),
            ("⚠️", "Stock crítico", str(datos["productos_stock_critico"]), T.RED),
        ]

        for icono, titulo, valor, color in tarjetas:
            card = tk.Frame(self.frame_dashboard, bg=T.CARD, padx=14, pady=8)
            card.pack(side="left", expand=True, fill="x", padx=6)

            tk.Label(card, text=icono + "  " + titulo,
                     font=("Courier New", 8), bg=T.CARD, fg=T.MUTED).pack(anchor="w")
            tk.Label(card, text=valor,
                     font=("Courier New", 16, "bold"), bg=T.CARD, fg=color).pack(anchor="w")

    def _crear_boton_card(self, parent, icono, texto, comando):
        frame = tk.Frame(parent, bg=T.CARD, cursor="hand2", width=190, height=90)
        frame.pack_propagate(False)

        tk.Label(frame, text=icono, font=("Segoe UI Emoji", 22),
                 bg=T.CARD).pack(pady=(10, 2))
        tk.Label(frame, text=texto, font=("Courier New", 9, "bold"),
                 bg=T.CARD, fg=T.FG).pack()

        def on_enter(e):
            frame.configure(bg=T.HOVER)
            for w in frame.winfo_children(): w.configure(bg=T.HOVER)

        def on_leave(e):
            frame.configure(bg=T.CARD)
            for w in frame.winfo_children(): w.configure(bg=T.CARD)

        frame.bind("<Enter>", on_enter)
        frame.bind("<Leave>", on_leave)
        frame.bind("<Button-1>", lambda e: comando())
        for child in frame.winfo_children():
            child.bind("<Enter>", on_enter)
            child.bind("<Leave>", on_leave)
            child.bind("<Button-1>", lambda e: comando())

        return frame

    def _obtener_botones_por_rol(self):
        botones = []

        # Venta: solo admin y vendedor (NO repositor)
        if self.usuario.rol in ("administrador", "vendedor"):
            botones.append(("🛒", "Registrar Venta", self._abrir_venta))

        if self.usuario.rol in ("administrador", "repositor"):
            botones.append(("📊", "Ver Stock", self._abrir_stock))
            botones.append(("⚠️", "Alertas de Stock", self._abrir_alertas))

        # Botón para avisar al admin (solo repositor)
        if self.usuario.rol == "repositor":
            botones.append(("📢", "Avisar al Admin", self._ventana_notificar_admin))

        if self.usuario.rol == "administrador":
            botones.append(("🏪", "Consolidación", self._abrir_consolidacion))
            botones.append(("📄", "Reportes", self._abrir_reportes))
            botones.append(("📦", "Movimientos", self._abrir_movimientos))
            botones.append(("⚙️", "Administración", self._abrir_admin))
            botones.append(("📈", "Métricas piloto", self._abrir_metricas))

        botones.append(("🔄", "Cerrar Sesión", self._cerrar_sesion))
        return botones
    def _centrar_ventana(self):
        self.update_idletasks()
        x = (self.winfo_screenwidth() - self.winfo_width()) // 2
        y = (self.winfo_screenheight() - self.winfo_height()) // 2
        self.geometry(f"+{x}+{y}")

    # ------------------------------------------------------------------
    # ALERTAS
    # ------------------------------------------------------------------

    def _verificar_alertas_inicio(self):
        try:
            from backend.base_datos.repositorios import listar_productos
            productos = listar_productos()
            alertas = [p for p in productos if p.alerta_stock_minimo() and p.activo]
            if alertas:
                n = len(alertas)
                texto = f"⚠️  {n} producto{'s' if n > 1 else ''} con stock bajo — Clic aquí para ver"
                self.lbl_alerta.config(text=texto)
                self.frame_alerta.pack(fill="x", after=self.winfo_children()[0])
        except Exception:
            pass

    # ------------------------------------------------------------------
    # NAVEGACIÓN
    # ------------------------------------------------------------------

    def _abrir_venta(self):
        from interfaz.ventana_venta import VentanaVenta
        VentanaVenta(self, self.usuario)

    def _abrir_stock(self):
        from interfaz.ventana_stock import VentanaStock
        VentanaStock(self, self.usuario)

    def _abrir_alertas(self):
        from interfaz.ventana_stock import VentanaAlertas
        VentanaAlertas(self)

    def _abrir_movimientos(self):
        from interfaz.ventana_movimientos import VentanaMovimientos
        VentanaMovimientos(self)

    def _abrir_metricas(self):
        try:
            from interfaz.ventana_metricas import VentanaMetricas
            VentanaMetricas(self, self.usuario)
        except Exception as e:
            import traceback
            messagebox.showerror("Error", f"{type(e).__name__}: {e}\n\n{traceback.format_exc()}", parent=self)

    def _abrir_configuracion(self):
        try:
            from interfaz.ventana_configuracion import VentanaConfiguracion
            VentanaConfiguracion(self)
        except Exception as e:
            import traceback
            messagebox.showerror("Error", f"{type(e).__name__}: {e}\n\n{traceback.format_exc()}", parent=self)

    def _abrir_consolidacion(self):
        try:
            from interfaz.ventana_consolidacion import VentanaConsolidacion
            VentanaConsolidacion(self)
        except Exception as e:
            import traceback
            messagebox.showerror("Error", f"{type(e).__name__}: {e}\n\n{traceback.format_exc()}", parent=self)

    def _abrir_reportes(self):
        try:
            from interfaz.ventana_reportes import VentanaReportes
            VentanaReportes(self)
        except Exception as e:
            import traceback
            messagebox.showerror("Error", f"{type(e).__name__}: {e}\n\n{traceback.format_exc()}", parent=self)

    def _abrir_admin(self):
        if self.usuario.rol != "administrador":
            messagebox.showerror("Acceso denegado",
                                 "Solo los administradores pueden acceder.", parent=self)
            return
        try:
            from interfaz.ventana_admin import VentanaAdmin
            VentanaAdmin(self)
        except Exception as e:
            import traceback
            messagebox.showerror("Error", f"{type(e).__name__}: {e}\n\n{traceback.format_exc()}", parent=self)

    def _ventana_notificar_admin(self):
        """El repositor escribe un mensaje que queda guardado para el admin."""
        ventana = tk.Toplevel(self)
        ventana.title("📢 Avisar al Administrador")
        ventana.geometry("460x300")
        ventana.configure(bg=T.BG)
        ventana.resizable(False, False)
        ventana.grab_set()

        tk.Label(ventana, text="📢 Aviso para el Administrador",
                 font=("Courier New", 13, "bold"),
                 bg=T.BG, fg=T.YELLOW).pack(pady=(18, 4))
        tk.Label(ventana, text="Escribí tu mensaje (ej: faltan productos, problema de stock, etc.)",
                 font=("Courier New", 9), bg=T.BG, fg=T.MUTED,
                 wraplength=400).pack(pady=(0, 10))

        texto = tk.Text(ventana, bg=T.CARD, fg=T.FG,
                        font=("Courier New", 10), relief="flat", bd=6,
                        height=6, wrap="word")
        texto.pack(fill="x", padx=20, pady=(0, 10))
        texto.focus_set()

        def enviar():
            msg = texto.get("1.0", tk.END).strip()
            if not msg:
                messagebox.showwarning("Mensaje vacío",
                                       "Escribí algo antes de enviar.", parent=ventana)
                return
            from backend.base_datos.repositorios import crear_notificacion
            crear_notificacion(
                mensaje=f"[{self.usuario.nombre_usuario}]: {msg}",
                remitente_id=self.usuario.id
            )
            messagebox.showinfo("✅ Enviado",
                                "El mensaje fue guardado. El admin lo verá al entrar.",
                                parent=ventana)
            ventana.destroy()

        tk.Button(ventana, text="📤 Enviar aviso",
                  font=("Courier New", 10, "bold"),
                  bg=T.YELLOW, fg=T.ON_ACCENT,
                  relief="flat", cursor="hand2",
                  command=enviar).pack(ipadx=12, ipady=5)

    def _verificar_notificaciones_admin(self):
        """Al entrar el admin, muestra un popup si hay mensajes sin leer."""
        from backend.base_datos.repositorios import listar_notificaciones_no_leidas, marcar_notificaciones_leidas
        notifs = listar_notificaciones_no_leidas()
        if not notifs:
            return

        ventana = tk.Toplevel(self)
        ventana.title(f"📬 Tenés {len(notifs)} aviso(s) nuevo(s)")
        ventana.geometry("500x360")
        ventana.configure(bg=T.BG)
        ventana.grab_set()

        tk.Label(ventana,
                 text=f"📬 {len(notifs)} aviso(s) de repositores",
                 font=("Courier New", 13, "bold"),
                 bg=T.BG, fg=T.YELLOW).pack(pady=(16, 6))

        frame = tk.Frame(ventana, bg=T.CARD)
        frame.pack(fill="both", expand=True, padx=16, pady=(0, 10))

        scroll = tk.Scrollbar(frame)
        scroll.pack(side="right", fill="y")
        lista = tk.Text(frame, bg=T.CARD, fg=T.FG,
                        font=("Courier New", 9), relief="flat", bd=6,
                        yscrollcommand=scroll.set, state="normal", wrap="word")
        scroll.config(command=lista.yview)
        lista.pack(fill="both", expand=True)

        for n in notifs:
            fecha = n["fecha"][:16] if n["fecha"] else ""
            msg_linea = f"  [{fecha}]  " + n["mensaje"] + "\n\n"
            lista.insert(tk.END, msg_linea)

        lista.config(state="disabled")

        def marcar_y_cerrar():
            marcar_notificaciones_leidas()
            ventana.destroy()

        tk.Button(ventana, text="✔ Marcar como leídos y cerrar",
                  font=("Courier New", 10, "bold"),
                  bg=T.GREEN, fg=T.ON_ACCENT,
                  relief="flat", cursor="hand2",
                  command=marcar_y_cerrar).pack(pady=8, ipadx=10, ipady=5)

    # ------------------------------------------------------------------
    # SESIÓN
    # ------------------------------------------------------------------

    def _cerrar_sesion(self):
        if messagebox.askyesno("Cerrar sesión",
                                "¿Desea cerrar la sesión actual y volver al login?",
                                parent=self):
            self.cerrar_sesion_solicitado = True
            self.destroy()

    def _cambiar_tema(self, nombre):
        """Aplica el tema y rehace esta ventana (main.py la vuelve a abrir con el mismo usuario)."""
        if nombre == T.actual:
            return
        abiertas = [w for w in self.winfo_children() if isinstance(w, tk.Toplevel)]
        if abiertas and not messagebox.askyesno(
                "Cambiar tema",
                "Para aplicar el tema se cierran las ventanas que tenés abiertas "
                "(lo que no esté guardado se pierde).\n\n¿Continuar?",
                parent=self):
            self._var_tema.set(T.actual)     # deja marcado el tema que sigue vigente
            return
        T.aplicar(nombre)
        self.reabrir_por_tema = True
        self.destroy()

    def _salir(self):
        if messagebox.askyesno("Salir", "¿Desea cerrar el sistema?", parent=self):
            self.cerrar_sesion_solicitado = False
            self.destroy()
