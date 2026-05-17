"""End-to-end tests for the 1337 game using dpytest.

Covers the full daily flow: three users place bets via /1337, the scheduler
determines the winner, Discord roles are reassigned, and the announcement
message is posted to the guild's channel.
"""

import asyncio
from datetime import datetime, timedelta

import discord.ext.test as dpytest
import pytest

from game.game_1337_logic import Game1337Logic
from tests.conftest import FakeInteraction


pytestmark = pytest.mark.asyncio


async def _place_bet(bet_cog, member, guild, channel):
    interaction = FakeInteraction(member, guild, channel)
    await bet_cog.bet_1337.callback(bet_cog, interaction)
    return interaction


async def test_full_1337_flow_vote_winner_roles_and_announcement(
    bot_setup, monkeypatch
):
    """Three players vote, the latest bet wins, all three roles flip, and the
    announcement names the new General/Commander/Sergeant."""
    db = bot_setup["db"]
    game_cog = bot_setup["game_cog"]
    bet_cog = bot_setup["bet_cog"]
    guild = bot_setup["guild"]
    channel = bot_setup["channel"]
    m1, m2, m3 = bot_setup["members"]
    sergeant_role = bot_setup["roles"]["sergeant"]
    commander_role = bot_setup["roles"]["commander"]
    general_role = bot_setup["roles"]["general"]

    today = datetime.now().date()

    # Seed prior wins so today's result causes ALL three roles to change:
    #   365-day standings → m1(3) > m2(2) > m3(1 after today)  → General = m1
    #   14-day standings  → m2(2) > m1(1) = m3(1 after today)  → Commander = m2
    #   today's winner = m3 (neither General nor Commander)    → Sergeant = m3
    db.add_historical_winner(m1.id, m1.display_name, today - timedelta(days=30))
    db.add_historical_winner(m1.id, m1.display_name, today - timedelta(days=20))
    db.add_historical_winner(m1.id, m1.display_name, today - timedelta(days=10))
    db.add_historical_winner(m2.id, m2.display_name, today - timedelta(days=8))
    db.add_historical_winner(m2.id, m2.display_name, today - timedelta(days=5))

    # --- VOTE: three players each place a /1337 bet -----------------------
    int1 = await _place_bet(bet_cog, m1, guild, channel)
    await asyncio.sleep(0.01)
    int2 = await _place_bet(bet_cog, m2, guild, channel)
    await asyncio.sleep(0.01)
    int3 = await _place_bet(bet_cog, m3, guild, channel)

    # All three got ephemeral confirmations from the bet command.
    for ix in (int1, int2, int3):
        assert ix.response.messages, "bet command did not respond"
        assert "Bet placed" in (ix.response.messages[0].get("content") or "")
        assert ix.response.messages[0]["ephemeral"] is True

    bets = db.get_daily_bets(today)
    assert [b["user_id"] for b in bets] == [m1.id, m2.id, m3.id]

    # --- WINNER DETERMINATION --------------------------------------------
    # Choose a deterministic win time just after the latest bet so m3 is the
    # closest valid bet. The time is in the recent past, so the cog's
    # busy-wait short-circuits.
    win_time = bets[-1]["play_time"] + timedelta(milliseconds=10)
    monkeypatch.setattr(
        Game1337Logic,
        "get_daily_win_time",
        lambda self, game_date=None: win_time,
    )

    await game_cog._determine_daily_winner()

    # Winner is persisted: closest valid bet (m3) is recorded.
    winner = db.get_daily_winner(today)
    assert winner is not None, "winner row should exist after determination"
    assert winner["user_id"] == m3.id
    assert winner["bet_type"] == "regular"
    assert winner["millisecond_diff"] == 10

    # --- ROLE CHANGES -----------------------------------------------------
    # Each Discord member should have exactly the role assigned by the logic.
    assert general_role in m1.roles, "m1 (most 365-day wins) should be General"
    assert (
        commander_role in m2.roles
    ), "m2 (most 14-day non-General) should be Commander"
    assert sergeant_role in m3.roles, "m3 (today's winner) should be Sergeant"

    # And cross-role pollution shouldn't happen.
    assert commander_role not in m1.roles
    assert sergeant_role not in m1.roles
    assert general_role not in m2.roles
    assert sergeant_role not in m2.roles
    assert general_role not in m3.roles
    assert commander_role not in m3.roles

    # Database mirrors the Discord state.
    assert db.get_role_assignment(guild.id, "general")["user_id"] == m1.id
    assert db.get_role_assignment(guild.id, "commander")["user_id"] == m2.id
    assert db.get_role_assignment(guild.id, "sergeant")["user_id"] == m3.id

    # --- ANNOUNCEMENT POSTED ---------------------------------------------
    # Drain dpytest's queue and find the winner announcement (the only public
    # message produced by the flow — bet confirmations are ephemeral).
    posted = []
    while True:
        msg = (
            dpytest.sent_queue.get_nowait() if not dpytest.sent_queue.empty() else None
        )
        if msg is None:
            break
        posted.append(msg)

    contents = [m.content for m in posted if m.content]
    assert contents, "expected an announcement message in the channel"
    announcement = next((c for c in contents if "won with" in c), None)
    assert announcement is not None, f"no winner announcement found in: {contents}"

    assert m3.display_name in announcement
    assert "regular bet" in announcement
    # Role-change lines must reflect each transition.
    assert f"New General: {m1.display_name}" in announcement
    assert f"New Commander: {m2.display_name}" in announcement
    assert f"New Sergeant: {m3.display_name}" in announcement


async def test_bet_rejected_after_winner_decided(bot_setup, monkeypatch):
    """Once a winner exists for today, further /1337 attempts are rejected."""
    db = bot_setup["db"]
    game_cog = bot_setup["game_cog"]
    bet_cog = bot_setup["bet_cog"]
    guild = bot_setup["guild"]
    channel = bot_setup["channel"]
    m1, m2, _ = bot_setup["members"]

    today = datetime.now().date()

    # One bet, decide winner, then a second player tries to bet.
    await _place_bet(bet_cog, m1, guild, channel)

    bets = db.get_daily_bets(today)
    win_time = bets[-1]["play_time"] + timedelta(milliseconds=5)
    monkeypatch.setattr(
        Game1337Logic,
        "get_daily_win_time",
        lambda self, game_date=None: win_time,
    )
    await game_cog._determine_daily_winner()
    assert db.get_daily_winner(today) is not None

    late = await _place_bet(bet_cog, m2, guild, channel)
    assert late.response.messages, "late bet should still get a response"
    content = late.response.messages[0]["content"] or ""
    assert "game is over" in content.lower() or "game just ended" in content.lower()
