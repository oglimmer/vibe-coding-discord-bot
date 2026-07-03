"""Unit tests for the /about command's build info and runtime stats."""

import math
import unittest
from unittest.mock import Mock

import discord

from commands.about_command import AboutCommand


def _fake_guild(member_count):
    guild = Mock()
    guild.member_count = member_count
    return guild


def _make_cog(latency=0.042, guilds=None):
    bot = Mock()
    bot.latency = latency
    bot.guilds = guilds if guilds is not None else [_fake_guild(3), _fake_guild(5)]
    return AboutCommand(bot)


class TestFormatUptime(unittest.TestCase):
    def test_seconds_only(self):
        self.assertEqual(AboutCommand._format_uptime(5), "5s")

    def test_minutes_and_seconds(self):
        self.assertEqual(AboutCommand._format_uptime(61), "1m 1s")

    def test_full_breakdown(self):
        # 1 day, 1 hour, 1 minute, 1 second
        self.assertEqual(AboutCommand._format_uptime(90061), "1d 1h 1m 1s")

    def test_negative_clamped_to_zero(self):
        self.assertEqual(AboutCommand._format_uptime(-10), "0s")


class TestRuntimeFields(unittest.TestCase):
    def test_reports_servers_and_users(self):
        cog = _make_cog(guilds=[_fake_guild(3), _fake_guild(5)])
        fields = dict(cog._runtime_fields())
        self.assertEqual(fields["🌐 Servers"], "`2`")
        self.assertEqual(fields["👥 Users"], "`8`")

    def test_latency_rendered_in_ms(self):
        cog = _make_cog(latency=0.042)
        fields = dict(cog._runtime_fields())
        self.assertEqual(fields["📡 Latency"], "`42 ms`")

    def test_latency_nan_before_first_heartbeat(self):
        cog = _make_cog(latency=float("nan"))
        fields = dict(cog._runtime_fields())
        self.assertEqual(fields["📡 Latency"], "`n/a`")

    def test_member_count_none_treated_as_zero(self):
        cog = _make_cog(guilds=[_fake_guild(None), _fake_guild(4)])
        fields = dict(cog._runtime_fields())
        self.assertEqual(fields["👥 Users"], "`4`")

    def test_versions_present(self):
        cog = _make_cog()
        fields = dict(cog._runtime_fields())
        self.assertIn(discord.__version__, fields["🐍 Versions"])


class TestAboutEmbed(unittest.TestCase):
    def test_embed_includes_runtime_stats(self):
        cog = _make_cog()
        embed = cog._create_about_embed()
        names = {f.name for f in embed.fields}
        # The whole point of the feature: runtime stats show up in /about.
        for expected in ("⏱️ Uptime", "📡 Latency", "🌐 Servers", "👥 Users"):
            self.assertIn(expected, names)

    def test_uptime_seconds_non_negative(self):
        cog = _make_cog()
        self.assertGreaterEqual(cog._uptime_seconds(), 0)
        self.assertFalse(math.isnan(cog._uptime_seconds()))


if __name__ == "__main__":
    unittest.main()
