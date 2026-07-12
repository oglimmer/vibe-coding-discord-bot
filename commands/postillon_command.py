import asyncio
import logging
from zoneinfo import ZoneInfo

import discord
from discord import app_commands
from discord.ext import commands, tasks

from config import Config
from services.postillon.feed_client import PostillonFeedClient
from services.postillon.service import (
    FEED_KEY,
    PostillonService,
    create_postillon_embed,
)

logger = logging.getLogger(__name__)


class PostillonView(discord.ui.View):
    def __init__(self, posts: list[dict]):
        super().__init__(timeout=300)
        self.posts = posts
        self.page = 0
        self._update_buttons()

    def embed(self):
        embed = create_postillon_embed(self.posts[self.page])
        embed.set_footer(text=f"Der Postillon · {self.page + 1}/{len(self.posts)}")
        return embed

    def _update_buttons(self):
        self.previous.disabled = self.page == 0
        self.next.disabled = self.page >= len(self.posts) - 1

    @discord.ui.button(label="Zurück", style=discord.ButtonStyle.secondary)
    async def previous(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        self.page = max(0, self.page - 1)
        self._update_buttons()
        await interaction.response.edit_message(embed=self.embed(), view=self)

    @discord.ui.button(label="Weiter", style=discord.ButtonStyle.secondary)
    async def next(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.page = min(len(self.posts) - 1, self.page + 1)
        self._update_buttons()
        await interaction.response.edit_message(embed=self.embed(), view=self)


class PostillonCommand(commands.Cog):
    def __init__(self, bot, db_manager, service, poll_interval_minutes: int):
        self.bot = bot
        self.db_manager = db_manager
        self.service = service
        self.poll_interval_minutes = poll_interval_minutes
        self.feed_poll.change_interval(minutes=poll_interval_minutes)
        self.feed_poll.start()

    def cog_unload(self):
        self.feed_poll.cancel()

    @tasks.loop(minutes=15)
    async def feed_poll(self):
        try:
            result = await self.service.run_import()
            logger.info("Postillon feed poll finished: %s", result)
        except Exception:
            logger.exception("Unexpected error in Postillon feed poll")

    @feed_poll.before_loop
    async def before_feed_poll(self):
        await self.bot.wait_until_ready()

    @app_commands.command(
        name="postillon",
        description="Zeigt die neuesten gespeicherten Postillon-Beiträge",
    )
    @app_commands.describe(amount="Anzahl der Beiträge (1 bis 25)")
    async def postillon(
        self,
        interaction: discord.Interaction,
        amount: app_commands.Range[int, 1, 25] = 10,
    ):
        posts = await asyncio.to_thread(
            self.db_manager.get_recent_postillon_posts, amount
        )
        if not posts:
            await interaction.response.send_message(
                "Es wurden noch keine Postillon-Beiträge importiert.", ephemeral=True
            )
            return
        view = PostillonView(posts)
        await interaction.response.send_message(embed=view.embed(), view=view)

    @app_commands.command(
        name="postillon_status", description="Zeigt den Zustand des Postillon-Imports"
    )
    async def postillon_status(self, interaction: discord.Interaction):
        state, stats = await asyncio.gather(
            asyncio.to_thread(self.db_manager.get_postillon_feed_state, FEED_KEY),
            asyncio.to_thread(
                self.db_manager.get_postillon_stats, self.service.channel_id
            ),
        )
        state = state or {}
        deliveries = stats.get("deliveries", {})
        embed = discord.Embed(title="Postillon-Import", color=0xD71920)
        embed.add_field(name="Artikel", value=str(stats.get("posts", 0)))
        embed.add_field(name="Ausstehend", value=str(deliveries.get("pending", 0)))
        embed.add_field(name="Versendet", value=str(deliveries.get("sent", 0)))
        embed.add_field(
            name="Letzter Erfolg", value=str(state.get("last_success_at") or "Noch nie")
        )
        embed.add_field(
            name="Nächster Poll",
            value=self.feed_poll.next_iteration.astimezone(
                ZoneInfo(Config.POSTILLON_TIMEZONE)
            ).strftime("%d.%m.%Y %H:%M %Z")
            if self.feed_poll.next_iteration
            else "wird geplant",
        )
        embed.add_field(name="Intervall", value=f"{self.poll_interval_minutes} Minuten")
        embed.add_field(
            name="Initialimport",
            value="abgeschlossen" if state.get("initial_sync_completed") else "offen",
        )
        if state.get("last_error"):
            embed.add_field(
                name="Letzter Fehler",
                value=str(state["last_error"])[:1024],
                inline=False,
            )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(
        name="postillon_sync", description="Startet den Postillon-Import manuell"
    )
    @app_commands.default_permissions(manage_guild=True)
    async def postillon_sync(self, interaction: discord.Interaction):
        if not interaction.permissions.manage_guild:
            await interaction.response.send_message(
                "Dafür wird die Berechtigung Server verwalten benötigt.", ephemeral=True
            )
            return
        await interaction.response.defer(ephemeral=True, thinking=True)
        result = await self.service.run_import()
        await interaction.followup.send(
            "Import beendet: "
            f"Status `{result.status}`, gelesen {result.fetched}, neu {result.inserted}, "
            f"aktualisiert {result.updated}, versendet {result.delivered}, "
            f"fehlgeschlagen {result.failed}."
            + (f"\n{result.message}" if result.message else ""),
            ephemeral=True,
        )


async def setup(bot, db_manager):
    if Config.POSTILLON_POLL_INTERVAL_MINUTES <= 0:
        raise ValueError("POSTILLON_POLL_INTERVAL_MINUTES must be greater than zero")
    client = PostillonFeedClient(
        Config.POSTILLON_FEED_URL, Config.POSTILLON_REQUEST_TIMEOUT_SECONDS
    )
    service = PostillonService(
        bot=bot,
        db_manager=db_manager,
        feed_client=client,
        channel_id=Config.POSTILLON_CHANNEL_ID,
        announce_first_sync=Config.POSTILLON_ANNOUNCE_FIRST_SYNC,
        delivery_delay_seconds=Config.POSTILLON_DELIVERY_DELAY_SECONDS,
        lease_seconds=Config.POSTILLON_LEASE_SECONDS,
    )
    await bot.add_cog(
        PostillonCommand(
            bot,
            db_manager,
            service,
            Config.POSTILLON_POLL_INTERVAL_MINUTES,
        )
    )
