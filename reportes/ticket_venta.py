"""
Generador de ticket/comprobante PDF para el cliente.
Usa ReportLab (ya instalado en el proyecto).
"""
import os
from datetime import datetime
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A6  # ticket tamaño A6 (media hoja)
from reportlab.lib import colors


def generar_ticket_pdf(venta_id, vendedor, items, subtotal, iva_pct,
                       iva_monto, total, medio_pago, interes_pct=0,
                       ruta_salida=None):
    """
    Genera un ticket PDF de comprobante para el cliente.

    Parámetros:
        venta_id    : int  — número de venta
        vendedor    : str  — nombre del vendedor
        items       : list[dict]  — cada dict: {nombre, cantidad, precio, subtotal}
        subtotal    : float
        iva_pct     : int   — porcentaje IVA (ej: 21)
        iva_monto   : float
        total       : float  — total final (ya con interés si aplica)
        medio_pago  : str   — "Efectivo", "Débito", "Crédito"
        interes_pct : float — porcentaje de interés aplicado (0 si no aplica)
        ruta_salida : str   — path del archivo; si None se genera automáticamente

    Retorna:
        str — ruta del PDF generado
    """
    if ruta_salida is None:
        os.makedirs("tickets", exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        ruta_salida = os.path.join("tickets", f"ticket_venta_{venta_id}_{ts}.pdf")

    ancho, alto = A6   # 148 x 105 mm → usamos en portrait (105 x 148 mm)
    # A6 portrait: 297.6 x 419.5 puntos aprox
    c = canvas.Canvas(ruta_salida, pagesize=A6)

    # ── Fondo oscuro ────────────────────────────────────────────────
    c.setFillColorRGB(0.118, 0.118, 0.18)
    c.rect(0, 0, ancho, alto, fill=True, stroke=False)

    y = alto - 18

    # ── Encabezado ──────────────────────────────────────────────────
    c.setFillColorRGB(0.796, 0.651, 0.969)   # lila
    c.setFont("Helvetica-Bold", 12)
    c.drawCentredString(ancho / 2, y, "COMPROBANTE DE VENTA")
    y -= 14

    c.setFillColorRGB(0.427, 0.443, 0.522)   # gris claro
    c.setFont("Helvetica", 8)
    fecha = datetime.now().strftime("%d/%m/%Y  %H:%M")
    c.drawCentredString(ancho / 2, y, fecha)
    y -= 10

    c.setFillColorRGB(0.796, 0.651, 0.969)
    c.line(10, y, ancho - 10, y)
    y -= 12

    # Nro venta + vendedor
    c.setFillColorRGB(0.8, 0.839, 0.957)    # blanco azulado
    c.setFont("Helvetica-Bold", 9)
    c.drawString(12, y, f"Venta Nro: #{venta_id}")
    c.drawRightString(ancho - 12, y, f"Vendedor: {vendedor}")
    y -= 14

    # ── Línea de encabezado de tabla ────────────────────────────────
    c.setFillColorRGB(0.796, 0.651, 0.969)
    c.line(10, y, ancho - 10, y)
    y -= 10

    c.setFillColorRGB(0.643, 0.745, 0.886)   # azul encabezado
    c.setFont("Helvetica-Bold", 8)
    c.drawString(12, y, "Producto")
    c.drawCentredString(ancho * 0.62, y, "Cant.")
    c.drawCentredString(ancho * 0.78, y, "P.Unit")
    c.drawRightString(ancho - 12, y, "Subtotal")
    y -= 8
    c.setFillColorRGB(0.427, 0.443, 0.522)
    c.line(10, y, ancho - 10, y)
    y -= 10

    # ── Ítems ────────────────────────────────────────────────────────
    c.setFillColorRGB(0.8, 0.839, 0.957)
    c.setFont("Helvetica", 8)

    for item in items:
        nombre = item["nombre"][:22]   # truncar si es muy largo
        c.drawString(12, y, nombre)
        c.drawCentredString(ancho * 0.62, y, str(item["cantidad"]))
        c.drawCentredString(ancho * 0.78, y, f"${item['precio']:,.0f}")
        c.drawRightString(ancho - 12, y, f"${item['precio'] * item['cantidad']:,.2f}")
        y -= 11

        if y < 80:   # página adicional si hace falta
            c.showPage()
            c.setFillColorRGB(0.118, 0.118, 0.18)
            c.rect(0, 0, ancho, alto, fill=True, stroke=False)
            y = alto - 20
            c.setFillColorRGB(0.8, 0.839, 0.957)
            c.setFont("Helvetica", 8)

    # ── Separador ───────────────────────────────────────────────────
    c.setFillColorRGB(0.427, 0.443, 0.522)
    c.line(10, y, ancho - 10, y)
    y -= 10

    # ── Totales ─────────────────────────────────────────────────────
    c.setFillColorRGB(0.8, 0.839, 0.957)
    c.setFont("Helvetica", 8)
    c.drawString(12, y, f"Subtotal:")
    c.drawRightString(ancho - 12, y, f"${subtotal:,.2f}")
    y -= 10

    c.drawString(12, y, f"IVA ({iva_pct}%):")
    c.drawRightString(ancho - 12, y, f"${iva_monto:,.2f}")
    y -= 10

    # Interés si aplica
    if interes_pct > 0:
        interes_monto = (subtotal + iva_monto) * (interes_pct / 100)
        c.setFillColorRGB(0.980, 0.694, 0.529)   # naranja
        c.drawString(12, y, f"Recargo tarjeta ({interes_pct:.0f}%):")
        c.drawRightString(ancho - 12, y, f"${interes_monto:,.2f}")
        y -= 10
        c.setFillColorRGB(0.8, 0.839, 0.957)

    # Línea total
    c.setFillColorRGB(0.796, 0.651, 0.969)
    c.line(10, y, ancho - 10, y)
    y -= 12

    c.setFillColorRGB(0.651, 0.890, 0.631)    # verde
    c.setFont("Helvetica-Bold", 11)
    c.drawString(12, y, "TOTAL:")
    c.drawRightString(ancho - 12, y, f"${total:,.2f}")
    y -= 14

    # Medio de pago
    c.setFillColorRGB(0.8, 0.839, 0.957)
    c.setFont("Helvetica", 8)
    icono = {"Efectivo": "💵", "Débito": "💳", "Crédito": "💳"}.get(medio_pago, "")
    c.drawCentredString(ancho / 2, y, f"Pago: {medio_pago}")
    y -= 14

    # ── Pie ─────────────────────────────────────────────────────────
    c.setFillColorRGB(0.796, 0.651, 0.969)
    c.line(10, y, ancho - 10, y)
    y -= 10

    c.setFillColorRGB(0.427, 0.443, 0.522)
    c.setFont("Helvetica", 7)
    c.drawCentredString(ancho / 2, y, "¡Gracias por su compra!")
    y -= 8
    c.drawCentredString(ancho / 2, y, "Autómatas y Lenguajes — UDA 2026")

    c.save()
    return ruta_salida
