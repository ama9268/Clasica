import io
import uuid

from PIL import Image, ImageOps
from django.core.files.base import ContentFile

MAX_DIMENSION = 1920
WEBP_QUALITY = 82


def optimize_image(image_file, quality=WEBP_QUALITY, max_dimension=MAX_DIMENSION):
    """
    Convierte una imagen subida a WebP, redimensionando si supera max_dimension px.
    Devuelve un ContentFile con extensión .webp, o el archivo original si falla.
    """
    try:
        raw = getattr(image_file, 'file', image_file)
        if hasattr(raw, 'seek'):
            raw.seek(0)
        img = Image.open(raw)
        img.load()
    except Exception:
        return image_file

    try:
        img = ImageOps.exif_transpose(img)
    except Exception:
        pass

    if img.mode not in ('RGB', 'RGBA'):
        img = img.convert('RGB')

    if max(img.width, img.height) > max_dimension:
        img.thumbnail((max_dimension, max_dimension), Image.LANCZOS)

    original_name = getattr(image_file, 'name', '') or ''
    stem = original_name.rsplit('.', 1)[0] if '.' in original_name else original_name
    if not stem:
        stem = uuid.uuid4().hex

    output = io.BytesIO()
    img.save(output, format='WEBP', quality=quality)
    output.seek(0)

    return ContentFile(output.read(), name=f"{stem}.webp")
