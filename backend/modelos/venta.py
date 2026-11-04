from datetime import datetime
from sqlalchemy import Column, Integer, Float, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship

from backend.base_datos.conexion import Base
from backend.config import pdv_actual


class Venta(Base):
    __tablename__ = "ventas"

    id          = Column(Integer, primary_key=True, index=True)
    usuario_id  = Column(Integer, ForeignKey("usuarios.id"))
    total       = Column(Float, default=0)
    medio_pago  = Column(String(20), default="Efectivo")   # Efectivo / Débito / Crédito
    fecha       = Column(DateTime, default=datetime.now)
    pdv         = Column(String(40), default=pdv_actual)                   # punto de venta (caja/sucursal)
    duracion_seg = Column(Float, nullable=True)                            # tiempo de registro (métrica del piloto)
    op_id       = Column(String(40), nullable=True)                        # id único de la operación (evita ventas duplicadas)

    # relación con usuario e ítems
    usuario = relationship("Usuario")
    items   = relationship("ItemVenta", back_populates="venta",
                           cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Venta(id={self.id}, total={self.total}, medio={self.medio_pago})>"


class ItemVenta(Base):
    __tablename__ = "items_venta"

    id          = Column(Integer, primary_key=True, index=True)
    venta_id    = Column(Integer, ForeignKey("ventas.id"))
    producto_id = Column(Integer, ForeignKey("productos.id"))
    nombre      = Column(String(120))   # snapshot del nombre al momento de la venta
    precio      = Column(Float)         # snapshot del precio
    cantidad    = Column(Integer)
    subtotal    = Column(Float)

    venta    = relationship("Venta", back_populates="items")
    producto = relationship("Producto")

    def __repr__(self):
        return f"<ItemVenta(venta={self.venta_id}, prod={self.nombre}, x{self.cantidad})>"
