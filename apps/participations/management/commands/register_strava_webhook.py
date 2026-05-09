import requests
from django.core.management.base import BaseCommand
from django.conf import settings


class Command(BaseCommand):
    help = "Registra (o verifica) la suscripción webhook de Strava a nivel de app"

    def add_arguments(self, parser):
        parser.add_argument("--callback-url", required=True, help="URL pública del webhook, ej: https://tudominio.com/webhooks/strava/")
        parser.add_argument("--delete", action="store_true", help="Elimina la suscripción existente")

    def handle(self, *args, **options):
        client_id = settings.STRAVA_CLIENT_ID
        client_secret = settings.STRAVA_CLIENT_SECRET
        verify_token = settings.STRAVA_VERIFY_TOKEN

        if not client_id or not client_secret:
            self.stderr.write(self.style.ERROR("STRAVA_CLIENT_ID o STRAVA_CLIENT_SECRET no configurados en .env"))
            return

        # Ver suscripciones existentes
        r = requests.get(
            "https://www.strava.com/api/v3/push_subscriptions",
            params={"client_id": client_id, "client_secret": client_secret},
            timeout=10,
        )
        self.stdout.write(f"Suscripciones actuales: {r.json()}")

        if options["delete"]:
            subs = r.json()
            if subs:
                sub_id = subs[0]["id"]
                d = requests.delete(
                    f"https://www.strava.com/api/v3/push_subscriptions/{sub_id}",
                    params={"client_id": client_id, "client_secret": client_secret},
                    timeout=10,
                )
                self.stdout.write(self.style.SUCCESS(f"Suscripción {sub_id} eliminada (status {d.status_code})"))
            return

        # Crear nueva suscripción
        callback_url = options["callback_url"]
        r = requests.post(
            "https://www.strava.com/api/v3/push_subscriptions",
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "callback_url": callback_url,
                "verify_token": verify_token,
            },
            timeout=10,
        )
        if r.status_code == 201:
            self.stdout.write(self.style.SUCCESS(f"Webhook registrado: {r.json()}"))
        else:
            self.stderr.write(self.style.ERROR(f"Error {r.status_code}: {r.text}"))
