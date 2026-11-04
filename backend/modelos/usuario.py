from sqlalchemy import Column, Integer, String, Boolean
from backend.base_datos.conexion import Base


class Usuario(Base):
    __tablename__ = "usuarios"

    id = Column(Integer, primary_key=True, index=True)
    nombre_usuario = Column(String, unique=True, nullable=False)
    password = Column(String, nullable=False)
    rol = Column(String, nullable=False)
    activo = Column(Boolean, default=True)

    def __repr__(self):
        return f"<Usuario(nombre_usuario={self.nombre_usuario}, rol={self.rol})>"
