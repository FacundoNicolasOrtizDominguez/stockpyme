"""
registro.py — Qué funciones puede ejecutar una caja remota en el servidor.

Es una LISTA BLANCA: el servidor solo ejecuta nombres de esta lista, nunca código arbitrario.
Este módulo no importa SQLAlchemy al cargarse (el cliente lo usa solo para conocer los nombres);
construir_registro() sí lo necesita y solo se llama en el servidor.
"""

FUNCIONES_PUBLICAS = (
    # productos
    "crear_producto", "listar_productos", "buscar_producto_por_id", "actualizar_producto",
    "actualizar_stock", "ajustar_stock", "cambiar_estado_producto", "eliminar_producto",
    # usuarios
    "crear_usuario", "listar_usuarios", "buscar_usuario", "actualizar_usuario",
    "cambiar_estado_usuario", "eliminar_usuario", "verificar_credenciales",
    # ventas y consolidación
    "crear_venta", "listar_ventas", "listar_ventas_por_rango", "resumen_hoy",
    "registrar_venta_atomica", "resumen_por_pdv", "ultimas_ventas",
    # proveedores, movimientos y avisos
    "crear_proveedor", "listar_proveedores", "registrar_movimiento", "listar_movimientos",
    "crear_notificacion", "listar_notificaciones_no_leidas", "marcar_notificaciones_leidas",
    # métricas del piloto
    "registrar_tiempo_manual", "registrar_conteo_fisico", "resumen_metricas", "datos_metricas",
)

# Funciones que solo leen: el cliente puede reintentarlas sin riesgo si falla la red.
PREFIJOS_SOLO_LECTURA = ("listar_", "buscar_", "resumen_", "ultimas_", "datos_")


def es_solo_lectura(nombre):
    return nombre.startswith(PREFIJOS_SOLO_LECTURA) and nombre != "verificar_credenciales"


def construir_registro():
    """{nombre: función} usando la implementación local (solo en el servidor)."""
    from backend.base_datos import repositorios_local as repo
    return {nombre: getattr(repo, nombre) for nombre in FUNCIONES_PUBLICAS}
