import os
from datetime import datetime
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4

def generar_pdf_ventas(ventas, ruta_salida="reporte_ventas.pdf"):
    """
    Genera un PDF con el listado de ventas.
    'ventas' debe ser una lista de diccionarios con claves:
        'id', 'usuario', 'total'
    o una lista de objetos Venta con esos atributos.
    """
    os.makedirs(os.path.dirname(ruta_salida) if os.path.dirname(ruta_salida) else '.', exist_ok=True)

    ancho, alto = A4
    c = canvas.Canvas(ruta_salida, pagesize=A4)
    fecha_actual = datetime.now().strftime('%d/%m/%Y %H:%M')

    def nueva_pagina():
        """Dibuja el encabezado en cada página nueva."""
        c.setFillColorRGB(0.118, 0.118, 0.18)   # #1e1e2e
        c.rect(0, 0, ancho, alto, fill=True, stroke=False)

        c.setFillColorRGB(0.796, 0.651, 0.969)  # #cba6f7
        c.setFont("Helvetica-Bold", 18)
        c.drawString(50, alto - 50, "Reporte de Ventas")

        c.setFillColorRGB(0.427, 0.443, 0.522)  # #6c7086
        c.setFont("Helvetica", 10)
        c.drawString(50, alto - 70, f"Generado el: {fecha_actual}")

        # Línea separadora
        c.setStrokeColorRGB(0.796, 0.651, 0.969)
        c.line(50, alto - 82, ancho - 50, alto - 82)

        # Encabezados de tabla
        c.setFillColorRGB(0.8, 0.839, 0.957)    # #cdd6f4
        c.setFont("Helvetica-Bold", 11)
        c.drawString(55, alto - 100, "ID")
        c.drawString(110, alto - 100, "Usuario")
        c.drawString(260, alto - 100, "PDV")
        c.drawString(400, alto - 100, "Total ($)")
        c.line(50, alto - 108, ancho - 50, alto - 108)

        return alto - 125  # y inicial para los datos

    y = nueva_pagina()
    total_general = 0.0

    for venta in ventas:
        # Soporte para dict o para objeto SQLAlchemy
        if isinstance(venta, dict):
            venta_id    = venta.get('id', '-')
            usuario_str = str(venta.get('usuario', 'N/A'))
            total_venta = float(venta.get('total', 0))
            pdv_str     = str(venta.get('pdv') or '-')
        else:
            venta_id    = venta.id
            usuario_str = venta.usuario.nombre_usuario if venta.usuario else "N/A"
            total_venta = float(venta.total)
            pdv_str     = str(getattr(venta, 'pdv', None) or '-')

        total_general += total_venta

        c.setFillColorRGB(0.8, 0.839, 0.957)
        c.setFont("Helvetica", 10)
        c.drawString(55,  y, str(venta_id))
        c.drawString(110, y, usuario_str[:20])
        c.drawString(260, y, pdv_str[:20])
        c.drawString(400, y, f"${total_venta:.2f}")

        y -= 22

        if y < 80:
            c.showPage()
            y = nueva_pagina()

    # Línea y total final
    c.setStrokeColorRGB(0.796, 0.651, 0.969)
    c.line(50, y, ancho - 50, y)
    y -= 22

    c.setFillColorRGB(0.796, 0.651, 0.969)
    c.setFont("Helvetica-Bold", 12)
    c.drawString(55, y, f"TOTAL RECAUDADO: ${total_general:.2f}")

    c.save()
    return ruta_salida
