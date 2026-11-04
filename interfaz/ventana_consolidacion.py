"""
interfaz/ventana_consolidacion.py
=================================
Panel de consolidación para el administrador/encargado (historia E3):
ventas del día de TODOS los puntos de venta, últimas ventas y productos con
stock crítico, con actualización automática cada pocos segundos.
"""

import tkinter as tk
from tkinter import ttk
from datetime import date, datetime

from backend.config import PDV_NOMBRE
from interfaz.componentes import agregar_boton_volver
from backend.base_datos.repositorios import (
    resumen_por_pdv, ultimas_ventas, listar_productos,
)
from interfaz import tema as T

FONT_TITLE = ("Courier New", 16, "bold")
FONT_LABEL = ("Courier New", 10)
FONT_BTN   = ("Courier New", 10, "bold")

REFRESCO_MS = 10_000


class VentanaConsolidacion(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("🏪 Consolidación de puntos de venta")
        self.geometry("780x640")
        self.configure(bg=T.BG)
        self._job = None
        self._construir_ui()
        self._centrar()
        self._refrescar()

    # ------------------------------------------------------------------
    def _construir_ui(self):
        cab = tk.Frame(self, bg=T.PANEL, pady=12)
        cab.pack(fill="x")
        agregar_boton_volver(self, cab)
        tk.Label(cab, text="🏪 Consolidación de puntos de venta",
                 font=FONT_TITLE, bg=T.PANEL, fg=T.ACCENT).pack()
        self.lbl_estado = tk.Label(cab, text="", font=("Courier New", 9),
                                   bg=T.PANEL, fg=T.MUTED)
        self.lbl_estado.pack()

        self._estilo()

        # ── Resumen por PDV (hoy) ───────────────────────────────────
        self._titulo_seccion("Ventas de hoy por punto de venta")
        self.tabla_pdv = self._tabla(
            [("pdv", "Punto de venta", 280), ("ventas", "Ventas", 120), ("total", "Total", 160)],
            alto=5,
        )
        self.tabla_pdv.tag_configure("total", foreground=T.GREEN,
                                     font=("Courier New", 9, "bold"))

        # ── Últimas ventas ──────────────────────────────────────────
        self._titulo_seccion("Últimas ventas de hoy (todos los PDV)")
        self.tabla_ventas = self._tabla(
            [("id", "#", 50), ("hora", "Hora", 80), ("pdv", "PDV", 140),
             ("usuario", "Usuario", 140), ("medio", "Medio", 100), ("total", "Total", 110)],
            alto=8,
        )

        # ── Stock crítico ───────────────────────────────────────────
        self._titulo_seccion("Productos con stock crítico (stock compartido por todas las cajas)")
        self.tabla_stock = self._tabla(
            [("producto", "Producto", 340), ("stock", "Stock", 100), ("minimo", "Mínimo", 100)],
            alto=5,
        )

        # ── Botones ─────────────────────────────────────────────────
        fila = tk.Frame(self, bg=T.BG)
        fila.pack(pady=10)
        tk.Button(fila, text="🔄 Actualizar ahora", font=FONT_BTN, bg=T.ACCENT, fg=T.BG,
                  relief="flat", cursor="hand2", pady=5, padx=14,
                  command=self._refrescar).pack(side="left", padx=6)
        tk.Button(fila, text="Cerrar", font=FONT_BTN, bg=T.CARD, fg=T.MUTED,
                  relief="flat", cursor="hand2", pady=5, padx=14,
                  command=self.destroy).pack(side="left", padx=6)

    @staticmethod
    def _estilo():
        e = ttk.Style()
        T.usar_tema_ttk(e)
        e.configure("Treeview", background=T.CARD, fieldbackground=T.CARD,
                    foreground=T.FG, rowheight=22, font=("Courier New", 9))
        e.configure("Treeview.Heading", background=T.HOVER, foreground=T.ACCENT,
                    font=("Courier New", 9, "bold"))
        e.map("Treeview", background=[("selected", T.SELECT)])

    def _titulo_seccion(self, texto):
        tk.Label(self, text=texto, font=("Courier New", 10, "bold"),
                 bg=T.BG, fg=T.FG).pack(anchor="w", padx=20, pady=(10, 2))

    def _tabla(self, columnas, alto):
        marco = tk.Frame(self, bg=T.BG)
        marco.pack(fill="x", padx=20)
        tabla = ttk.Treeview(marco, columns=[c[0] for c in columnas],
                             show="headings", height=alto)
        for clave, titulo, ancho in columnas:
            tabla.heading(clave, text=titulo)
            tabla.column(clave, width=ancho, anchor="w")
        tabla.pack(fill="x")
        return tabla

    # ------------------------------------------------------------------
    def _refrescar(self):
        try:
            hoy = date.today()
            resumen = resumen_por_pdv(hoy, hoy)
            ventas = ultimas_ventas(30, hoy, hoy)
            productos = listar_productos(solo_activos=True)

            self._limpiar(self.tabla_pdv)
            total_ventas, total_monto = 0, 0.0
            for r in resumen:
                marca = " (este equipo)" if r["pdv"] == PDV_NOMBRE else ""
                self.tabla_pdv.insert("", "end", values=(
                    r["pdv"] + marca, r["cantidad_ventas"], f"${r['total']:,.2f}"))
                total_ventas += r["cantidad_ventas"]
                total_monto += r["total"]
            self.tabla_pdv.insert("", "end", tags=("total",), values=(
                "TOTAL", total_ventas, f"${total_monto:,.2f}"))

            self._limpiar(self.tabla_ventas)
            for v in ventas:
                self.tabla_ventas.insert("", "end", values=(
                    v["id"], v["fecha"][11:19], v["pdv"], v["usuario"],
                    v["medio_pago"], f"${v['total']:,.2f}"))

            self._limpiar(self.tabla_stock)
            criticos = [p for p in productos if p.stock <= (p.stock_minimo or 0)]
            for p in sorted(criticos, key=lambda p: p.stock):
                self.tabla_stock.insert("", "end", values=(p.nombre, p.stock, p.stock_minimo))
            if not criticos:
                self.tabla_stock.insert("", "end", values=("✅ Sin productos en stock crítico", "", ""))

            self.lbl_estado.config(
                text=f"Actualizado {datetime.now():%H:%M:%S} — se refresca solo cada "
                     f"{REFRESCO_MS // 1000} s — este equipo: {PDV_NOMBRE}",
                fg=T.MUTED)
        except Exception as e:
            self.lbl_estado.config(text=f"No se pudo actualizar: {e}", fg=T.RED)
        finally:
            if self.winfo_exists():
                if self._job is not None:
                    self.after_cancel(self._job)
                self._job = self.after(REFRESCO_MS, self._refrescar)

    @staticmethod
    def _limpiar(tabla):
        for item in tabla.get_children():
            tabla.delete(item)

    def destroy(self):
        if self._job is not None:
            try:
                self.after_cancel(self._job)
            except Exception:
                pass
            self._job = None
        super().destroy()

    def _centrar(self):
        self.update_idletasks()
        x = (self.winfo_screenwidth() - self.winfo_width()) // 2
        y = (self.winfo_screenheight() - self.winfo_height()) // 2
        self.geometry(f"+{x}+{y}")
