import discord
from discord.ext import commands
import logging

from config import Config
from handlers.klugscheisser_handler import KlugscheisserHandler
from handlers.factcheck_handler import FactCheckHandler

logger = logging.getLogger(__name__)


class KlugscheisserCommand(commands.Cog):
    """Commands for managing the klugscheißer feature."""

    def __init__(self, bot, db_manager):
        self.bot = bot
        self.db_manager = db_manager
        self.klugscheisser_handler = KlugscheisserHandler(db_manager)
        self.factcheck_handler = FactCheckHandler(db_manager)

    @discord.app_commands.command(
        name="ks_join", description="🤓 Join the klugscheißer troll feature"
    )
    async def ks_join(self, interaction: discord.Interaction):
        """Allow user to opt in to the klugscheißer feature."""
        try:
            user_id = interaction.user.id
            user_preference = self.db_manager.get_klugscheisser_preference(user_id)

            if user_preference["opted_in"]:
                embed = discord.Embed(
                    title="🤓 Klugscheißer Status",
                    description="Du bist bereits für den Klugscheißer-Modus angemeldet!",
                    color=discord.Color.blue(),
                )

                if user_preference["created_at"]:
                    embed.add_field(
                        name="Angemeldet seit",
                        value=user_preference["created_at"].strftime("%d.%m.%Y %H:%M"),
                        inline=False,
                    )

                await interaction.response.send_message(embed=embed, ephemeral=True)
                return

            # Create confirmation embed
            embed = discord.Embed(
                title="⚠️ Klugscheißer-Modus Opt-in",
                description=(
                    "**Durch das Opt-in werden deine längeren Nachrichten (>100 Zeichen) "
                    f"gelegentlich ({Config.KLUGSCHEISSER_PROBABILITY}% Wahrscheinlichkeit) "
                    "an OpenAI zur Faktenerkennung und für ergänzende Informationen gesendet. 🤓\n\n"
                    "**Was passiert:**\n"
                    "• Deine Nachrichten werden analysiert\n"
                    "• Du bekommst hilfreiche Zusatzinfos\n"
                    "• Faktenchecks und Kontext zu deinen Nachrichten\n"
                    "• Andere können mit 🔍 Reaktionen Faktenchecks anfordern\n"
                    "• Du kannst jederzeit wieder aussteigen\n\n"
                    "**Möchtest du, dass ich ab und zu klugscheiße?**"
                ),
                color=discord.Color.orange(),
            )

            # Create view with buttons
            view = OptinConfirmView(self.db_manager, user_id)
            await interaction.response.send_message(
                embed=embed, view=view, ephemeral=True
            )

        except Exception as e:
            logger.error(f"Error in klugscheisser_optin command: {e}")
            await interaction.response.send_message(
                "❌ Fehler beim Anmelden für den Klugscheißer-Modus.", ephemeral=True
            )

    @discord.app_commands.command(
        name="ks_leave", description="😌 Leave the klugscheißer troll feature"
    )
    async def ks_leave(self, interaction: discord.Interaction):
        """Allow user to opt out of the klugscheißer feature."""
        try:
            user_id = interaction.user.id
            user_preference = self.db_manager.get_klugscheisser_preference(user_id)

            if not user_preference["opted_in"]:
                embed = discord.Embed(
                    title="😌 Klugscheißer Status",
                    description="Du bist bereits vom Klugscheißer-Modus abgemeldet!",
                    color=discord.Color.green(),
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return

            # Opt out the user
            success = self.db_manager.set_klugscheisser_preference(user_id, False)

            if success:
                embed = discord.Embed(
                    title="✅ Klugscheißer-Modus deaktiviert",
                    description="Du wurdest erfolgreich vom Klugscheißer-Feature abgemeldet. Ich halte jetzt die Klappe! 😌",
                    color=discord.Color.green(),
                )
                embed.add_field(
                    name="Was bedeutet das?",
                    value="• Deine Nachrichten werden nicht mehr an OpenAI gesendet\n• Du erhältst keine Klugscheißer-Antworten mehr\n• Andere können keine Faktenchecks für deine Nachrichten anfordern\n• Du kannst dich jederzeit wieder anmelden",
                    inline=False,
                )
            else:
                embed = discord.Embed(
                    title="❌ Fehler",
                    description="Beim Abmelden ist ein Fehler aufgetreten. Bitte versuche es später erneut.",
                    color=discord.Color.red(),
                )

            await interaction.response.send_message(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"Error in klugscheisser_optout command: {e}")
            await interaction.response.send_message(
                "❌ Fehler beim Abmelden vom Klugscheißer-Modus.", ephemeral=True
            )

    @discord.app_commands.command(
        name="ks_status", description="📊 Check your klugscheißer troll status"
    )
    async def ks_status(self, interaction: discord.Interaction):
        """Show user's current klugscheißer opt-in status."""
        try:
            user_id = interaction.user.id
            user_preference = self.db_manager.get_klugscheisser_preference(user_id)
            daily_factcheck_count = self.db_manager.get_daily_factcheck_count(user_id)

            if user_preference["opted_in"]:
                embed = discord.Embed(
                    title="🤓 Klugscheißer-Status: Aktiviert",
                    description="Du bist für den Klugscheißer-Modus angemeldet!",
                    color=discord.Color.blue(),
                )

                if user_preference["created_at"]:
                    embed.add_field(
                        name="Angemeldet seit",
                        value=user_preference["created_at"].strftime("%d.%m.%Y %H:%M"),
                        inline=True,
                    )

                embed.add_field(
                    name="Wahrscheinlichkeit",
                    value=f"{Config.KLUGSCHEISSER_PROBABILITY}%",
                    inline=True,
                )

                embed.add_field(
                    name="Mindestlänge",
                    value=f"{Config.KLUGSCHEISSER_MIN_LENGTH} Zeichen",
                    inline=True,
                )

                embed.add_field(
                    name="Faktenchecks heute",
                    value=f"{daily_factcheck_count}/{Config.FACTCHECK_DAILY_LIMIT_PER_USER}",
                    inline=True,
                )

                embed.add_field(
                    name="Reaktions-Emoji",
                    value=f"{Config.FACTCHECK_REACTION_EMOJI} für Faktenchecks",
                    inline=True,
                )

                embed.add_field(
                    name="Abmelden",
                    value="Verwende `/ks_leave` um dich abzumelden",
                    inline=False,
                )
            else:
                embed = discord.Embed(
                    title="😌 Klugscheißer-Status: Deaktiviert",
                    description="Du bist nicht für den Klugscheißer-Modus angemeldet.",
                    color=discord.Color.orange(),
                )

                embed.add_field(
                    name="Anmelden",
                    value="Verwende `/ks_join` um dich anzumelden",
                    inline=False,
                )

            await interaction.response.send_message(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"Error in klugscheisser_status command: {e}")
            await interaction.response.send_message(
                "❌ Fehler beim Abrufen des Status.", ephemeral=True
            )

    @discord.app_commands.command(
        name="ks_stats", description="📈 Show klugscheißer troll statistics"
    )
    async def ks_stats(self, interaction: discord.Interaction):
        """Show klugscheißer feature statistics."""
        try:
            stats = await self.klugscheisser_handler.get_statistics()
            factcheck_stats = await self.factcheck_handler.get_statistics()
            opted_in_count = self.db_manager.get_opted_in_users_count()

            embed = discord.Embed(
                title="🔍 Klugscheißer & Faktenchecker Statistics",
                color=discord.Color.blue(),
            )

            # Feature status
            status_emoji = "✅" if stats["klugscheisser_enabled"] else "❌"
            embed.add_field(
                name="Klugscheißer Status",
                value=f"{status_emoji} {'Enabled' if stats['klugscheisser_enabled'] else 'Disabled'}",
                inline=True,
            )

            # OpenAI availability
            api_emoji = "✅" if stats["openai_available"] else "❌"
            embed.add_field(
                name="OpenAI API",
                value=f"{api_emoji} {'Available' if stats['openai_available'] else 'Not available'}",
                inline=True,
            )

            # Configuration
            embed.add_field(
                name="Auto Probability",
                value=f"{stats['probability_percent']}%",
                inline=True,
            )

            embed.add_field(
                name="Min Length", value=f"{stats['min_length']} chars", inline=True
            )

            embed.add_field(
                name="Users on Cooldown",
                value=str(stats["users_on_cooldown"]),
                inline=True,
            )

            embed.add_field(
                name="Opted-in Users", value=str(opted_in_count), inline=True
            )

            # Fact-check specific info
            embed.add_field(
                name="Daily Limit",
                value=f"{factcheck_stats['daily_limit_per_user']} per user",
                inline=True,
            )

            embed.add_field(
                name="Reaktions-Emoji",
                value=factcheck_stats["reaction_emoji"],
                inline=True,
            )

            # Model info
            embed.add_field(
                name="AI Model", value=Config.KLUGSCHEISSER_MODEL, inline=True
            )

            embed.set_footer(
                text="Klugscheißer & Faktenchecker Features • Vibe Discord Bot"
            )

            await interaction.response.send_message(embed=embed)

        except Exception as e:
            logger.error(f"Error in klugscheisser_stats command: {e}")
            await interaction.response.send_message(
                "❌ Error retrieving statistics.", ephemeral=True
            )

    @discord.app_commands.command(
        name="ks_help", description="❓ Get help about the klugscheißer troll feature"
    )
    async def ks_help(self, interaction: discord.Interaction):
        """Show help and information about the klugscheißer feature."""
        try:
            embed = discord.Embed(
                title="🤓 Klugscheißer Troll - Hilfe",
                description="Der Bot kann als Internet-Troll auf deine Nachrichten reagieren!",
                color=discord.Color.blue(),
            )

            # How it works
            embed.add_field(
                name="🔄 Wie es funktioniert",
                value=(
                    f"1. **Opt-in**: `/ks_join` - Du stimmst zu\n"
                    f"2. **Wahrscheinlichkeit**: {Config.KLUGSCHEISSER_PROBABILITY}% Chance bei Nachrichten >{Config.KLUGSCHEISSER_MIN_LENGTH} Zeichen\n"
                    f"3. **AI Troll-Check**: Bot entscheidet ob Message trollbar ist\n"
                    f"4. **Troll Response**: Humorvolle Gegenmeinung wird gepostet"
                ),
                inline=False,
            )

            # Commands
            embed.add_field(
                name="📝 Commands",
                value=(
                    "`/ks_join` - Klugscheißer-Modus beitreten\n"
                    "`/ks_leave` - Klugscheißer-Modus verlassen\n"
                    "`/ks_status` - Deinen Status überprüfen\n"
                    "`/ks_stats` - Globale Statistiken anzeigen\n"
                    "`/ks_help` - Diese Hilfe anzeigen"
                ),
                inline=True,
            )

            # Fact-check commands
            embed.add_field(
                name="🔍 Faktenchecker Commands",
                value=(
                    "`/fact_left` - Verbleibende Faktenchecks\n"
                    "`/fact_stats` - Deine Faktencheck-Stats\n"
                    "`/bullshit` - Das Bullshit Board\n"
                    f"`{Config.FACTCHECK_REACTION_EMOJI}` Reaktion - Faktencheck anfordern"
                ),
                inline=True,
            )

            # Troll characteristics
            embed.add_field(
                name="🧌 Troll-Charakteristiken",
                value=(
                    "• **Immer kontra** - egal bei welchem Thema\n"
                    "• **Rechtschreibung kritisieren** - pedantisch\n"
                    "• **Fake-Facts erfinden** - unterstützt eigene Position\n"
                    "• **Troll-Phrasen** verwenden\n"
                    "• **Humorvoll provokativ** - nie verletzend"
                ),
                inline=False,
            )

            # Privacy
            embed.add_field(
                name="🔒 Datenschutz",
                value=(
                    "• **Opt-in erforderlich** - keine Verarbeitung ohne Zustimmung\n"
                    "• **Jederzeit kündbar** - mit `/ks_leave`\n"
                    "• **Transparent** - du weißt was passiert"
                ),
                inline=False,
            )

            # Example
            embed.add_field(
                name="💬 Beispiel",
                value=(
                    "**Du**: 'Pizza ist lecker'\n"
                    "**Bot**: '🤓 Pizza ist Mainstream! Wahre Foodies essen nur handgemachte Pasta. Change my mind! 🍕'"
                ),
                inline=False,
            )

            embed.set_footer(text="Vibe Discord Bot • Internet-Troll Klugscheißer")

            await interaction.response.send_message(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"Error in ks_help command: {e}")
            await interaction.response.send_message(
                "❌ Fehler beim Anzeigen der Hilfe.", ephemeral=True
            )

    @discord.app_commands.command(
        name="fact_left",
        description="🔢 Check how many fact-checks you have left today",
    )
    async def fact_left(self, interaction: discord.Interaction):
        """Show user's remaining fact-checks for today."""
        try:
            user_id = interaction.user.id
            daily_count = self.db_manager.get_daily_factcheck_count(user_id)
            remaining = Config.FACTCHECK_DAILY_LIMIT_PER_USER - daily_count

            embed = discord.Embed(
                title="🔢 Verbleibende Faktenchecks", color=discord.Color.blue()
            )

            if remaining > 0:
                embed.add_field(
                    name="Heute noch verfügbar",
                    value=f"**{remaining}** von {Config.FACTCHECK_DAILY_LIMIT_PER_USER}",
                    inline=True,
                )

                embed.add_field(
                    name="Bereits verwendet", value=f"{daily_count}", inline=True
                )

                embed.add_field(
                    name="Reaktions-Emoji",
                    value=f"Reagiere mit {Config.FACTCHECK_REACTION_EMOJI} auf Nachrichten",
                    inline=False,
                )

                if remaining <= 2:
                    embed.color = discord.Color.orange()
                    embed.add_field(
                        name="⚠️ Warnung",
                        value="Du hast nur noch wenige Faktenchecks übrig!",
                        inline=False,
                    )
            else:
                embed.color = discord.Color.red()
                embed.add_field(
                    name="❌ Limit erreicht",
                    value=f"Du hast bereits alle **{Config.FACTCHECK_DAILY_LIMIT_PER_USER}** Faktenchecks für heute verwendet.",
                    inline=False,
                )

                embed.add_field(
                    name="Reset",
                    value="Deine Faktenchecks werden um Mitternacht zurückgesetzt.",
                    inline=False,
                )

            await interaction.response.send_message(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"Error in factcheck_remaining command: {e}")
            await interaction.response.send_message(
                "❌ Fehler beim Abrufen der verbleibenden Faktenchecks.", ephemeral=True
            )

    @discord.app_commands.command(
        name="bullshit",
        description="🗑️ Show the bullshit board - users with worst fact-check scores from last 30 days",
    )
    async def bullshit(self, interaction: discord.Interaction):
        """Show the bullshit board with users ranked by worst fact-check scores from the last 30 days."""
        try:
            # Fixed to last 30 days, starting at page 0
            days = 30
            page_index = 0

            # Defer response as this might take a while
            await interaction.response.defer()

            # Get data for last 30 days, no minimum check requirement
            board_data = self.db_manager.get_bullshit_board_data(
                page=page_index,
                per_page=10,
                days=days,
                sort_by="score_asc",  # Lowest accuracy first (most bullshit)
            )
            total_count = self.db_manager.get_bullshit_board_count(days=days)
            total_pages = (total_count + 9) // 10  # Ceiling division

            if not board_data:
                embed = discord.Embed(
                    title="🗑️ Bullshit Board",
                    description="Keine Faktenchecks in den letzten 30 Tagen gefunden.",
                    color=discord.Color.orange(),
                )
                await interaction.followup.send(embed=embed)
                return

            # Format the bullshit board embed
            embed = self._format_bullshit_embed(board_data, page_index, total_pages, 30)

            # Create view with navigation buttons
            view = BullshitBoardView(page_index, total_pages, 30, self.db_manager)

            await interaction.followup.send(embed=embed, view=view)

        except Exception as e:
            logger.error(f"Error in bullshit_board command: {e}")
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "❌ Fehler beim Laden des Bullshit Boards.", ephemeral=True
                )
            else:
                await interaction.followup.send(
                    "❌ Fehler beim Laden des Bullshit Boards.", ephemeral=True
                )

    def _format_bullshit_embed(self, board_data, page, total_pages, days):
        """Format the bullshit board as a simplified Discord embed."""
        embed = discord.Embed(
            title="🗑️ Bullshit Board",
            description="User nach Faktenchecker-Genauigkeit sortiert (niedrigste zuerst)",
            color=discord.Color.red(),
        )

        if not board_data:
            embed.add_field(
                name="📭 Keine Daten",
                value="Keine Faktenchecks in den letzten 30 Tagen gefunden.",
                inline=False,
            )
            return embed

        # Create ranking list
        ranking_text = ""
        for i, user in enumerate(board_data):
            rank = (page * 10) + i + 1
            rank_emoji = self._get_rank_emoji(rank)
            score_emoji = self._get_score_emoji_for_board(user["avg_score"])

            # Simplified display: rank, username, score, check count
            ranking_text += f"{rank_emoji} {user['avg_score']:.1f}% **{user['username']}** {score_emoji} ({user['times_checked_by_others']} checks)\n"

        embed.add_field(name="🏆 Ranking", value=ranking_text, inline=False)

        # Add score explanation
        embed.add_field(
            name="📈 Score-Erklärung",
            value=(
                "**Sortierung: Niedrigste Genauigkeit zuerst (die größten Bullshitter oben)**\n"
                "Genauigkeit: 0% = völliger Bullshit, 100% = komplett korrekt\n"
                "Emojis: ❌ 0-20% • ⚠️ 21-40% • 🤔 41-60% • ✅ 61-80% • 💯 81-100%"
            ),
            inline=False,
        )

        # Add footer with pagination info
        embed.set_footer(
            text=f"Seite {page+1}/{total_pages} • Letzte 30 Tage • Self-Checks zählen nicht zum Score"
        )

        return embed

    def _get_rank_emoji(self, rank):
        """Get emoji for rank position."""
        if rank == 1:
            return "👑"
        elif rank == 2:
            return "🥈"
        elif rank == 3:
            return "🥉"
        elif rank <= 5:
            return "💩"
        else:
            return f"{rank}"

    def _get_score_emoji_for_board(self, score):
        """Get emoji for accuracy score in board context (consistent with factcheck handler)."""
        if score <= 20:
            return "❌"  # 0-20%: Definitiv falsch
        elif score <= 40:
            return "⚠️"  # 21-40%: Größtenteils falsch
        elif score <= 60:
            return "🤔"  # 41-60%: Gemischt
        elif score <= 80:
            return "✅"  # 61-80%: Größtenteils korrekt
        else:
            return "💯"  # 81-100%: Vollständig korrekt

    @discord.app_commands.command(
        name="fact_stats", description="📊 Show your personal fact-check statistics"
    )
    async def fact_stats(self, interaction: discord.Interaction):
        """Show user's personal fact-check statistics."""
        try:
            user_id = interaction.user.id
            daily_count = self.db_manager.get_daily_factcheck_count(user_id)
            user_stats = self.db_manager.get_factcheck_statistics(user_id, days=30)

            embed = discord.Embed(
                title="📊 Deine Faktenchecker-Statistiken", color=discord.Color.blue()
            )

            embed.add_field(
                name="Heute verwendet",
                value=f"{daily_count}/{Config.FACTCHECK_DAILY_LIMIT_PER_USER}",
                inline=True,
            )

            if user_stats and user_stats["total_requests"] > 0:
                embed.add_field(
                    name="Letzte 30 Tage",
                    value=f"{user_stats['total_requests']} Faktenchecks",
                    inline=True,
                )

                embed.add_field(
                    name="Durchschnittlicher Score",
                    value=f"{user_stats['avg_score']:.1f}/9",
                    inline=True,
                )

                if (
                    user_stats["min_score"] is not None
                    and user_stats["max_score"] is not None
                ):
                    embed.add_field(
                        name="Score-Bereich",
                        value=f"{user_stats['min_score']} - {user_stats['max_score']}",
                        inline=True,
                    )
            else:
                embed.add_field(
                    name="Letzte 30 Tage", value="Keine Faktenchecks", inline=True
                )

            embed.add_field(
                name="Reaktions-Emoji",
                value=f"Reagiere mit {Config.FACTCHECK_REACTION_EMOJI} auf Nachrichten",
                inline=False,
            )

            embed.set_footer(
                text=f"Tägliches Limit: {Config.FACTCHECK_DAILY_LIMIT_PER_USER} Faktenchecks"
            )

            await interaction.response.send_message(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"Error in factcheck_stats command: {e}")
            await interaction.response.send_message(
                "❌ Fehler beim Abrufen der Statistiken.", ephemeral=True
            )


class BullshitBoardView(discord.ui.View):
    """View with navigation buttons for bullshit board pagination."""

    def __init__(self, page, total_pages, days, db_manager):
        super().__init__(timeout=300.0)  # 5 minute timeout
        self.page = page
        self.total_pages = total_pages
        self.days = days
        self.db_manager = db_manager

        # Disable buttons if not applicable
        if page <= 0:
            self.previous_button.disabled = True
        if page >= total_pages - 1:
            self.next_button.disabled = True

    @discord.ui.button(label="◀️ Zurück", style=discord.ButtonStyle.secondary)
    async def previous_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        """Go to previous page."""
        try:
            if self.page > 0:
                new_page = self.page - 1

                # Get new data
                board_data = self.db_manager.get_bullshit_board_data(
                    page=new_page, per_page=10, days=self.days, sort_by="score_asc"
                )

                if board_data:
                    # Format new embed
                    embed = self._format_bullshit_embed(
                        board_data, new_page, self.total_pages, self.days
                    )

                    # Update view
                    new_view = BullshitBoardView(
                        new_page, self.total_pages, self.days, self.db_manager
                    )

                    await interaction.response.edit_message(embed=embed, view=new_view)
                else:
                    await interaction.response.send_message(
                        "❌ Keine Daten verfügbar.", ephemeral=True
                    )
            else:
                await interaction.response.send_message(
                    "❌ Du bist bereits auf der ersten Seite.", ephemeral=True
                )

        except Exception as e:
            logger.error(f"Error in previous_button: {e}")
            await interaction.response.send_message(
                "❌ Fehler beim Laden der vorherigen Seite.", ephemeral=True
            )

    @discord.ui.button(label="▶️ Weiter", style=discord.ButtonStyle.secondary)
    async def next_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        """Go to next page."""
        try:
            if self.page < self.total_pages - 1:
                new_page = self.page + 1

                # Get new data
                board_data = self.db_manager.get_bullshit_board_data(
                    page=new_page, per_page=10, days=self.days, sort_by="score_asc"
                )

                if board_data:
                    # Format new embed
                    embed = self._format_bullshit_embed(
                        board_data, new_page, self.total_pages, self.days
                    )

                    # Update view
                    new_view = BullshitBoardView(
                        new_page, self.total_pages, self.days, self.db_manager
                    )

                    await interaction.response.edit_message(embed=embed, view=new_view)
                else:
                    await interaction.response.send_message(
                        "❌ Keine Daten verfügbar.", ephemeral=True
                    )
            else:
                await interaction.response.send_message(
                    "❌ Du bist bereits auf der letzten Seite.", ephemeral=True
                )

        except Exception as e:
            logger.error(f"Error in next_button: {e}")
            await interaction.response.send_message(
                "❌ Fehler beim Laden der nächsten Seite.", ephemeral=True
            )

    @discord.ui.button(label="🔄 Aktualisieren", style=discord.ButtonStyle.primary)
    async def refresh_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        """Refresh current page."""
        try:
            # Get fresh data
            board_data = self.db_manager.get_bullshit_board_data(
                page=self.page, per_page=10, days=self.days, sort_by="score_asc"
            )
            total_count = self.db_manager.get_bullshit_board_count(days=self.days)
            new_total_pages = (total_count + 9) // 10

            if board_data:
                # Format refreshed embed
                embed = self._format_bullshit_embed(
                    board_data, self.page, new_total_pages, self.days
                )

                # Update view with potentially new total pages
                new_view = BullshitBoardView(
                    self.page, new_total_pages, self.days, self.db_manager
                )

                await interaction.response.edit_message(embed=embed, view=new_view)
            else:
                await interaction.response.send_message(
                    "❌ Keine Daten verfügbar.", ephemeral=True
                )

        except Exception as e:
            logger.error(f"Error in refresh_button: {e}")
            await interaction.response.send_message(
                "❌ Fehler beim Aktualisieren.", ephemeral=True
            )

    @discord.ui.select(
        placeholder="Sortierung wählen...",
        options=[
            discord.SelectOption(
                label="🗑️ Meister Bullshit",
                value="score_asc",
                description="Niedrigste Genauigkeit zuerst (Standard)",
            ),
            discord.SelectOption(
                label="🏆 Beste Genauigkeit",
                value="score_desc",
                description="Höchste Genauigkeit zuerst",
            ),
            discord.SelectOption(
                label="📝 Meist gecheckt",
                value="checked_desc",
                description="Nach Anzahl Checks von anderen",
            ),
            discord.SelectOption(
                label="🔥 Aktivste User",
                value="activity_desc",
                description="Nach Gesamt-Aktivität",
            ),
        ],
    )
    async def sort_select(
        self, interaction: discord.Interaction, select: discord.ui.Select
    ):
        """Change sorting of the bullshit board."""
        try:
            sort_by = select.values[0]

            # Get data with new sorting
            board_data = self.db_manager.get_bullshit_board_data(
                page=0,  # Reset to first page when changing sort
                per_page=10,
                days=self.days,
                sort_by=sort_by,
            )

            if board_data:
                # Format embed with new sorting
                embed = self._format_bullshit_embed(
                    board_data, 0, self.total_pages, self.days
                )

                # Update view (reset to page 0)
                new_view = BullshitBoardView(
                    0, self.total_pages, self.days, self.db_manager
                )
                # Set the select to show current selection
                for option in new_view.sort_select.options:
                    option.default = option.value == sort_by

                await interaction.response.edit_message(embed=embed, view=new_view)
            else:
                await interaction.response.send_message(
                    "❌ Keine Daten verfügbar.", ephemeral=True
                )

        except Exception as e:
            logger.error(f"Error in sort_select: {e}")
            await interaction.response.send_message(
                "❌ Fehler beim Sortieren.", ephemeral=True
            )

    def _format_bullshit_embed(self, board_data, page, total_pages, days):
        """Format the bullshit board as a simplified Discord embed (same as in command class)."""
        embed = discord.Embed(
            title="🗑️ Bullshit Board",
            description="User nach Faktenchecker-Genauigkeit sortiert (niedrigste zuerst)",
            color=discord.Color.red(),
        )

        if not board_data:
            embed.add_field(
                name="📭 Keine Daten",
                value="Keine Faktenchecks in den letzten 30 Tagen gefunden.",
                inline=False,
            )
            return embed

        # Create ranking list
        ranking_text = ""
        for i, user in enumerate(board_data):
            rank = (page * 10) + i + 1
            rank_emoji = self._get_rank_emoji(rank)
            score_emoji = self._get_score_emoji_for_board(user["avg_score"])

            # Simplified display: rank, username, score, check count
            ranking_text += f"{rank_emoji} {user['avg_score']:.1f}% **{user['username']}** {score_emoji} ({user['times_checked_by_others']} checks)\n"

        embed.add_field(name="🏆 Ranking", value=ranking_text, inline=False)

        # Add score explanation
        embed.add_field(
            name="📈 Score-Erklärung",
            value=(
                "**Sortierung: Niedrigste Genauigkeit zuerst (die größten Bullshitter oben)**\n"
                "Genauigkeit: 0% = völliger Bullshit, 100% = komplett korrekt\n"
                "Emojis: ❌ 0-20% • ⚠️ 21-40% • 🤔 41-60% • ✅ 61-80% • 💯 81-100%"
            ),
            inline=False,
        )

        # Add footer with pagination info
        embed.set_footer(
            text=f"Seite {page+1}/{total_pages} • Letzte 30 Tage • Self-Checks zählen nicht zum Score"
        )

        return embed

    def _get_rank_emoji(self, rank):
        """Get emoji for rank position."""
        if rank == 1:
            return "👑"
        elif rank == 2:
            return "🥈"
        elif rank == 3:
            return "🥉"
        elif rank <= 5:
            return "💩"
        else:
            return f"{rank}"

    def _get_score_emoji_for_board(self, score):
        """Get emoji for accuracy score in board context (consistent with factcheck handler)."""
        if score <= 20:
            return "❌"  # 0-20%: Definitiv falsch
        elif score <= 40:
            return "⚠️"  # 21-40%: Größtenteils falsch
        elif score <= 60:
            return "🤔"  # 41-60%: Gemischt
        elif score <= 80:
            return "✅"  # 61-80%: Größtenteils korrekt
        else:
            return "💯"  # 81-100%: Vollständig korrekt

    async def on_timeout(self):
        """Handle view timeout."""
        # Disable all buttons when timeout occurs
        for item in self.children:
            item.disabled = True


class OptinConfirmView(discord.ui.View):
    """View with confirmation buttons for opt-in process."""

    def __init__(self, db_manager, user_id):
        super().__init__(timeout=300.0)  # 5 minute timeout
        self.db_manager = db_manager
        self.user_id = user_id

    @discord.ui.button(
        label="🤓 Ja, klugscheiße ruhig!", style=discord.ButtonStyle.primary
    )
    async def confirm_optin(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        """Handle opt-in confirmation."""
        try:
            success = self.db_manager.set_klugscheisser_preference(self.user_id, True)

            if success:
                embed = discord.Embed(
                    title="✅ Klugscheißer-Modus aktiviert!",
                    description="Du wurdest erfolgreich für den Klugscheißer-Modus angemeldet! 🤓",
                    color=discord.Color.green(),
                )
                embed.add_field(
                    name="Was passiert jetzt?",
                    value=(
                        f"• Deine längeren Nachrichten (>{Config.KLUGSCHEISSER_MIN_LENGTH} Zeichen) werden "
                        f"mit {Config.KLUGSCHEISSER_PROBABILITY}% Wahrscheinlichkeit analysiert\n"
                        "• Du erhältst hilfreiche Zusatzinfos und Faktenchecks\n"
                        f"• Andere können mit {Config.FACTCHECK_REACTION_EMOJI} Reaktionen Faktenchecks anfordern\n"
                        "• Du kannst dich jederzeit wieder abmelden mit `/ks_leave`"
                    ),
                    inline=False,
                )
            else:
                embed = discord.Embed(
                    title="❌ Fehler",
                    description="Beim Anmelden ist ein Fehler aufgetreten. Bitte versuche es später erneut.",
                    color=discord.Color.red(),
                )

            # Disable all buttons
            for item in self.children:
                item.disabled = True

            await interaction.response.edit_message(embed=embed, view=self)

        except Exception as e:
            logger.error(f"Error in opt-in confirmation: {e}")
            await interaction.response.send_message(
                "❌ Fehler beim Bestätigen der Anmeldung.", ephemeral=True
            )

    @discord.ui.button(
        label="😌 Nein, lieber nicht", style=discord.ButtonStyle.secondary
    )
    async def cancel_optin(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        """Handle opt-in cancellation."""
        embed = discord.Embed(
            title="😌 Anmeldung abgebrochen",
            description="Du wurdest nicht für den Klugscheißer-Modus angemeldet. Du kannst dich jederzeit mit `/ks_join` anmelden.",
            color=discord.Color.orange(),
        )

        # Disable all buttons
        for item in self.children:
            item.disabled = True

        await interaction.response.edit_message(embed=embed, view=self)

    async def on_timeout(self):
        """Handle view timeout."""
        # Disable all buttons when timeout occurs
        for item in self.children:
            item.disabled = True


async def setup(bot, db_manager):
    """Setup function to add the cog to the bot."""
    await bot.add_cog(KlugscheisserCommand(bot, db_manager))
    logger.info("Klugscheißer command loaded")
