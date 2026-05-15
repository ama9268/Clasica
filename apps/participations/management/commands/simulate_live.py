"""
Simula participantes emitiendo posiciones GPS en tiempo real al Channel Layer.

Uso:
    python manage.py simulate_live --edition <pk>

Opciones:
    --edition   PK de la edicion (obligatorio)
    --interval  Segundos entre cada ronda de actualizaciones (default: 2)
    --step      Puntos de ruta a avanzar por intervalo (default: 10)
                  Usa --step 50 para demo rapida (~2 min con ruta de 5000 pts)
    --spread    Separacion inicial maxima entre corredores en puntos (default: 200)

Ctrl+C para detener.

Ejemplo rapido:
    python manage.py simulate_live --edition 3 --step 50 --interval 1
"""

import asyncio
import math

from django.core.management.base import BaseCommand, CommandError

from apps.accounts.models import UserProfile
from apps.editions.models import Edition
from apps.participations.models import Participation

SIM_TAG = "sim__"


def _haversine_speed(coord_a, coord_b, elapsed_s):
    """Velocidad aproximada en km/h entre dos puntos lon/lat."""
    if elapsed_s <= 0:
        return 0.0
    lon1, lat1 = math.radians(coord_a[0]), math.radians(coord_a[1])
    lon2, lat2 = math.radians(coord_b[0]), math.radians(coord_b[1])
    dlat, dlon = lat2 - lat1, lon2 - lon1
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    dist_km = 6371 * 2 * math.asin(math.sqrt(a))
    return round(dist_km / (elapsed_s / 3600), 2)


class Command(BaseCommand):
    help = "Simula posiciones GPS en vivo via Channel Layer para la vista de tracking."

    def add_arguments(self, parser):
        parser.add_argument("--edition", type=int, required=True)
        parser.add_argument("--interval", type=float, default=2.0,
                            help="Segundos entre rondas de actualizacion")
        parser.add_argument("--step", type=int, default=10,
                            help="Puntos de ruta a avanzar por intervalo")
        parser.add_argument("--spread", type=int, default=200,
                            help="Separacion inicial maxima entre corredores (puntos)")

    def handle(self, *args, **options):
        asyncio.run(self._run(options))

    async def _run(self, options):
        from channels.layers import get_channel_layer

        edition_pk = options["edition"]
        interval = options["interval"]
        step = options["step"]
        spread = options["spread"]

        # --- Cargar edicion ---
        try:
            edition = await Edition.objects.select_related("route_variant").aget(pk=edition_pk)
        except Edition.DoesNotExist:
            raise CommandError(f"No existe edicion pk={edition_pk}.")

        route_geometry = edition.route_geometry
        if not route_geometry and edition.route_variant_id:
            variant = edition.route_variant
            route_geometry = variant.route_geometry

        if not route_geometry:
            raise CommandError("La edicion no tiene ruta. Sube un GPX o asigna una variante.")

        route_coords = list(route_geometry.coords)
        total_pts = len(route_coords)

        # --- Cargar usuarios simulados inscritos ---
        user_ids = [
            p async for p in
            Participation.objects
            .filter(edition=edition, user__username__startswith=SIM_TAG)
            .values_list("user_id", flat=True)
        ]
        if not user_ids:
            raise CommandError(
                "No hay usuarios simulados inscritos en esta edicion. "
                "Ejecuta primero: python manage.py simulate_race --edition {edition_pk}"
            )

        users = {u.pk: u async for u in UserProfile.objects.filter(pk__in=user_ids)}

        # Posicion inicial escalonada para que no salgan todos juntos
        positions = {}
        for idx, uid in enumerate(user_ids):
            offset = (idx * (spread // max(len(user_ids), 1))) % spread
            positions[uid] = offset

        channel_layer = get_channel_layer()
        group_name = f"tracking_{edition_pk}"

        eta_steps = (total_pts - spread) // step
        eta_s = int(eta_steps * interval)

        self.stdout.write(
            self.style.NOTICE(
                f"\nEdicion : {edition}\n"
                f"Ruta    : {total_pts} puntos\n"
                f"Usuarios: {len(user_ids)}\n"
                f"Paso    : {step} pts / {interval}s\n"
                f"ETA     : ~{eta_s // 60}m {eta_s % 60}s hasta que el primero termine\n"
                f"Grupo WS: {group_name}\n"
                f"Ctrl+C para detener.\n"
            )
        )

        finished = set()
        tick = 0

        try:
            while len(finished) < len(user_ids):
                tick += 1
                active = 0
                for uid in user_ids:
                    if uid in finished:
                        continue
                    pos = positions[uid]
                    if pos >= total_pts:
                        finished.add(uid)
                        self.stdout.write(
                            self.style.SUCCESS(
                                f"  [FIN] {users[uid].full_name or users[uid].username}"
                            )
                        )
                        continue

                    coord = route_coords[pos]
                    prev_coord = route_coords[max(0, pos - step)]
                    speed = _haversine_speed(prev_coord, coord, interval)

                    await channel_layer.group_send(
                        group_name,
                        {
                            "type": "position_update",
                            "user_id": uid,
                            "username": users[uid].full_name or users[uid].username,
                            "lat": coord[1],
                            "lng": coord[0],
                            "speed": speed,
                        },
                    )
                    positions[uid] = pos + step
                    active += 1

                self.stdout.write(
                    f"  tick={tick:04d} | activos={active}/{len(user_ids)} "
                    f"| terminados={len(finished)}"
                )
                await asyncio.sleep(interval)

        except KeyboardInterrupt:
            self.stdout.write(self.style.WARNING("\nSimulacion detenida por el usuario."))
            return

        self.stdout.write(self.style.SUCCESS("\nTodos los corredores han terminado el recorrido."))
