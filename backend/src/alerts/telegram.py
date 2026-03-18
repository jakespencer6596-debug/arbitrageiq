"""
Telegram alert system.
Sends formatted alerts for arb opportunities and discrepancies.
Implements rate limiting and self-registration via /start command.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional

from constants import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, ALERT_COOLDOWN_SECONDS

logger = logging.getLogger(__name__)

_bot_app = None
_last_alerts: dict[str, datetime] = {}


def _get_chat_id() -> str:
    """Get current chat_id from env (may be updated at runtime)."""
    return os.environ.get("TELEGRAM_CHAT_ID", TELEGRAM_CHAT_ID)


def _is_rate_limited(market_id: str) -> bool:
    """Check if we've alerted on this market too recently."""
    if market_id not in _last_alerts:
        return False
    elapsed = (datetime.utcnow() - _last_alerts[market_id]).total_seconds()
    return elapsed < ALERT_COOLDOWN_SECONDS


def _log_alert(alert_type: str, market_id: str, preview: str, success: bool = True):
    """Save alert to database log."""
    try:
        from db.models import SessionLocal, AlertLog
        db = SessionLocal()
        db.add(AlertLog(
            alert_type=alert_type,
            market_id=market_id,
            message_preview=preview[:500],
            success=success,
        ))
        db.commit()
        db.close()
    except Exception as e:
        logger.error(f"Failed to log alert: {e}")


async def start_command(update, context):
    """
    Handles /start from Telegram.
    Captures chat_id, saves to .env, confirms registration.
    """
    chat_id = str(update.effective_chat.id)
    user_name = update.effective_user.first_name or "User"

    # Save to .env dynamically
    env_path = os.path.join(os.path.dirname(__file__), '..', '..', '..', '.env')
    try:
        lines = []
        if os.path.exists(env_path):
            with open(env_path, 'r') as f:
                lines = f.readlines()

        updated = False
        for i, line in enumerate(lines):
            if line.startswith("TELEGRAM_CHAT_ID="):
                lines[i] = f"TELEGRAM_CHAT_ID={chat_id}\n"
                updated = True

        if not updated:
            lines.append(f"TELEGRAM_CHAT_ID={chat_id}\n")

        with open(env_path, 'w') as f:
            f.writelines(lines)
    except Exception as e:
        logger.error(f"Failed to update .env with chat_id: {e}")

    # Update in-memory
    os.environ["TELEGRAM_CHAT_ID"] = chat_id

    await update.message.reply_text(
        f"ArbitrageIQ registered!\n\n"
        f"Welcome {user_name}! You'll receive alerts for:\n"
        "- Arbitrage opportunities (guaranteed profit)\n"
        "- Prediction market discrepancies\n\n"
        "Commands:\n"
        "/test - Send a test alert\n"
        "/status - Show system status",
        parse_mode=None,
    )

    _log_alert("system", "registration", f"User {user_name} registered chat_id={chat_id}")
    logger.info(f"Telegram user registered: {user_name} (chat_id={chat_id})")


async def test_command(update, context):
    """Send a test alert to verify connection."""
    await update.message.reply_text(
        "Test Alert - ArbitrageIQ\n\n"
        "ARB FOUND: +2.3% profit\n"
        "Event: Cowboys vs Eagles (NFL)\n"
        "Leg 1: DraftKings Cowboys -3 @ 1.926 -> Stake $523\n"
        "Leg 2: FanDuel Eagles +3.5 @ 2.15 -> Stake $477\n"
        "Profit on $1,000: $23.00\n\n"
        "This is a test message - not a real opportunity.",
        parse_mode=None,
    )


async def status_command(update, context):
    """Show system status."""
    try:
        from db.models import SessionLocal, SystemStatus, MarketPrice, ArbOpportunity
        db = SessionLocal()
        statuses = db.query(SystemStatus).all()
        market_count = db.query(MarketPrice).filter_by(is_active=True).count()
        arb_count = db.query(ArbOpportunity).filter_by(is_active=True).count()
        db.close()

        lines = ["ArbitrageIQ Status\n"]
        lines.append(f"Markets tracked: {market_count}")
        lines.append(f"Active arbs: {arb_count}")
        lines.append("")
        for s in statuses:
            last = s.last_success.strftime("%H:%M UTC") if s.last_success else "never"
            credits = f" ({s.credits_remaining} credits)" if s.credits_remaining else ""
            lines.append(f"  {s.source}: last OK {last}{credits}")

        await update.message.reply_text("\n".join(lines), parse_mode=None)
    except Exception as e:
        await update.message.reply_text(f"Error fetching status: {e}", parse_mode=None)


async def send_arb_alert(opp) -> bool:
    """
    Send a formatted arbitrage opportunity alert.
    Accepts ArbOpportunityResult or dict.
    Returns True if sent successfully.
    """
    chat_id = _get_chat_id()
    if chat_id == "PENDING" or not _bot_app:
        logger.warning("Telegram not configured - skipping arb alert")
        return False

    if isinstance(opp, dict):
        event_name = opp.get("event_name", "Unknown")
        profit_pct = opp.get("profit_pct", 0)
        legs = opp.get("legs", [])
        profit_on_1000 = opp.get("profit_on_1000", 0)
    else:
        event_name = opp.event_name
        profit_pct = opp.profit_pct
        legs = opp.legs
        profit_on_1000 = opp.profit_on_1000

    market_id = f"arb_{event_name}"
    if _is_rate_limited(market_id):
        return False

    legs_text = ""
    for i, leg in enumerate(legs):
        if isinstance(leg, dict):
            src = leg.get("source", "")
            out = leg.get("outcome", "")
            odds = leg.get("decimal_odds", 0)
            stake = leg.get("stake_dollars", 0)
        else:
            src = leg.source
            out = leg.outcome
            odds = leg.decimal_odds
            stake = leg.stake_dollars
        legs_text += f"  Leg {i+1}: {src.title()} {out.title()} @ {odds:.2f} -> Stake ${stake:.0f}\n"

    msg = (
        f"ARB FOUND: +{profit_pct*100:.1f}% profit\n\n"
        f"Event: {event_name}\n"
        f"{legs_text}"
        f"Profit on $1,000: ${profit_on_1000:.2f}\n"
        f"Time: {datetime.utcnow().strftime('%H:%M:%S UTC')}"
    )

    try:
        await _bot_app.bot.send_message(chat_id=chat_id, text=msg, parse_mode=None)
        _last_alerts[market_id] = datetime.utcnow()
        _log_alert("arb", market_id, msg[:200])
        return True
    except Exception as e:
        logger.error(f"Failed to send arb alert: {e}")
        _log_alert("arb", market_id, str(e), success=False)
        return False


async def send_discrepancy_alert(disc) -> bool:
    """
    Send a formatted discrepancy alert.
    Accepts DiscrepancyResult or dict.
    Returns True if sent successfully.
    """
    chat_id = _get_chat_id()
    if chat_id == "PENDING" or not _bot_app:
        return False

    if isinstance(disc, dict):
        market_id = disc.get("market_id", "")
        event_name = disc.get("event_name", "Unknown")
        source = disc.get("source", "")
        category = disc.get("category", "")
        market_prob = disc.get("market_probability", 0)
        data_prob = disc.get("data_implied_probability", 0)
        edge = disc.get("edge_pct", 0)
        direction = disc.get("direction", "")
        data_source = disc.get("data_source", "")
        data_value = disc.get("data_value", 0)
        data_unit = disc.get("data_unit", "")
        confidence = disc.get("confidence", "medium")
    else:
        market_id = disc.market_id
        event_name = disc.event_name
        source = disc.source
        category = disc.category
        market_prob = disc.market_probability
        data_prob = disc.data_implied_probability
        edge = disc.edge_pct
        direction = disc.direction
        data_source = disc.data_source
        data_value = disc.data_value
        data_unit = disc.data_unit
        confidence = disc.confidence

    if _is_rate_limited(market_id):
        return False

    direction_text = "BUY YES" if direction == "BUY_YES" else "BUY NO"

    msg = (
        f"DISCREPANCY: {category.title()} market mispriced\n\n"
        f"Market: {event_name}\n"
        f"Platform: {source.title()}\n"
        f"Market price: {market_prob*100:.0f}%\n"
        f"{data_source.replace('_',' ').title()}: {data_value:.1f} {data_unit} -> {data_prob*100:.0f}% implied\n"
        f"Edge: {edge*100:.0f}% -> {direction_text}\n"
        f"Confidence: {confidence.title()}\n"
        f"Time: {datetime.utcnow().strftime('%H:%M:%S UTC')}"
    )

    try:
        await _bot_app.bot.send_message(chat_id=chat_id, text=msg, parse_mode=None)
        _last_alerts[market_id] = datetime.utcnow()
        _log_alert("discrepancy", market_id, msg[:200])
        return True
    except Exception as e:
        logger.error(f"Failed to send discrepancy alert: {e}")
        _log_alert("discrepancy", market_id, str(e), success=False)
        return False


async def init_bot():
    """Initialize the Telegram bot and start polling for commands."""
    global _bot_app

    if not TELEGRAM_BOT_TOKEN or TELEGRAM_BOT_TOKEN == "None":
        logger.warning("No Telegram token - alerts disabled")
        return

    try:
        from telegram import Update
        from telegram.ext import Application, CommandHandler

        _bot_app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
        _bot_app.add_handler(CommandHandler("start", start_command))
        _bot_app.add_handler(CommandHandler("test", test_command))
        _bot_app.add_handler(CommandHandler("status", status_command))

        await _bot_app.initialize()
        await _bot_app.start()
        await _bot_app.updater.start_polling()

        # Send startup notification if chat_id is configured
        chat_id = _get_chat_id()
        if chat_id != "PENDING":
            try:
                await _bot_app.bot.send_message(
                    chat_id=chat_id,
                    text="ArbitrageIQ is online\nMonitoring markets for opportunities...",
                    parse_mode=None,
                )
            except Exception as e:
                logger.warning(f"Could not send startup message: {e}")

        logger.info("Telegram bot initialized and polling")
    except Exception as e:
        logger.error(f"Failed to initialize Telegram bot: {e}")
        _bot_app = None


async def shutdown_bot():
    """Gracefully shut down the Telegram bot."""
    global _bot_app
    if _bot_app:
        try:
            await _bot_app.updater.stop()
            await _bot_app.stop()
            await _bot_app.shutdown()
        except Exception as e:
            logger.error(f"Error shutting down Telegram bot: {e}")
        _bot_app = None
