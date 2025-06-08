import discord
from discord.ext import commands

class BotClient(commands.Bot):
    def __init__(self, command_prefix, intents=None):
        if intents is None:
            intents = discord.Intents.default()
            intents.message_content = True
        super().__init__(command_prefix=command_prefix, intents=intents)
        self.load_commands()

    def load_commands(self):
        # Load command modules here
        from commands.greetings import GreetingsCommand
        self.greetings_command = GreetingsCommand(None)  # Pass None for now, will fix later

    async def on_ready(self):
        print(f'Logged in as {self.user} (ID: {self.user.id})')
        print('------')

    async def on_message(self, message):
        if message.author == self.user:
            return

        await self.handle_greetings(message)

        if message.content.startswith(self.command_prefix):
            await self.execute_command(message)

    async def handle_greetings(self, message):
        greetings = ["hello", "hi", "hey"]
        if any(greet in message.content.lower() for greet in greetings):
            await message.channel.send("👋")

    async def execute_command(self, message):
        command_name = message.content[len(self.command_prefix):].strip()
        if command_name == "greetings":
            await self.greetings_command.execute(message)