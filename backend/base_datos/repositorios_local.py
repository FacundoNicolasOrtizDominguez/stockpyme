# ============================================================
# REPOSITORIOS — Capa de acceso a datos
# Sistema de Control de Stock y Ventas
# ============================================================

import bcrypt
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from backend.base_datos.conexion import SessionLocal
from backend.config import pdv_actual
from backend.base_datos.transacciones import (   # noqa: F401  (se re-exportan para la interfaz)
    registrar_venta_atomica, ajustar_stock_atomico, fijar_stock_atomico, resumen_por_pdv, ultimas_ventas,
    StockInsuficienteError, ProductoInexistenteError, ConflictoStockError,
)
from backend.base_datos.metricas import (   # noqa: F401  (métricas del piloto)
    registrar_tiempo_manual, registrar_conteo_fisico, resumen_metricas, datos_metricas,
)
from backend.modelos.producto import Producto
from backend.modelos.usuario import Usuario
from backend.modelos.venta import Venta, ItemVenta
from backend.modelos.proveedor import Proveedor


# ─────────────────────────────────────────────
# HELPERS INTERNOS
# ─────────────────────────────────────────────

def _expunge_all(session, objetos):
    for obj in objetos:
        session.expunge(obj)
    session.close()


def _hashear_password(password_plana: str) -> str:
    return bcrypt.hashpw(
        password_plana.encode("utf-8"),
        bcrypt.gensalt()
    ).decode("utf-8")


# ─────────────────────────────────────────────
# PRODUCTOS
# ─────────────────────────────────────────────

def crear_producto(nombre, categoria, precio, stock, stock_minimo=5):
    nombre    = nombre.strip()
    categoria = categoria.strip()
    if not nombre:       raise ValueError("El nombre del producto no puede estar vacío.")
    if not categoria:    raise ValueError("La categoría no puede estar vacía.")
    if precio < 0:       raise ValueError("El precio no puede ser negativo.")
    if stock < 0:        raise ValueError("El stock no puede ser negativo.")
    if stock_minimo < 0: raise ValueError("El stock mínimo no puede ser negativo.")

    session = SessionLocal()
    try:
        producto = Producto(nombre=nombre, categoria=categoria,
                            precio=precio, stock=stock, stock_minimo=stock_minimo)
        session.add(producto)
        session.commit()
        session.refresh(producto)
        session.expunge(producto)
        return producto
    except SQLAlchemyError:
        session.rollback()
        return None
    finally:
        session.close()


def listar_productos(solo_activos=False):
    session = SessionLocal()
    try:
        query = session.query(Producto)
        if solo_activos:
            query = query.filter(Producto.activo == True)
        productos = query.order_by(Producto.nombre).all()
        for p in productos:
            session.expunge(p)
        return productos
    except SQLAlchemyError:
        return []
    finally:
        session.close()


def buscar_producto_por_id(id_producto):
    session = SessionLocal()
    try:
        producto = session.query(Producto).filter(Producto.id == id_producto).first()
        if producto:
            session.expunge(producto)
        return producto
    except SQLAlchemyError:
        return None
    finally:
        session.close()


def actualizar_producto(id_producto, nombre=None, categoria=None,
                        precio=None, stock_minimo=None):
    if nombre is not None:
        nombre = nombre.strip()
        if not nombre: raise ValueError("El nombre no puede estar vacío.")
    if categoria is not None:
        categoria = categoria.strip()
        if not categoria: raise ValueError("La categoría no puede estar vacía.")
    if precio is not None and precio < 0:
        raise ValueError("El precio no puede ser negativo.")
    if stock_minimo is not None and stock_minimo < 0:
        raise ValueError("El stock mínimo no puede ser negativo.")

    session = SessionLocal()
    try:
        producto = session.query(Producto).filter(Producto.id == id_producto).first()
        if producto is None: return None
        if nombre       is not None: producto.nombre       = nombre
        if categoria    is not None: producto.categoria    = categoria
        if precio       is not None: producto.precio       = precio
        if stock_minimo is not None: producto.stock_minimo = stock_minimo
        session.commit()
        session.refresh(producto)
        session.expunge(producto)
        return producto
    except SQLAlchemyError:
        session.rollback()
        return None
    finally:
        session.close()


def actualizar_stock(id_producto, nuevo_stock, stock_esperado=None, usuario_id=None,
                     tipo=None, descripcion=""):
    """
    Fija el stock en un valor absoluto, de forma segura.
    Pasá `stock_esperado` (lo que se veía en pantalla): si otra caja lo cambió, lanza
    ConflictoStockError en lugar de pisar ese cambio en silencio.
    Retorna el Producto actualizado, o None si no existe.
    """
    resultado = fijar_stock_atomico(id_producto, nuevo_stock, esperado=stock_esperado,
                                    usuario_id=usuario_id, tipo=tipo, descripcion=descripcion)
    if resultado is None:
        return None
    return buscar_producto_por_id(id_producto)


def ajustar_stock(id_producto, cantidad_a_sumar, usuario_id=None, tipo=None, descripcion=""):
    """
    Suma (o resta, si es negativo) stock de forma atómica en la base, sin leer antes el
    valor en Python (no pisa cambios de otras cajas).
    Si se pasa `tipo` ('entrada', 'ajuste'), el movimiento de stock se registra en la MISMA
    transacción. Lanza ValueError (StockInsuficienteError) si el resultado fuera negativo.
    Retorna el Producto actualizado, o None si no existe.
    """
    nuevo = ajustar_stock_atomico(id_producto, cantidad_a_sumar, usuario_id=usuario_id,
                                  tipo=tipo, descripcion=descripcion)
    if nuevo is None:
        return None
    return buscar_producto_por_id(id_producto)


def cambiar_estado_producto(id_producto, activo: bool):
    session = SessionLocal()
    try:
        producto = session.query(Producto).filter(Producto.id == id_producto).first()
        if producto is None: return None
        producto.activo = activo
        session.commit()
        session.refresh(producto)
        session.expunge(producto)
        return producto
    except SQLAlchemyError:
        session.rollback()
        return None
    finally:
        session.close()


def eliminar_producto(id_producto):
    session = SessionLocal()
    try:
        producto = session.query(Producto).filter(Producto.id == id_producto).first()
        if producto is None: return False
        session.delete(producto)
        session.commit()
        return True
    except SQLAlchemyError:
        session.rollback()
        return False
    finally:
        session.close()


# ─────────────────────────────────────────────
# USUARIOS
# ─────────────────────────────────────────────

def crear_usuario(nombre_usuario, password, rol):
    from backend.config import ROLES_VALIDOS
    nombre_usuario = nombre_usuario.strip()
    if not nombre_usuario:       raise ValueError("El nombre de usuario no puede estar vacío.")
    if len(nombre_usuario) < 3:  raise ValueError("El nombre de usuario debe tener al menos 3 caracteres.")
    if not password:             raise ValueError("La contraseña no puede estar vacía.")
    if len(password) < 4:        raise ValueError("La contraseña debe tener al menos 4 caracteres.")
    if rol not in ROLES_VALIDOS: raise ValueError(f"Rol inválido. Opciones: {', '.join(ROLES_VALIDOS)}.")

    session = SessionLocal()
    try:
        usuario = Usuario(nombre_usuario=nombre_usuario,
                          password=_hashear_password(password),
                          rol=rol, activo=True)
        session.add(usuario)
        session.commit()
        session.refresh(usuario)
        session.expunge(usuario)
        return usuario
    except IntegrityError:
        session.rollback()
        return None
    except SQLAlchemyError:
        session.rollback()
        return None
    finally:
        session.close()


def verificar_credenciales(nombre_usuario, password):
    """
    Valida usuario y contraseña EN EL SERVIDOR (el hash de la contraseña nunca viaja a las cajas).
    Retorna (estado, usuario): estado ∈ 'ok' | 'no_existe' | 'clave_incorrecta' | 'inactivo'.
    `usuario` solo viene con estado 'ok'.
    """
    usuario = buscar_usuario(nombre_usuario)
    if usuario is None:
        return ("no_existe", None)
    guardado = usuario.password or ""
    try:
        coincide = bcrypt.checkpw(password.encode("utf-8"), guardado.encode("utf-8"))
    except Exception:
        # Base de desarrollo con contraseñas en texto plano (no es un hash bcrypt)
        coincide = (not guardado.startswith("$2")) and password == guardado
    if not coincide:
        return ("clave_incorrecta", None)
    if not usuario.activo:
        return ("inactivo", None)
    return ("ok", usuario)


def listar_usuarios():
    session = SessionLocal()
    try:
        usuarios = session.query(Usuario).order_by(Usuario.nombre_usuario).all()
        for u in usuarios:
            session.expunge(u)
        return usuarios
    except SQLAlchemyError:
        return []
    finally:
        session.close()


def buscar_usuario(nombre_usuario):
    session = SessionLocal()
    try:
        usuario = session.query(Usuario).filter(
            Usuario.nombre_usuario == nombre_usuario
        ).first()
        if usuario:
            session.expunge(usuario)
        return usuario
    except SQLAlchemyError:
        return None
    finally:
        session.close()


def actualizar_usuario(id_usuario, nuevo_rol=None, nueva_password=None):
    from backend.config import ROLES_VALIDOS
    if nuevo_rol is not None and nuevo_rol not in ROLES_VALIDOS:
        raise ValueError(f"Rol inválido. Opciones: {', '.join(ROLES_VALIDOS)}.")
    if nueva_password is not None and len(nueva_password) < 4:
        raise ValueError("La contraseña debe tener al menos 4 caracteres.")

    session = SessionLocal()
    try:
        usuario = session.query(Usuario).filter(Usuario.id == id_usuario).first()
        if usuario is None: return None
        if nuevo_rol      is not None: usuario.rol      = nuevo_rol
        if nueva_password is not None: usuario.password = _hashear_password(nueva_password)
        session.commit()
        session.refresh(usuario)
        session.expunge(usuario)
        return usuario
    except SQLAlchemyError:
        session.rollback()
        return None
    finally:
        session.close()


def cambiar_estado_usuario(id_usuario, activo: bool):
    session = SessionLocal()
    try:
        usuario = session.query(Usuario).filter(Usuario.id == id_usuario).first()
        if usuario is None: return None
        usuario.activo = activo
        session.commit()
        session.refresh(usuario)
        session.expunge(usuario)
        return usuario
    except SQLAlchemyError:
        session.rollback()
        return None
    finally:
        session.close()


# ─────────────────────────────────────────────
# VENTAS
# ─────────────────────────────────────────────

def crear_venta(usuario_id, total, medio_pago="Efectivo", items=None):
    """
    Registra una venta completa con su medio de pago e ítems detallados.

    ⚠ NO descuenta stock. Para vender desde la interfaz usar
    registrar_venta_atomica() (transacciones.py), que hace todo junto y es
    seguro con varias cajas. Esta función queda solo por compatibilidad.

    Parámetros:
        usuario_id : int
        total      : float — total final (con IVA e interés si aplica)
        medio_pago : str   — "Efectivo" | "Débito" | "Crédito"
        items      : list[dict] — cada dict: {id, nombre, precio, cantidad}
                     Si es None o vacío se guarda la venta sin detalle.

    Retorna:
        Venta creada (éxito) | None (error)
    """
    if total < 0:
        raise ValueError("El total de la venta no puede ser negativo.")

    session = SessionLocal()
    try:
        from datetime import datetime
        venta = Venta(
            usuario_id=usuario_id,
            total=total,
            medio_pago=medio_pago,
            fecha=datetime.now(),
            pdv=pdv_actual(),
        )
        session.add(venta)
        session.flush()   # obtiene venta.id antes del commit

        if items:
            for item in items:
                iv = ItemVenta(
                    venta_id    = venta.id,
                    producto_id = item["id"],
                    nombre      = item["nombre"],
                    precio      = item["precio"],
                    cantidad    = item["cantidad"],
                    subtotal    = item["precio"] * item["cantidad"],
                )
                session.add(iv)

        session.commit()
        session.refresh(venta)
        session.expunge(venta)
        return venta
    except SQLAlchemyError as e:
        session.rollback()
        return None
    finally:
        session.close()


def listar_ventas():
    """
    Retorna todas las ventas con usuario e ítems precargados.
    """
    from sqlalchemy.orm import joinedload
    session = SessionLocal()
    try:
        ventas = (
            session.query(Venta)
            .options(
                joinedload(Venta.usuario),
                joinedload(Venta.items)
            )
            .order_by(Venta.id)
            .all()
        )
        from sqlalchemy.orm import make_transient
        resultado = []
        for v in ventas:
            u      = v.usuario
            items  = list(v.items)
            session.expunge(v)
            if u and u in session:
                session.expunge(u)
            for iv in items:
                if iv in session:
                    session.expunge(iv)
            v.usuario = u
            v.items   = items
            resultado.append(v)
        return resultado
    except SQLAlchemyError:
        return []
    finally:
        session.close()


# ─────────────────────────────────────────────
# PROVEEDORES
# ─────────────────────────────────────────────

def crear_proveedor(nombre, telefono, email, direccion):
    nombre = nombre.strip()
    if not nombre:
        raise ValueError("El nombre del proveedor no puede estar vacío.")
    session = SessionLocal()
    try:
        proveedor = Proveedor(nombre=nombre, telefono=telefono,
                              email=email, direccion=direccion)
        session.add(proveedor)
        session.commit()
        session.refresh(proveedor)
        session.expunge(proveedor)
        return proveedor
    except SQLAlchemyError:
        session.rollback()
        return None
    finally:
        session.close()


def listar_proveedores():
    session = SessionLocal()
    try:
        proveedores = session.query(Proveedor).order_by(Proveedor.nombre).all()
        for p in proveedores:
            session.expunge(p)
        return proveedores
    except SQLAlchemyError:
        return []
    finally:
        session.close()


# ─────────────────────────────────────────────
# MOVIMIENTOS DE STOCK
# ─────────────────────────────────────────────

def registrar_movimiento(producto_id, cantidad, tipo, usuario_id=None, descripcion=""):
    """
    Registra un movimiento de stock.
    tipo: "entrada" | "salida" | "ajuste" | "venta"
    cantidad: positivo = entrada, negativo = salida/ajuste
    """
    from backend.modelos.movimiento_stock import MovimientoStock
    from datetime import datetime
    session = SessionLocal()
    try:
        mov = MovimientoStock(
            producto_id=producto_id,
            usuario_id=usuario_id,
            cantidad=cantidad,
            tipo=tipo,
            descripcion=descripcion,
            fecha=datetime.now(),
            pdv=pdv_actual(),
        )
        session.add(mov)
        session.commit()
        session.refresh(mov)
        session.expunge(mov)
        return mov
    except Exception:
        session.rollback()
        return None
    finally:
        session.close()


def listar_movimientos(producto_id=None, limite=200):
    """
    Retorna los últimos movimientos de stock, opcionalmente filtrados por producto.
    """
    from backend.modelos.movimiento_stock import MovimientoStock
    from sqlalchemy.orm import joinedload
    session = SessionLocal()
    try:
        q = session.query(MovimientoStock).options(
            joinedload(MovimientoStock.producto),
            joinedload(MovimientoStock.usuario)
        )
        if producto_id:
            q = q.filter(MovimientoStock.producto_id == producto_id)
        movs = q.order_by(MovimientoStock.fecha.desc()).limit(limite).all()

        resultado = []
        for m in movs:
            prod = m.producto
            usu  = m.usuario
            session.expunge(m)
            if prod and prod in session:
                session.expunge(prod)
            if usu and usu in session:
                session.expunge(usu)
            m.producto = prod
            m.usuario  = usu
            resultado.append(m)
        return resultado
    except Exception:
        return []
    finally:
        session.close()


def eliminar_usuario(id_usuario):
    """Elimina permanentemente un usuario por su ID."""
    session = SessionLocal()
    try:
        usuario = session.query(Usuario).filter(Usuario.id == id_usuario).first()
        if usuario is None:
            return False
        session.delete(usuario)
        session.commit()
        return True
    except SQLAlchemyError:
        session.rollback()
        return False
    finally:
        session.close()


def listar_ventas_por_rango(fecha_desde=None, fecha_hasta=None):
    """
    Retorna ventas filtradas por rango de fechas (datetime objects).
    Si no se pasan fechas, devuelve todas las ventas.
    """
    from sqlalchemy.orm import joinedload
    from datetime import datetime, timedelta
    session = SessionLocal()
    try:
        q = session.query(Venta).options(
            joinedload(Venta.usuario),
            joinedload(Venta.items)
        )
        if fecha_desde:
            q = q.filter(Venta.fecha >= fecha_desde)
        if fecha_hasta:
            # incluir todo el día hasta
            fin = datetime.combine(fecha_hasta.date() if hasattr(fecha_hasta, 'date') else fecha_hasta,
                                   __import__('datetime').time(23, 59, 59))
            q = q.filter(Venta.fecha <= fin)
        ventas = q.order_by(Venta.id).all()

        resultado = []
        for v in ventas:
            u     = v.usuario
            items = list(v.items)
            session.expunge(v)
            if u and u in session:
                session.expunge(u)
            for iv in items:
                if iv in session:
                    session.expunge(iv)
            v.usuario = u
            v.items   = items
            resultado.append(v)
        return resultado
    except SQLAlchemyError:
        return []
    finally:
        session.close()


def resumen_hoy():
    """
    Retorna un dict con: total_vendido_hoy, cantidad_ventas_hoy, productos_stock_critico.
    """
    from datetime import datetime, date
    from sqlalchemy import func
    hoy = date.today()
    session = SessionLocal()
    try:
        inicio = datetime.combine(hoy, __import__('datetime').time(0, 0, 0))
        fin    = datetime.combine(hoy, __import__('datetime').time(23, 59, 59))

        resultado_ventas = session.query(
            func.count(Venta.id),
            func.coalesce(func.sum(Venta.total), 0.0)
        ).filter(Venta.fecha >= inicio, Venta.fecha <= fin).first()

        cantidad_ventas   = resultado_ventas[0] if resultado_ventas else 0
        total_vendido     = float(resultado_ventas[1]) if resultado_ventas else 0.0

        productos_criticos = session.query(Producto).filter(
            Producto.activo == True,
            Producto.stock <= Producto.stock_minimo
        ).count()

        return {
            "total_vendido_hoy": total_vendido,
            "cantidad_ventas_hoy": cantidad_ventas,
            "productos_stock_critico": productos_criticos,
        }
    except Exception:
        return {"total_vendido_hoy": 0.0, "cantidad_ventas_hoy": 0, "productos_stock_critico": 0}
    finally:
        session.close()


# ─────────────────────────────────────────────
# NOTIFICACIONES (repositor → admin)
# ─────────────────────────────────────────────

def crear_notificacion(mensaje, remitente_id=None):
    """
    Guarda una notificación en la BD para que el admin la vea al entrar.
    """
    import sqlite3
    from backend.config import NOMBRE_BD
    con = sqlite3.connect(NOMBRE_BD)
    cur = con.cursor()
    # Crear tabla si no existe (idempotente)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS notificaciones (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            mensaje      TEXT NOT NULL,
            remitente_id INTEGER,
            leida        INTEGER DEFAULT 0,
            fecha        TEXT DEFAULT (datetime('now'))
        )
    """)
    cur.execute(
        "INSERT INTO notificaciones (mensaje, remitente_id) VALUES (?, ?)",
        (mensaje, remitente_id)
    )
    con.commit()
    con.close()
    return True


def listar_notificaciones_no_leidas():
    """Retorna lista de dicts con las notificaciones sin leer."""
    import sqlite3
    from backend.config import NOMBRE_BD
    con = sqlite3.connect(NOMBRE_BD)
    cur = con.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS notificaciones (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            mensaje      TEXT NOT NULL,
            remitente_id INTEGER,
            leida        INTEGER DEFAULT 0,
            fecha        TEXT DEFAULT (datetime('now'))
        )
    """)
    rows = cur.execute(
        "SELECT id, mensaje, remitente_id, fecha FROM notificaciones WHERE leida = 0 ORDER BY fecha DESC"
    ).fetchall()
    con.close()
    return [{"id": r[0], "mensaje": r[1], "remitente_id": r[2], "fecha": r[3]} for r in rows]


def marcar_notificaciones_leidas():
    """Marca todas las notificaciones como leídas."""
    import sqlite3
    from backend.config import NOMBRE_BD
    con = sqlite3.connect(NOMBRE_BD)
    con.execute("UPDATE notificaciones SET leida = 1 WHERE leida = 0")
    con.commit()
    con.close()
