class EventHandler:
    def __init__(self, bot_client):
        self.bot_client = bot_client

    async def on_ready(self):
        print(f'Logged in as {self.bot_client.user.name} - {self.bot_client.user.id}')

    async def on_member_join(self, member):
        print(f'{member.name} has joined the server.')