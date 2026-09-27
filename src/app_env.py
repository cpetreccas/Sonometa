"""Carga de la configuración local (.env) de Sonometa.

En la app instalada (PyInstaller) no hay carpeta de proyecto y el .env no va dentro
del instalador: el token personal de Discogs no debe distribuirse. Por eso el .env
se busca en un sitio fijo por usuario, %APPDATA%\\Sonometa\\.env (junto a la caché y
los catálogos, así sobrevive a reinstalaciones), y después en la raíz del proyecto
para desarrollo. Las variables ya definidas en el entorno tienen prioridad, y entre
los dos archivos manda el primero que defina cada variable.
"""
import os
import sys

from dotenv import load_dotenv

_loaded = False


def user_env_path() -> str:
    """Ruta del .env por usuario: %APPDATA%\\Sonometa\\.env."""
    base_dir = os.getenv("APPDATA") or os.path.expanduser("~")
    return os.path.join(base_dir, "Sonometa", ".env")


def _candidate_paths():
    yield user_env_path()
    if not getattr(sys, "frozen", False):
        # Desarrollo: .env en la raíz del proyecto (este archivo está en src/).
        yield os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")


def load_app_env() -> None:
    """Carga los .env disponibles una sola vez (llamadas repetidas no hacen nada)."""
    global _loaded
    if _loaded:
        return
    _loaded = True
    for path in _candidate_paths():
        if os.path.isfile(path):
            load_dotenv(path, override=False)
