"""
interfaz/ventana_metricas.py
============================
Métricas del piloto (criterios de aceptación §2.3 del informe), solo administrador:

  • Muestra los 3 indicadores con su meta y su estado.
  • Cronómetro para medir ventas hechas con el proceso manual (línea base de tiempos).
  • Registro de conteos físicos (inicio / fin / control) contra el stock del sistema.
  • Exporta el informe del piloto a Excel.

Los tiempos con el sistema y las alertas/quiebres se miden solos, mientras se vende.
"""

import time
import tkinter as tk
from tkinter import messagebox, filedialog

from backend.base_datos.repositorios import (
    resumen_metricas, datos_metricas, registrar_tiempo_manual,
    registrar_conteo_fisico, listar_productos,
)
from backend.red.errores import ErrorRed
from interfaz.componentes import agregar_boton_volver
from reportes.excel_metricas import exportar_excel_metricas
from interfaz import tema as T

FONT_TITLE = ("Courier New", 16, "bold")
FONT_LABEL = ("Courier New", 10)
FONT_BIG   = ("Courier New", 22, "bold")
FONT_BTN   = ("Courier New", 10, "bold")

def _estados():
    """Texto y color de cada estado (se arma al usarlo para respetar el tema activo)."""
    return {
        "cumple":    ("✔ CUMPLE",    T.GREEN),
        "no_cumple": ("✘ NO CUMPLE", T.RED),
        "pendiente": ("… PENDIENTE", T.YELLOW),
    }


def _boton(parent, texto, comando, bg=None, fg=None):
    bg = bg or T.ACCENT
    fg = fg or T.ON_ACCENT
    return tk.Button(parent, text=texto, command=comando, font=FONT_BTN, bg=bg, fg=fg,
                     activebackground=T.FG, relief="flat", cursor="hand2", padx=12, pady=6)


def _centrar(ventana):
    ventana.update_idletasks()
    x = (ventana.winfo_screenwidth() - ventana.winfo_width()) // 2
    y = (ventana.winfo_screenheight() - ventana.winfo_height()) // 3
    ventana.geometry(f"+{x}+{y}")


# ======================================================================
# VENTANA PRINCIPAL DE MÉTRICAS
# ======================================================================

class VentanaMetricas(tk.Toplevel):
    def __init__(self, parent, usuario):
        super().__init__(parent)
        self.usuario = usuario
        self.title("📈 Métricas del piloto")
        self.geometry("820x640")
        self.minsize(720, 560)
        self.configure(bg=T.BG)

        cab = tk.Frame(self, bg=T.PANEL, pady=12)
        cab.pack(fill="x")
        tk.Label(cab, text="📈 Métricas del piloto", font=FONT_TITLE,
                 bg=T.PANEL, fg=T.ACCENT).pack()
        tk.Label(cab, text="Criterios de aceptación §2.3 — el piloto es exitoso si se cumplen los tres",
                 font=("Courier New", 9), bg=T.PANEL, fg=T.MUTED).pack()
        agregar_boton_volver(self, cab)

        self.lbl_global = tk.Label(self, text="", font=("Courier New", 12, "bold"),
                                   bg=T.BG, fg=T.FG, pady=8)
        self.lbl_global.pack()

        self.tarjetas = {}
        for clave, titulo in (("desfase", "1 · Desfase de stock (conteo físico vs sistema)"),
                              ("tiempo", "2 · Tiempo de registro de una venta"),
                              ("alertas", "3 · Alertas de stock bajo a tiempo")):
            self.tarjetas[clave] = self._crear_tarjeta(titulo)

        fila = tk.Frame(self, bg=T.BG)
        fila.pack(pady=10)
        _boton(fila, "⏱ Cronometrar venta manual", self._abrir_cronometro, T.BLUE).pack(side="left", padx=5)
        _boton(fila, "📋 Registrar conteo físico", self._abrir_conteo, T.GREEN).pack(side="left", padx=5)
        _boton(fila, "📊 Exportar a Excel", self._exportar).pack(side="left", padx=5)
        _boton(fila, "🔄", self._refrescar, T.CARD, T.FG).pack(side="left", padx=5)

        self.lbl_estado = tk.Label(self, text="", font=("Courier New", 9), bg=T.BG, fg=T.MUTED)
        self.lbl_estado.pack(pady=(0, 6))

        _centrar(self)
        self._refrescar()

    def _crear_tarjeta(self, titulo):
        marco = tk.Frame(self, bg=T.CARD, padx=14, pady=8)
        marco.pack(fill="x", padx=20, pady=5)
        tk.Label(marco, text=titulo, font=("Courier New", 10, "bold"),
                 bg=T.CARD, fg=T.FG).pack(anchor="w")
        fila = tk.Frame(marco, bg=T.CARD)
        fila.pack(fill="x")
        valor = tk.Label(fila, text="—", font=FONT_BIG, bg=T.CARD, fg=T.FG)
        valor.pack(side="left")
        estado = tk.Label(fila, text="", font=FONT_BTN, bg=T.CARD)
        estado.pack(side="right")
        detalle = tk.Label(marco, text="", font=("Courier New", 9), bg=T.CARD,
                           fg=T.MUTED, justify="left", wraplength=740, anchor="w")
        detalle.pack(fill="x")
        return {"valor": valor, "estado": estado, "detalle": detalle}

    def _refrescar(self):
        try:
            r = resumen_metricas()
        except ErrorRed as e:
            self.lbl_estado.config(text=str(e), fg=T.RED)
            return
        except Exception as e:
            self.lbl_estado.config(text=f"No se pudieron calcular las métricas: {e}", fg=T.RED)
            return

        valores = {
            "desfase": r["desfase"]["reduccion_pct"],
            "tiempo": r["tiempo"]["reduccion_pct"],
            "alertas": r["alertas"]["cumplimiento_pct"],
        }
        sufijos = {"desfase": "% menos desfase", "tiempo": "% menos tiempo", "alertas": "% con alerta previa"}
        for clave, tarjeta in self.tarjetas.items():
            ind = r[clave]
            v = valores[clave]
            tarjeta["valor"].config(text="—" if v is None else f"{v:.1f} {sufijos[clave]}")
            texto, color = _estados()[ind["estado"]]
            tarjeta["estado"].config(text=texto, fg=color)
            tarjeta["detalle"].config(text=f"Meta: {ind['meta_pct']} %  ·  {ind['detalle']}")

        if r["exito_piloto"]:
            self.lbl_global.config(text="🏆 Los tres indicadores se cumplen: piloto exitoso", fg=T.GREEN)
        elif r["pendientes"]:
            self.lbl_global.config(text="Piloto en curso: faltan datos de algún indicador", fg=T.YELLOW)
        else:
            self.lbl_global.config(text="Algún indicador no alcanzó la meta: documentar causa raíz", fg=T.RED)
        self.lbl_estado.config(text="Tiempos con el sistema y alertas se miden solos al vender.", fg=T.MUTED)

    def _abrir_cronometro(self):
        DialogoCronometro(self, self.usuario, al_guardar=self._refrescar)

    def _abrir_conteo(self):
        DialogoConteo(self, self.usuario, al_guardar=self._refrescar)

    def _exportar(self):
        try:
            datos = datos_metricas()
        except ErrorRed as e:
            messagebox.showerror("Sin conexión", str(e), parent=self)
            return
        ruta = filedialog.asksaveasfilename(
            parent=self, defaultextension=".xlsx", filetypes=[("Excel", "*.xlsx")],
            initialfile="metricas_piloto.xlsx", title="Guardar métricas del piloto")
        if not ruta:
            return
        try:
            exportar_excel_metricas(datos, ruta)
            messagebox.showinfo("✅ Éxito", f"Informe de métricas generado:\n{ruta}", parent=self)
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo generar el Excel:\n{e}", parent=self)


# ======================================================================
# CRONÓMETRO DE VENTA MANUAL
# ======================================================================

class DialogoCronometro(tk.Toplevel):
    """Mide cuánto tarda una venta con el proceso manual (antes del sistema)."""

    def __init__(self, parent, usuario, al_guardar=None):
        super().__init__(parent)
        self.usuario = usuario
        self.al_guardar = al_guardar
        self.title("⏱ Cronómetro de venta manual")
        self.configure(bg=T.BG)
        self.resizable(False, False)
        self._t0 = None
        self._job = None
        self._transcurrido = 0.0

        tk.Label(self, text="Cronometrá UNA venta hecha como se hace hoy (sin el sistema).\n"
                            "Se necesitan 10 para la línea base.",
                 font=FONT_LABEL, bg=T.BG, fg=T.FG, pady=10, padx=20).pack()
        self.lbl_tiempo = tk.Label(self, text="00:00.0", font=("Courier New", 34, "bold"),
                                   bg=T.BG, fg=T.GREEN)
        self.lbl_tiempo.pack(pady=6)

        tk.Label(self, text="Nota (opcional, ej: cajero y tipo de venta):", font=("Courier New", 9),
                 bg=T.BG, fg=T.MUTED).pack()
        self.entry_nota = tk.Entry(self, font=FONT_LABEL, bg=T.CARD, fg=T.FG,
                                   insertbackground=T.FG, relief="flat", width=36)
        self.entry_nota.pack(pady=4, ipady=3)

        fila = tk.Frame(self, bg=T.BG)
        fila.pack(pady=10)
        self.btn_inicio = _boton(fila, "▶ Iniciar", self._iniciar, T.GREEN)
        self.btn_inicio.pack(side="left", padx=4)
        self.btn_stop = _boton(fila, "■ Detener y guardar", self._detener, T.BLUE)
        self.btn_stop.pack(side="left", padx=4)
        self.btn_stop.config(state="disabled")
        _boton(fila, "Cerrar", self._cerrar, T.CARD, T.FG).pack(side="left", padx=4)

        self.lbl_info = tk.Label(self, text="", font=("Courier New", 9), bg=T.BG, fg=T.MUTED, pady=6)
        self.lbl_info.pack()
        self.protocol("WM_DELETE_WINDOW", self._cerrar)
        self.transient(parent)
        _centrar(self)

    def _iniciar(self):
        self._t0 = time.perf_counter()
        self.btn_inicio.config(state="disabled")
        self.btn_stop.config(state="normal")
        self._tick()

    def _tick(self):
        if self._t0 is None:
            return
        self._transcurrido = time.perf_counter() - self._t0
        m, s = divmod(self._transcurrido, 60)
        self.lbl_tiempo.config(text=f"{int(m):02d}:{s:04.1f}")
        self._job = self.after(100, self._tick)

    def _detener(self):
        if self._t0 is None:
            return
        segundos = time.perf_counter() - self._t0
        self._t0 = None
        if self._job:
            self.after_cancel(self._job)
            self._job = None
        try:
            registrar_tiempo_manual(segundos, nota=self.entry_nota.get().strip(),
                                    usuario_id=self.usuario.id)
        except (ValueError, ErrorRed) as e:
            messagebox.showerror("No se guardó", str(e), parent=self)
            self.btn_inicio.config(state="normal")
            self.btn_stop.config(state="disabled")
            return
        self.lbl_info.config(text=f"✔ Guardado: {segundos:.1f} s. Podés cronometrar otra venta.", fg=T.GREEN)
        self.btn_inicio.config(state="normal")
        self.btn_stop.config(state="disabled")
        self.entry_nota.delete(0, "end")
        if self.al_guardar:
            self.al_guardar()

    def _cerrar(self):
        self._t0 = None
        if self._job:
            self.after_cancel(self._job)
        self.destroy()


# ======================================================================
# CONTEO FÍSICO
# ======================================================================

class DialogoConteo(tk.Toplevel):
    """
    Carga un conteo físico. A propósito NO muestra el stock del sistema: se cuenta primero y
    se compara después (evita que el conteo se contagie con el número de la pantalla).
    """

    def __init__(self, parent, usuario, al_guardar=None):
        super().__init__(parent)
        self.usuario = usuario
        self.al_guardar = al_guardar
        self.title("📋 Conteo físico de stock")
        self.geometry("560x600")
        self.configure(bg=T.BG)

        tk.Label(self, text="Contá cada producto físicamente y anotá la cantidad.\n"
                            "Dejá en blanco lo que no hayas contado.",
                 font=FONT_LABEL, bg=T.BG, fg=T.FG, pady=8).pack()

        fila = tk.Frame(self, bg=T.BG)
        fila.pack()
        tk.Label(fila, text="Momento:", font=FONT_LABEL, bg=T.BG, fg=T.FG).pack(side="left", padx=(0, 8))
        self.var_momento = tk.StringVar(value="inicio")
        for valor, texto in (("inicio", "Inicio del piloto"), ("fin", "Fin del piloto"), ("control", "Control")):
            tk.Radiobutton(fila, text=texto, value=valor, variable=self.var_momento, font=("Courier New", 9),
                           bg=T.BG, fg=T.FG, selectcolor=T.CARD, activebackground=T.BG,
                           activeforeground=T.FG).pack(side="left", padx=4)

        # Lista con scroll
        contenedor = tk.Frame(self, bg=T.BG)
        contenedor.pack(fill="both", expand=True, padx=14, pady=8)
        canvas = tk.Canvas(contenedor, bg=T.CARD, highlightthickness=0)
        scroll = tk.Scrollbar(contenedor, orient="vertical", command=canvas.yview)
        interior = tk.Frame(canvas, bg=T.CARD)
        interior.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=interior, anchor="nw")
        canvas.configure(yscrollcommand=scroll.set)
        canvas.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

        self.entradas = []          # [(producto, Entry)]
        try:
            productos = listar_productos(solo_activos=True)
        except ErrorRed as e:
            messagebox.showerror("Sin conexión", str(e), parent=self)
            self.destroy()
            return
        for i, p in enumerate(productos):
            tk.Label(interior, text=f"{p.nombre}", font=FONT_LABEL, bg=T.CARD, fg=T.FG,
                     anchor="w", width=34).grid(row=i, column=0, padx=8, pady=3, sticky="w")
            e = tk.Entry(interior, font=FONT_LABEL, width=8, bg=T.BG, fg=T.FG,
                         insertbackground=T.FG, relief="flat", justify="center")
            e.grid(row=i, column=1, padx=8, pady=3, ipady=2)
            self.entradas.append((p, e))
        if not productos:
            tk.Label(interior, text="No hay productos activos.", font=FONT_LABEL,
                     bg=T.CARD, fg=T.MUTED, pady=20).pack()

        self.var_ajustar = tk.BooleanVar(value=False)
        tk.Checkbutton(self, text="Además, dejar el stock del sistema igual a lo contado",
                       variable=self.var_ajustar, font=("Courier New", 9), bg=T.BG, fg=T.FG,
                       selectcolor=T.CARD, activebackground=T.BG, activeforeground=T.FG).pack()

        fila = tk.Frame(self, bg=T.BG)
        fila.pack(pady=10)
        _boton(fila, "💾 Guardar conteo", self._guardar, T.GREEN).pack(side="left", padx=5)
        _boton(fila, "Cancelar", self.destroy, T.CARD, T.FG).pack(side="left", padx=5)
        self.transient(parent)
        _centrar(self)

    def _guardar(self):
        conteos = []
        for p, e in self.entradas:
            txt = e.get().strip()
            if not txt:
                continue
            try:
                n = int(txt)
                if n < 0:
                    raise ValueError
            except ValueError:
                messagebox.showerror("Dato inválido",
                                     f"«{p.nombre}»: ingresá un número entero mayor o igual a 0.", parent=self)
                return
            conteos.append({"producto_id": p.id, "stock_fisico": n})
        if not conteos:
            messagebox.showwarning("Sin datos", "No cargaste ningún producto.", parent=self)
            return

        momento = self.var_momento.get()
        ajustar = self.var_ajustar.get()
        extra = "\nEl stock del sistema SE VA A MODIFICAR para igualar lo contado." if ajustar else ""
        if not messagebox.askyesno(
                "Confirmar conteo",
                f"Se guardará el conteo «{momento}» de {len(conteos)} producto(s).{extra}\n\n¿Continuar?",
                parent=self):
            return
        try:
            r = registrar_conteo_fisico(momento, conteos, usuario_id=self.usuario.id, ajustar_stock=ajustar)
        except (ValueError, ErrorRed) as e:
            messagebox.showerror("No se guardó", str(e), parent=self)
            return
        messagebox.showinfo(
            "✅ Conteo guardado",
            f"{r['productos']} producto(s) contados.\n"
            f"Con diferencia contra el sistema: {r['con_diferencia']}\n"
            f"Desfase total: {r['desfase_total']} unidad(es).", parent=self)
        if self.al_guardar:
            self.al_guardar()
        self.destroy()
