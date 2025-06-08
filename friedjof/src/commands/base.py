class BaseCommand:
    def __init__(self, bot):
        self.bot = bot

    async def execute(self, context):
        raise NotImplementedError("This method should be overridden by subclasses.")
