"""
interfaz/ventana_movimientos.py
================================
Historial de movimientos de stock.
Solo accesible para el administrador.
"""

import tkinter as tk
from tkinter import ttk

from backend.base_datos.repositorios import listar_movimientos, listar_productos
from interfaz.componentes import agregar_boton_volver
from interfaz import tema as T


FONT_TITLE = ("Courier New", 15, "bold")
FONT_LABEL = ("Courier New", 9)


class VentanaMovimientos(tk.Toplevel):
    """Muestra el historial de movimientos de stock con filtros."""

    def __init__(self, master):
        super().__init__(master)
        self.title("📦 Historial de Movimientos de Stock")
        self.geometry("860x520")
        self.minsize(700, 400)
        self.configure(bg=T.BG)
        self.grab_set()

        self.movimientos = listar_movimientos(limite=500)
        productos = listar_productos()
        self.productos_map = {p.id: p.nombre for p in productos}

        self._construir_ui()
        self._centrar()

    def _construir_ui(self):
        # Encabezado
        frame_header = tk.Frame(self, bg=T.PANEL, pady=10)
        frame_header.pack(fill="x")
        agregar_boton_volver(self, frame_header)
        tk.Label(frame_header, text="📦  Historial de Movimientos",
                 font=FONT_TITLE, bg=T.PANEL, fg=T.BLUE).pack()
        tk.Label(frame_header, text="Últimos 500 movimientos de stock registrados",
                 font=FONT_LABEL, bg=T.PANEL, fg=T.MUTED).pack(pady=(2, 0))

        # Filtros
        frame_filtros = tk.Frame(self, bg=T.BG)
        frame_filtros.pack(fill="x", padx=12, pady=8)

        tk.Label(frame_filtros, text="🔍 Buscar producto:", font=FONT_LABEL,
                 bg=T.BG, fg=T.FG).pack(side="left")
        self.var_buscar = tk.StringVar()
        self.var_buscar.trace_add("write", lambda *_: self._filtrar())
        tk.Entry(frame_filtros, textvariable=self.var_buscar,
                 font=("Courier New", 10), bg=T.CARD, fg=T.FG,
                 insertbackground=T.BLUE, relief="flat", bd=4, width=20
                 ).pack(side="left", padx=(4, 14), ipady=3)

        tk.Label(frame_filtros, text="Tipo:", font=FONT_LABEL,
                 bg=T.BG, fg=T.FG).pack(side="left")
        self.var_tipo = tk.StringVar(value="Todos")
        ttk.Combobox(
            frame_filtros, textvariable=self.var_tipo,
            values=["Todos", "entrada", "salida", "ajuste", "venta"],
            state="readonly", width=12, font=("Courier New", 9)
        ).pack(side="left", padx=4)
        self.var_tipo.trace_add("write", lambda *_: self._filtrar())

        tk.Button(frame_filtros, text="↺ Actualizar",
                  font=FONT_LABEL, bg=T.HOVER, fg=T.FG,
                  relief="flat", cursor="hand2",
                  command=self._recargar
                  ).pack(side="right", ipadx=6, ipady=3)

        # Tabla
        cols = ("Fecha", "Producto", "Tipo", "Cantidad", "Usuario", "Descripción")
        self.tabla = ttk.Treeview(self, columns=cols, show="headings", height=16)
        _estilizar_tabla(self.tabla)
        anchos = (140, 170, 80, 80, 100, 200)
        for col, w in zip(cols, anchos):
            self.tabla.heading(col, text=col)
            self.tabla.column(col, width=w, anchor="center")

        scroll = ttk.Scrollbar(self, orient="vertical", command=self.tabla.yview)
        self.tabla.configure(yscrollcommand=scroll.set)
        self.tabla.pack(side="left", fill="both", expand=True, padx=(12, 0), pady=(0, 12))
        scroll.pack(side="left", fill="y", pady=(0, 12))

        self._cargar_tabla(self.movimientos)

    def _cargar_tabla(self, movimientos):
        self.tabla.delete(*self.tabla.get_children())
        for m in movimientos:
            nombre_prod = (m.producto.nombre if m.producto
                          else self.productos_map.get(m.producto_id, f"ID {m.producto_id}"))
            nombre_usu  = m.usuario.nombre_usuario if m.usuario else "—"
            fecha_str   = m.fecha.strftime("%d/%m/%Y %H:%M") if m.fecha else "—"
            cantidad_str = f"+{m.cantidad}" if m.cantidad > 0 else str(m.cantidad)

            tag = {
                "entrada": "entrada",
                "venta":   "salida",
                "salida":  "salida",
                "ajuste":  "ajuste",
            }.get(m.tipo, "")

            self.tabla.insert("", "end",
                values=(fecha_str, nombre_prod, m.tipo, cantidad_str, nombre_usu, m.descripcion or ""),
                tags=(tag,))

        self.tabla.tag_configure("entrada", foreground=T.GREEN)
        self.tabla.tag_configure("salida",  foreground=T.RED)
        self.tabla.tag_configure("ajuste",  foreground=T.YELLOW)

    def _filtrar(self):
        texto = self.var_buscar.get().lower()
        tipo  = self.var_tipo.get()
        filtrados = []
        for m in self.movimientos:
            nombre_prod = (m.producto.nombre if m.producto
                          else self.productos_map.get(m.producto_id, ""))
            if texto and texto not in nombre_prod.lower():
                continue
            if tipo != "Todos" and m.tipo != tipo:
                continue
            filtrados.append(m)
        self._cargar_tabla(filtrados)

    def _recargar(self):
        self.movimientos = listar_movimientos(limite=500)
        self._filtrar()

    def _centrar(self):
        self.update_idletasks()
        x = (self.winfo_screenwidth() - self.winfo_width()) // 2
        y = (self.winfo_screenheight() - self.winfo_height()) // 2
        self.geometry(f"+{x}+{y}")


def _estilizar_tabla(tabla):
    estilo = ttk.Style()
    T.usar_tema_ttk(estilo)
    estilo.configure("Treeview",
                     background=T.CARD, fieldbackground=T.CARD,
                     foreground=T.FG, rowheight=24,
                     font=("Courier New", 9))
    estilo.configure("Treeview.Heading",
                     background=T.HOVER, foreground=T.BLUE,
                     font=("Courier New", 9, "bold"))
    estilo.map("Treeview", background=[("selected", T.SELECT)])
