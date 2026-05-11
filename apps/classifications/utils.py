from apps.classifications.models import Classification, get_category
from apps.participations.models import Activity


def recalculate_positions(edition) -> None:
    """Rebuild Classification records for all valid activities in an edition."""
    valid = list(
        Activity.objects.filter(
            participation__edition=edition, is_valid=True
        ).select_related("participation__user")
        .order_by("elapsed_time_seconds")
    )
    category_counters: dict[str, int] = {}
    for pos, activity in enumerate(valid, start=1):
        participation = activity.participation
        user = participation.user
        category = get_category(user.birth_date, edition.date) if user.birth_date else "open"
        category_counters[category] = category_counters.get(category, 0) + 1
        Classification.objects.update_or_create(
            participation=participation,
            defaults={
                "time_seconds": activity.elapsed_time_seconds,
                "category": category,
                "position_overall": pos,
                "position_category": category_counters[category],
            },
        )
