"""
Structural regression net for command wiring.

Runs the bot's real setup_hook with the heavy dependencies (DB, network,
handlers) faked out, and asserts every command cog loads. This catches the
class of bug where a command's setup() signature drifts from the way main.py
calls it — a mismatch that ruff, py_compile, and the feature test suites all
miss because none of them exercise the startup path.
"""

import asyncio
import os
import sys
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

# Import the project the same way the app does, without connecting to anything.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ.setdefault("DISCORD_TOKEN", "test-token")
os.environ.setdefault("DB_USER", "test")
os.environ.setdefault("DB_PASSWORD", "test")

import main  # noqa: E402

# Cogs that must always register when the bot starts.
EXPECTED_COGS = {
    "AboutCommand",
    "GreetingsCommand",
    "KlugscheisserCommand",
}


class TestCommandSetup(unittest.TestCase):
    async def _setup_and_drain(self):
        with (
            patch.object(main, "DatabaseManager", MagicMock()),
            patch.object(main, "MessageHandler", MagicMock()),
            patch.object(main, "FactCheckHandler", MagicMock()),
        ):
            bot = main.DiscordBot()
            # tree.sync() would hit the Discord API; everything else is offline.
            bot.tree.sync = AsyncMock()
            await bot.setup_hook()
        # Some cogs start discord.ext.tasks loops on load; without a connected
        # client they fail in before_loop. Cancel and await them so their
        # exceptions are retrieved instead of leaking as loop-teardown noise.
        pending = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
        for task in pending:
            task.cancel()
        await asyncio.gather(*pending, return_exceptions=True)
        return bot

    def _run_setup_hook(self):
        return asyncio.run(self._setup_and_drain())

    def test_setup_hook_wires_all_commands(self):
        bot = self._run_setup_hook()
        loaded = set(bot.cogs.keys())
        missing = EXPECTED_COGS - loaded
        self.assertFalse(
            missing,
            f"setup_hook did not register expected cogs: {missing} (loaded: {loaded})",
        )

    def test_about_command_is_registered(self):
        # The /about command specifically must be wired with a matching
        # setup() signature; a mismatch raises TypeError inside setup_hook.
        bot = self._run_setup_hook()
        self.assertIn("AboutCommand", bot.cogs)


if __name__ == "__main__":
    unittest.main()
