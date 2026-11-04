import tkinter as tk
from tkinter import ttk, messagebox

from backend.base_datos.repositorios import listar_productos
from interfaz.componentes import agregar_boton_volver
from interfaz import tema as T


# ==============================
# VENTANA DE STOCK
# ==============================

class VentanaStock(tk.Toplevel):
    """
    Muestra el inventario.
    - Admin: ve todos los productos con todas las acciones.
    - Repositor: ve productos categorizados en "con stock" / "sin stock"
      y puede marcar los sin stock para avisar al admin.
    """

    def __init__(self, master, usuario=None):
        super().__init__(master)
        self.usuario = usuario
        es_repositor = usuario and usuario.rol == "repositor"

        self.title("Inventario — Stock Actual")
        self.geometry("820x540")
        self.minsize(660, 400)
        self.configure(bg=T.BG)

        self.productos = listar_productos(solo_activos=True)
        self.mostrar_sin_stock = tk.BooleanVar(value=True)  # repositor ve todo
        self.es_repositor = es_repositor

        self._construir_ui()
        self._centrar_ventana()
        self.grab_set()

    # ------------------------------------------------------------------

    def _construir_ui(self):
        frame_header = tk.Frame(self, bg=T.PANEL, pady=10)
        frame_header.pack(fill="x")
        agregar_boton_volver(self, frame_header)
        tk.Label(
            frame_header, text="📊  Stock Actual",
            font=("Courier New", 16, "bold"),
            bg=T.PANEL, fg=T.BLUE
        ).pack()
        self.lbl_contador = tk.Label(
            frame_header,
            text=f"{len(self.productos)} productos registrados",
            font=("Courier New", 9), bg=T.PANEL, fg=T.MUTED
        )
        self.lbl_contador.pack(pady=(2, 0))

        # Filtros
        frame_filtros = tk.Frame(self, bg=T.BG)
        frame_filtros.pack(fill="x", padx=12, pady=8)

        tk.Label(frame_filtros, text="🔍 Buscar:", font=("Courier New", 10),
                 bg=T.BG, fg=T.FG).pack(side="left")
        self.var_buscar = tk.StringVar()
        self.var_buscar.trace_add("write", lambda *_: self._filtrar())
        tk.Entry(
            frame_filtros, textvariable=self.var_buscar,
            font=("Courier New", 10), bg=T.CARD, fg=T.FG,
            insertbackground=T.BLUE, relief="flat", bd=4, width=20
        ).pack(side="left", padx=(4, 14), ipady=3)

        tk.Label(frame_filtros, text="Categoría:", font=("Courier New", 10),
                 bg=T.BG, fg=T.FG).pack(side="left")
        categorias = ["Todas"] + sorted(set(p.categoria for p in self.productos))
        self.var_categoria = tk.StringVar(value="Todas")
        self.var_categoria.trace_add("write", lambda *_: self._filtrar())
        ttk.Combobox(
            frame_filtros, textvariable=self.var_categoria,
            values=categorias, state="readonly", width=16,
            font=("Courier New", 10)
        ).pack(side="left", padx=4)

        if not self.es_repositor:
            chk = tk.Checkbutton(
                frame_filtros, text="Mostrar sin stock",
                variable=self.mostrar_sin_stock,
                command=self._filtrar,
                font=("Courier New", 9),
                bg=T.BG, fg=T.RED,
                selectcolor=T.CARD,
                activebackground=T.BG, activeforeground=T.RED,
                cursor="hand2"
            )
            chk.pack(side="left", padx=12)

        tk.Button(
            frame_filtros, text="↺ Actualizar",
            font=("Courier New", 9), bg=T.HOVER, fg=T.FG,
            relief="flat", cursor="hand2",
            command=self._recargar
        ).pack(side="right", ipadx=6, ipady=3)

        # Para repositor: pestañas con/sin stock
        if self.es_repositor:
            self._construir_vista_repositor()
        else:
            self._construir_tabla_completa()

    def _construir_tabla_completa(self):
        cols = ("ID", "Nombre", "Categoría", "Precio", "Stock", "Stock Mín.", "Estado")
        self.tabla = ttk.Treeview(self, columns=cols, show="headings", height=16)
        _estilizar_tabla(self.tabla)
        anchos = (40, 180, 110, 90, 70, 80, 80)
        for col, w in zip(cols, anchos):
            self.tabla.heading(col, text=col)
            self.tabla.column(col, width=w, anchor="center")

        scroll = ttk.Scrollbar(self, orient="vertical", command=self.tabla.yview)
        self.tabla.configure(yscrollcommand=scroll.set)
        self.tabla.pack(side="left", fill="both", expand=True, padx=(12, 0), pady=(0, 12))
        scroll.pack(side="left", fill="y", pady=(0, 12))
        self._cargar_tabla(self.productos)

    def _construir_vista_repositor(self):
        """Vista especial para el repositor: dos tablas separadas."""
        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True, padx=12, pady=(0, 12))

        # Tab 1: Con stock
        frame_con = tk.Frame(notebook, bg=T.BG)
        notebook.add(frame_con, text="✅ Con Stock")
        cols = ("ID", "Nombre", "Categoría", "Stock", "Stock Mín.")
        self.tabla_con_stock = ttk.Treeview(frame_con, columns=cols, show="headings", height=10)
        _estilizar_tabla(self.tabla_con_stock)
        for col, w in zip(cols, (40, 200, 130, 80, 90)):
            self.tabla_con_stock.heading(col, text=col)
            self.tabla_con_stock.column(col, width=w, anchor="center")
        self.tabla_con_stock.pack(fill="both", expand=True)

        # Tab 2: Sin stock / stock bajo
        frame_sin = tk.Frame(notebook, bg=T.BG)
        notebook.add(frame_sin, text="⚠️ Sin Stock / Crítico")
        tk.Label(frame_sin,
                 text="Estos productos necesitan reposición. Avisá al administrador.",
                 font=("Courier New", 9), bg=T.BG, fg=T.RED).pack(pady=4)

        cols2 = ("ID", "Nombre", "Categoría", "Stock Actual", "Faltante")
        self.tabla_sin_stock = ttk.Treeview(frame_sin, columns=cols2, show="headings", height=10)
        _estilizar_tabla(self.tabla_sin_stock)
        for col, w in zip(cols2, (40, 200, 130, 90, 80)):
            self.tabla_sin_stock.heading(col, text=col)
            self.tabla_sin_stock.column(col, width=w, anchor="center")
        self.tabla_sin_stock.pack(fill="both", expand=True, pady=(0, 6))

        tk.Button(
            frame_sin, text="📢 Notificar Admin (imprimir lista)",
            font=("Courier New", 9, "bold"),
            bg=T.RED, fg=T.ON_ACCENT,
            relief="flat", cursor="hand2",
            command=self._notificar_admin
        ).pack(pady=4, ipadx=10, ipady=4)

        self._cargar_tablas_repositor(self.productos)

    def _cargar_tabla(self, productos):
        self.tabla.delete(*self.tabla.get_children())
        mostrar_cero = self.mostrar_sin_stock.get()
        visibles = 0
        for p in productos:
            if not mostrar_cero and p.stock == 0:
                continue
            estado = "Activo" if p.activo else "Inactivo"
            tag = "" if p.activo and not p.alerta_stock_minimo() else ("bajo" if p.activo else "inactivo")
            self.tabla.insert(
                "", "end",
                values=(p.id, p.nombre, p.categoria, f"${p.precio:.2f}",
                        p.stock, p.stock_minimo, estado),
                tags=(tag,)
            )
            visibles += 1
        self.tabla.tag_configure("bajo",    foreground=T.RED)
        self.tabla.tag_configure("inactivo", foreground=T.MUTED)
        self.lbl_contador.config(text=f"{visibles} producto(s) mostrados")

    def _cargar_tablas_repositor(self, productos):
        self.tabla_con_stock.delete(*self.tabla_con_stock.get_children())
        self.tabla_sin_stock.delete(*self.tabla_sin_stock.get_children())
        con = sin = 0
        for p in productos:
            if not p.activo:
                continue
            if p.stock > p.stock_minimo:
                self.tabla_con_stock.insert("", "end",
                    values=(p.id, p.nombre, p.categoria, p.stock, p.stock_minimo))
                con += 1
            else:
                faltante = max(0, p.stock_minimo - p.stock)
                self.tabla_sin_stock.insert("", "end",
                    values=(p.id, p.nombre, p.categoria, p.stock, faltante),
                    tags=("alerta",))
                sin += 1
        self.tabla_sin_stock.tag_configure("alerta", foreground=T.RED)
        self.lbl_contador.config(text=f"{con} con stock — {sin} requieren reposición")

    def _filtrar(self):
        texto = self.var_buscar.get().lower()
        cat   = self.var_categoria.get()
        filtrados = [
            p for p in self.productos
            if (texto in p.nombre.lower() or texto in p.categoria.lower())
            and (cat == "Todas" or p.categoria == cat)
        ]
        if self.es_repositor:
            self._cargar_tablas_repositor(filtrados)
        else:
            self._cargar_tabla(filtrados)

    def _recargar(self):
        self.productos = listar_productos(solo_activos=True)
        self._filtrar()

    def _notificar_admin(self):
        """Genera un resumen de texto de los productos sin stock para copiar/imprimir."""
        faltantes = [p for p in self.productos if p.activo and p.stock <= p.stock_minimo]
        if not faltantes:
            messagebox.showinfo("Sin pendientes", "No hay productos que necesiten reposición.", parent=self)
            return

        ventana = tk.Toplevel(self)
        ventana.title("Lista para Reposición")
        ventana.geometry("500x400")
        ventana.configure(bg=T.BG)
        ventana.grab_set()

        tk.Label(ventana, text="📋 Lista de Reposición",
                 font=("Courier New", 14, "bold"),
                 bg=T.BG, fg=T.RED).pack(pady=10)
        tk.Label(ventana, text="Copiá este texto y enviáselo al administrador:",
                 font=("Courier New", 9), bg=T.BG, fg=T.MUTED).pack()

        texto = tk.Text(ventana, bg=T.CARD, fg=T.FG,
                        font=("Courier New", 10), relief="flat", bd=6)
        texto.pack(fill="both", expand=True, padx=12, pady=8)

        from datetime import datetime
        lineas = [f"LISTA DE REPOSICIÓN — {datetime.now().strftime('%d/%m/%Y %H:%M')}", ""]
        for p in faltantes:
            falt = max(0, p.stock_minimo - p.stock)
            lineas.append(f"• {p.nombre} ({p.categoria}) — Stock actual: {p.stock} — Faltan: {falt}")
        texto.insert("1.0", "\n".join(lineas))
        texto.config(state="disabled")

        tk.Button(ventana, text="Cerrar", font=("Courier New", 9),
                  bg=T.HOVER, fg=T.FG, relief="flat", cursor="hand2",
                  command=ventana.destroy).pack(pady=6, ipadx=14, ipady=4)

    def _centrar_ventana(self):
        self.update_idletasks()
        x = (self.winfo_screenwidth() - self.winfo_width()) // 2
        y = (self.winfo_screenheight() - self.winfo_height()) // 2
        self.geometry(f"+{x}+{y}")


# ==============================
# VENTANA DE ALERTAS DE STOCK
# ==============================

class VentanaAlertas(tk.Toplevel):
    def __init__(self, master):
        super().__init__(master)
        self.title("⚠️ Alertas de Stock Mínimo")
        self.geometry("640x400")
        self.configure(bg=T.BG)

        productos = listar_productos()
        self.alertas = [p for p in productos if p.alerta_stock_minimo() and p.activo]

        self._construir_ui()
        self._centrar_ventana()
        self.grab_set()

    def _construir_ui(self):
        frame_header = tk.Frame(self, bg=T.PANEL, pady=10)
        frame_header.pack(fill="x")
        agregar_boton_volver(self, frame_header)
        tk.Label(
            frame_header, text="⚠️  Productos con Stock Bajo",
            font=("Courier New", 15, "bold"),
            bg=T.PANEL, fg=T.RED
        ).pack()
        tk.Label(
            frame_header,
            text=f"{len(self.alertas)} producto(s) requieren reposición",
            font=("Courier New", 9), bg=T.PANEL, fg=T.MUTED
        ).pack(pady=(2, 0))

        if not self.alertas:
            tk.Label(
                self, text="✅ Todos los productos tienen stock suficiente.",
                font=("Courier New", 12), bg=T.BG, fg=T.GREEN
            ).pack(expand=True)
            return

        cols = ("ID", "Nombre", "Categoría", "Stock Actual", "Stock Mínimo", "Faltante")
        tabla = ttk.Treeview(self, columns=cols, show="headings", height=14)
        _estilizar_tabla(tabla)
        for col, w in zip(cols, (40, 180, 110, 90, 90, 80)):
            tabla.heading(col, text=col)
            tabla.column(col, width=w, anchor="center")

        for p in self.alertas:
            faltante = max(0, p.stock_minimo - p.stock)
            tabla.insert("", "end",
                values=(p.id, p.nombre, p.categoria, p.stock, p.stock_minimo, faltante),
                tags=("alerta",))
        tabla.tag_configure("alerta", foreground=T.RED)
        tabla.pack(fill="both", expand=True, padx=12, pady=12)

    def _centrar_ventana(self):
        self.update_idletasks()
        x = (self.winfo_screenwidth() - self.winfo_width()) // 2
        y = (self.winfo_screenheight() - self.winfo_height()) // 2
        self.geometry(f"+{x}+{y}")


# ==============================
# HELPER COMPARTIDO
# ==============================

def _estilizar_tabla(tabla):
    estilo = ttk.Style()
    T.usar_tema_ttk(estilo)
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
