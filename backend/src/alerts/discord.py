"""
Discord webhook alert system.
Sends formatted alerts for arb opportunities and discrepancies
to user-configured Discord webhook URLs.
"""

import logging
from datetime import datetime

import httpx

from db.models import SessionLocal, User, AlertLog

logger = logging.getLogger(__name__)


async def send_arb_alert(opp, webhook_url: str) -> bool:
    """Send an arb opportunity alert to a Discord webhook."""
    if not webhook_url:
        return False

    if isinstance(opp, dict):
        event_name = opp.get("event_name", "Unknown")
        profit_pct = opp.get("profit_pct", 0)
        net_profit_pct = opp.get("net_profit_pct", profit_pct)
        legs = opp.get("legs", [])
        profit_on_1000 = opp.get("profit_on_1000", 0)
        confidence = opp.get("confidence", "medium")
        arb_type = opp.get("arb_type", "cross_platform")
    else:
        event_name = opp.event_name
        profit_pct = opp.profit_pct
        net_profit_pct = getattr(opp, "net_profit_pct", profit_pct)
        legs = opp.legs
        profit_on_1000 = opp.profit_on_1000
        confidence = getattr(opp, "confidence", "medium")
        arb_type = getattr(opp, "arb_type", "cross_platform")

    # Build legs description
    legs_lines = []
    for i, leg in enumerate(legs[:5]):
        if isinstance(leg, dict):
            src = leg.get("source", "?")
            out = leg.get("outcome", "?")
            odds = leg.get("decimal_odds", 0)
            stake = leg.get("stake_dollars", 0)
        else:
            src = leg.source
            out = leg.outcome
            odds = leg.decimal_odds
            stake = leg.stake_dollars
        legs_lines.append(f"**Leg {i+1}:** {src.title()} — {out} @ {odds:.2f}x (${stake:.0f})")

    # Confidence emoji
    conf_emoji = {"high": ":green_circle:", "medium": ":yellow_circle:", "low": ":white_circle:"}.get(confidence, ":white_circle:")

    embed = {
        "embeds": [{
            "title": f"Arb Found: +{net_profit_pct*100:.2f}% net profit",
            "description": f"**{event_name}**\n\n" + "\n".join(legs_lines),
            "color": 0x10B981,  # mint green
            "fields": [
                {"name": "Profit on $1K", "value": f"${profit_on_1000:.2f}", "inline": True},
                {"name": "Confidence", "value": f"{conf_emoji} {confidence.title()}", "inline": True},
                {"name": "Type", "value": arb_type.replace("_", " ").title(), "inline": True},
            ],
            "footer": {"text": f"ArbitrageIQ | {datetime.utcnow().strftime('%H:%M:%S UTC')}"},
        }],
        "username": "ArbitrageIQ",
    }

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(webhook_url, json=embed, timeout=10)
            if resp.status_code in (200, 204):
                _log_alert("discord_arb", event_name[:100], f"+{net_profit_pct*100:.2f}%")
                return True
            else:
                logger.error(f"Discord webhook returned {resp.status_code}: {resp.text[:200]}")
                return False
    except Exception as e:
        logger.error(f"Discord alert failed: {e}")
        return False


async def send_discrepancy_alert(disc, webhook_url: str) -> bool:
    """Send a discrepancy/value signal alert to a Discord webhook."""
    if not webhook_url:
        return False

    if isinstance(disc, dict):
        event_name = disc.get("event_name", "Unknown")
        edge = disc.get("edge", 0)
        direction = disc.get("direction", "")
        platform = disc.get("platform", disc.get("source", ""))
        consensus = disc.get("consensus_price", 0)
        market = disc.get("platform_price", disc.get("market_probability", 0))
        num_sources = disc.get("num_sources", 0)
    else:
        event_name = disc.event_name
        edge = disc.edge
        direction = disc.direction
        platform = disc.platform
        consensus = disc.consensus_price
        market = disc.platform_price
        num_sources = disc.num_sources

    is_buy = "YES" in direction.upper()
    color = 0x10B981 if is_buy else 0xF43F5E

    embed = {
        "embeds": [{
            "title": f"Value Signal: {abs(edge)*100:.1f}% edge on {platform}",
            "description": f"**{event_name}**\n\n{direction} — Market at {market*100:.1f}%, consensus at {consensus*100:.1f}%",
            "color": color,
            "fields": [
                {"name": "Edge", "value": f"{abs(edge)*100:.1f}%", "inline": True},
                {"name": "Sources", "value": str(num_sources), "inline": True},
            ],
            "footer": {"text": f"ArbitrageIQ | {datetime.utcnow().strftime('%H:%M:%S UTC')}"},
        }],
        "username": "ArbitrageIQ",
    }

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(webhook_url, json=embed, timeout=10)
            return resp.status_code in (200, 204)
    except Exception as e:
        logger.error(f"Discord discrepancy alert failed: {e}")
        return False


def _log_alert(alert_type, market_id, msg, success=True):
    """Log alert to database."""
    try:
        db = SessionLocal()
        db.add(AlertLog(
            alert_type=alert_type,
            market_id=market_id,
            message_preview=msg[:200] if msg else "",
            success=success,
            channel="discord",
            status="sent" if success else "failed",
        ))
        db.commit()
        db.close()
    except Exception:
        pass
