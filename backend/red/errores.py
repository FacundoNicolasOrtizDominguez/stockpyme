"""Errores de la capa de red (el cliente los traduce a mensajes claros para el usuario)."""


class ErrorRed(RuntimeError):
    """Error genérico de comunicación con el servidor."""


class ErrorConexion(ErrorRed):
    """No se pudo hablar con el servidor (apagado, red caída, IP o puerto incorrectos)."""


class ErrorAutenticacionRed(ErrorRed):
    """El servidor rechazó el token de acceso."""
