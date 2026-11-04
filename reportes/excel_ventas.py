"""
reportes/excel_ventas.py — Reporte de ventas en Excel (historia de usuario E5).

Genera un .xlsx con 3 hojas:
  • Resumen   — totales generales y por punto de venta y por medio de pago
  • Ventas    — una fila por venta (id, fecha, PDV, usuario, medio de pago, total)
  • Detalle   — una fila por ítem vendido (útil para revisar rentabilidad por producto)

`ventas` es la lista que devuelve listar_ventas_por_rango() (objetos Venta con
.usuario e .items cargados) o una lista de dicts con las mismas claves.
"""
import os
from collections import defaultdict

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter

_HDR_FONT = Font(name="Calibri", bold=True, color="FFFFFF", size=11)
_HDR_FILL = PatternFill("solid", fgColor="1E1E2E")
_TIT_FONT = Font(name="Calibri", bold=True, size=14, color="1E1E2E")
_MONEDA = '"$"#,##0.00'


def _get(v, clave, defecto=None):
    if isinstance(v, dict):
        return v.get(clave, defecto)
    return getattr(v, clave, defecto)


def _usuario(v):
    u = _get(v, "usuario")
    if u is None:
        return "N/A"
    if isinstance(u, str):
        return u
    return getattr(u, "nombre_usuario", "N/A")


def _fecha(v):
    f = _get(v, "fecha")
    if f is None:
        return ""
    return f.strftime("%d/%m/%Y %H:%M") if hasattr(f, "strftime") else str(f)[:16]


def _encabezado(ws, fila, columnas):
    for i, nombre in enumerate(columnas, start=1):
        c = ws.cell(row=fila, column=i, value=nombre)
        c.font, c.fill = _HDR_FONT, _HDR_FILL
        c.alignment = Alignment(horizontal="center")


def _anchos(ws, anchos):
    for i, a in enumerate(anchos, start=1):
        ws.column_dimensions[get_column_letter(i)].width = a


def exportar_excel_ventas(ventas, ruta_salida="reporte_ventas.xlsx", rango_texto=""):
    carpeta = os.path.dirname(ruta_salida)
    if carpeta:
        os.makedirs(carpeta, exist_ok=True)

    wb = Workbook()

    # ── Hoja Ventas ─────────────────────────────────────────────────
    ws_v = wb.active
    ws_v.title = "Ventas"
    _encabezado(ws_v, 1, ["Venta #", "Fecha", "PDV", "Usuario", "Medio de pago", "Total"])

    por_pdv = defaultdict(lambda: [0, 0.0])
    por_medio = defaultdict(lambda: [0, 0.0])
    total_general = 0.0

    for fila, v in enumerate(ventas, start=2):
        total = float(_get(v, "total", 0) or 0)
        pdv = _get(v, "pdv") or "Sin asignar"
        medio = _get(v, "medio_pago") or "Efectivo"
        ws_v.cell(row=fila, column=1, value=_get(v, "id"))
        ws_v.cell(row=fila, column=2, value=_fecha(v))
        ws_v.cell(row=fila, column=3, value=pdv)
        ws_v.cell(row=fila, column=4, value=_usuario(v))
        ws_v.cell(row=fila, column=5, value=medio)
        ws_v.cell(row=fila, column=6, value=total).number_format = _MONEDA
        total_general += total
        por_pdv[pdv][0] += 1;     por_pdv[pdv][1] += total
        por_medio[medio][0] += 1; por_medio[medio][1] += total

    n = len(ventas)
    fila_tot = n + 2
    ws_v.cell(row=fila_tot, column=5, value="TOTAL").font = Font(bold=True)
    c = ws_v.cell(row=fila_tot, column=6, value=f"=SUM(F2:F{n + 1})" if n else 0)
    c.font, c.number_format = Font(bold=True), _MONEDA
    ws_v.freeze_panes = "A2"
    _anchos(ws_v, [10, 18, 16, 18, 16, 16])

    # ── Hoja Detalle ────────────────────────────────────────────────
    ws_d = wb.create_sheet("Detalle")
    _encabezado(ws_d, 1, ["Venta #", "Fecha", "PDV", "Producto", "Precio unit.", "Cantidad", "Subtotal"])
    fila = 2
    for v in ventas:
        for it in (_get(v, "items", []) or []):
            ws_d.cell(row=fila, column=1, value=_get(v, "id"))
            ws_d.cell(row=fila, column=2, value=_fecha(v))
            ws_d.cell(row=fila, column=3, value=_get(v, "pdv") or "Sin asignar")
            ws_d.cell(row=fila, column=4, value=_get(it, "nombre"))
            ws_d.cell(row=fila, column=5, value=float(_get(it, "precio", 0) or 0)).number_format = _MONEDA
            ws_d.cell(row=fila, column=6, value=int(_get(it, "cantidad", 0) or 0))
            ws_d.cell(row=fila, column=7, value=float(_get(it, "subtotal", 0) or 0)).number_format = _MONEDA
            fila += 1
    ws_d.freeze_panes = "A2"
    _anchos(ws_d, [10, 18, 16, 30, 14, 10, 14])

    # ── Hoja Resumen (primera) ──────────────────────────────────────
    ws_r = wb.create_sheet("Resumen", 0)
    ws_r["A1"] = "Reporte de ventas"
    ws_r["A1"].font = _TIT_FONT
    if rango_texto:
        ws_r["A2"] = rango_texto
    ws_r["A4"], ws_r["B4"] = "Ventas registradas", n
    ws_r["A5"], ws_r["B5"] = "Total vendido", total_general
    ws_r["B5"].number_format = _MONEDA
    ws_r["A6"], ws_r["B6"] = "Ticket promedio", (total_general / n) if n else 0
    ws_r["B6"].number_format = _MONEDA

    def _tabla(fila_ini, titulo, etiqueta, datos):
        ws_r.cell(row=fila_ini, column=1, value=titulo).font = Font(bold=True, size=12)
        _encabezado(ws_r, fila_ini + 1, ["", "Cantidad de ventas", "Total"])
        ws_r.cell(row=fila_ini + 1, column=1, value=etiqueta).font = _HDR_FONT
        ws_r.cell(row=fila_ini + 1, column=1).fill = _HDR_FILL
        f = fila_ini + 2
        for clave, (cant, tot) in sorted(datos.items(), key=lambda kv: -kv[1][1]):
            ws_r.cell(row=f, column=1, value=clave)
            ws_r.cell(row=f, column=2, value=cant)
            ws_r.cell(row=f, column=3, value=tot).number_format = _MONEDA
            f += 1
        return f + 1

    sig = _tabla(8, "Ventas por PDV", "PDV", por_pdv)
    _tabla(sig, "Ventas por medio de pago", "Medio de pago", por_medio)
    _anchos(ws_r, [28, 20, 18])

    wb.save(ruta_salida)
    return ruta_salida
