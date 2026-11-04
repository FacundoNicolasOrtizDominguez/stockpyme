# StockPyME: sistema de stock y ventas

Aplicación de escritorio para controlar inventario y ventas en comercios, con una o varias cajas conectadas por red local.

Proyecto universitario en equipo, Universidad del Aconcagua, 2026. Repositorio original del grupo: [Daniel6051/proyecto-grupal](https://github.com/Daniel6051/proyecto-grupal).

## Qué hace

- Inicio de sesión con roles: administrador, vendedor y repositor. Las contraseñas se guardan con bcrypt.
- Registro de ventas con ticket en PDF.
- Stock en tiempo real, alertas de stock bajo y movimientos de inventario.
- Administración de usuarios, productos y proveedores.
- Métricas, y reportes en PDF y Excel.
- Tres temas de color: morado, oscuro y claro.
- Instalador para Windows, con asistente de configuración de red.

## Modos de funcionamiento

- **Local:** una sola PC con su propia base de datos.
- **Servidor:** esta PC guarda la base y atiende a las demás cajas por la red local. También se puede usar como caja.
- **Cliente:** esta PC no tiene base y usa la del servidor, con un token compartido.

Se configura desde la aplicación o con un archivo `config_local.json`; hay un modelo en `config_local.ejemplo.json`.

## Estructura

```
backend/base_datos   conexión, migraciones, transacciones y métricas
backend/modelos      producto, usuario, venta, proveedor y movimiento de stock
backend/red          cliente y servidor para trabajar con varias cajas
interfaz/            ventanas en Tkinter
reportes/            tickets, PDF y Excel
tests/               pruebas automáticas
```

## Instalación

Probado en Windows con Python 3.14.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python main.py
```

La primera vez, la aplicación pide crear el usuario administrador. Para probarla con usuarios de demostración, definí la variable `STOCKPYME_DEMO=1` antes de arrancar.

## Pruebas

```powershell
python -m unittest discover -s tests -t .
```

Son 59 pruebas de transacciones y concurrencia, métricas y comunicación en red.

## Generar el instalador

```powershell
pip install -r requirements.txt -r requirements-build.txt
.\build_windows.ps1
```

Empaqueta con PyInstaller y, si está instalado Inno Setup 6, genera el instalador.

## Tecnologías

Python, Tkinter, SQLite, SQLAlchemy, bcrypt, ReportLab, openpyxl, Pillow, PyInstaller e Inno Setup.
