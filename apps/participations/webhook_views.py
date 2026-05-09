import hashlib
import hmac
import json
import logging
from django.conf import settings
from django.http import HttpRequest, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

logger = logging.getLogger(__name__)


@csrf_exempt
@require_http_methods(["GET", "POST"])
def strava_webhook(request: HttpRequest) -> JsonResponse:
    if request.method == "GET":
        return _handle_challenge(request)
    return _handle_event(request)


def _handle_challenge(request: HttpRequest) -> JsonResponse:
    mode = request.GET.get("hub.mode")
    token = request.GET.get("hub.verify_token")
    challenge = request.GET.get("hub.challenge")
    if mode == "subscribe" and token == settings.STRAVA_VERIFY_TOKEN:
        return JsonResponse({"hub.challenge": challenge})
    return JsonResponse({"error": "Forbidden"}, status=403)


def _handle_event(request: HttpRequest) -> JsonResponse:
    # Validar firma HMAC
    signature_header = request.headers.get("X-Strava-Signature", "")
    if not _verify_signature(request.body, signature_header):
        logger.warning("Strava webhook: firma inválida")
        return JsonResponse({"error": "Invalid signature"}, status=403)

    try:
        payload = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    # Responder 200 inmediatamente y encolar tarea Celery
    if payload.get("object_type") == "activity" and payload.get("aspect_type") == "create":
        from .tasks import process_strava_activity
        process_strava_activity.delay(
            activity_id=payload["object_id"],
            athlete_id=payload["owner_id"],
        )
    return JsonResponse({"status": "ok"})


def _verify_signature(body: bytes, header: str) -> bool:
    if not header or not settings.STRAVA_CLIENT_SECRET:
        return True  # en desarrollo sin secret configurado, permitir
    try:
        parts = dict(p.split("=", 1) for p in header.split(","))
        timestamp = parts.get("t", "")
        signature = parts.get("v1", "")
        message = f"{timestamp}.{body.decode()}".encode()
        expected = hmac.new(
            settings.STRAVA_CLIENT_SECRET.encode(), message, hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(expected, signature)
    except Exception:
        return False
