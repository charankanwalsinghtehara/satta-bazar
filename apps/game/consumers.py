import json

from asgiref.sync import async_to_sync
from channels.generic.websocket import JsonWebsocketConsumer

PUBLIC_GROUPS = {
    "prices": "satta_market_prices",
    "events": "satta_market_events",
    "rounds": "satta_round_status",
}


class MarketConsumer(JsonWebsocketConsumer):
    def connect(self):
        self.subscriptions = set()
        self.accept()
        self.send_json(
            {
                "type": "connected",
                "subscriptions": [],
                "recovery": "/api/v1/market/overview/",
            }
        )

    def receive(self, text_data=None, bytes_data=None, **kwargs):
        try:
            data = json.loads(text_data or "{}")
        except json.JSONDecodeError:
            self.close(code=4400)
            return
        if not isinstance(data, dict) or data.get("action") not in {"subscribe", "unsubscribe"}:
            self.close(code=4400)
            return
        topics = data.get("topics")
        if (
            not isinstance(topics, list)
            or not topics
            or any(not isinstance(topic, str) or topic not in PUBLIC_GROUPS for topic in topics)
        ):
            self.send_json({"type": "error", "detail": "Unknown subscription topic."})
            return
        joining = data["action"] == "subscribe"
        for topic in topics:
            group = PUBLIC_GROUPS[topic]
            if joining and topic not in self.subscriptions:
                async_to_sync(self.channel_layer.group_add)(group, self.channel_name)
                self.subscriptions.add(topic)
            elif not joining and topic in self.subscriptions:
                async_to_sync(self.channel_layer.group_discard)(group, self.channel_name)
                self.subscriptions.remove(topic)
        self.send_json(
            {
                "type": "subscriptions",
                "topics": sorted(self.subscriptions),
                "recovery": "/api/v1/market/overview/",
            }
        )

    def market_message(self, event):
        self.send_json(event["payload"])

    def disconnect(self, close_code):
        for topic in self.subscriptions:
            async_to_sync(self.channel_layer.group_discard)(PUBLIC_GROUPS[topic], self.channel_name)


class PrivateUserConsumer(JsonWebsocketConsumer):
    def connect(self):
        user = self.scope["user"]
        if not user.is_authenticated:
            self.close(code=4401)
            return
        self.group_name = f"satta_user_{user.pk.hex}"
        async_to_sync(self.channel_layer.group_add)(self.group_name, self.channel_name)
        self.accept()
        self.send_json({"type": "connected", "private": True})

    def receive(self, text_data=None, bytes_data=None, **kwargs):
        try:
            message = json.loads(text_data or "{}")
        except json.JSONDecodeError:
            self.close(code=4400)
            return
        if message != {"action": "ping"}:
            self.send_json({"type": "error", "detail": "Private socket only accepts ping."})
            return
        self.send_json({"type": "pong"})

    def private_message(self, event):
        self.send_json(event["payload"])

    def disconnect(self, close_code):
        if hasattr(self, "group_name"):
            async_to_sync(self.channel_layer.group_discard)(self.group_name, self.channel_name)
