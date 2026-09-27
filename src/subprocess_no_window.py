"""Evita que cada proceso hijo (ffmpeg/ffprobe) abra una ventana de consola en Windows.

La app empaquetada con PyInstaller no tiene consola (console=False), y en ese caso
Windows crea una ventana nueva para cada programa de consola que se lanza. pydub
llama a ffmpeg/ffprobe con subprocess.Popen sin creationflags, así que al evaluar
la calidad se abría una terminal por canción. Aquí se sustituye subprocess.Popen
por una versión que añade CREATE_NO_WINDOW cuando quien llama no indica flags.

Debe importarse antes que pydub: pydub.utils hace `from subprocess import Popen`
y se queda con la clase que haya en ese momento.
"""
import subprocess
import sys

_installed = False


def install() -> None:
    global _installed
    if _installed or sys.platform != "win32":
        return
    _installed = True

    original_popen = subprocess.Popen
    no_window = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)

    class _NoWindowPopen(original_popen):
        def __init__(self, *args, **kwargs):
            if not kwargs.get("creationflags"):
                kwargs["creationflags"] = no_window
            super().__init__(*args, **kwargs)

    subprocess.Popen = _NoWindowPopen


install()
