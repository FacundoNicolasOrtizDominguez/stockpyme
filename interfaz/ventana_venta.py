import os
import time
import uuid
import tkinter as tk
from tkinter import ttk, messagebox

from interfaz.componentes import agregar_boton_volver
from backend.base_datos.repositorios import (
    listar_productos, registrar_venta_atomica, StockInsuficienteError,
)
from backend.config import IVA
from backend.red.errores import ErrorRed
from interfaz import tema as T

# Interés por tarjeta de crédito (10 %)
INTERES_CREDITO = 10   # porcentaje


# ==============================
# VENTANA DE VENTA CON CARRITO
# ==============================

class VentanaVenta(tk.Toplevel):
    """
    Ventana para registrar una venta.
    Permite:
      - Buscar y agregar productos al carrito (solo muestra los que tienen stock > 0)
      - Ver subtotales, IVA y total en tiempo real
      - Quitar ítems del carrito
      - Elegir medio de pago (Efectivo / Débito / Crédito)
      - Crédito aplica un recargo configurable (INTERES_CREDITO %)
      - Cerrar la venta (descuenta stock y persiste en BD)
      - Generar ticket/comprobante PDF para el cliente
    """

    def __init__(self, master, usuario):
        super().__init__(master)
        self.usuario = usuario
        self.title("Registrar Venta")
        self.geometry("860x600")
        self.minsize(700, 500)
        self.configure(bg=T.BG)
        self.resizable(True, True)

        # Estado interno
        self.carrito: list[dict] = []
        self.productos_bd: list = listar_productos()
        self.medio_pago = tk.StringVar(value="Efectivo")

        # Métrica del piloto: cronómetro desde el primer producto agregado hasta «Finalizar»
        # y un id único por intento de venta (evita duplicados si la red falla a mitad).
        self._t0 = None
        self._duracion = None
        self._intento = None
        self._construir_ui()
        self._centrar_ventana()
        self.grab_set()

        # Salir: la flecha "← Volver", la X de la ventana y la tecla Esc piden confirmación
        self.protocol("WM_DELETE_WINDOW", self._salir)

    # ------------------------------------------------------------------
    # INTERFAZ
    # ------------------------------------------------------------------

    def _construir_ui(self):
        # ── Encabezado ────────────────────────────────────────────────
        frame_header = tk.Frame(self, bg=T.PANEL, pady=10)
        frame_header.pack(fill="x")
        agregar_boton_volver(self, frame_header, comando=self._salir)
        tk.Label(
            frame_header, text="🛒  Nueva Venta",
            font=("Courier New", 16, "bold"),
            bg=T.PANEL, fg=T.GREEN
        ).pack()
        tk.Label(
            frame_header,
            text=f"Vendedor: {self.usuario.nombre_usuario}",
            font=("Courier New", 9), bg=T.PANEL, fg=T.MUTED
        ).pack()

        # ── Cuerpo: dos columnas ──────────────────────────────────────
        frame_cuerpo = tk.Frame(self, bg=T.BG)
        frame_cuerpo.pack(fill="both", expand=True, padx=12, pady=8)
        frame_cuerpo.columnconfigure(0, weight=1)
        frame_cuerpo.columnconfigure(1, weight=1)
        frame_cuerpo.rowconfigure(0, weight=1)

        self._construir_catalogo(frame_cuerpo)
        self._construir_carrito(frame_cuerpo)

        # ── Pie: totales + medio de pago + botones ───────────────────
        self._construir_pie()

    def _construir_catalogo(self, parent):
        frame = tk.LabelFrame(
            parent, text=" Catálogo de Productos ",
            font=("Courier New", 10, "bold"),
            bg=T.BG, fg=T.ACCENT, bd=1, relief="solid"
        )
        frame.grid(row=0, column=0, sticky="nsew", padx=(0, 6))

        # Buscador
        frame_buscar = tk.Frame(frame, bg=T.BG)
        frame_buscar.pack(fill="x", padx=8, pady=(8, 4))
        tk.Label(frame_buscar, text="🔍", bg=T.BG, fg=T.FG).pack(side="left")
        self.var_buscar = tk.StringVar()
        self.var_buscar.trace_add("write", lambda *_: self._filtrar_productos())
        tk.Entry(
            frame_buscar, textvariable=self.var_buscar,
            font=("Courier New", 10), bg=T.CARD, fg=T.FG,
            insertbackground=T.ACCENT, relief="flat", bd=4
        ).pack(side="left", fill="x", expand=True, ipady=3)

        # Tabla de productos
        cols = ("ID", "Nombre", "Categoría", "Precio", "Stock")
        self.tabla_productos = ttk.Treeview(
            frame, columns=cols, show="headings", height=12
        )
        self._estilizar_tabla(self.tabla_productos)
        for col, w in zip(cols, (40, 160, 100, 80, 60)):
            self.tabla_productos.heading(col, text=col)
            self.tabla_productos.column(col, width=w, anchor="center")
        self.tabla_productos.pack(fill="both", expand=True, padx=8, pady=4)

        # Cantidad + Agregar
        frame_agregar = tk.Frame(frame, bg=T.BG)
        frame_agregar.pack(fill="x", padx=8, pady=(4, 8))
        tk.Label(frame_agregar, text="Cantidad:", font=("Courier New", 10),
                 bg=T.BG, fg=T.FG).pack(side="left")
        self.spin_cantidad = tk.Spinbox(
            frame_agregar, from_=1, to=9999, width=5,
            font=("Courier New", 10), bg=T.CARD, fg=T.FG,
            buttonbackground=T.HOVER, relief="flat"
        )
        self.spin_cantidad.pack(side="left", padx=6)
        tk.Button(
            frame_agregar, text="Agregar al carrito →",
            font=("Courier New", 10, "bold"),
            bg=T.GREEN, fg=T.ON_ACCENT,
            activebackground=T.TEAL, relief="flat", cursor="hand2",
            command=self._agregar_al_carrito
        ).pack(side="left", ipady=3, ipadx=8)

        self._cargar_productos()

    def _construir_carrito(self, parent):
        frame = tk.LabelFrame(
            parent, text=" Carrito de Venta ",
            font=("Courier New", 10, "bold"),
            bg=T.BG, fg=T.GREEN, bd=1, relief="solid"
        )
        frame.grid(row=0, column=1, sticky="nsew", padx=(6, 0))

        cols = ("Producto", "Cant.", "Precio u.", "Subtotal")
        self.tabla_carrito = ttk.Treeview(
            frame, columns=cols, show="headings", height=14
        )
        self._estilizar_tabla(self.tabla_carrito)
        for col, w in zip(cols, (160, 50, 80, 90)):
            self.tabla_carrito.heading(col, text=col)
            self.tabla_carrito.column(col, width=w, anchor="center")
        self.tabla_carrito.pack(fill="both", expand=True, padx=8, pady=(8, 4))

        tk.Button(
            frame, text="✖ Quitar ítem seleccionado",
            font=("Courier New", 9),
            bg=T.RED, fg=T.ON_ACCENT,
            activebackground=T.MAROON, relief="flat", cursor="hand2",
            command=self._quitar_del_carrito
        ).pack(pady=(0, 8), ipadx=6, ipady=3)

    def _construir_pie(self):
        frame_pie = tk.Frame(self, bg=T.PANEL, pady=8)
        frame_pie.pack(fill="x", padx=12)

        # 3 columnas que se estiran con la ventana
        frame_pie.columnconfigure(0, weight=2)
        frame_pie.columnconfigure(1, weight=1)
        frame_pie.columnconfigure(2, weight=2)

        # ── Col 0: Totales ────────────────────────────────────────────
        frame_totales = tk.Frame(frame_pie, bg=T.PANEL)
        frame_totales.grid(row=0, column=0, sticky="w", padx=(0, 8))

        self.lbl_subtotal = tk.Label(
            frame_totales, text="Subtotal:   $0.00",
            font=("Courier New", 10), bg=T.PANEL, fg=T.FG
        )
        self.lbl_subtotal.pack(anchor="w")

        self.lbl_iva = tk.Label(
            frame_totales, text=f"IVA ({int(IVA*100)}%):  $0.00",
            font=("Courier New", 10), bg=T.PANEL, fg=T.PEACH
        )
        self.lbl_iva.pack(anchor="w")

        self.lbl_interes = tk.Label(
            frame_totales, text="",
            font=("Courier New", 9), bg=T.PANEL, fg=T.PEACH
        )
        self.lbl_interes.pack(anchor="w")

        self.lbl_total = tk.Label(
            frame_totales, text="TOTAL:      $0.00",
            font=("Courier New", 13, "bold"), bg=T.PANEL, fg=T.GREEN
        )
        self.lbl_total.pack(anchor="w", pady=(3, 0))

        # ── Col 1: Medio de pago (centro, compacto horizontal) ────────
        frame_pago = tk.Frame(frame_pie, bg=T.PANEL)
        frame_pago.grid(row=0, column=1, sticky="nsew", padx=6)

        tk.Label(frame_pago, text="Medio de pago:",
                 font=("Courier New", 9, "bold"),
                 bg=T.PANEL, fg=T.ACCENT).pack(anchor="w")

        # Radiobuttons en fila horizontal para ahorrar espacio vertical
        frame_radios = tk.Frame(frame_pago, bg=T.PANEL)
        frame_radios.pack(anchor="w", fill="x")

        for medio, icono in [("Efectivo", "💵"), ("Débito", "💳"), ("Crédito", "💳+")]:
            tk.Radiobutton(
                frame_radios, text=f"{icono}\n{medio}",
                variable=self.medio_pago, value=medio,
                font=("Courier New", 8),
                bg=T.PANEL, fg=T.FG,
                selectcolor=T.CARD,
                activebackground=T.PANEL, activeforeground=T.ACCENT,
                cursor="hand2",
                indicatoron=False,           # estilo botón, no círculo
                relief="flat",
                bd=1,
                padx=6, pady=3,
                command=self._actualizar_totales
            ).pack(side="left", padx=2, pady=2)

        tk.Label(frame_pago, text=f"Crédito: +{INTERES_CREDITO}% recargo",
                 font=("Courier New", 7), bg=T.PANEL, fg=T.MUTED).pack(anchor="w")

        # ── Col 2: Botones (derecha) ──────────────────────────────────
        frame_botones = tk.Frame(frame_pie, bg=T.PANEL)
        frame_botones.grid(row=0, column=2, sticky="e")

        tk.Button(
            frame_botones, text="🗑 Limpiar",
            font=("Courier New", 9),
            bg=T.HOVER, fg=T.FG,
            activebackground=T.SELECT, relief="flat", cursor="hand2",
            command=self._limpiar_carrito
        ).pack(side="left", padx=(0, 6), ipadx=6, ipady=4)

        tk.Button(
            frame_botones, text="✔ Finalizar Venta",
            font=("Courier New", 11, "bold"),
            bg=T.ACCENT, fg=T.ON_ACCENT,
            activebackground=T.ACCENT_HOVER, relief="flat", cursor="hand2",
            command=self._cerrar_venta
        ).pack(side="left", ipadx=10, ipady=6)

    # ------------------------------------------------------------------
    # LÓGICA DEL CATÁLOGO
    # ------------------------------------------------------------------

    def _cargar_productos(self):
        """Carga productos activos con stock > 0 en la tabla del catálogo."""
        self.tabla_productos.delete(*self.tabla_productos.get_children())
        for p in self.productos_bd:
            if p.activo and p.stock > 0:
                tag = "bajo_stock" if p.alerta_stock_minimo() else ""
                self.tabla_productos.insert(
                    "", "end",
                    values=(p.id, p.nombre, p.categoria, f"${p.precio:.2f}", p.stock),
                    tags=(tag,)
                )
        self.tabla_productos.tag_configure("bajo_stock", foreground=T.RED)

    def _filtrar_productos(self):
        """Filtra el catálogo según el texto del buscador (solo stock > 0)."""
        texto = self.var_buscar.get().lower()
        self.tabla_productos.delete(*self.tabla_productos.get_children())
        for p in self.productos_bd:
            if p.activo and p.stock > 0 and (
                texto in p.nombre.lower() or texto in p.categoria.lower()
            ):
                tag = "bajo_stock" if p.alerta_stock_minimo() else ""
                self.tabla_productos.insert(
                    "", "end",
                    values=(p.id, p.nombre, p.categoria, f"${p.precio:.2f}", p.stock),
                    tags=(tag,)
                )
        self.tabla_productos.tag_configure("bajo_stock", foreground=T.RED)

    # ------------------------------------------------------------------
    # LÓGICA DEL CARRITO
    # ------------------------------------------------------------------

    def _agregar_al_carrito(self):
        seleccion = self.tabla_productos.focus()
        if not seleccion:
            messagebox.showwarning("Sin selección", "Seleccioná un producto del catálogo.", parent=self)
            return

        try:
            cantidad = int(self.spin_cantidad.get())
            if cantidad <= 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Cantidad inválida", "Ingresá una cantidad válida (número entero positivo).", parent=self)
            return

        valores = self.tabla_productos.item(seleccion, "values")
        id_prod = int(valores[0])

        producto = next((p for p in self.productos_bd if p.id == id_prod), None)
        if producto is None:
            return

        en_carrito = sum(i["cantidad"] for i in self.carrito if i["id"] == id_prod)
        if producto.stock < en_carrito + cantidad:
            messagebox.showerror(
                "Stock insuficiente",
                f"Stock disponible: {producto.stock - en_carrito} unidades.",
                parent=self
            )
            return

        existente = next((i for i in self.carrito if i["id"] == id_prod), None)
        if existente:
            existente["cantidad"] += cantidad
        else:
            self.carrito.append({
                "id": id_prod,
                "nombre": producto.nombre,
                "precio": producto.precio,
                "cantidad": cantidad,
            })

        if self._t0 is None:
            self._t0 = time.perf_counter()
        self._intento = None            # el carrito cambió: es otra venta
        self._actualizar_tabla_carrito()
        self._actualizar_totales()

    def _quitar_del_carrito(self):
        seleccion = self.tabla_carrito.focus()
        if not seleccion:
            messagebox.showwarning("Sin selección", "Seleccioná un ítem del carrito.", parent=self)
            return
        idx = self.tabla_carrito.index(seleccion)
        self.carrito.pop(idx)
        self._intento = None
        if not self.carrito:
            self._reiniciar_medicion()
        self._actualizar_tabla_carrito()
        self._actualizar_totales()

    def _salir(self):
        """Pregunta antes de salir; avisa si hay productos en el carrito."""
        if self.carrito:
            n = len(self.carrito)
            msg = (f"Hay {n} producto(s) en el carrito sin cobrar.\n"
                   "Si salís ahora se van a perder.\n\n¿Salir igual?")
        else:
            msg = "¿Querés salir de Registrar Venta?"
        if messagebox.askyesno("Salir", msg, parent=self):
            self.destroy()

    def _recargar_productos(self):
        """Vuelve a leer los productos de la base (stock real, también el de otras cajas)."""
        self.productos_bd = listar_productos()
        self._cargar_productos()

    def _limpiar_carrito(self):
        if self.carrito and messagebox.askyesno("Limpiar", "¿Vaciar el carrito?", parent=self):
            self.carrito.clear()
            self._reiniciar_medicion()
            self._actualizar_tabla_carrito()
            self._actualizar_totales()

    def _reiniciar_medicion(self):
        self._t0 = None
        self._duracion = None
        self._intento = None

    def _op_id_del_intento(self, medio, total):
        """Mismo id mientras el carrito, el medio y el total no cambien (reintentos seguros)."""
        firma = (medio, round(total, 2),
                 tuple((i["id"], i["cantidad"], i["precio"]) for i in self.carrito))
        if self._intento is None or self._intento[0] != firma:
            self._intento = (firma, uuid.uuid4().hex)
        return self._intento[1]

    def _actualizar_tabla_carrito(self):
        self.tabla_carrito.delete(*self.tabla_carrito.get_children())
        for item in self.carrito:
            subtotal = item["precio"] * item["cantidad"]
            self.tabla_carrito.insert(
                "", "end",
                values=(item["nombre"], item["cantidad"],
                        f"${item['precio']:.2f}", f"${subtotal:.2f}")
            )

    def _calcular_totales(self):
        """Devuelve (subtotal, iva_monto, interes_monto, total_final)."""
        subtotal = sum(i["precio"] * i["cantidad"] for i in self.carrito)
        iva_monto = subtotal * IVA
        base_con_iva = subtotal + iva_monto
        if self.medio_pago.get() == "Crédito":
            interes_monto = base_con_iva * (INTERES_CREDITO / 100)
        else:
            interes_monto = 0.0
        total = base_con_iva + interes_monto
        return subtotal, iva_monto, interes_monto, total

    def _actualizar_totales(self):
        subtotal, iva_monto, interes_monto, total = self._calcular_totales()
        self.lbl_subtotal.config(text=f"Subtotal:    ${subtotal:,.2f}")
        self.lbl_iva.config(text=f"IVA ({int(IVA*100)}%):   ${iva_monto:,.2f}")
        if interes_monto > 0:
            self.lbl_interes.config(
                text=f"Recargo cred. ({INTERES_CREDITO}%): ${interes_monto:,.2f}"
            )
        else:
            self.lbl_interes.config(text="")
        self.lbl_total.config(text=f"TOTAL:       ${total:,.2f}")

    # ------------------------------------------------------------------
    # CERRAR VENTA
    # ------------------------------------------------------------------

    def _cerrar_venta(self):
        if not self.carrito:
            messagebox.showwarning("Carrito vacío", "Agregá productos antes de finalizar la venta.", parent=self)
            return

        if self._duracion is None and self._t0 is not None:
            self._duracion = time.perf_counter() - self._t0

        subtotal, iva_monto, interes_monto, total = self._calcular_totales()
        medio = self.medio_pago.get()

        msg_interes = ""
        if medio == "Crédito":
            msg_interes = f"\n(Incluye recargo de {INTERES_CREDITO}% por tarjeta de crédito)"

        confirmacion = messagebox.askyesno(
            "Confirmar venta",
            f"Medio de pago: {medio}\n"
            f"Total a cobrar: ${total:,.2f}{msg_interes}\n\n"
            f"¿Confirmar la venta?",
            parent=self
        )
        if not confirmacion:
            self._duracion = None
            return

        try:
            # Venta + ítems + descuento de stock + movimientos en UNA transacción.
            # El stock se descuenta en la base (no con el valor cacheado en pantalla),
            # así dos cajas no se pisan y no se puede vender sin existencia.
            try:
                venta = registrar_venta_atomica(
                    usuario_id = self.usuario.id,
                    total      = total,
                    medio_pago = medio,
                    items      = self.carrito,
                    duracion_seg = self._duracion,
                    op_id      = self._op_id_del_intento(medio, total),
                )
            except StockInsuficienteError as e:
                messagebox.showerror(
                    "Stock insuficiente",
                    f"No hay stock suficiente de «{e.nombre}».\n"
                    f"Disponible ahora: {e.disponible}  |  En el carrito: {e.pedido}\n\n"
                    "Otra caja pudo haber vendido el producto. La venta NO se registró.\n"
                    "Ajustá las cantidades y volvé a intentar.",
                    parent=self
                )
                self._duracion = None
                self._intento = None
                self._recargar_productos()   # refrescar existencias reales
                return
            except ErrorRed as e:
                messagebox.showerror(
                    "Sin conexión con el servidor",
                    f"{e}\n\nLa venta pudo haberse registrado igual. Volvé a tocar «Finalizar Venta»: "
                    "si ya estaba registrada, NO se duplica.",
                    parent=self
                )
                return

            # Preguntar si desea generar ticket PDF
            generar = messagebox.askyesno(
                "Ticket de venta",
                "¿Deseas generar el comprobante PDF para el cliente?",
                parent=self
            )

            ruta_ticket = None
            if generar:
                ruta_ticket = self._generar_ticket(venta.id, subtotal, iva_monto, interes_monto, total, medio)

            msg_final = f"Venta #{venta.id} registrada exitosamente.\nTotal: ${total:,.2f}"
            if venta.ya_registrada:
                msg_final += "\n(La venta ya había quedado registrada: no se duplicó.)"
            if venta.alertas_stock:
                msg_final += "\n\n⚠ Stock bajo tras esta venta:\n" + "\n".join(
                    f"  • {a['nombre']}: quedan {a['stock']} (mínimo {a['stock_minimo']})"
                    for a in venta.alertas_stock
                )
            if ruta_ticket:
                msg_final += f"\n\nTicket guardado en:\n{os.path.abspath(ruta_ticket)}"

            messagebox.showinfo("Venta registrada ✔", msg_final, parent=self)

            # Abrir PDF automáticamente si se generó
            if ruta_ticket and os.path.exists(ruta_ticket):
                try:
                    os.startfile(os.path.abspath(ruta_ticket))
                except Exception:
                    pass  # Linux/Mac no tienen startfile

            self.carrito.clear()
            self._reiniciar_medicion()
            self._actualizar_tabla_carrito()
            self._actualizar_totales()
            self._recargar_productos()

        except Exception as e:
            messagebox.showerror("Error", f"No se pudo registrar la venta:\n{e}", parent=self)

    def _generar_ticket(self, venta_id, subtotal, iva_monto, interes_monto, total, medio):
        """Llama al generador de ticket PDF y retorna la ruta."""
        try:
            from reportes.ticket_venta import generar_ticket_pdf
            # Guardar siempre en <raíz del proyecto>/tickets/
            from backend.config import TICKETS_DIR
            carpeta_tickets = TICKETS_DIR
            os.makedirs(carpeta_tickets, exist_ok=True)
            from datetime import datetime
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            ruta = os.path.join(carpeta_tickets, f"ticket_venta_{venta_id}_{ts}.pdf")

            ruta = generar_ticket_pdf(
                venta_id   = venta_id,
                vendedor   = self.usuario.nombre_usuario,
                items      = self.carrito,
                subtotal   = subtotal,
                iva_pct    = int(IVA * 100),
                iva_monto  = iva_monto,
                total      = total,
                medio_pago = medio,
                interes_pct = INTERES_CREDITO if medio == "Crédito" else 0,
                ruta_salida = ruta,
            )
            return ruta
        except Exception as e:
            messagebox.showerror("Error al generar ticket", str(e), parent=self)
            return None

    # ------------------------------------------------------------------
    # HELPERS
    # ------------------------------------------------------------------

    @staticmethod
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
            background=T.HOVER, foreground=T.ACCENT,
            font=("Courier New", 9, "bold")
        )
        estilo.map("Treeview", background=[("selected", T.SELECT)])

    def _centrar_ventana(self):
        self.update_idletasks()
        x = (self.winfo_screenwidth() - self.winfo_width()) // 2
        y = (self.winfo_screenheight() - self.winfo_height()) // 2
        self.geometry(f"+{x}+{y}")
