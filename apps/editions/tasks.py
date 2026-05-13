import logging
from datetime import time

from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task
def auto_close_expired_editions():
    """Cierra ediciones 'open' que superaron las 21:30 sin ningún finisher válido."""
    from apps.editions.models import Edition
    from apps.participations.models import Activity

    now = timezone.localtime(timezone.now())
    if now.time() < time(21, 30):
        return

    editions = Edition.objects.filter(status=Edition.STATUS_OPEN, date=now.date())
    for edition in editions:
        has_finisher = Activity.objects.filter(
            participation__edition=edition, is_valid=True
        ).exists()
        if not has_finisher:
            edition.status = Edition.STATUS_CLOSED
            edition.save(update_fields=["status"])
            logger.info("Edición %s cerrada automáticamente (sin finishers a las 21:30).", edition)
