from .base import *  # noqa

DEBUG = True

ALLOWED_HOSTS = ["*"]

# En desarrollo sin GDAL nativo en Windows, desactivar GeoDjango si falla
# y usar backend estándar. Comentar las líneas de abajo si GeoDjango funciona.
# DATABASES["default"]["ENGINE"] = "django.db.backends.postgresql"

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
