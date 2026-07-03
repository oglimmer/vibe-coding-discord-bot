"""Shared fixtures for the e2e test suite (dpytest-based)."""

import os
import sys
from datetime import datetime, timedelta

# Make project root importable and prevent real DB connects.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ.setdefault("DISCORD_TOKEN", "test-token")
os.environ.setdefault("DB_USER", "test")
os.environ.setdefault("DB_PASSWORD", "test")

import discord
import discord.ext.test as dpytest
import pytest_asyncio
from discord.ext import commands

from config import Config
from commands.bet_1337_command import setup as setup_bet_1337_command
from commands.bet_1337_early_bird_command import (
    setup as setup_bet_1337_early_bird_command,
)
from commands.game_1337_command import setup as setup_game_1337_command
from game.game_1337_logic import Game1337Logic


class FakeDB:
    """In-memory stand-in for DatabaseManager covering the 1337 flow."""

    def __init__(self):
        self.bets = []
        self.winners = []
        self.role_assignments = {}

    # --- bets -------------------------------------------------------------

    def save_1337_bet(
        self,
        user_id,
        username,
        play_time,
        game_date,
        bet_type="regular",
        server_id=None,
        channel_id=None,
    ):
        if any(w["game_date"] == game_date for w in self.winners):
            return "game_closed"
        for b in self.bets:
            if b["user_id"] == user_id and b["game_date"] == game_date:
                b.update(play_time=play_time, bet_type=bet_type, username=username)
                return "saved"
        self.bets.append(
            {
                "user_id": user_id,
                "username": username,
                "play_time": play_time,
                "game_date": game_date,
                "bet_type": bet_type,
                "server_id": server_id,
                "channel_id": channel_id,
            }
        )
        return "saved"

    def get_user_bet(self, user_id, game_date):
        for b in self.bets:
            if b["user_id"] == user_id and b["game_date"] == game_date:
                return {
                    k: b[k] for k in ("user_id", "username", "play_time", "bet_type")
                }
        return None

    def get_daily_bets(self, game_date):
        rows = [b for b in self.bets if b["game_date"] == game_date]
        rows.sort(key=lambda b: b["play_time"])
        return [
            {
                k: b.get(k)
                for k in (
                    "user_id",
                    "username",
                    "play_time",
                    "bet_type",
                    "server_id",
                    "channel_id",
                )
            }
            for b in rows
        ]

    # --- winners ----------------------------------------------------------

    def decide_winner_atomically(self, game_date, win_time, pick_winner):
        if any(w["game_date"] == game_date for w in self.winners):
            return {"already_decided": True}

        bets = self.get_daily_bets(game_date)
        picked = pick_winner(bets, win_time)
        if picked is None or picked.get("catastrophic_event"):
            return picked

        self.winners.append(
            {
                "user_id": picked["user_id"],
                "username": picked["username"],
                "game_date": game_date,
                "win_time": win_time,
                "play_time": picked["play_time"],
                "bet_type": picked["bet_type"],
                "millisecond_diff": picked["millisecond_diff"],
                "server_id": picked.get("server_id"),
            }
        )
        return picked

    def add_historical_winner(
        self, user_id, username, game_date, bet_type="regular", millisecond_diff=0
    ):
        """Test helper to seed prior wins so role transitions can be exercised."""
        win_time = datetime.combine(game_date, datetime.min.time()).replace(
            hour=13, minute=37
        )
        self.winners.append(
            {
                "user_id": user_id,
                "username": username,
                "game_date": game_date,
                "win_time": win_time,
                "play_time": win_time,
                "bet_type": bet_type,
                "millisecond_diff": millisecond_diff,
                "server_id": None,
            }
        )

    def get_daily_winner(self, game_date):
        for w in self.winners:
            if w["game_date"] == game_date:
                return {
                    k: w[k]
                    for k in (
                        "user_id",
                        "username",
                        "win_time",
                        "play_time",
                        "bet_type",
                        "millisecond_diff",
                    )
                }
        return None

    def get_winner_stats(self, user_id=None, days=None):
        winners = self.winners
        if days is not None:
            cutoff = (datetime.now() - timedelta(days=days)).date()
            winners = [w for w in winners if w["game_date"] >= cutoff]

        if user_id is not None:
            return sum(1 for w in winners if w["user_id"] == user_id)

        agg = {}
        for w in winners:
            uid = w["user_id"]
            entry = agg.setdefault(
                uid, {"wins": 0, "last_win": w["game_date"], "username": w["username"]}
            )
            entry["wins"] += 1
            if w["game_date"] >= entry["last_win"]:
                entry["last_win"] = w["game_date"]
                entry["username"] = w["username"]

        result = [
            {
                "user_id": uid,
                "username": v["username"],
                "wins": v["wins"],
                "last_win": v["last_win"],
            }
            for uid, v in agg.items()
        ]
        result.sort(key=lambda r: (-r["wins"], -r["last_win"].toordinal()))
        return result

    # --- role assignments -------------------------------------------------

    def set_role_assignment(self, guild_id, user_id, role_type, role_id):
        self.role_assignments[(guild_id, role_type)] = {
            "user_id": user_id,
            "role_id": role_id,
        }
        return True

    def get_role_assignment(self, guild_id, role_type):
        entry = self.role_assignments.get((guild_id, role_type))
        if not entry:
            return None
        return {"user_id": entry["user_id"], "role_id": entry["role_id"]}

    def get_all_role_assignments(self, guild_id):
        return [
            {"user_id": v["user_id"], "role_type": rt, "role_id": v["role_id"]}
            for (gid, rt), v in self.role_assignments.items()
            if gid == guild_id
        ]

    def remove_role_assignment(self, guild_id, role_type):
        self.role_assignments.pop((guild_id, role_type), None)
        return True

    def close(self):
        pass


class FakeResponse:
    """Minimal stand-in for ``Interaction.response``."""

    def __init__(self):
        self.messages = []

    async def send_message(self, content=None, ephemeral=False, **kwargs):
        self.messages.append({"content": content, "ephemeral": ephemeral, **kwargs})


class FakeInteraction:
    """Just enough of ``discord.Interaction`` for the 1337 slash commands."""

    def __init__(self, user, guild, channel):
        self.user = user
        self.guild = guild
        self.guild_id = guild.id
        self.channel_id = channel.id
        self.response = FakeResponse()


@pytest_asyncio.fixture
async def bot_setup(monkeypatch):
    """Bring up a configured bot + FakeDB + dpytest guild with roles."""
    intents = discord.Intents.default()
    intents.message_content = True
    intents.members = True
    intents.guilds = True

    bot = commands.Bot(command_prefix="!", intents=intents)
    # dpytest needs the client's loop wired up before dispatching events.
    await bot._async_setup_hook()

    # Bets are placed via /1337 which validates against game time. We don't
    # care about the wall clock during tests, so disable the cutoff guard.
    monkeypatch.setattr(
        Game1337Logic,
        "is_game_time_passed",
        lambda self, current_time=None: False,
    )

    fake_db = FakeDB()

    await setup_bet_1337_command(bot, fake_db)
    await setup_bet_1337_early_bird_command(bot, fake_db)
    await setup_game_1337_command(bot, fake_db)

    game_cog = bot.get_cog("Game1337Command")
    # The cog auto-starts a daily scheduler in __init__; kill it so it can't
    # fire during the test.
    game_cog.daily_scheduler.cancel()
    if game_cog.winner_determination_task:
        game_cog.winner_determination_task.cancel()

    dpytest.configure(bot, guilds=1, text_channels=1, members=3)

    guild = bot.guilds[0]
    sergeant_role = await guild.create_role(name="Sergeant")
    commander_role = await guild.create_role(name="Commander")
    general_role = await guild.create_role(name="General")

    monkeypatch.setattr(Config, "SERGEANT_ROLE_ID", sergeant_role.id)
    monkeypatch.setattr(Config, "COMMANDER_ROLE_ID", commander_role.id)
    monkeypatch.setattr(Config, "GENERAL_ROLE_ID", general_role.id)
    monkeypatch.setattr(Config, "ANNOUNCEMENT_CHANNEL_ID", None)

    yield {
        "bot": bot,
        "db": fake_db,
        "game_cog": game_cog,
        "bet_cog": bot.get_cog("Bet1337Command"),
        "roles": {
            "sergeant": sergeant_role,
            "commander": commander_role,
            "general": general_role,
        },
        "guild": guild,
        "channel": guild.text_channels[0],
        "members": [m for m in guild.members if not m.bot][:3],
    }

    try:
        await dpytest.empty_queue()
    except Exception:
        pass
