class MessageHandler:
    def __init__(self, bot_client):
        self.bot_client = bot_client

    async def handle_message(self, message):
        if message.author == self.bot_client.user:
            return

        if any(greeting in message.content.lower() for greeting in ["hello", "hi", "hey"]):
            await message.channel.send("👋 Hello!")

        # Additional message handling logic can be added here in the future.