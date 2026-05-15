"""
Simula participantes enviando tracks GPS a una edición.

Uso básico:
    python manage.py simulate_race --edition <pk>

Opciones:
    --edition   PK de la edición (obligatorio)
    --users     Número de usuarios válidos a simular (default: 5)
    --invalid   Número adicional de usuarios con track inválido (default: 2)
    --noise     Radio de ruido GPS en grados (default: 0.0001 ≈ 10 m)
    --clean     Elimina los usuarios de simulación creados previamente

Ejemplo completo:
    python manage.py simulate_race --edition 3 --users 8 --invalid 3
"""

import random
import string
from datetime import date, timedelta

from django.core.management.base import BaseCommand, CommandError
from django.contrib.gis.geos import LineString

from apps.accounts.models import UserProfile
from apps.editions.models import Edition
from apps.participations.models import Participation, Activity
from apps.participations.tasks import validate_track
from apps.classifications.utils import recalculate_positions

SIM_TAG = "sim__"  # prefijo de username para identificar usuarios simulados


def _random_suffix(n=6):
    return "".join(random.choices(string.ascii_lowercase + string.digits, k=n))


def _add_noise(coord, noise):
    lon, lat = coord
    return (
        lon + random.uniform(-noise, noise),
        lat + random.uniform(-noise, noise),
    )


def _build_valid_track(route_coords, noise):
    """Toma las coordenadas de la ruta oficial y añade ruido GPS mínimo."""
    return [_add_noise(c, noise) for c in route_coords]


def _build_invalid_track(route_coords):
    """Desplaza toda la ruta 0.05° (~5 km) para garantizar fallo de validación."""
    offset_lon = 0.05
    offset_lat = 0.05
    return [(lon + offset_lon, lat + offset_lat) for lon, lat in route_coords]


def _build_short_track(route_coords):
    """Usa solo el 30% inicial de la ruta (abandono simulado)."""
    cutoff = max(2, len(route_coords) // 3)
    return route_coords[:cutoff]


def _random_elapsed(min_h=1.0, max_h=3.5):
    return int(random.uniform(min_h * 3600, max_h * 3600))


def _random_speed(elapsed_s, distance_km):
    if distance_km and elapsed_s:
        base = (distance_km / (elapsed_s / 3600)) * random.uniform(0.95, 1.05)
        return round(base, 2)
    return round(random.uniform(20.0, 35.0), 2)


def _random_birth_date():
    """Genera fechas de nacimiento repartidas entre las categorías de edad."""
    year = random.randint(1955, 2000)
    month = random.randint(1, 12)
    day = random.randint(1, 28)
    return date(year, month, day)


class Command(BaseCommand):
    help = "Simula participantes con tracks GPS para testear validación y clasificación."

    def add_arguments(self, parser):
        parser.add_argument("--edition", type=int, required=True, help="PK de la edición")
        parser.add_argument("--users", type=int, default=5, help="Número de tracks válidos")
        parser.add_argument("--invalid", type=int, default=2, help="Número de tracks inválidos")
        parser.add_argument(
            "--noise", type=float, default=0.0001,
            help="Ruido GPS en grados (0.0001 ≈ 10 m)"
        )
        parser.add_argument(
            "--clean", action="store_true",
            help="Elimina usuarios de simulación previos antes de empezar"
        )

    def handle(self, *args, **options):
        edition_pk = options["edition"]
        n_valid = options["users"]
        n_invalid = options["invalid"]
        noise = options["noise"]
        do_clean = options["clean"]

        # --- Cargar edición ---
        try:
            edition = Edition.objects.get(pk=edition_pk)
        except Edition.DoesNotExist:
            raise CommandError(f"No existe ninguna edición con pk={edition_pk}.")

        route_geometry = edition.route_geometry
        distance_km = edition.route_distance_km or 0

        if not route_geometry and edition.route_variant:
            route_geometry = edition.route_variant.route_geometry
            distance_km = edition.route_variant.route_distance_km or distance_km
            self.stdout.write(
                self.style.NOTICE(
                    f"  Usando geometría de variante: {edition.route_variant.name}"
                )
            )

        if not route_geometry:
            raise CommandError(
                "La edición no tiene route_geometry ni variante con geometría. "
                "Sube un GPX primero."
            )

        route_coords = list(route_geometry.coords)
        edition_geometry = route_geometry

        self.stdout.write(
            self.style.NOTICE(
                f"\nEdición: {edition} | Ruta: {len(route_coords)} puntos | "
                f"{distance_km:.1f} km"
            )
        )

        # --- Limpieza opcional ---
        if do_clean:
            deleted, _ = UserProfile.objects.filter(
                username__startswith=SIM_TAG
            ).delete()
            self.stdout.write(self.style.WARNING(f"  Eliminados {deleted} objetos de simulaciones previas."))

        # --- Generar participantes ---
        results = []

        for i in range(n_valid + n_invalid):
            is_valid_scenario = i < n_valid
            suffix = _random_suffix()
            username = f"{SIM_TAG}{suffix}"
            full_name = f"Simulado {suffix.upper()}"

            user, _ = UserProfile.objects.get_or_create(
                username=username,
                defaults={
                    "full_name": full_name,
                    "birth_date": _random_birth_date(),
                    "email": f"{username}@sim.local",
                },
            )
            user.set_unusable_password()
            user.save(update_fields=["password"])

            participation, _ = Participation.objects.get_or_create(
                user=user, edition=edition
            )

            # --- Construir track ---
            if is_valid_scenario:
                coords = _build_valid_track(route_coords, noise)
                scenario_label = "válido"
            elif (i - n_valid) % 2 == 0:
                coords = _build_invalid_track(route_coords)
                scenario_label = "inválido (desviado)"
            else:
                coords = _build_short_track(route_coords)
                scenario_label = "inválido (corto)"

            track_geom = LineString(coords, srid=4326)
            elapsed = _random_elapsed()
            avg_speed = _random_speed(elapsed, distance_km)

            score, valid = validate_track(edition_geometry, track_geom)

            Activity.objects.update_or_create(
                participation=participation,
                defaults={
                    "elapsed_time_seconds": elapsed,
                    "is_valid": valid,
                    "validation_score": score,
                    "average_moving_speed": avg_speed,
                },
            )

            results.append((user.full_name, scenario_label, elapsed, score, valid))

            symbol = self.style.SUCCESS("[OK]") if valid else self.style.ERROR("[--]")
            self.stdout.write(
                f"  {symbol}  {full_name:25s} | {scenario_label:25s} | "
                f"{elapsed//3600:02d}:{(elapsed%3600)//60:02d}:{elapsed%60:02d} | "
                f"score={score:.3f} | valido={valid}"
            )

        # --- Recalcular clasificación ---
        recalculate_positions(edition)

        valid_count = sum(1 for *_, v in results if v)
        self.stdout.write(
            self.style.SUCCESS(
                f"\nListo. {valid_count}/{len(results)} tracks válidos. "
                f"Clasificación recalculada para '{edition}'.\n"
            )
        )
