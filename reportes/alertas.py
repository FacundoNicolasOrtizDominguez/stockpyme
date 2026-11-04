def generar_reporte_alertas(inventario):
    """
    Recibe el inventario y devuelve una lista con las alertas de los productos
    que están por debajo o igual a su stock mínimo.
    """

    alertas = []
    for item in inventario:
        if item['stock'] <= item['stock_minimo']:
            alertas.append({
                "producto": item['nombre'],
                "stock_actual": item['stock'],
                "stock_minimo": item['stock_minimo'],
                "mensaje": f"⚠️ ALERTA: '{item['nombre']}' tiene stock crítico ({item['stock']} unidades)."
            })
    return alertas

#basicamente recorre el stock y te dice cual esta bajo el minimo