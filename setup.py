from cx_Freeze import setup, Executable
import os
import sys
import json

# Crear config.json si no existe
if not os.path.exists('config.json'):
    with open('config.json', 'w') as f:
        json.dump({"nombre_empresa": "Mi Bar"}, f)

# Archivos adicionales a incluir
include_files = [
    'inventario_licores.db' if os.path.exists('inventario_licores.db') else None,
    'config.json',
    'icon.ico' if os.path.exists('icon.ico') else None
]
include_files = [f for f in include_files if f is not None]  # Eliminar None

# Configuración de build
build_options = {
    "packages": ["os", "sys", "tkinter", "matplotlib", "pandas", "sqlite3", "numpy", "json", "webbrowser"],
    "includes": ["matplotlib.backends.backend_tkagg"],
    "excludes": ["tkinter.test"],
    "include_files": include_files
}

# Configuración base para Windows
base = "Win32GUI" if sys.platform == "win32" else None

setup(
    name="InventarioLicores",
    version="1.2.0",
    description="Aplicación de inventario de licores",
    options={"build_exe": build_options},
    executables=[Executable("Inventarios.py", base=base)]
)