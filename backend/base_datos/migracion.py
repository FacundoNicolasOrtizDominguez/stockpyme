"""
migracion.py — Migración automática de la base de datos existente.

Agrega las columnas y tablas nuevas SIN destruir los datos existentes.
Se llama una sola vez al arrancar el sistema (desde main.py).
Es idempotente: si las columnas ya existen, no hace nada.
"""
import sqlite3
import os

from backend.config import DB_PATH, PDV_NOMBRE


def _columnas(cur, tabla):
    return {row[1] for row in cur.execute(f"PRAGMA table_info({tabla})")}


def migrar(ruta=None):
    ruta = ruta or DB_PATH
    if not os.path.exists(ruta):
        return

    con = sqlite3.connect(ruta, timeout=15)
    try:
        cur = con.cursor()

        tablas = {row[0] for row in cur.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )}

        # ── 1. Tabla ventas: medio_pago, fecha y pdv ─────────────────
        if "ventas" in tablas:
            cols = _columnas(cur, "ventas")
            if "medio_pago" not in cols:
                cur.execute("ALTER TABLE ventas ADD COLUMN medio_pago TEXT DEFAULT 'Efectivo'")
                print("[migración] ventas.medio_pago agregado")
            if "fecha" not in cols:
                # SQLite no admite DEFAULT no constante en ALTER TABLE: sin default.
                cur.execute("ALTER TABLE ventas ADD COLUMN fecha TEXT")
                cur.execute("UPDATE ventas SET fecha = datetime('now') WHERE fecha IS NULL")
                print("[migración] ventas.fecha agregado")
            if "pdv" not in cols:
                cur.execute("ALTER TABLE ventas ADD COLUMN pdv TEXT")
                cur.execute("UPDATE ventas SET pdv = ? WHERE pdv IS NULL", (PDV_NOMBRE,))
                print("[migración] ventas.pdv agregado")
            if "duracion_seg" not in cols:
                cur.execute("ALTER TABLE ventas ADD COLUMN duracion_seg REAL")
                print("[migración] ventas.duracion_seg agregado")
            if "op_id" not in cols:
                cur.execute("ALTER TABLE ventas ADD COLUMN op_id TEXT")
                print("[migración] ventas.op_id agregado")

        # ── 2. Tabla items_venta ─────────────────────────────────────
        if "items_venta" not in tablas:
            cur.execute("""
                CREATE TABLE items_venta (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    venta_id    INTEGER REFERENCES ventas(id),
                    producto_id INTEGER REFERENCES productos(id),
                    nombre      TEXT,
                    precio      REAL,
                    cantidad    INTEGER,
                    subtotal    REAL
                )
            """)
            print("[migración] tabla items_venta creada")

        # ── 3. Tabla movimientos_stock (+ pdv) ───────────────────────
        if "movimientos_stock" not in tablas:
            cur.execute("""
                CREATE TABLE movimientos_stock (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    producto_id INTEGER NOT NULL REFERENCES productos(id),
                    usuario_id  INTEGER REFERENCES usuarios(id),
                    cantidad    INTEGER NOT NULL,
                    tipo        TEXT NOT NULL,
                    descripcion TEXT DEFAULT '',
                    fecha       TEXT DEFAULT (datetime('now')),
                    pdv         TEXT
                )
            """)
            print("[migración] tabla movimientos_stock creada")
        elif "pdv" not in _columnas(cur, "movimientos_stock"):
            cur.execute("ALTER TABLE movimientos_stock ADD COLUMN pdv TEXT")
            cur.execute("UPDATE movimientos_stock SET pdv = ? WHERE pdv IS NULL", (PDV_NOMBRE,))
            print("[migración] movimientos_stock.pdv agregado")

        # ── 4. Índices para consultas por fecha/PDV ──────────────────
        if "ventas" in tablas:
            cur.execute("CREATE INDEX IF NOT EXISTS ix_ventas_fecha ON ventas(fecha)")
            cur.execute("CREATE INDEX IF NOT EXISTS ix_items_venta_venta ON items_venta(venta_id)")

        con.commit()
    finally:
        con.close()

    crear_tablas_extra(ruta)
    print("[migración] BD actualizada correctamente")


# Tablas de las métricas del piloto (§2.3 del informe) + índice anti-duplicados de ventas
_DDL_EXTRA = (
    """CREATE TABLE IF NOT EXISTS conteos_fisicos (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        lote          TEXT NOT NULL,
        momento       TEXT NOT NULL,          -- 'inicio' | 'fin' | 'control'
        fecha         TEXT NOT NULL,
        pdv           TEXT,
        producto_id   INTEGER NOT NULL,
        producto      TEXT,
        stock_sistema INTEGER NOT NULL,
        stock_fisico  INTEGER NOT NULL,
        diferencia    INTEGER NOT NULL,
        usuario_id    INTEGER
    )""",
    """CREATE TABLE IF NOT EXISTS tiempos_venta_manual (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        fecha       TEXT NOT NULL,
        pdv         TEXT,
        segundos    REAL NOT NULL,
        nota        TEXT DEFAULT '',
        usuario_id  INTEGER
    )""",
    """CREATE TABLE IF NOT EXISTS eventos_stock (
        id             INTEGER PRIMARY KEY AUTOINCREMENT,
        fecha          TEXT NOT NULL,
        pdv            TEXT,
        producto_id    INTEGER NOT NULL,
        producto       TEXT,
        tipo           TEXT NOT NULL,         -- 'alerta' | 'quiebre'
        stock          INTEGER,
        stock_minimo   INTEGER,
        origen         TEXT,
        alertado_antes INTEGER                -- solo en 'quiebre': 1 si ya estaba en alerta
    )""",
)


def crear_tablas_extra(ruta=None):
    """Crea (si faltan) las tablas de métricas y el índice único de ventas.op_id. Idempotente."""
    ruta = ruta or DB_PATH
    if not os.path.exists(ruta):
        return
    con = sqlite3.connect(ruta, timeout=15)
    try:
        cur = con.cursor()
        for ddl in _DDL_EXTRA:
            cur.execute(ddl)
        tablas = {r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if "ventas" in tablas and "op_id" in _columnas(cur, "ventas"):
            cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS ux_ventas_op_id "
                        "ON ventas(op_id) WHERE op_id IS NOT NULL")
        con.commit()
    finally:
        con.close()
