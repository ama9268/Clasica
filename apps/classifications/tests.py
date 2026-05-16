import pytest
from datetime import date

from apps.classifications.models import Classification, get_category
from apps.participations.models import Activity, Participation
from apps.classifications.utils import recalculate_positions


# ── get_category ────────────────────────────────────────────────────────────

@pytest.mark.unit
class TestGetCategory:
    edition_date = date(2026, 6, 1)

    def test_category_open(self):
        birth = date(1996, 1, 1)  # 30 años
        assert get_category(birth, self.edition_date) == "open"

    def test_category_m40_exact(self):
        birth = date(1986, 6, 1)  # 40 años exactos en la fecha de edición
        assert get_category(birth, self.edition_date) == "m40"

    def test_category_m40_mid(self):
        birth = date(1981, 3, 15)  # 45 años
        assert get_category(birth, self.edition_date) == "m40"

    def test_category_m50(self):
        birth = date(1973, 1, 1)  # 53 años
        assert get_category(birth, self.edition_date) == "m50"

    def test_category_m60_exact(self):
        birth = date(1966, 6, 1)  # 60 años exactos
        assert get_category(birth, self.edition_date) == "m60"

    def test_category_m60_senior(self):
        birth = date(1954, 1, 1)  # 72 años
        assert get_category(birth, self.edition_date) == "m60"

    def test_category_boundary_open(self):
        birth = date(1987, 6, 2)  # cumple 39 en junio 2026 → open
        assert get_category(birth, self.edition_date) == "open"


# ── recalculate_positions ────────────────────────────────────────────────────

@pytest.mark.django_db
class TestRecalculatePositions:

    def test_single_finisher(self, user, edition, participation):
        Activity.objects.create(
            participation=participation,
            elapsed_time_seconds=3600,
            is_valid=True,
        )
        recalculate_positions(edition)
        c = Classification.objects.get(participation=participation)
        assert c.position_overall == 1
        assert c.position_category == 1
        assert c.time_seconds == 3600

    def test_two_finishers_same_category(self, user, edition):
        from apps.accounts.models import UserProfile
        u3 = UserProfile.objects.create_user(
            username="ciclista3", password="x",
            birth_date=date(1982, 1, 1),  # M40 igual que user (1985)
        )
        p1 = Participation.objects.create(user=user, edition=edition)
        p3 = Participation.objects.create(user=u3, edition=edition)
        Activity.objects.create(participation=p1, elapsed_time_seconds=3000, is_valid=True)
        Activity.objects.create(participation=p3, elapsed_time_seconds=3200, is_valid=True)

        recalculate_positions(edition)

        c1 = Classification.objects.get(participation=p1)
        c3 = Classification.objects.get(participation=p3)
        assert c1.position_overall == 1
        assert c1.position_category == 1
        assert c3.position_overall == 2
        assert c3.position_category == 2

    def test_two_finishers_different_categories(self, user, user2, edition):
        # user → M40 (1985), user2 → M50 (1973)
        p1 = Participation.objects.create(user=user, edition=edition)
        p2 = Participation.objects.create(user=user2, edition=edition)
        Activity.objects.create(participation=p1, elapsed_time_seconds=3600, is_valid=True)
        Activity.objects.create(participation=p2, elapsed_time_seconds=3500, is_valid=True)

        recalculate_positions(edition)

        c1 = Classification.objects.get(participation=p1)
        c2 = Classification.objects.get(participation=p2)
        assert c2.position_overall == 1  # user2 más rápido
        assert c1.position_overall == 2
        assert c1.position_category == 1  # primero en M40
        assert c2.position_category == 1  # primero en M50

    def test_invalid_activities_excluded(self, user, user2, edition):
        p1 = Participation.objects.create(user=user, edition=edition)
        p2 = Participation.objects.create(user=user2, edition=edition)
        Activity.objects.create(participation=p1, elapsed_time_seconds=3600, is_valid=True)
        Activity.objects.create(participation=p2, elapsed_time_seconds=3000, is_valid=False)

        recalculate_positions(edition)

        assert Classification.objects.filter(participation=p1).exists()
        assert not Classification.objects.filter(participation=p2).exists()
