"""
interfaz/componentes.py — Piezas de interfaz compartidas por todas las ventanas.
"""
import tkinter as tk
from interfaz import tema as T


def agregar_boton_volver(ventana, cabecera, comando=None, texto="← Volver"):
    """
    Pone una flecha "← Volver" en la esquina izquierda de la cabecera de `ventana`
    y hace que la tecla Esc haga lo mismo.

    - ventana : el Toplevel que se cierra.
    - cabecera: el Frame del encabezado (se coloca encima, sin mover los demás widgets).
    - comando : función a ejecutar; por defecto cierra la ventana. Se puede pasar una
                que pida confirmación (ej. la pantalla de venta con carrito).
    """
    accion = comando or ventana.destroy
    boton = tk.Button(
        cabecera, text=texto,
        font=("Courier New", 10, "bold"),
        bg=T.CARD, fg=T.FG,
        activebackground=T.HOVER, activeforeground=T.FG,
        relief="flat", bd=0, cursor="hand2",
        padx=10, pady=4, command=accion,
    )
    boton.place(x=12, rely=0.5, anchor="w")
    cabecera.after_idle(boton.lift)          # siempre por encima de los títulos
    ventana.bind("<Escape>", lambda _e: accion())
    return boton
