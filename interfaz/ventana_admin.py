# ============================================================
# VENTANA DE ADMINISTRACIÓN
# Sistema de Control de Stock y Ventas
# ============================================================
# Solo accesible para usuarios con rol "administrador".
# Contiene dos pestañas:
#   1. Gestión de Productos  — alta, edición, ajuste de stock,
#                              activar/desactivar.
#   2. Gestión de Usuarios   — alta, cambio de rol/contraseña,
#                              activar/desactivar.
# ============================================================

import tkinter as tk
from tkinter import ttk, messagebox

from backend.config import ROLES_VALIDOS, STOCK_MINIMO_DEFAULT
from interfaz.componentes import agregar_boton_volver
from backend.base_datos.repositorios import (
    # productos
    crear_producto, listar_productos, actualizar_producto,
    ajustar_stock, cambiar_estado_producto, eliminar_producto,
    # usuarios
    crear_usuario, listar_usuarios, actualizar_usuario,
    cambiar_estado_usuario, eliminar_usuario,
    # movimientos
    registrar_movimiento,
)
from interfaz import tema as T


# ─────────────────────────────────────────────────────────────
# VENTANA PRINCIPAL DE ADMINISTRACIÓN
# ─────────────────────────────────────────────────────────────

class VentanaAdmin(tk.Toplevel):
    """
    Panel de administración con pestañas para Productos y Usuarios.
    Solo el administrador puede abrirla (verificado en ventana_principal).
    """

    def __init__(self, master):
        super().__init__(master)
        self.title("⚙️  Panel de Administración")
        self.geometry("900x580")
        self.minsize(780, 500)
        self.configure(bg=T.BG)

        self._construir_ui()
        self._centrar_ventana()
        self.grab_set()

    # ------------------------------------------------------------------
    # ESTRUCTURA
    # ------------------------------------------------------------------

    def _construir_ui(self):
        # Encabezado
        frame_header = tk.Frame(self, bg=T.PANEL, pady=12)
        frame_header.pack(fill="x")
        agregar_boton_volver(self, frame_header)
        tk.Label(
            frame_header, text="⚙️  Panel de Administración",
            font=("Courier New", 17, "bold"),
            bg=T.PANEL, fg=T.ACCENT
        ).pack()
        tk.Label(
            frame_header,
            text="Gestión de productos y usuarios del sistema",
            font=("Courier New", 9), bg=T.PANEL, fg=T.MUTED
        ).pack(pady=(2, 0))

        # Pestañas
        estilo = ttk.Style()
        T.usar_tema_ttk(estilo)
        estilo.configure(
            "TNotebook", background=T.BG, borderwidth=0
        )
        estilo.configure(
            "TNotebook.Tab",
            background=T.CARD, foreground=T.FG,
            font=("Courier New", 10, "bold"),
            padding=[14, 6]
        )
        estilo.map(
            "TNotebook.Tab",
            background=[("selected", T.HOVER)],
            foreground=[("selected", T.ACCENT)]
        )

        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True, padx=10, pady=10)

        tab_productos = tk.Frame(notebook, bg=T.BG)
        tab_usuarios = tk.Frame(notebook, bg=T.BG)

        notebook.add(tab_productos, text="  📦 Productos  ")
        notebook.add(tab_usuarios, text="  👤 Usuarios  ")

        PanelProductos(tab_productos)
        PanelUsuarios(tab_usuarios)

    def _centrar_ventana(self):
        self.update_idletasks()
        x = (self.winfo_screenwidth() - self.winfo_width()) // 2
        y = (self.winfo_screenheight() - self.winfo_height()) // 2
        self.geometry(f"+{x}+{y}")


# ─────────────────────────────────────────────────────────────
# HELPERS COMPARTIDOS
# ─────────────────────────────────────────────────────────────

def _estilizar_tabla(tabla):
    estilo = ttk.Style()
    estilo.configure(
        "Treeview",
        background=T.CARD, fieldbackground=T.CARD,
        foreground=T.FG, rowheight=24,
        font=("Courier New", 9)
    )
    estilo.configure(
        "Treeview.Heading",
        background=T.HOVER, foreground=T.BLUE,
        font=("Courier New", 9, "bold")
    )
    estilo.map("Treeview", background=[("selected", T.SELECT)])


def _boton(parent, texto, comando, color_bg=None, color_fg=None):
    color_bg = color_bg or T.HOVER      # se resuelven acá (no como default) para respetar el tema activo
    color_fg = color_fg or T.FG
    return tk.Button(
        parent, text=texto, command=comando,
        font=("Courier New", 9, "bold"),
        bg=color_bg, fg=color_fg,
        activebackground=T.SELECT, activeforeground=T.FG,
        relief="flat", cursor="hand2"
    )


def _label(parent, texto, fg=None, bold=False):
    fg = fg or T.FG
    font = ("Courier New", 10, "bold") if bold else ("Courier New", 10)
    return tk.Label(parent, text=texto, font=font, bg=T.BG, fg=fg, anchor="w")


def _entry(parent, textvariable=None, width=28, show=None):
    kwargs = dict(
        font=("Courier New", 10), bg=T.CARD, fg=T.FG,
        insertbackground=T.ACCENT, relief="flat", bd=5, width=width
    )
    if textvariable:
        kwargs["textvariable"] = textvariable
    if show:
        kwargs["show"] = show
    return tk.Entry(parent, **kwargs)


# ─────────────────────────────────────────────────────────────
# PANEL — PRODUCTOS
# ─────────────────────────────────────────────────────────────

class PanelProductos(tk.Frame):
    """
    Pestaña de gestión de productos.
    Acciones: Agregar | Editar | Ajustar stock | Activar/Desactivar
    """

    def __init__(self, master):
        super().__init__(master, bg=T.BG)
        self.pack(fill="both", expand=True)
        self.productos = []
        self._construir_ui()
        self._recargar()

    # ------------------------------------------------------------------
    # INTERFAZ
    # ------------------------------------------------------------------

    def _construir_ui(self):
        # ── Barra superior: buscador + botones ──
        # Dos filas: buscador arriba, botones abajo (así no se cortan en ventanas angostas)
        frame_busqueda = tk.Frame(self, bg=T.BG)
        frame_busqueda.pack(fill="x", padx=10, pady=(8, 2))

        tk.Label(frame_busqueda, text="🔍", bg=T.BG, fg=T.FG).pack(side="left")
        self.var_buscar = tk.StringVar()
        self.var_buscar.trace_add("write", lambda *_: self._filtrar())
        _entry(frame_busqueda, textvariable=self.var_buscar, width=30).pack(
            side="left", padx=(4, 14), ipady=3
        )
        _boton(frame_busqueda, "↺ Actualizar", self._recargar).pack(
            side="right", ipadx=6, ipady=3)

        frame_top = tk.Frame(self, bg=T.BG)
        frame_top.pack(fill="x", padx=10, pady=(2, 6))

        _boton(frame_top, "＋ Nuevo", self._dialogo_agregar,
               color_bg=T.GREEN, color_fg=T.ON_ACCENT).pack(side="left", ipadx=4, ipady=3)
        _boton(frame_top, "✏ Editar", self._dialogo_editar).pack(
            side="left", padx=4, ipadx=4, ipady=3)
        _boton(frame_top, "📦 Ajustar stock", self._dialogo_ajustar_stock,
               color_bg=T.BLUE, color_fg=T.ON_ACCENT).pack(
            side="left", ipadx=4, ipady=3)
        _boton(frame_top, "⊘ Act./Desact.", self._toggle_estado,
               color_bg=T.RED, color_fg=T.ON_ACCENT).pack(
            side="left", padx=4, ipadx=4, ipady=3)
        _boton(frame_top, "🗑 Eliminar", self._eliminar_producto,
               color_bg=T.RED, color_fg=T.ON_ACCENT).pack(
            side="left", ipadx=4, ipady=3)

        # ── Tabla ──
        cols = ("ID", "Nombre", "Categoría", "Precio", "Stock", "Stk. Mín.", "Estado")
        self.tabla = ttk.Treeview(self, columns=cols, show="headings", height=16)
        _estilizar_tabla(self.tabla)
        anchos = (40, 200, 120, 90, 70, 80, 80)
        for col, w in zip(cols, anchos):
            self.tabla.heading(col, text=col,
                               command=lambda c=col: self._ordenar(c))
            self.tabla.column(col, width=w, anchor="center")

        scroll = ttk.Scrollbar(self, orient="vertical", command=self.tabla.yview)
        self.tabla.configure(yscrollcommand=scroll.set)
        self.tabla.pack(side="left", fill="both", expand=True,
                        padx=(10, 0), pady=(0, 10))
        scroll.pack(side="left", fill="y", pady=(0, 10))

        self.tabla.tag_configure("bajo", foreground=T.RED)
        self.tabla.tag_configure("inactivo", foreground=T.MUTED)

        # Doble clic abre edición
        self.tabla.bind("<Double-1>", lambda _: self._dialogo_editar())

    # ------------------------------------------------------------------
    # CARGA Y FILTRO
    # ------------------------------------------------------------------

    def _recargar(self):
        self.productos = listar_productos()
        self._filtrar()

    def _filtrar(self):
        texto = self.var_buscar.get().lower().strip()
        filtrados = [
            p for p in self.productos
            if texto in p.nombre.lower() or texto in p.categoria.lower()
        ]
        self._cargar_tabla(filtrados)

    def _cargar_tabla(self, lista):
        self.tabla.delete(*self.tabla.get_children())
        for p in lista:
            estado = "Activo" if p.activo else "Inactivo"
            tag = ""
            if not p.activo:
                tag = "inactivo"
            elif p.stock <= p.stock_minimo:
                tag = "bajo"
            self.tabla.insert(
                "", "end",
                values=(p.id, p.nombre, p.categoria,
                        f"${p.precio:.2f}", p.stock, p.stock_minimo, estado),
                tags=(tag,)
            )

    def _ordenar(self, columna):
        """Ordena la tabla al hacer clic en el encabezado."""
        mapa = {
            "ID": "id", "Nombre": "nombre", "Categoría": "categoria",
            "Precio": "precio", "Stock": "stock",
            "Stk. Mín.": "stock_minimo", "Estado": "activo"
        }
        attr = mapa.get(columna, "nombre")
        self.productos.sort(key=lambda p: getattr(p, attr))
        self._filtrar()

    # ------------------------------------------------------------------
    # OBTENER PRODUCTO SELECCIONADO
    # ------------------------------------------------------------------

    def _producto_seleccionado(self):
        sel = self.tabla.focus()
        if not sel:
            messagebox.showwarning("Sin selección",
                                   "Seleccioná un producto de la tabla.", parent=self)
            return None
        id_prod = int(self.tabla.item(sel, "values")[0])
        return next((p for p in self.productos if p.id == id_prod), None)

    # ------------------------------------------------------------------
    # DIÁLOGO — AGREGAR PRODUCTO
    # ------------------------------------------------------------------

    def _dialogo_agregar(self):
        dialogo = _Dialogo(self, titulo="Nuevo Producto", ancho=420, alto=380)

        _label(dialogo.frame, "Nombre *").grid(row=0, column=0, sticky="w", pady=4)
        var_nombre = tk.StringVar()
        _entry(dialogo.frame, var_nombre).grid(row=0, column=1, sticky="ew", pady=4)

        _label(dialogo.frame, "Categoría *").grid(row=1, column=0, sticky="w", pady=4)
        var_cat = tk.StringVar()
        _entry(dialogo.frame, var_cat).grid(row=1, column=1, sticky="ew", pady=4)

        _label(dialogo.frame, "Precio *").grid(row=2, column=0, sticky="w", pady=4)
        var_precio = tk.StringVar()
        _entry(dialogo.frame, var_precio).grid(row=2, column=1, sticky="ew", pady=4)

        _label(dialogo.frame, "Stock inicial").grid(row=3, column=0, sticky="w", pady=4)
        var_stock = tk.StringVar(value="0")
        _entry(dialogo.frame, var_stock).grid(row=3, column=1, sticky="ew", pady=4)

        _label(dialogo.frame, f"Stock mínimo (def. {STOCK_MINIMO_DEFAULT})").grid(
            row=4, column=0, sticky="w", pady=4)
        var_smin = tk.StringVar(value=str(STOCK_MINIMO_DEFAULT))
        _entry(dialogo.frame, var_smin).grid(row=4, column=1, sticky="ew", pady=4)

        dialogo.frame.columnconfigure(1, weight=1)

        def guardar():
            nombre = var_nombre.get().strip()
            categoria = var_cat.get().strip()
            precio_txt = var_precio.get().strip()
            stock_txt = var_stock.get().strip()
            smin_txt = var_smin.get().strip()

            # Validaciones de tipeo
            errores = []
            if not nombre:
                errores.append("• El nombre es obligatorio.")
            if not categoria:
                errores.append("• La categoría es obligatoria.")
            precio = _parsear_float(precio_txt)
            if precio is None:
                errores.append("• El precio debe ser un número (ej: 1250.50).")
            elif precio < 0:
                errores.append("• El precio no puede ser negativo.")
            stock = _parsear_int(stock_txt)
            if stock is None:
                errores.append("• El stock debe ser un número entero.")
            elif stock < 0:
                errores.append("• El stock no puede ser negativo.")
            smin = _parsear_int(smin_txt)
            if smin is None:
                errores.append("• El stock mínimo debe ser un número entero.")
            elif smin < 0:
                errores.append("• El stock mínimo no puede ser negativo.")

            if errores:
                messagebox.showerror("Datos inválidos", "\n".join(errores),
                                     parent=dialogo)
                return

            try:
                resultado = crear_producto(nombre, categoria, precio, stock, smin)
            except ValueError as e:
                messagebox.showerror("Error de validación", str(e), parent=dialogo)
                return

            if resultado is None:
                messagebox.showerror("Error",
                                     "No se pudo guardar el producto. Revisá la base de datos.",
                                     parent=dialogo)
                return

            messagebox.showinfo("Éxito",
                                f"Producto «{resultado.nombre}» creado correctamente.",
                                parent=dialogo)
            dialogo.destroy()
            self._recargar()

        _boton(dialogo, "💾 Guardar", guardar,
               color_bg=T.GREEN, color_fg=T.ON_ACCENT).pack(pady=12, ipadx=10, ipady=5)

    # ------------------------------------------------------------------
    # DIÁLOGO — EDITAR PRODUCTO
    # ------------------------------------------------------------------

    def _dialogo_editar(self):
        producto = self._producto_seleccionado()
        if not producto:
            return

        dialogo = _Dialogo(self, titulo=f"Editar producto #{producto.id}",
                           ancho=420, alto=340)

        _label(dialogo.frame, "Nombre *").grid(row=0, column=0, sticky="w", pady=4)
        var_nombre = tk.StringVar(value=producto.nombre)
        _entry(dialogo.frame, var_nombre).grid(row=0, column=1, sticky="ew", pady=4)

        _label(dialogo.frame, "Categoría *").grid(row=1, column=0, sticky="w", pady=4)
        var_cat = tk.StringVar(value=producto.categoria)
        _entry(dialogo.frame, var_cat).grid(row=1, column=1, sticky="ew", pady=4)

        _label(dialogo.frame, "Precio *").grid(row=2, column=0, sticky="w", pady=4)
        var_precio = tk.StringVar(value=str(producto.precio))
        _entry(dialogo.frame, var_precio).grid(row=2, column=1, sticky="ew", pady=4)

        _label(dialogo.frame, "Stock mínimo").grid(row=3, column=0, sticky="w", pady=4)
        var_smin = tk.StringVar(value=str(producto.stock_minimo))
        _entry(dialogo.frame, var_smin).grid(row=3, column=1, sticky="ew", pady=4)

        dialogo.frame.columnconfigure(1, weight=1)

        def guardar():
            nombre = var_nombre.get().strip()
            categoria = var_cat.get().strip()
            precio_txt = var_precio.get().strip()
            smin_txt = var_smin.get().strip()

            errores = []
            if not nombre:
                errores.append("• El nombre es obligatorio.")
            if not categoria:
                errores.append("• La categoría es obligatoria.")
            precio = _parsear_float(precio_txt)
            if precio is None:
                errores.append("• El precio debe ser un número (ej: 1250.50).")
            elif precio < 0:
                errores.append("• El precio no puede ser negativo.")
            smin = _parsear_int(smin_txt)
            if smin is None:
                errores.append("• El stock mínimo debe ser un número entero.")
            elif smin < 0:
                errores.append("• El stock mínimo no puede ser negativo.")

            if errores:
                messagebox.showerror("Datos inválidos", "\n".join(errores),
                                     parent=dialogo)
                return

            try:
                resultado = actualizar_producto(
                    producto.id, nombre=nombre, categoria=categoria,
                    precio=precio, stock_minimo=smin
                )
            except ValueError as e:
                messagebox.showerror("Error de validación", str(e), parent=dialogo)
                return

            if resultado is None:
                messagebox.showerror("Error",
                                     "No se pudo actualizar el producto.",
                                     parent=dialogo)
                return

            messagebox.showinfo("Éxito", "Producto actualizado correctamente.",
                                parent=dialogo)
            dialogo.destroy()
            self._recargar()

        _boton(dialogo, "💾 Guardar cambios", guardar,
               color_bg=T.BLUE, color_fg=T.ON_ACCENT).pack(pady=12, ipadx=10, ipady=5)

    # ------------------------------------------------------------------
    # DIÁLOGO — AJUSTAR STOCK
    # ------------------------------------------------------------------

    def _dialogo_ajustar_stock(self):
        producto = self._producto_seleccionado()
        if not producto:
            return

        dialogo = _Dialogo(
            self,
            titulo=f"Ajustar stock — {producto.nombre}",
            ancho=380, alto=230
        )

        _label(dialogo.frame,
               f"Stock actual: {producto.stock} unidades",
               fg=T.GREEN, bold=True).grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 10))

        _label(dialogo.frame,
               "Cantidad a ingresar\n(negativo para corregir):").grid(
            row=1, column=0, sticky="w", pady=4)
        var_cant = tk.StringVar(value="0")
        _entry(dialogo.frame, var_cant, width=12).grid(
            row=1, column=1, sticky="w", pady=4, padx=8)

        _label(dialogo.frame,
               "Motivo (opcional):").grid(row=2, column=0, sticky="w", pady=4)
        var_motivo = tk.StringVar()
        _entry(dialogo.frame, var_motivo).grid(row=2, column=1, sticky="ew", pady=4)

        dialogo.frame.columnconfigure(1, weight=1)

        def confirmar():
            cant_txt = var_cant.get().strip()
            cantidad = _parsear_int(cant_txt)
            if cantidad is None:
                messagebox.showerror("Dato inválido",
                                     "Ingresá un número entero (puede ser negativo para reducir).",
                                     parent=dialogo)
                return
            if cantidad == 0:
                messagebox.showwarning("Sin cambio",
                                       "Ingresaste 0. No se realizó ningún cambio.",
                                       parent=dialogo)
                return

            nuevo_stock = producto.stock + cantidad
            if nuevo_stock < 0:
                messagebox.showerror(
                    "Stock insuficiente",
                    f"No podés reducir {abs(cantidad)} unidades.\n"
                    f"Stock actual: {producto.stock}.",
                    parent=dialogo
                )
                return

            confirmado = messagebox.askyesno(
                "Confirmar ajuste",
                f"Stock actual: {producto.stock}\n"
                f"Ajuste: {'+' if cantidad > 0 else ''}{cantidad}\n"
                f"Stock resultante: {nuevo_stock}\n\n¿Confirmar?",
                parent=dialogo
            )
            if not confirmado:
                return

            tipo_mov = "entrada" if cantidad > 0 else "ajuste"
            desc_mov = var_motivo.get().strip()
            try:
                # Un solo paso atómico: cambia el stock Y guarda el movimiento juntos.
                resultado = ajustar_stock(
                    producto.id, cantidad,
                    tipo=tipo_mov,
                    descripcion=desc_mov or "Ajuste manual desde administración",
                )
            except ValueError as e:
                messagebox.showerror("Error", str(e), parent=dialogo)
                return

            if resultado is None:
                messagebox.showerror("Error",
                                     "No se pudo actualizar el stock.",
                                     parent=dialogo)
                return

            messagebox.showinfo("Stock actualizado",
                                f"Nuevo stock de «{producto.nombre}»: {resultado.stock} unidades.",
                                parent=dialogo)
            dialogo.destroy()
            self._recargar()

        _boton(dialogo, "✔ Confirmar ajuste", confirmar,
               color_bg=T.BLUE, color_fg=T.ON_ACCENT).pack(pady=12, ipadx=10, ipady=5)

    # ------------------------------------------------------------------
    # ACTIVAR / DESACTIVAR
    # ------------------------------------------------------------------

    def _toggle_estado(self):
        producto = self._producto_seleccionado()
        if not producto:
            return

        nuevo_estado = not producto.activo
        accion = "activar" if nuevo_estado else "desactivar"

        if not messagebox.askyesno(
            "Confirmar",
            f"¿Deseás {accion} el producto «{producto.nombre}»?",
            parent=self
        ):
            return

        resultado = cambiar_estado_producto(producto.id, nuevo_estado)
        if resultado is None:
            messagebox.showerror("Error",
                                 "No se pudo cambiar el estado del producto.",
                                 parent=self)
            return

        estado_txt = "activado" if nuevo_estado else "desactivado"
        messagebox.showinfo("Éxito",
                            f"Producto «{producto.nombre}» {estado_txt}.",
                            parent=self)
        self._recargar()

    def _eliminar_producto(self):
        producto = self._producto_seleccionado()
        if not producto:
            return
        if not messagebox.askyesno(
            "Eliminar producto",
            f"¿Eliminar PERMANENTEMENTE «{producto.nombre}»?\n\nEsta acción no se puede deshacer.",
            parent=self
        ):
            return
        ok = eliminar_producto(producto.id)
        if ok:
            messagebox.showinfo("Eliminado",
                                f"Producto «{producto.nombre}» eliminado.", parent=self)
            self._recargar()
        else:
            messagebox.showerror("Error",
                                 "No se pudo eliminar el producto.", parent=self)


# ─────────────────────────────────────────────────────────────
# PANEL — USUARIOS
# ─────────────────────────────────────────────────────────────

class PanelUsuarios(tk.Frame):
    """
    Pestaña de gestión de usuarios.
    Acciones: Crear | Cambiar rol | Cambiar contraseña | Activar/Desactivar
    """

    def __init__(self, master):
        super().__init__(master, bg=T.BG)
        self.pack(fill="both", expand=True)
        self.usuarios = []
        self._construir_ui()
        self._recargar()

    # ------------------------------------------------------------------
    # INTERFAZ
    # ------------------------------------------------------------------

    def _construir_ui(self):
        # Barra superior
        frame_top = tk.Frame(self, bg=T.BG)
        frame_top.pack(fill="x", padx=10, pady=(8, 4))

        _boton(frame_top, "＋ Nuevo usuario", self._dialogo_crear_usuario,
               color_bg=T.GREEN, color_fg=T.ON_ACCENT).pack(
            side="left", ipadx=6, ipady=3)
        _boton(frame_top, "🔑 Cambiar rol", self._dialogo_cambiar_rol).pack(
            side="left", padx=6, ipadx=6, ipady=3)
        _boton(frame_top, "🔒 Cambiar contraseña",
               self._dialogo_cambiar_password,
               color_bg=T.BLUE, color_fg=T.ON_ACCENT).pack(
            side="left", ipadx=6, ipady=3)
        _boton(frame_top, "⊘ Act./Desact.", self._toggle_estado,
               color_bg=T.RED, color_fg=T.ON_ACCENT).pack(
            side="left", padx=6, ipadx=6, ipady=3)
        _boton(frame_top, "🗑 Eliminar", self._eliminar_usuario,
               color_bg=T.RED, color_fg=T.ON_ACCENT).pack(
            side="left", ipadx=6, ipady=3)
        _boton(frame_top, "↺ Actualizar", self._recargar).pack(
            side="right", ipadx=6, ipady=3)

        # Tabla
        cols = ("ID", "Usuario", "Rol", "Estado")
        self.tabla = ttk.Treeview(self, columns=cols, show="headings", height=16)
        _estilizar_tabla(self.tabla)
        for col, w in zip(cols, (50, 250, 150, 100)):
            self.tabla.heading(col, text=col)
            self.tabla.column(col, width=w, anchor="center")

        scroll = ttk.Scrollbar(self, orient="vertical", command=self.tabla.yview)
        self.tabla.configure(yscrollcommand=scroll.set)
        self.tabla.pack(side="left", fill="both", expand=True,
                        padx=(10, 0), pady=(0, 10))
        scroll.pack(side="left", fill="y", pady=(0, 10))

        self.tabla.tag_configure("inactivo", foreground=T.MUTED)
        self.tabla.tag_configure("admin", foreground=T.ACCENT)

        self.tabla.bind("<Double-1>", lambda _: self._dialogo_cambiar_rol())

    # ------------------------------------------------------------------
    # CARGA
    # ------------------------------------------------------------------

    def _recargar(self):
        self.usuarios = listar_usuarios()
        self._cargar_tabla()

    def _cargar_tabla(self):
        self.tabla.delete(*self.tabla.get_children())
        for u in self.usuarios:
            estado = "Activo" if u.activo else "Inactivo"
            tag = "admin" if u.rol == "administrador" else (
                "inactivo" if not u.activo else ""
            )
            self.tabla.insert(
                "", "end",
                values=(u.id, u.nombre_usuario, u.rol, estado),
                tags=(tag,)
            )

    # ------------------------------------------------------------------
    # OBTENER USUARIO SELECCIONADO
    # ------------------------------------------------------------------

    def _usuario_seleccionado(self):
        sel = self.tabla.focus()
        if not sel:
            messagebox.showwarning("Sin selección",
                                   "Seleccioná un usuario de la tabla.",
                                   parent=self)
            return None
        id_u = int(self.tabla.item(sel, "values")[0])
        return next((u for u in self.usuarios if u.id == id_u), None)

    # ------------------------------------------------------------------
    # DIÁLOGO — CREAR USUARIO
    # ------------------------------------------------------------------

    def _dialogo_crear_usuario(self):
        dialogo = _Dialogo(self, titulo="Nuevo Usuario", ancho=400, alto=340)

        _label(dialogo.frame, "Nombre de usuario *").grid(
            row=0, column=0, sticky="w", pady=4)
        var_nombre = tk.StringVar()
        _entry(dialogo.frame, var_nombre).grid(row=0, column=1, sticky="ew", pady=4)

        _label(dialogo.frame, "Contraseña *").grid(
            row=1, column=0, sticky="w", pady=4)
        var_pw = tk.StringVar()
        _entry(dialogo.frame, var_pw, show="●").grid(
            row=1, column=1, sticky="ew", pady=4)

        _label(dialogo.frame, "Repetir contraseña *").grid(
            row=2, column=0, sticky="w", pady=4)
        var_pw2 = tk.StringVar()
        _entry(dialogo.frame, var_pw2, show="●").grid(
            row=2, column=1, sticky="ew", pady=4)

        _label(dialogo.frame, "Rol *").grid(row=3, column=0, sticky="w", pady=4)
        var_rol = tk.StringVar(value=ROLES_VALIDOS[1])
        combo_rol = ttk.Combobox(
            dialogo.frame, textvariable=var_rol,
            values=list(ROLES_VALIDOS), state="readonly",
            font=("Courier New", 10), width=20
        )
        combo_rol.grid(row=3, column=1, sticky="w", pady=4)

        dialogo.frame.columnconfigure(1, weight=1)

        def guardar():
            nombre = var_nombre.get().strip()
            pw = var_pw.get()
            pw2 = var_pw2.get()
            rol = var_rol.get()

            errores = []
            if not nombre:
                errores.append("• El nombre de usuario es obligatorio.")
            elif len(nombre) < 3:
                errores.append("• El nombre debe tener al menos 3 caracteres.")
            if not pw:
                errores.append("• La contraseña es obligatoria.")
            elif len(pw) < 4:
                errores.append("• La contraseña debe tener al menos 4 caracteres.")
            elif pw != pw2:
                errores.append("• Las contraseñas no coinciden.")
            if rol not in ROLES_VALIDOS:
                errores.append("• Seleccioná un rol válido.")

            if errores:
                messagebox.showerror("Datos inválidos", "\n".join(errores),
                                     parent=dialogo)
                return

            resultado = crear_usuario(nombre, pw, rol)
            if resultado is None:
                messagebox.showerror(
                    "Error",
                    f"No se pudo crear el usuario.\n"
                    f"Es posible que el nombre «{nombre}» ya esté en uso.",
                    parent=dialogo
                )
                return

            messagebox.showinfo("Éxito",
                                f"Usuario «{resultado.nombre_usuario}» creado correctamente.",
                                parent=dialogo)
            dialogo.destroy()
            self._recargar()

        _boton(dialogo, "💾 Crear usuario", guardar,
               color_bg=T.GREEN, color_fg=T.ON_ACCENT).pack(pady=12, ipadx=10, ipady=5)

    # ------------------------------------------------------------------
    # DIÁLOGO — CAMBIAR ROL
    # ------------------------------------------------------------------

    def _dialogo_cambiar_rol(self):
        usuario = self._usuario_seleccionado()
        if not usuario:
            return

        dialogo = _Dialogo(
            self,
            titulo=f"Cambiar rol — {usuario.nombre_usuario}",
            ancho=360, alto=200
        )

        _label(dialogo.frame,
               f"Rol actual: {usuario.rol}", fg=T.MUTED).grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 10))

        _label(dialogo.frame, "Nuevo rol:").grid(row=1, column=0, sticky="w", pady=4)
        var_rol = tk.StringVar(value=usuario.rol)
        combo_rol = ttk.Combobox(
            dialogo.frame, textvariable=var_rol,
            values=list(ROLES_VALIDOS), state="readonly",
            font=("Courier New", 10), width=18
        )
        combo_rol.grid(row=1, column=1, sticky="w", pady=4, padx=8)
        dialogo.frame.columnconfigure(1, weight=1)

        def guardar():
            nuevo_rol = var_rol.get()
            if nuevo_rol == usuario.rol:
                messagebox.showinfo("Sin cambio",
                                    "El rol seleccionado es el mismo que el actual.",
                                    parent=dialogo)
                return

            if not messagebox.askyesno(
                "Confirmar",
                f"¿Cambiar el rol de «{usuario.nombre_usuario}» a {nuevo_rol}?",
                parent=dialogo
            ):
                return

            try:
                resultado = actualizar_usuario(usuario.id, nuevo_rol=nuevo_rol)
            except ValueError as e:
                messagebox.showerror("Error", str(e), parent=dialogo)
                return

            if resultado is None:
                messagebox.showerror("Error", "No se pudo actualizar el rol.",
                                     parent=dialogo)
                return

            messagebox.showinfo("Éxito", "Rol actualizado correctamente.",
                                parent=dialogo)
            dialogo.destroy()
            self._recargar()

        _boton(dialogo, "💾 Guardar", guardar,
               color_bg=T.BLUE, color_fg=T.ON_ACCENT).pack(pady=12, ipadx=10, ipady=5)

    # ------------------------------------------------------------------
    # DIÁLOGO — CAMBIAR CONTRASEÑA
    # ------------------------------------------------------------------

    def _dialogo_cambiar_password(self):
        usuario = self._usuario_seleccionado()
        if not usuario:
            return

        dialogo = _Dialogo(
            self,
            titulo=f"Cambiar contraseña — {usuario.nombre_usuario}",
            ancho=380, alto=240
        )

        _label(dialogo.frame, "Nueva contraseña *").grid(
            row=0, column=0, sticky="w", pady=4)
        var_pw = tk.StringVar()
        _entry(dialogo.frame, var_pw, show="●").grid(
            row=0, column=1, sticky="ew", pady=4)

        _label(dialogo.frame, "Repetir contraseña *").grid(
            row=1, column=0, sticky="w", pady=4)
        var_pw2 = tk.StringVar()
        _entry(dialogo.frame, var_pw2, show="●").grid(
            row=1, column=1, sticky="ew", pady=4)

        dialogo.frame.columnconfigure(1, weight=1)

        def guardar():
            pw = var_pw.get()
            pw2 = var_pw2.get()

            errores = []
            if not pw:
                errores.append("• La contraseña es obligatoria.")
            elif len(pw) < 4:
                errores.append("• La contraseña debe tener al menos 4 caracteres.")
            if pw != pw2:
                errores.append("• Las contraseñas no coinciden.")

            if errores:
                messagebox.showerror("Datos inválidos", "\n".join(errores),
                                     parent=dialogo)
                return

            if not messagebox.askyesno(
                "Confirmar",
                f"¿Cambiar la contraseña de «{usuario.nombre_usuario}»?",
                parent=dialogo
            ):
                return

            try:
                resultado = actualizar_usuario(usuario.id, nueva_password=pw)
            except ValueError as e:
                messagebox.showerror("Error", str(e), parent=dialogo)
                return

            if resultado is None:
                messagebox.showerror("Error", "No se pudo actualizar la contraseña.",
                                     parent=dialogo)
                return

            messagebox.showinfo("Éxito", "Contraseña actualizada correctamente.",
                                parent=dialogo)
            dialogo.destroy()
            self._recargar()

        _boton(dialogo, "💾 Guardar", guardar,
               color_bg=T.BLUE, color_fg=T.ON_ACCENT).pack(pady=12, ipadx=10, ipady=5)

    # ------------------------------------------------------------------
    # ACTIVAR / DESACTIVAR
    # ------------------------------------------------------------------

    def _toggle_estado(self):
        usuario = self._usuario_seleccionado()
        if not usuario:
            return

        nuevo_estado = not usuario.activo
        accion = "activar" if nuevo_estado else "desactivar"

        if not messagebox.askyesno(
            "Confirmar",
            f"¿Deseás {accion} al usuario «{usuario.nombre_usuario}»?",
            parent=self
        ):
            return

        resultado = cambiar_estado_usuario(usuario.id, nuevo_estado)
        if resultado is None:
            messagebox.showerror("Error",
                                 "No se pudo cambiar el estado del usuario.",
                                 parent=self)
            return

        estado_txt = "activado" if nuevo_estado else "desactivado"
        messagebox.showinfo("Éxito",
                            f"Usuario «{usuario.nombre_usuario}» {estado_txt}.",
                            parent=self)
        self._recargar()

    def _eliminar_usuario(self):
        usuario = self._usuario_seleccionado()
        if not usuario:
            return
        if not messagebox.askyesno(
            "Eliminar usuario",
            f"¿Eliminar PERMANENTEMENTE al usuario «{usuario.nombre_usuario}»?\n\nEsta acción no se puede deshacer.",
            parent=self
        ):
            return
        ok = eliminar_usuario(usuario.id)
        if ok:
            messagebox.showinfo("Eliminado",
                                f"Usuario «{usuario.nombre_usuario}» eliminado.", parent=self)
            self._recargar()
        else:
            messagebox.showerror("Error",
                                 "No se pudo eliminar el usuario.", parent=self)


# ─────────────────────────────────────────────────────────────
# HELPER — VENTANA MODAL GENÉRICA
# ─────────────────────────────────────────────────────────────

class _Dialogo(tk.Toplevel):
    """
    Ventana modal reutilizable para formularios.
    Expone self.frame (grid) donde cada panel coloca sus widgets.
    """

    def __init__(self, master, titulo, ancho=400, alto=300):
        super().__init__(master)
        self.title(titulo)
        self.geometry(f"{ancho}x{alto}")
        self.resizable(False, False)
        self.configure(bg=T.BG)
        self.grab_set()
        self.focus_force()

        self.frame = tk.Frame(self, bg=T.BG, padx=20, pady=14)
        self.frame.pack(fill="both", expand=True)

        self._centrar()

    def _centrar(self):
        self.update_idletasks()
        x = (self.winfo_screenwidth() - self.winfo_width()) // 2
        y = (self.winfo_screenheight() - self.winfo_height()) // 2
        self.geometry(f"+{x}+{y}")


# ─────────────────────────────────────────────────────────────
# HELPERS DE PARSEO SEGURO (cubren errores de tipeo)
# ─────────────────────────────────────────────────────────────

def _parsear_int(texto: str):
    """
    Convierte texto a int de forma segura.
    Acepta negativos. Retorna None si la conversión falla.
    """
    try:
        return int(texto.strip().replace(",", ""))
    except (ValueError, AttributeError):
        return None


def _parsear_float(texto: str):
    """
    Convierte texto a float de forma segura.
    Acepta coma o punto como separador decimal.
    Retorna None si la conversión falla.
    """
    try:
        return float(texto.strip().replace(",", "."))
    except (ValueError, AttributeError):
        return None
