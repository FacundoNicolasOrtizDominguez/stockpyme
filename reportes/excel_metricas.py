"""
reportes/excel_metricas.py — Informe de métricas del piloto (§2.3) en Excel.

Recibe el diccionario que devuelve datos_metricas() y genera un .xlsx con:
  • Indicadores : los 3 criterios con valor, meta y estado (cumple / no cumple / pendiente)
  • Conteos     : conteos físicos contra sistema (línea base y cierre)
  • Tiempos     : cronometrajes manuales y ventas registradas con el sistema
  • Eventos     : alertas de stock bajo y quiebres, con o sin alerta previa
"""
import os

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter

_HDR_FONT = Font(name="Calibri", bold=True, color="FFFFFF", size=11)
_HDR_FILL = PatternFill("solid", fgColor="1E1E2E")
_ESTADOS = {
    "cumple":    ("✔ Cumple",    "C6EFCE"),
    "no_cumple": ("✘ No cumple", "FFC7CE"),
    "pendiente": ("… Pendiente", "FFEB9C"),
}


def _encabezado(ws, fila, columnas):
    for i, nombre in enumerate(columnas, start=1):
        c = ws.cell(row=fila, column=i, value=nombre)
        c.font, c.fill = _HDR_FONT, _HDR_FILL
        c.alignment = Alignment(horizontal="center")


def _anchos(ws, anchos):
    for i, a in enumerate(anchos, start=1):
        ws.column_dimensions[get_column_letter(i)].width = a


def _pct(v):
    return "—" if v is None else f"{v:.1f} %"


def exportar_excel_metricas(datos, ruta_salida="metricas_piloto.xlsx"):
    carpeta = os.path.dirname(ruta_salida)
    if carpeta:
        os.makedirs(carpeta, exist_ok=True)
    r = datos["resumen"]
    wb = Workbook()

    # ── Indicadores ─────────────────────────────────────────────────
    ws = wb.active
    ws.title = "Indicadores"
    ws["A1"] = "Métricas del piloto — criterios de aceptación (§2.3)"
    ws["A1"].font = Font(bold=True, size=14, color="1E1E2E")
    estado_global, color_global = (("✔ PILOTO EXITOSO", "C6EFCE") if r["exito_piloto"]
                                   else ("PILOTO NO CONCLUIDO / NO EXITOSO", "FFEB9C"))
    ws["A2"] = estado_global
    ws["A2"].font = Font(bold=True)
    ws["A2"].fill = PatternFill("solid", fgColor=color_global)

    _encabezado(ws, 4, ["Indicador", "Resultado", "Meta de éxito", "Estado", "Detalle"])
    des, tie, ale = r["desfase"], r["tiempo"], r["alertas"]
    filas = [
        ("Desfase de stock (conteo físico vs sistema)", _pct(des["reduccion_pct"]) + " de reducción",
         f"Reducción ≥ {des['meta_pct']} %", des),
        ("Tiempo de registro de una venta", _pct(tie["reduccion_pct"]) + " de reducción",
         f"Reducción ≥ {tie['meta_pct']} %", tie),
        ("Alertas de stock bajo a tiempo", _pct(ale["cumplimiento_pct"]) + " de quiebres alertados",
         f"{ale['meta_pct']} % alertados antes de agotarse", ale),
    ]
    for i, (nombre, resultado, meta, ind) in enumerate(filas, start=5):
        texto, color = _ESTADOS[ind["estado"]]
        ws.cell(row=i, column=1, value=nombre)
        ws.cell(row=i, column=2, value=resultado)
        ws.cell(row=i, column=3, value=meta)
        c = ws.cell(row=i, column=4, value=texto)
        c.fill = PatternFill("solid", fgColor=color)
        c.font = Font(bold=True)
        ws.cell(row=i, column=5, value=ind["detalle"]).alignment = Alignment(wrap_text=True)
    _anchos(ws, [44, 32, 38, 16, 80])

    # ── Conteos ─────────────────────────────────────────────────────
    ws = wb.create_sheet("Conteos")
    _encabezado(ws, 1, ["Lote", "Momento", "Fecha", "PDV", "Producto", "Stock sistema", "Stock físico", "Diferencia"])
    for i, c in enumerate(datos["conteos"], start=2):
        for j, k in enumerate(["lote", "momento", "fecha", "pdv", "producto",
                               "stock_sistema", "stock_fisico", "diferencia"], start=1):
            ws.cell(row=i, column=j, value=str(c[k])[:19] if k == "fecha" else c[k])
    ws.freeze_panes = "A2"
    _anchos(ws, [14, 10, 20, 14, 30, 14, 14, 12])

    # ── Tiempos ─────────────────────────────────────────────────────
    ws = wb.create_sheet("Tiempos")
    _encabezado(ws, 1, ["Origen", "Fecha", "PDV", "Segundos", "Nota / Venta #"])
    fila = 2
    for t in datos["tiempos_manual"]:
        for j, v in enumerate(["Manual (antes)", str(t["fecha"])[:19], t["pdv"], t["segundos"], t["nota"]], start=1):
            ws.cell(row=fila, column=j, value=v)
        fila += 1
    for t in datos["tiempos_sistema"]:
        for j, v in enumerate(["Sistema (después)", str(t["fecha"])[:19], t["pdv"], t["segundos"], t["venta"]], start=1):
            ws.cell(row=fila, column=j, value=v)
        fila += 1
    ws.freeze_panes = "A2"
    _anchos(ws, [20, 20, 14, 12, 24])

    # ── Eventos ─────────────────────────────────────────────────────
    ws = wb.create_sheet("Eventos de stock")
    _encabezado(ws, 1, ["Fecha", "PDV", "Producto", "Tipo", "Stock", "Mínimo", "Origen", "Alertado antes"])
    for i, e in enumerate(datos["eventos"], start=2):
        alertado = "" if e["tipo"] != "quiebre" else ("Sí" if e["alertado_antes"] else "No")
        for j, v in enumerate([str(e["fecha"])[:19], e["pdv"], e["producto"], e["tipo"],
                               e["stock"], e["stock_minimo"], e["origen"], alertado], start=1):
            ws.cell(row=i, column=j, value=v)
    ws.freeze_panes = "A2"
    _anchos(ws, [20, 14, 28, 10, 8, 8, 18, 15])

    wb.save(ruta_salida)
    return ruta_salida
