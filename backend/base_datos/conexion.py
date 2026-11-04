from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, declarative_base

from backend.config import DATABASE_URL, SQL_ECHO

# ==============================
# MOTOR DE BASE DE DATOS
# ==============================

# timeout: segundos que espera si otra caja está escribiendo (en vez de fallar
# enseguida con "database is locked").
engine = create_engine(
    DATABASE_URL,
    echo=SQL_ECHO,
    connect_args={"timeout": 15},
)


@event.listens_for(engine, "connect")
def _configurar_sqlite(dbapi_con, _registro):
    cur = dbapi_con.cursor()
    cur.execute("PRAGMA busy_timeout = 15000")
    cur.close()


# ==============================
# SESIONES
# ==============================

SessionLocal = sessionmaker(bind=engine)

# ==============================
# BASE DE MODELOS
# ==============================

Base = declarative_base()

# ==============================
# CREAR BASE DE DATOS
# ==============================

def crear_base_datos():
    Base.metadata.create_all(bind=engine)
