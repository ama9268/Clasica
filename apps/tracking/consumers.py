import json
import logging
from channels.generic.websocket import AsyncWebsocketConsumer

logger = logging.getLogger(__name__)


class TrackingConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.edition_id = self.scope["url_route"]["kwargs"]["edition_id"]
        self.group_name = f"tracking_{self.edition_id}"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        logger.info("WS connected edition=%s", self.edition_id)

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)
        logger.info("WS disconnected edition=%s", self.edition_id)

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
        except json.JSONDecodeError:
            return
        user = self.scope.get("user")
        if not user or not user.is_authenticated:
            return
        payload = {
            "type": "position_update",
            "user_id": user.pk,
            "username": user.get_full_name() or user.username,
            "lat": data.get("lat"),
            "lng": data.get("lng"),
            "speed": data.get("speed"),
        }
        await self.channel_layer.group_send(self.group_name, payload)

    async def position_update(self, event):
        await self.send(text_data=json.dumps(event))
