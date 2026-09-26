"""Shared win time and /1337-info output on days without a winner."""

from datetime import date, datetime, timedelta
from unittest.mock import Mock

from commands.info_1337_command import Info1337Command
from game.game_1337_logic import Game1337Logic
from tests.conftest import FakeDB

GAME_DATE = date(2026, 9, 26)
WIN_TIME = datetime(2026, 9, 26, 13, 37, 0, 628000)


def _bet(user_id, username, play_time, bet_type="early_bird"):
    return {
        "user_id": user_id,
        "username": username,
        "play_time": play_time,
        "game_date": GAME_DATE,
        "bet_type": bet_type,
        "server_id": None,
        "channel_id": None,
    }


def _fields(embed):
    return {f.name: f.value for f in embed.fields}


# --- win time -------------------------------------------------------------


def test_separate_instances_share_win_time():
    db = FakeDB()
    scheduler = Game1337Logic(db)
    info = Game1337Logic(db)

    assert scheduler.get_daily_win_time(GAME_DATE) == info.get_daily_win_time(GAME_DATE)


def test_stored_win_time_survives_restart():
    db = FakeDB()
    db.win_times[GAME_DATE] = WIN_TIME

    assert Game1337Logic(db).get_daily_win_time(GAME_DATE) == WIN_TIME


def test_win_time_falls_back_to_memory_when_db_fails():
    db = Mock()
    db.get_1337_win_time.return_value = None
    db.save_1337_win_time.return_value = None
    logic = Game1337Logic(db)

    first = logic.get_daily_win_time(GAME_DATE)

    assert logic.get_daily_win_time(GAME_DATE) == first
    db.save_1337_win_time.assert_called_once()


# --- explain_missing_winner ----------------------------------------------


def test_explain_no_bets():
    assert Game1337Logic(FakeDB()).explain_missing_winner([], WIN_TIME) == "no_bets"


def test_explain_all_bets_late():
    bets = [
        _bet(1, "a", WIN_TIME + timedelta(milliseconds=265)),
        _bet(2, "b", WIN_TIME + timedelta(seconds=32)),
    ]
    assert Game1337Logic(FakeDB()).explain_missing_winner(bets, WIN_TIME) == "all_late"


def test_explain_catastrophic():
    same = WIN_TIME - timedelta(milliseconds=100)
    bets = [_bet(1, "a", same, "regular"), _bet(2, "b", same, "regular")]
    assert (
        Game1337Logic(FakeDB()).explain_missing_winner(bets, WIN_TIME) == "catastrophic"
    )


def test_explain_winner_pending_right_after_win_time():
    bets = [_bet(1, "a", WIN_TIME - timedelta(milliseconds=100))]
    now = WIN_TIME + timedelta(seconds=2)
    assert (
        Game1337Logic(FakeDB()).explain_missing_winner(bets, WIN_TIME, now) == "pending"
    )


def test_explain_unknown_when_no_result_saved_long_after_win_time():
    bets = [_bet(1, "a", WIN_TIME - timedelta(milliseconds=100))]
    now = WIN_TIME + timedelta(hours=10)
    assert (
        Game1337Logic(FakeDB()).explain_missing_winner(bets, WIN_TIME, now) == "unknown"
    )


# --- /1337-info embed ------------------------------------------------------


def test_info_shows_no_winner_when_all_bets_late():
    db = FakeDB()
    db.win_times[GAME_DATE] = WIN_TIME
    late_bet = _bet(2, "late", WIN_TIME + timedelta(milliseconds=265))
    db.bets = [
        _bet(1, "venus", datetime(2026, 9, 26, 13, 37, 33, 334000)),
        late_bet,
    ]
    cog = Info1337Command(None, db)

    embed = cog._create_post_game_embed(late_bet, GAME_DATE)
    fields = _fields(embed)

    assert "No winner today" in fields["📅 Game Status"]
    assert "after the win time" in fields["📅 Game Status"]
    assert fields["🎯 Win Time"] == "`13:37:00.628`"
    assert fields["👥 Total Players"] == "**2**"
    assert "`265ms` after" in fields["📊 Your Performance"]
    assert "⏳ Status" not in fields


def test_info_still_pending_right_after_win_time():
    now = datetime.now()
    game_date = now.date()
    win_time = now - timedelta(seconds=1)
    db = FakeDB()
    db.win_times[game_date] = win_time
    bet = _bet(1, "early", win_time - timedelta(milliseconds=100), "regular")
    bet["game_date"] = game_date
    db.bets = [bet]
    cog = Info1337Command(None, db)

    fields = _fields(cog._create_post_game_embed(None, game_date))

    assert "still being calculated" in fields["⏳ Status"]


def test_info_no_winner_when_result_missing_long_after_win_time():
    # 2026-09-26: the win time was re-rolled after a restart, so a bet sits
    # before it but the scheduler never saved a winner.
    db = FakeDB()
    db.win_times[GAME_DATE] = datetime(2026, 9, 26, 13, 37, 59, 529000)
    bet = _bet(1, "oglimmer", datetime(2026, 9, 26, 13, 37, 34))
    db.bets = [bet]
    cog = Info1337Command(None, db)

    fields = _fields(cog._create_post_game_embed(bet, GAME_DATE))

    assert "⏳ Status" not in fields
    assert "No winner today" in fields["📅 Game Status"]
    assert "No result was saved" in fields["📅 Game Status"]
    assert "🎯 Win Time" not in fields
    assert "📊 Your Performance" not in fields
