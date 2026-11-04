"""
transacciones.py — Operaciones críticas de stock, ATÓMICAS y seguras con varias cajas.

Todo lo que cambia stock pasa por acá. Cada operación es UNA transacción SQLite con
BEGIN IMMEDIATE (toma el lock de escritura desde el inicio: dos cajas se serializan
en lugar de pisarse) y el stock se modifica en la propia base, nunca con un valor
leído antes en Python:

    UPDATE productos SET stock = stock - :n WHERE id = :id AND stock >= :n

Además, dentro de la MISMA transacción se registran los movimientos de stock y los
eventos de alerta/quiebre que usan las métricas del piloto.

Usa sqlite3 directo (sin SQLAlchemy) a propósito: es más simple de razonar y de
testear con hilos.
"""
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime

from backend.config import DB_PATH, pdv_actual

_ESPERA_LOCK_SEG = 15


# ─────────────────────────────────────────────
# ERRORES  (todos son ValueError: el código que captura ValueError sigue andando)
# ─────────────────────────────────────────────

class StockInsuficienteError(ValueError):
    def __init__(self, producto_id, nombre, disponible, pedido):
        self.producto_id = producto_id
        self.nombre = nombre
        self.disponible = disponible
        self.pedido = pedido
        super().__init__(f"Stock insuficiente. Stock actual: {disponible}.")


class ProductoInexistenteError(ValueError):
    def __init__(self, producto_id):
        self.producto_id = producto_id
        super().__init__(f"El producto #{producto_id} no existe.")


class ConflictoStockError(ValueError):
    """El stock cambió (otra caja) desde que el usuario lo vio en pantalla."""

    def __init__(self, producto_id, nombre, esperado, actual):
        self.producto_id = producto_id
        self.nombre = nombre
        self.esperado = esperado
        self.actual = actual
        super().__init__(
            f"El stock de «{nombre}» cambió mientras editabas: vos veías {esperado} "
            f"y ahora hay {actual}. Actualizá la pantalla y volvé a intentar."
        )


# ─────────────────────────────────────────────
# RESULTADOS
# ─────────────────────────────────────────────

@dataclass
class VentaRegistrada:
    id: int
    fecha: str
    total: float
    medio_pago: str
    pdv: str
    # productos que quedaron en o por debajo de su stock mínimo tras la venta
    alertas_stock: list = field(default_factory=list)
    # True si el pedido ya estaba registrado (reintento tras una respuesta perdida)
    ya_registrada: bool = False


# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────

def _conectar(db_path=None):
    # isolation_level=None -> autocommit; las transacciones las manejamos a mano.
    con = sqlite3.connect(db_path or DB_PATH, timeout=_ESPERA_LOCK_SEG, isolation_level=None)
    con.execute(f"PRAGMA busy_timeout = {_ESPERA_LOCK_SEG * 1000}")
    return con


def _ahora():
    # Mismo formato que guarda SQLAlchemy para DateTime en SQLite
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")


def _rollback_seguro(con):
    try:
        if con.in_transaction:
            con.execute("ROLLBACK")
    except sqlite3.Error:
        pass


def registrar_eventos_stock(con, producto_id, nombre, antes, despues, minimo, pdv, fecha, origen):
    """
    Deja constancia (tabla eventos_stock) de los cruces de umbral que usan las métricas:
      • 'alerta'  : el stock pasó de > mínimo a <= mínimo.
      • 'quiebre' : el stock llegó a 0 (alertado_antes = 1 si ya estaba en alerta en una
                    operación anterior; 0 si saltó de > mínimo directo a 0).
    Nunca hace fallar la operación principal.
    """
    minimo = minimo or 0
    try:
        if antes > minimo and despues <= minimo:
            con.execute(
                "INSERT INTO eventos_stock (fecha, pdv, producto_id, producto, tipo, stock, stock_minimo, origen) "
                "VALUES (?, ?, ?, ?, 'alerta', ?, ?, ?)",
                (fecha, pdv, producto_id, nombre, despues, minimo, origen),
            )
        if antes > 0 and despues <= 0:
            con.execute(
                "INSERT INTO eventos_stock (fecha, pdv, producto_id, producto, tipo, stock, stock_minimo, origen, alertado_antes) "
                "VALUES (?, ?, ?, ?, 'quiebre', ?, ?, ?, ?)",
                (fecha, pdv, producto_id, nombre, despues, minimo, origen, 1 if antes <= minimo else 0),
            )
    except sqlite3.OperationalError:
        pass


def _registrar_movimiento(con, producto_id, usuario_id, cantidad, tipo, descripcion, fecha, pdv):
    con.execute(
        "INSERT INTO movimientos_stock (producto_id, usuario_id, cantidad, tipo, descripcion, fecha, pdv) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (producto_id, usuario_id, cantidad, tipo, descripcion, fecha, pdv),
    )


# ─────────────────────────────────────────────
# VENTA ATÓMICA
# ─────────────────────────────────────────────

def registrar_venta_atomica(usuario_id, total, medio_pago, items, pdv=None,
                            duracion_seg=None, op_id=None, db_path=None):
    """
    Registra venta + ítems + descuento de stock + movimientos en UNA transacción.

    items       : lista de dicts {id, nombre, precio, cantidad}
    duracion_seg: segundos que tardó el registro (métrica del piloto; opcional)
    op_id       : identificador único de la operación. Si llega dos veces (p. ej. la
                  caja no recibió la respuesta y reintenta) NO se vuelve a vender:
                  se devuelve la venta ya registrada (ya_registrada=True).

    Lanza StockInsuficienteError / ProductoInexistenteError / ValueError sin dejar
    nada a medio hacer. Devuelve VentaRegistrada.
    """
    if not items:
        raise ValueError("La venta no tiene productos.")
    if total is None or total < 0:
        raise ValueError("El total de la venta no puede ser negativo.")
    for it in items:
        if int(it["cantidad"]) <= 0:
            raise ValueError(f"Cantidad inválida para «{it['nombre']}».")

    pdv = pdv or pdv_actual()
    fecha = _ahora()
    con = _conectar(db_path)
    try:
        con.execute("BEGIN IMMEDIATE")

        if op_id:
            previa = con.execute(
                "SELECT id, fecha, total, medio_pago, pdv FROM ventas WHERE op_id = ?", (op_id,)
            ).fetchone()
            if previa:
                con.execute("ROLLBACK")
                return VentaRegistrada(previa[0], str(previa[1]), float(previa[2] or 0),
                                       previa[3], previa[4], [], True)

        cur = con.execute(
            "INSERT INTO ventas (usuario_id, total, medio_pago, fecha, pdv, duracion_seg, op_id) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (usuario_id, float(total), medio_pago, fecha, pdv,
             None if duracion_seg is None else float(duracion_seg), op_id),
        )
        venta_id = cur.lastrowid

        for it in items:
            pid = int(it["id"])
            cant = int(it["cantidad"])
            fila = con.execute(
                "SELECT nombre, stock, stock_minimo FROM productos WHERE id = ?", (pid,)
            ).fetchone()
            if fila is None:
                raise ProductoInexistenteError(pid)
            nombre, stock_antes, minimo = fila[0], fila[1] or 0, fila[2]

            upd = con.execute(
                "UPDATE productos SET stock = stock - ? WHERE id = ? AND stock >= ?",
                (cant, pid, cant),
            )
            if upd.rowcount == 0:
                raise StockInsuficienteError(pid, nombre, stock_antes, cant)

            precio = float(it["precio"])
            con.execute(
                "INSERT INTO items_venta (venta_id, producto_id, nombre, precio, cantidad, subtotal) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (venta_id, pid, it["nombre"], precio, cant, precio * cant),
            )
            _registrar_movimiento(con, pid, usuario_id, -cant, "venta",
                                  f"Venta #{venta_id} — {it['nombre']}", fecha, pdv)
            registrar_eventos_stock(con, pid, nombre, stock_antes, stock_antes - cant,
                                    minimo, pdv, fecha, f"venta #{venta_id}")

        ids = sorted({int(it["id"]) for it in items})
        marcas = ",".join("?" * len(ids))
        alertas = [
            {"id": r[0], "nombre": r[1], "stock": r[2], "stock_minimo": r[3]}
            for r in con.execute(
                f"SELECT id, nombre, stock, stock_minimo FROM productos "
                f"WHERE id IN ({marcas}) AND stock <= COALESCE(stock_minimo, 0)",
                ids,
            )
        ]

        con.execute("COMMIT")
        return VentaRegistrada(venta_id, fecha, float(total), medio_pago, pdv, alertas)
    except BaseException:
        _rollback_seguro(con)
        raise
    finally:
        con.close()


# ─────────────────────────────────────────────
# AJUSTE / FIJACIÓN DE STOCK ATÓMICOS
# ─────────────────────────────────────────────

def ajustar_stock_atomico(producto_id, delta, usuario_id=None, tipo=None, descripcion="",
                          pdv=None, db_path=None):
    """
    Suma `delta` (puede ser negativo) al stock directamente en la base.
    Si se indica `tipo` ('entrada', 'ajuste', ...), el movimiento de stock se guarda en la
    MISMA transacción (si algo falla no queda stock cambiado sin movimiento, ni al revés).
    Devuelve el nuevo stock, o None si el producto no existe.
    Lanza StockInsuficienteError si el resultado sería negativo.
    """
    pdv = pdv or pdv_actual()
    fecha = _ahora()
    con = _conectar(db_path)
    try:
        con.execute("BEGIN IMMEDIATE")
        fila = con.execute(
            "SELECT nombre, stock, stock_minimo FROM productos WHERE id = ?", (producto_id,)
        ).fetchone()
        if fila is None:
            con.execute("ROLLBACK")
            return None
        nombre, antes, minimo = fila[0], fila[1] or 0, fila[2]

        upd = con.execute(
            "UPDATE productos SET stock = stock + ? WHERE id = ? AND stock + ? >= 0",
            (delta, producto_id, delta),
        )
        if upd.rowcount == 0:
            raise StockInsuficienteError(producto_id, nombre, antes, -delta)
        nuevo = antes + delta

        if tipo:
            _registrar_movimiento(con, producto_id, usuario_id, delta, tipo,
                                  descripcion or "Ajuste manual", fecha, pdv)
        registrar_eventos_stock(con, producto_id, nombre, antes, nuevo, minimo, pdv, fecha, "ajuste")
        con.execute("COMMIT")
        return nuevo
    except BaseException:
        _rollback_seguro(con)
        raise
    finally:
        con.close()


def fijar_stock_atomico(producto_id, nuevo_stock, esperado=None, usuario_id=None, tipo=None,
                        descripcion="", pdv=None, db_path=None):
    """
    Fija el stock en un valor absoluto, de forma segura.

    esperado: el stock que el usuario VIO en pantalla. Si en la base ya es otro (porque
              otra caja vendió o ajustó), lanza ConflictoStockError en vez de pisar ese
              cambio en silencio.
    Devuelve el nuevo stock, o None si el producto no existe.
    """
    if nuevo_stock is None or int(nuevo_stock) < 0:
        raise ValueError("El stock no puede ser negativo.")
    nuevo_stock = int(nuevo_stock)
    pdv = pdv or pdv_actual()
    fecha = _ahora()
    con = _conectar(db_path)
    try:
        con.execute("BEGIN IMMEDIATE")
        fila = con.execute(
            "SELECT nombre, stock, stock_minimo FROM productos WHERE id = ?", (producto_id,)
        ).fetchone()
        if fila is None:
            con.execute("ROLLBACK")
            return None
        nombre, antes, minimo = fila[0], fila[1] or 0, fila[2]
        if esperado is not None and int(esperado) != antes:
            raise ConflictoStockError(producto_id, nombre, int(esperado), antes)

        con.execute("UPDATE productos SET stock = ? WHERE id = ?", (nuevo_stock, producto_id))
        if tipo and nuevo_stock != antes:
            _registrar_movimiento(con, producto_id, usuario_id, nuevo_stock - antes, tipo,
                                  descripcion or "Stock fijado manualmente", fecha, pdv)
        registrar_eventos_stock(con, producto_id, nombre, antes, nuevo_stock, minimo, pdv, fecha, "fijado")
        con.execute("COMMIT")
        return nuevo_stock
    except BaseException:
        _rollback_seguro(con)
        raise
    finally:
        con.close()


# ─────────────────────────────────────────────
# CONSULTAS MULTI-PDV (panel de consolidación)
# ─────────────────────────────────────────────

def resumen_por_pdv(desde=None, hasta=None, db_path=None):
    """
    Ventas agrupadas por punto de venta.
    desde / hasta: datetime o date (inclusive, día completo). None = sin límite.
    Devuelve [{'pdv', 'cantidad_ventas', 'total'}], ordenado por total descendente.
    """
    cond, params = [], []
    if desde is not None:
        cond.append("fecha >= ?")
        params.append(desde.strftime("%Y-%m-%d") + " 00:00:00")
    if hasta is not None:
        cond.append("fecha <= ?")
        params.append(hasta.strftime("%Y-%m-%d") + " 23:59:59.999999")
    donde = ("WHERE " + " AND ".join(cond)) if cond else ""

    con = _conectar(db_path)
    try:
        filas = con.execute(
            f"SELECT COALESCE(pdv, 'Sin asignar'), COUNT(*), COALESCE(SUM(total), 0) "
            f"FROM ventas {donde} GROUP BY COALESCE(pdv, 'Sin asignar') ORDER BY 3 DESC",
            params,
        ).fetchall()
        return [{"pdv": f[0], "cantidad_ventas": f[1], "total": float(f[2])} for f in filas]
    finally:
        con.close()


def ultimas_ventas(limite=50, desde=None, hasta=None, db_path=None):
    """Últimas ventas de todos los PDV: [{'id','fecha','pdv','usuario','medio_pago','total'}]."""
    cond, params = [], []
    if desde is not None:
        cond.append("v.fecha >= ?")
        params.append(desde.strftime("%Y-%m-%d") + " 00:00:00")
    if hasta is not None:
        cond.append("v.fecha <= ?")
        params.append(hasta.strftime("%Y-%m-%d") + " 23:59:59.999999")
    donde = ("WHERE " + " AND ".join(cond)) if cond else ""
    con = _conectar(db_path)
    try:
        filas = con.execute(
            f"SELECT v.id, v.fecha, COALESCE(v.pdv, 'Sin asignar'), "
            f"COALESCE(u.nombre_usuario, '—'), v.medio_pago, v.total "
            f"FROM ventas v LEFT JOIN usuarios u ON u.id = v.usuario_id "
            f"{donde} ORDER BY v.id DESC LIMIT ?",
            params + [int(limite)],
        ).fetchall()
        return [
            {"id": f[0], "fecha": str(f[1])[:19], "pdv": f[2], "usuario": f[3],
             "medio_pago": f[4], "total": float(f[5] or 0)}
            for f in filas
        ]
    finally:
        con.close()
