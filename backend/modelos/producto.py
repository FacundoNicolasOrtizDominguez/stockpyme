from sqlalchemy import Column, Integer, String, Float, Boolean
from backend.base_datos.conexion import Base


class Producto(Base):
    __tablename__ = "productos"

    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String, nullable=False)
    categoria = Column(String, nullable=False)
    precio = Column(Float, nullable=False)
    stock = Column(Integer, default=0)
    stock_minimo = Column(Integer, default=5)
    activo = Column(Boolean, default=True)

    def tiene_stock_suficiente(self, cantidad):
        return self.stock >= cantidad

    def descontar_stock(self, cantidad):
        if self.tiene_stock_suficiente(cantidad):
            self.stock -= cantidad
            return True
        return False

    def alerta_stock_minimo(self):
        return self.stock <= self.stock_minimo

    def __repr__(self):
        return f"<Producto(nombre={self.nombre}, stock={self.stock})>"
