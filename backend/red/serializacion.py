"""
serializacion.py — Conversión de resultados (objetos del modelo, dataclasses, fechas, etc.)
a JSON y de vuelta, para que las cajas hablen con el servidor.

Reglas:
  • Los objetos del modelo (SQLAlchemy) se envían con los campos que ya tienen cargados;
    NUNCA se envía el campo `password` (el hash de contraseña no sale del servidor).
  • Los ciclos (venta.items[i].venta) se cortan: el cliente los reconstruye solo.
  • datetime/date se marcan con __dt__ / __d__ para recuperar el tipo original.
  • tuplas y conjuntos viajan como listas.

No importa SQLAlchemy: detecta los objetos del modelo por duck-typing.
"""
from dataclasses import fields, is_dataclass
from datetime import datetime, date

CAMPOS_EXCLUIDOS = frozenset({"password"})


def _es_orm(obj):
    return hasattr(obj, "_sa_instance_state")


def a_json(obj, _ancestros=()):
    if obj is None or isinstance(obj, (bool, int, float, str)):
        return obj
    if isinstance(obj, datetime):                      # datetime ANTES que date (es subclase)
        return {"__dt__": obj.isoformat(sep=" ")}
    if isinstance(obj, date):
        return {"__d__": obj.isoformat()}
    if isinstance(obj, (list, tuple, set, frozenset)):
        return [a_json(x, _ancestros) for x in obj if not _es_ciclo(x, _ancestros)]
    if isinstance(obj, dict):
        return {str(k): a_json(v, _ancestros) for k, v in obj.items() if not _es_ciclo(v, _ancestros)}
    if is_dataclass(obj) and not isinstance(obj, type):
        d = {f.name: a_json(getattr(obj, f.name), _ancestros) for f in fields(obj)}
        d["__tipo__"] = type(obj).__name__
        return d
    if _es_orm(obj):
        ancestros = _ancestros + (id(obj),)
        d = {"__tipo__": type(obj).__name__}
        for clave, valor in list(obj.__dict__.items()):
            if clave.startswith("_") or clave in CAMPOS_EXCLUIDOS:
                continue
            if _es_ciclo(valor, ancestros):
                continue
            d[clave] = a_json(valor, ancestros)
        return d
    raise TypeError(f"No se puede serializar un {type(obj).__name__}")


def _es_ciclo(valor, ancestros):
    return _es_orm(valor) and id(valor) in ancestros


def desde_json(dato, clases=None):
    """
    clases: {'Producto': Producto, 'VentaRegistrada': VentaRegistrada, ...} para reconstruir
    los objetos con __tipo__. Sin clases solo se recuperan fechas/listas/dicts.
    """
    clases = clases or {}
    if isinstance(dato, list):
        return [desde_json(x, clases) for x in dato]
    if isinstance(dato, dict):
        if "__dt__" in dato and len(dato) == 1:
            return datetime.fromisoformat(dato["__dt__"])
        if "__d__" in dato and len(dato) == 1:
            return date.fromisoformat(dato["__d__"])
        if "__tipo__" in dato:
            cls = clases.get(dato["__tipo__"])
            if cls is None:
                raise TypeError(f"Tipo desconocido recibido del servidor: {dato['__tipo__']}")
            if is_dataclass(cls):
                permitidos = {f.name for f in fields(cls)}
                admite = permitidos.__contains__
            else:
                admite = lambda k: hasattr(cls, k)          # atributos mapeados del modelo
            kwargs = {k: desde_json(v, clases) for k, v in dato.items()
                      if k != "__tipo__" and admite(k)}
            return cls(**kwargs)
        return {k: desde_json(v, clases) for k, v in dato.items()}
    return dato
