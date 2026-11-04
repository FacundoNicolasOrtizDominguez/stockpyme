from sqlalchemy import Column, Integer, String, Boolean

from backend.base_datos.conexion import Base


class Proveedor(Base):
    __tablename__ = "proveedores"

    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String, nullable=False)
    telefono = Column(String, nullable=True)
    email = Column(String, nullable=True)
    direccion = Column(String, nullable=True)
    activo = Column(Boolean, default=True)

    def __repr__(self):
        return f"<Proveedor(nombre={self.nombre}, telefono={self.telefono})>"
