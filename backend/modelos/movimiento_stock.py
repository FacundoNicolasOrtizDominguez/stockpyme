from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship

from backend.base_datos.conexion import Base
from backend.config import pdv_actual


class MovimientoStock(Base):
    __tablename__ = "movimientos_stock"

    id          = Column(Integer, primary_key=True, index=True)
    producto_id = Column(Integer, ForeignKey("productos.id"), nullable=False)
    usuario_id  = Column(Integer, ForeignKey("usuarios.id"), nullable=True)
    cantidad    = Column(Integer, nullable=False)          # positivo = entrada, negativo = salida
    tipo        = Column(String(20), nullable=False)       # "entrada" | "salida" | "ajuste" | "venta"
    descripcion = Column(String(200), default="")
    fecha       = Column(DateTime, default=datetime.now)
    pdv         = Column(String(40), default=pdv_actual)   # punto de venta que originó el movimiento

    producto = relationship("Producto")
    usuario  = relationship("Usuario")

    def __repr__(self):
        return f"<MovimientoStock(prod={self.producto_id}, tipo={self.tipo}, cant={self.cantidad})>"
