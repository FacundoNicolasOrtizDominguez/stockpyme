import tkinter as tk
from tkinter import messagebox
import bcrypt

from backend.base_datos.repositorios import verificar_credenciales
from backend.red.errores import ErrorRed
from interfaz import tema as T


# ==============================
# VENTANA DE LOGIN
# ==============================

class VentanaLogin(tk.Toplevel):
    """
    Pantalla de inicio de sesión.
    Valida usuario y contraseña contra la base de datos usando bcrypt.
    Al autenticarse con éxito, abre la ventana principal según el rol.
    """

    def __init__(self, master=None):
        super().__init__(master)
        self.title("Iniciar sesión — Sistema de Stock y Ventas")
        self.resizable(False, False)
        self.geometry("380x390")
        self.configure(bg=T.BG)

        # Resultado de la autenticación
        self.usuario_autenticado = None
        # True si se cerró solo para volver a abrirse con otro tema (lo usa main.py)
        self.reabrir_por_tema = False

        T.configurar_ttk(self)

        self._construir_ui()
        self._centrar_ventana()

        # Bloquea la ventana padre hasta que se cierre el login
        self.grab_set()
        self.focus_force()

    # ------------------------------------------------------------------
    # CONSTRUCCIÓN DE LA INTERFAZ
    # ------------------------------------------------------------------

    def _construir_ui(self):
        # ---- Encabezado ----
        tk.Label(
            self,
            text="📦 Stock & Ventas",
            font=("Courier New", 18, "bold"),
            bg=T.BG,
            fg=T.ACCENT,
        ).pack(pady=(30, 4))

        tk.Label(
            self,
            text="Ingrese sus credenciales para continuar",
            font=("Courier New", 9),
            bg=T.BG,
            fg=T.MUTED,
        ).pack(pady=(0, 20))

        # ---- Formulario ----
        frame_form = tk.Frame(self, bg=T.BG)
        frame_form.pack(padx=40, fill="x")

        # Usuario
        tk.Label(
            frame_form, text="Usuario", font=("Courier New", 10),
            bg=T.BG, fg=T.FG, anchor="w"
        ).pack(fill="x", pady=(0, 2))

        self.entry_usuario = tk.Entry(
            frame_form,
            font=("Courier New", 11),
            bg=T.CARD,
            fg=T.FG,
            insertbackground=T.ACCENT,
            relief="flat",
            bd=6,
        )
        self.entry_usuario.pack(fill="x", ipady=4)

        tk.Label(frame_form, bg=T.BG, height=1).pack()  # espaciado

        # Contraseña
        tk.Label(
            frame_form, text="Contraseña", font=("Courier New", 10),
            bg=T.BG, fg=T.FG, anchor="w"
        ).pack(fill="x", pady=(0, 2))

        self.entry_password = tk.Entry(
            frame_form,
            show="●",
            font=("Courier New", 11),
            bg=T.CARD,
            fg=T.FG,
            insertbackground=T.ACCENT,
            relief="flat",
            bd=6,
        )
        self.entry_password.pack(fill="x", ipady=4)

        # ---- Botón ----
        tk.Button(
            self,
            text="INGRESAR",
            font=("Courier New", 11, "bold"),
            bg=T.ACCENT,
            fg=T.ON_ACCENT,
            activebackground=T.ACCENT_HOVER,
            activeforeground=T.ON_ACCENT,
            relief="flat",
            cursor="hand2",
            command=self._intentar_login,
        ).pack(pady=(20, 14), ipadx=20, ipady=6)

        self._construir_selector_tema()

        # Enter dispara el login
        self.bind("<Return>", lambda e: self._intentar_login())

    def _construir_selector_tema(self):
        """Fila con un botón por tema; el activo se marca con borde del color de acento."""
        marco = tk.Frame(self, bg=T.BG)
        marco.pack(pady=(0, 10))
        tk.Label(marco, text="Tema:", font=("Courier New", 9),
                 bg=T.BG, fg=T.MUTED).pack(side="left", padx=(0, 6))
        corto = {"morado": "Morado", "oscuro": "Oscuro", "claro": "Claro"}
        for nombre in T.ORDEN:
            paleta = T.TEMAS[nombre]          # cada botón muestra los colores de SU tema
            activo = (nombre == T.actual)
            tk.Button(
                marco, text=corto[nombre], font=("Courier New", 8, "bold"),
                bg=paleta["CARD"], fg=paleta["FG"],
                activebackground=paleta["HOVER"], activeforeground=paleta["FG"],
                relief="flat", cursor="hand2", padx=8, pady=2,
                highlightthickness=2,
                highlightbackground=T.ACCENT if activo else T.BG,
                highlightcolor=T.ACCENT,
                command=lambda n=nombre: self._cambiar_tema(n),
            ).pack(side="left", padx=2)

    def _cambiar_tema(self, nombre):
        if nombre == T.actual:
            return
        T.aplicar(nombre)               # lo guarda para la próxima vez
        self.reabrir_por_tema = True    # main.py vuelve a abrir el login ya con el tema nuevo
        self.destroy()

    def _centrar_ventana(self):
        self.update_idletasks()
        x = (self.winfo_screenwidth() - self.winfo_width()) // 2
        y = (self.winfo_screenheight() - self.winfo_height()) // 2
        self.geometry(f"+{x}+{y}")

    # ------------------------------------------------------------------
    # LÓGICA DE AUTENTICACIÓN
    # ------------------------------------------------------------------

    def _intentar_login(self):
        nombre = self.entry_usuario.get().strip()
        password = self.entry_password.get().strip()

        if not nombre or not password:
            messagebox.showwarning("Campos vacíos", "Complete usuario y contraseña.", parent=self)
            return

        # La contraseña se valida donde está la base (en modo cliente, en el servidor):
        # el hash nunca viaja a las cajas.
        try:
            estado, usuario = verificar_credenciales(nombre, password)
        except ErrorRed as e:
            messagebox.showerror("Sin conexión", str(e), parent=self)
            return

        mensajes = {
            "no_existe": "Usuario no encontrado.",
            "clave_incorrecta": "Contraseña incorrecta.",
            "inactivo": "El usuario está inactivo.",
        }
        if estado != "ok":
            messagebox.showerror("Error", mensajes.get(estado, "No se pudo iniciar sesión."), parent=self)
            return

        self.usuario_autenticado = usuario
        self.destroy()

    @staticmethod
    def _verificar_password(password_plana: str, hash_guardado: str) -> bool:
        """
        Verifica la contraseña contra el hash bcrypt almacenado.
        También acepta contraseñas guardadas en texto plano (modo desarrollo).
        """
        try:
            return bcrypt.checkpw(
                password_plana.encode("utf-8"),
                hash_guardado.encode("utf-8"),
            )
        except Exception:
            # Fallback para desarrollo: comparación directa
            return password_plana == hash_guardado
