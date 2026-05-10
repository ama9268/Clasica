#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys


def main():
    """Run administrative tasks."""
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'clasica_project.settings.base')
    
    # Configuración de GDAL/PROJ para Windows (Evita el error de proj.db)
    if os.name == 'nt':
        proj_path = os.path.join(os.path.dirname(__file__), 'venv', 'Lib', 'site-packages', 'osgeo', 'data', 'proj')
        if os.path.exists(proj_path):
            os.environ['PROJ_LIB'] = proj_path

    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == '__main__':
    main()
