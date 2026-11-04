"""
metricas.py — Instrumentación del piloto (criterios cuantitativos §2.3 del informe).

Tres indicadores, todos con su meta de éxito:

  1. Desfase de stock (conteo físico vs sistema): reducción ≥ 80 % entre el conteo de
     INICIO del piloto (línea base) y el de FIN.
  2. Tiempo de registro de una venta: reducción ≥ 30 % del promedio de 10 ventas
     cronometradas a mano (antes) contra las últimas 10 registradas con el sistema (después).
  3. Alertas de stock bajo: 100 % de los quiebres de stock (stock llegó a 0) tuvieron una
     alerta previa (el producto ya estaba en o bajo su mínimo en una operación anterior).

Usa sqlite3 directo, igual que transacciones.py.
"""
import sqlite3
import uuid

from backend.config import pdv_actual
from backend.base_datos.transacciones import (
    _conectar, _ahora, _rollback_seguro, _registrar_movimiento, registrar_eventos_stock,
)

META_DESFASE_PCT = 80
META_TIEMPO_PCT = 30
META_ALERTAS_PCT = 100
MUESTRA_TIEMPOS = 10

MOMENTOS_VALIDOS = ("inicio", "fin", "control")


# ─────────────────────────────────────────────
# REGISTRO DE DATOS
# ─────────────────────────────────────────────

def registrar_tiempo_manual(segundos, nota="", usuario_id=None, pdv=None, db_path=None):
    """Guarda el cronometraje de UNA venta hecha con el proceso manual (línea base de tiempos)."""
    segundos = float(segundos)
    if segundos <= 0:
        raise ValueError("El tiempo debe ser mayor que cero.")
    con = _conectar(db_path)
    try:
        con.execute(
            "INSERT INTO tiempos_venta_manual (fecha, pdv, segundos, nota, usuario_id) VALUES (?, ?, ?, ?, ?)",
            (_ahora(), pdv or pdv_actual(), segundos, nota or "", usuario_id),
        )
        return True
    finally:
        con.close()


def registrar_conteo_fisico(momento, conteos, usuario_id=None, ajustar_stock=False,
                            pdv=None, db_path=None):
    """
    Guarda un conteo físico contra el stock del sistema.

    momento : 'inicio' (línea base) | 'fin' (cierre del piloto) | 'control'.
    conteos : lista de {producto_id, stock_fisico}. Los productos no incluidos no se cuentan.
    ajustar_stock: si es True, además deja el stock del sistema igual al contado (con su
                   movimiento de stock). Por defecto NO toca el stock: solo mide el desfase.
    Devuelve {'lote', 'productos', 'desfase_total', 'con_diferencia'}.
    """
    if momento not in MOMENTOS_VALIDOS:
        raise ValueError(f"Momento inválido. Opciones: {', '.join(MOMENTOS_VALIDOS)}.")
    if not conteos:
        raise ValueError("No hay productos contados.")
    for c in conteos:
        if int(c["stock_fisico"]) < 0:
            raise ValueError("El stock contado no puede ser negativo.")

    pdv = pdv or pdv_actual()
    fecha = _ahora()
    lote = uuid.uuid4().hex[:10]
    desfase_total = 0
    con_dif = 0
    con = _conectar(db_path)
    try:
        con.execute("BEGIN IMMEDIATE")
        for c in conteos:
            pid, fisico = int(c["producto_id"]), int(c["stock_fisico"])
            fila = con.execute(
                "SELECT nombre, stock, stock_minimo FROM productos WHERE id = ?", (pid,)
            ).fetchone()
            if fila is None:
                continue
            nombre, sistema, minimo = fila[0], fila[1] or 0, fila[2]
            dif = fisico - sistema
            con.execute(
                "INSERT INTO conteos_fisicos (lote, momento, fecha, pdv, producto_id, producto, "
                "stock_sistema, stock_fisico, diferencia, usuario_id) VALUES (?,?,?,?,?,?,?,?,?,?)",
                (lote, momento, fecha, pdv, pid, nombre, sistema, fisico, dif, usuario_id),
            )
            desfase_total += abs(dif)
            if dif:
                con_dif += 1
            if ajustar_stock and dif:
                con.execute("UPDATE productos SET stock = ? WHERE id = ?", (fisico, pid))
                _registrar_movimiento(con, pid, usuario_id, dif, "ajuste",
                                      f"Ajuste por conteo físico ({momento})", fecha, pdv)
                registrar_eventos_stock(con, pid, nombre, sistema, fisico, minimo, pdv, fecha,
                                        f"conteo {momento}")
        con.execute("COMMIT")
        return {"lote": lote, "productos": len(conteos), "desfase_total": desfase_total,
                "con_diferencia": con_dif}
    except BaseException:
        _rollback_seguro(con)
        raise
    finally:
        con.close()


# ─────────────────────────────────────────────
# CÁLCULO DE INDICADORES
# ─────────────────────────────────────────────

def _desfase_de_lote(con, momento):
    fila = con.execute(
        "SELECT lote, MAX(fecha) FROM conteos_fisicos WHERE momento = ? "
        "GROUP BY lote ORDER BY MAX(id) DESC LIMIT 1", (momento,)
    ).fetchone()
    if not fila:
        return None
    r = con.execute(
        "SELECT COALESCE(SUM(ABS(diferencia)), 0), COUNT(*), "
        "COALESCE(SUM(CASE WHEN diferencia != 0 THEN 1 ELSE 0 END), 0) "
        "FROM conteos_fisicos WHERE lote = ?", (fila[0],)
    ).fetchone()
    return {"lote": fila[0], "fecha": str(fila[1])[:16], "unidades": r[0], "productos": r[1], "con_diferencia": r[2]}


def _promedio(valores):
    return (sum(valores) / len(valores)) if valores else None


def resumen_metricas(db_path=None):
    """Calcula los tres indicadores con su estado ('cumple' | 'no_cumple' | 'pendiente')."""
    con = _conectar(db_path)
    try:
        # ── 1. Desfase de stock ──────────────────────────────────────
        base = _desfase_de_lote(con, "inicio")
        final = _desfase_de_lote(con, "fin")
        desfase = {"meta_pct": META_DESFASE_PCT, "base": base, "final": final,
                   "reduccion_pct": None}
        if base is None or final is None:
            falta = "conteo de INICIO" if base is None else "conteo de FIN"
            desfase.update(estado="pendiente", detalle=f"Falta registrar el {falta}.")
        elif base["unidades"] == 0:
            ok = final["unidades"] == 0
            desfase.update(estado="cumple" if ok else "no_cumple",
                           detalle="La línea base no tenía desfase; "
                                   + ("el cierre tampoco." if ok else "el cierre sí tiene desfase."))
        else:
            red = (base["unidades"] - final["unidades"]) / base["unidades"] * 100
            desfase["reduccion_pct"] = red
            desfase.update(
                estado="cumple" if red >= META_DESFASE_PCT else "no_cumple",
                detalle=f"Desfase {base['unidades']} u. → {final['unidades']} u. "
                        f"(reducción {red:.1f} %, meta ≥ {META_DESFASE_PCT} %).")

        # ── 2. Tiempo de registro de una venta ───────────────────────
        manual = [r[0] for r in con.execute(
            "SELECT segundos FROM tiempos_venta_manual ORDER BY id DESC LIMIT ?", (MUESTRA_TIEMPOS,))]
        sistema = [r[0] for r in con.execute(
            "SELECT duracion_seg FROM ventas WHERE duracion_seg IS NOT NULL "
            "ORDER BY id DESC LIMIT ?", (MUESTRA_TIEMPOS,))]
        pm, ps = _promedio(manual), _promedio(sistema)
        tiempo = {"meta_pct": META_TIEMPO_PCT, "n_manual": len(manual), "n_sistema": len(sistema),
                  "manual_prom": pm, "sistema_prom": ps, "reduccion_pct": None,
                  "muestra_requerida": MUESTRA_TIEMPOS}
        if pm is None or ps is None:
            falta = "ventas cronometradas a mano" if pm is None else "ventas registradas con el sistema"
            tiempo.update(estado="pendiente", detalle=f"Faltan {falta}.")
        else:
            red = (pm - ps) / pm * 100
            tiempo["reduccion_pct"] = red
            completa = len(manual) >= MUESTRA_TIEMPOS and len(sistema) >= MUESTRA_TIEMPOS
            texto = (f"Manual {pm:.1f} s ({len(manual)} ventas) → sistema {ps:.1f} s "
                     f"({len(sistema)} ventas): reducción {red:.1f} % (meta ≥ {META_TIEMPO_PCT} %).")
            if completa:
                tiempo.update(estado="cumple" if red >= META_TIEMPO_PCT else "no_cumple", detalle=texto)
            else:
                tiempo.update(estado="pendiente",
                              detalle=texto + f" Provisorio: se necesitan {MUESTRA_TIEMPOS} ventas de cada tipo.")

        # ── 3. Alertas de stock bajo vs quiebres ─────────────────────
        quiebres = con.execute(
            "SELECT COUNT(*), COALESCE(SUM(CASE WHEN alertado_antes = 1 THEN 1 ELSE 0 END), 0) "
            "FROM eventos_stock WHERE tipo = 'quiebre'").fetchone()
        alertas_n = con.execute("SELECT COUNT(*) FROM eventos_stock WHERE tipo = 'alerta'").fetchone()[0]
        q, ok_q = quiebres[0], quiebres[1]
        alertas = {"meta_pct": META_ALERTAS_PCT, "quiebres": q, "con_alerta_previa": ok_q,
                   "alertas_disparadas": alertas_n,
                   "cumplimiento_pct": (ok_q / q * 100) if q else None}
        if q == 0:
            if alertas_n:
                alertas.update(estado="cumple",
                               detalle=f"{alertas_n} alerta(s) disparada(s) y ningún quiebre de stock.")
            else:
                alertas.update(estado="pendiente", detalle="Todavía no hubo alertas ni quiebres.")
        else:
            pct = ok_q / q * 100
            alertas.update(
                estado="cumple" if pct >= META_ALERTAS_PCT else "no_cumple",
                detalle=f"{ok_q} de {q} quiebre(s) tuvieron alerta previa ({pct:.0f} %, meta {META_ALERTAS_PCT} %).")

        return {"desfase": desfase, "tiempo": tiempo, "alertas": alertas,
                "exito_piloto": all(x["estado"] == "cumple" for x in (desfase, tiempo, alertas)),
                "pendientes": [n for n, x in (("desfase", desfase), ("tiempo", tiempo), ("alertas", alertas))
                               if x["estado"] == "pendiente"]}
    finally:
        con.close()


def datos_metricas(db_path=None):
    """Datos crudos + resumen, para exportar el informe del piloto."""
    con = _conectar(db_path)
    try:
        def filas(sql, cols):
            return [dict(zip(cols, r)) for r in con.execute(sql)]
        datos = {
            "conteos": filas(
                "SELECT lote, momento, fecha, pdv, producto, stock_sistema, stock_fisico, diferencia "
                "FROM conteos_fisicos ORDER BY id",
                ["lote", "momento", "fecha", "pdv", "producto", "stock_sistema", "stock_fisico", "diferencia"]),
            "tiempos_manual": filas(
                "SELECT fecha, pdv, segundos, nota FROM tiempos_venta_manual ORDER BY id",
                ["fecha", "pdv", "segundos", "nota"]),
            "tiempos_sistema": filas(
                "SELECT id, fecha, pdv, duracion_seg FROM ventas WHERE duracion_seg IS NOT NULL ORDER BY id",
                ["venta", "fecha", "pdv", "segundos"]),
            "eventos": filas(
                "SELECT fecha, pdv, producto, tipo, stock, stock_minimo, origen, alertado_antes "
                "FROM eventos_stock ORDER BY id",
                ["fecha", "pdv", "producto", "tipo", "stock", "stock_minimo", "origen", "alertado_antes"]),
        }
    finally:
        con.close()
    datos["resumen"] = resumen_metricas(db_path)
    return datos
