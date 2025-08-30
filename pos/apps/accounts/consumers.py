from channels.generic.websocket import AsyncWebsocketConsumer
import json

class TestConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        await self.accept()
        await self.send(text_data=json.dumps({
            "message": "WebSocket connection established!"
        }))

    async def receive(self, text_data):
        await self.send(text_data=json.dumps({
            "message": f"Received: {text_data}"
        }))

    async def disconnect(self, close_code):
        print("WebSocket disconnected")
