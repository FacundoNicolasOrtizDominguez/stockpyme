"""
interfaz/ventana_reportes.py
============================
Módulo de reportes con filtro de fechas para PDF de ventas.
"""

import tkinter as tk
from tkinter import messagebox, filedialog
from datetime import datetime, date, timedelta

from backend.base_datos.repositorios import listar_productos, listar_ventas, listar_ventas_por_rango
from interfaz.componentes import agregar_boton_volver
from reportes.pdf_ventas import generar_pdf_ventas
from reportes.excel_ventas import exportar_excel_ventas
from reportes.excel_inventario import exportar_excel_inventario
from reportes.alertas import generar_reporte_alertas
from interfaz import tema as T

FONT_TITLE = ("Courier New", 16, "bold")
FONT_LABEL = ("Courier New", 10)
FONT_BTN   = ("Courier New", 10, "bold")


class VentanaReportes(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("📄 Módulo de Reportes")
        self.geometry("660x580")
        self.resizable(False, False)
        self.configure(bg=T.BG)
        self.grab_set()
        self._construir_ui()
        self._centrar()

    def _construir_ui(self):
        frame_header = tk.Frame(self, bg=T.PANEL, pady=14)
        frame_header.pack(fill="x")
        agregar_boton_volver(self, frame_header)
        tk.Label(frame_header, text="📄 Módulo de Reportes",
                 font=FONT_TITLE, bg=T.PANEL, fg=T.ACCENT).pack()
        tk.Label(frame_header, text="Generá reportes del sistema en PDF y Excel",
                 font=FONT_LABEL, bg=T.PANEL, fg=T.MUTED).pack(pady=(4, 0))

        # ── PDF de ventas con filtro de fechas ────────────────────────
        frame_pdf = tk.Frame(self, bg=T.CARD, pady=12, padx=16)
        frame_pdf.pack(fill="x", padx=24, pady=8)

        frame_top = tk.Frame(frame_pdf, bg=T.CARD)
        frame_top.pack(fill="x")
        tk.Label(frame_top, text="📊", font=("Courier New", 14),
                 bg=T.CARD, fg=T.ACCENT).pack(side="left")
        tk.Label(frame_top, text="  Reporte de Ventas (PDF)",
                 font=("Courier New", 11, "bold"), bg=T.CARD, fg=T.FG).pack(side="left")

        tk.Label(frame_pdf, text="Filtrá por rango de fechas antes de generar el PDF.",
                 font=FONT_LABEL, bg=T.CARD, fg=T.MUTED, wraplength=540, justify="left"
                 ).pack(anchor="w", pady=(4, 6))

        # Selector de rango rápido
        frame_rango = tk.Frame(frame_pdf, bg=T.CARD)
        frame_rango.pack(anchor="w", pady=(0, 6))
        tk.Label(frame_rango, text="Rango rápido:", font=FONT_LABEL,
                 bg=T.CARD, fg=T.MUTED).pack(side="left", padx=(0, 8))

        self.var_rango = tk.StringVar(value="todo")
        opciones = [("Todo", "todo"), ("Hoy", "hoy"), ("Esta semana", "semana"), ("Este mes", "mes")]
        for txt, val in opciones:
            tk.Radiobutton(
                frame_rango, text=txt, variable=self.var_rango, value=val,
                font=("Courier New", 9), bg=T.CARD, fg=T.FG,
                selectcolor=T.HOVER, activebackground=T.CARD, activeforeground=T.FG,
                command=self._actualizar_fechas_rapidas
            ).pack(side="left", padx=4)

        # Fechas manuales
        frame_fechas = tk.Frame(frame_pdf, bg=T.CARD)
        frame_fechas.pack(anchor="w", pady=(2, 8))

        tk.Label(frame_fechas, text="Desde (dd/mm/aaaa):", font=FONT_LABEL,
                 bg=T.CARD, fg=T.MUTED).pack(side="left")
        self.entry_desde = tk.Entry(frame_fechas, font=("Courier New", 10),
                                    bg=T.HOVER, fg=T.FG, insertbackground=T.ACCENT,
                                    relief="flat", bd=4, width=12)
        self.entry_desde.pack(side="left", padx=(4, 14), ipady=3)

        tk.Label(frame_fechas, text="Hasta:", font=FONT_LABEL,
                 bg=T.CARD, fg=T.MUTED).pack(side="left")
        self.entry_hasta = tk.Entry(frame_fechas, font=("Courier New", 10),
                                    bg=T.HOVER, fg=T.FG, insertbackground=T.ACCENT,
                                    relief="flat", bd=4, width=12)
        self.entry_hasta.pack(side="left", padx=(4, 0), ipady=3)

        frame_botones = tk.Frame(frame_pdf, bg=T.CARD)
        frame_botones.pack(anchor="e")
        tk.Button(frame_botones, text="Generar Excel",
                  font=FONT_BTN, bg=T.GREEN, fg=T.BG,
                  activebackground=T.FG, relief="flat", cursor="hand2",
                  pady=4, padx=14, command=self._exportar_excel_ventas
                  ).pack(side="left", padx=(0, 8))
        tk.Button(frame_botones, text="Generar PDF",
                  font=FONT_BTN, bg=T.ACCENT, fg=T.BG,
                  activebackground=T.FG, relief="flat", cursor="hand2",
                  pady=4, padx=14, command=self._generar_pdf_ventas
                  ).pack(side="left")

        # ── Excel inventario ──────────────────────────────────────────
        self._seccion(
            icono="📋", titulo="Inventario Actual (Excel)",
            descripcion="Exporta el stock de todos los productos a un archivo .xlsx con formato.",
            color_btn=T.GREEN, comando=self._exportar_excel,
        )

        # ── Alertas de stock ──────────────────────────────────────────
        self._seccion(
            icono="⚠️", titulo="Alertas de Stock Mínimo",
            descripcion="Muestra los productos con stock igual o menor al mínimo configurado.",
            color_btn=T.YELLOW, comando=self._ver_alertas,
        )

        tk.Button(self, text="Cerrar", font=FONT_BTN,
                  bg=T.CARD, fg=T.MUTED, activebackground=T.PANEL,
                  relief="flat", cursor="hand2", pady=6,
                  command=self.destroy).pack(pady=(8, 16), ipadx=20)

    def _seccion(self, icono, titulo, descripcion, color_btn, comando):
        frame = tk.Frame(self, bg=T.CARD, pady=12, padx=16)
        frame.pack(fill="x", padx=24, pady=8)
        frame_top = tk.Frame(frame, bg=T.CARD)
        frame_top.pack(fill="x")
        tk.Label(frame_top, text=icono, font=("Courier New", 14),
                 bg=T.CARD, fg=color_btn).pack(side="left")
        tk.Label(frame_top, text=f"  {titulo}", font=("Courier New", 11, "bold"),
                 bg=T.CARD, fg=T.FG).pack(side="left")
        tk.Label(frame, text=descripcion, font=FONT_LABEL,
                 bg=T.CARD, fg=T.MUTED, wraplength=540, justify="left"
                 ).pack(anchor="w", pady=(4, 8))
        tk.Button(frame, text="Generar", font=FONT_BTN,
                  bg=color_btn, fg=T.BG, activebackground=T.FG,
                  relief="flat", cursor="hand2", pady=4, padx=14,
                  command=comando).pack(anchor="e")

    def _actualizar_fechas_rapidas(self):
        hoy = date.today()
        rango = self.var_rango.get()
        self.entry_desde.delete(0, tk.END)
        self.entry_hasta.delete(0, tk.END)
        if rango == "hoy":
            self.entry_desde.insert(0, hoy.strftime("%d/%m/%Y"))
            self.entry_hasta.insert(0, hoy.strftime("%d/%m/%Y"))
        elif rango == "semana":
            inicio = hoy - timedelta(days=hoy.weekday())
            self.entry_desde.insert(0, inicio.strftime("%d/%m/%Y"))
            self.entry_hasta.insert(0, hoy.strftime("%d/%m/%Y"))
        elif rango == "mes":
            inicio = hoy.replace(day=1)
            self.entry_desde.insert(0, inicio.strftime("%d/%m/%Y"))
            self.entry_hasta.insert(0, hoy.strftime("%d/%m/%Y"))
        # "todo" → vacío = sin filtro

    def _parsear_fecha(self, texto):
        texto = texto.strip()
        if not texto:
            return None
        for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d"):
            try:
                return datetime.strptime(texto, fmt)
            except ValueError:
                continue
        raise ValueError(f"Fecha inválida: '{texto}'. Usá el formato dd/mm/aaaa.")

    def _generar_pdf_ventas(self):
        try:
            fecha_desde = self._parsear_fecha(self.entry_desde.get())
            fecha_hasta = self._parsear_fecha(self.entry_hasta.get())
        except ValueError as e:
            messagebox.showerror("Fecha inválida", str(e), parent=self)
            return

        try:
            ventas = listar_ventas_por_rango(fecha_desde, fecha_hasta)
            if not ventas:
                messagebox.showinfo("Sin datos",
                                    "No hay ventas en el rango seleccionado.", parent=self)
                return

            ruta = filedialog.asksaveasfilename(
                parent=self, defaultextension=".pdf",
                filetypes=[("PDF", "*.pdf")],
                initialfile="reporte_ventas.pdf",
                title="Guardar reporte de ventas",
            )
            if not ruta:
                return

            generar_pdf_ventas(ventas, ruta)
            messagebox.showinfo("✅ Éxito",
                                f"PDF con {len(ventas)} venta(s) generado:\n{ruta}", parent=self)
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo generar el PDF:\n{e}", parent=self)

    def _exportar_excel_ventas(self):
        try:
            fecha_desde = self._parsear_fecha(self.entry_desde.get())
            fecha_hasta = self._parsear_fecha(self.entry_hasta.get())
        except ValueError as e:
            messagebox.showerror("Fecha inválida", str(e), parent=self)
            return

        try:
            ventas = listar_ventas_por_rango(fecha_desde, fecha_hasta)
            if not ventas:
                messagebox.showinfo("Sin datos",
                                    "No hay ventas en el rango seleccionado.", parent=self)
                return

            ruta = filedialog.asksaveasfilename(
                parent=self, defaultextension=".xlsx",
                filetypes=[("Excel", "*.xlsx")],
                initialfile="reporte_ventas.xlsx",
                title="Guardar reporte de ventas en Excel",
            )
            if not ruta:
                return

            desde_txt = fecha_desde.strftime("%d/%m/%Y") if fecha_desde else "el inicio"
            hasta_txt = fecha_hasta.strftime("%d/%m/%Y") if fecha_hasta else "hoy"
            exportar_excel_ventas(ventas, ruta, f"Ventas desde {desde_txt} hasta {hasta_txt}")
            messagebox.showinfo("✅ Éxito",
                                f"Excel con {len(ventas)} venta(s) generado:\n{ruta}", parent=self)
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo generar el Excel de ventas:\n{e}", parent=self)

    def _exportar_excel(self):
        try:
            productos = listar_productos()
            if not productos:
                messagebox.showinfo("Sin datos", "No hay productos en el inventario.", parent=self)
                return
            ruta = filedialog.asksaveasfilename(
                parent=self, defaultextension=".xlsx",
                filetypes=[("Excel", "*.xlsx")],
                initialfile="inventario.xlsx",
                title="Guardar inventario en Excel",
            )
            if not ruta:
                return
            exportar_excel_inventario(productos, ruta)
            messagebox.showinfo("✅ Éxito", f"Excel generado:\n{ruta}", parent=self)
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo generar el Excel:\n{e}", parent=self)

    def _ver_alertas(self):
        try:
            productos   = listar_productos()
            inventario  = [{"nombre": p.nombre, "stock": p.stock, "stock_minimo": p.stock_minimo}
                           for p in productos]
            alertas     = generar_reporte_alertas(inventario)

            v = tk.Toplevel(self)
            v.title("⚠️ Alertas de Stock Mínimo")
            v.configure(bg=T.BG)
            v.geometry("520x400")
            v.grab_set()

            tk.Label(v, text="⚠️ Alertas de Stock Mínimo",
                     font=FONT_TITLE, bg=T.BG, fg=T.YELLOW).pack(pady=12)

            frame_lista = tk.Frame(v, bg=T.BG)
            frame_lista.pack(fill="both", expand=True, padx=16, pady=4)
            scrollbar = tk.Scrollbar(frame_lista)
            scrollbar.pack(side="right", fill="y")
            listbox = tk.Listbox(frame_lista, bg=T.CARD, fg=T.FG,
                                 font=FONT_LABEL, selectbackground=T.ACCENT,
                                 relief="flat", bd=0, yscrollcommand=scrollbar.set)
            scrollbar.config(command=listbox.yview)
            listbox.pack(fill="both", expand=True)

            if not alertas:
                listbox.insert(tk.END, "✅ Todos los productos tienen stock suficiente.")
            else:
                for a in alertas:
                    listbox.insert(tk.END, a["mensaje"])

            tk.Button(v, text="Cerrar", font=FONT_BTN,
                      bg=T.CARD, fg=T.MUTED, relief="flat", cursor="hand2",
                      pady=5, command=v.destroy).pack(pady=10, ipadx=16)
        except Exception as e:
            messagebox.showerror("Error", f"No se pudieron cargar las alertas:\n{e}", parent=self)

    def _centrar(self):
        self.update_idletasks()
        x = (self.winfo_screenwidth() - self.winfo_width()) // 2
        y = (self.winfo_screenheight() - self.winfo_height()) // 2
        self.geometry(f"+{x}+{y}")
