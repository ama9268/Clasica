from apps.editions.models import Edition


def open_edition(request):
    """Inyecta la edición abierta (si existe) en todos los templates."""
    edition = Edition.objects.filter(status=Edition.STATUS_OPEN).first()
    user_registered = False
    if edition and request.user.is_authenticated:
        user_registered = edition.participations.filter(user=request.user).exists()
    return {
        "open_edition": edition,
        "user_registered_open": user_registered,
    }
