"""
Azuro Protocol decentralized sports betting ingestion client.

Azuro is a decentralized betting protocol on Polygon/Gnosis with
real-money markets. Uses The Graph subgraph for free data access.
Covers major sports — same events as DraftKings/FanDuel/Bet365.
"""

import httpx
import logging
from datetime import datetime, timezone

from ingestion.base import BaseClient
from ingestion.categorize import categorise

logger = logging.getLogger(__name__)

# Azuro subgraph on The Graph — free, no auth needed
AZURO_SUBGRAPH = "https://thegraph.azuro.org/subgraphs/name/azuro-protocol/azuro-api-polygon-v3"
_MAX_MARKETS = 200

GRAPHQL_QUERY = """
{
  games(
    first: %d
    where: { status: Created, startsAt_gt: "%d" }
    orderBy: turnover
    orderDirection: desc
  ) {
    gameId
    title
    slug
    sport { name }
    league { name country { name } }
    startsAt
    turnover
    conditions {
      conditionId
      outcomes {
        outcomeId
        currentOdds
        fund
      }
    }
  }
}
"""


class AzuroClient(BaseClient):
    source_name = "azuro"

    async def _fetch_raw(self) -> list[dict]:
        results = []
        now_ts = int(datetime.now(timezone.utc).timestamp())

        query = GRAPHQL_QUERY % (_MAX_MARKETS, now_ts)

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                AZURO_SUBGRAPH,
                json={"query": query},
            )
            resp.raise_for_status()
            data = resp.json()

            games = data.get("data", {}).get("games", [])

            for game in games:
                game_id = game.get("gameId", "")
                title = game.get("title", "")
                sport = game.get("sport", {}).get("name", "")
                league = game.get("league", {}).get("name", "")
                country = game.get("league", {}).get("country", {}).get("name", "")
                turnover = float(game.get("turnover", 0) or 0)
                starts_at = game.get("startsAt", "")

                if not game_id or not title:
                    continue

                # Build display name
                display_name = title
                if league:
                    display_name = f"{title} ({league})"

                category = categorise(f"{sport} {title} {league}")

                # Parse conditions (markets within the game)
                conditions = game.get("conditions", [])
                for cond in conditions:
                    cond_id = cond.get("conditionId", "")
                    outcomes = cond.get("outcomes", [])

                    if len(outcomes) < 2:
                        continue

                    for out in outcomes:
                        outcome_id = out.get("outcomeId", "")
                        odds_str = out.get("currentOdds", "0")
                        try:
                            decimal_odds = float(odds_str)
                        except (ValueError, TypeError):
                            continue

                        if decimal_odds <= 1.0:
                            continue

                        implied_prob = 1.0 / decimal_odds
                        if implied_prob <= 0.01 or implied_prob >= 0.99:
                            continue

                        market_id = f"{game_id}_{cond_id}_{outcome_id}"

                        results.append({
                            "source": "azuro",
                            "market_id": market_id,
                            "title": display_name,
                            "outcome": f"outcome_{outcome_id}",
                            "yes_price": round(implied_prob, 4),
                            "raw_odds": round(decimal_odds, 4),
                            "volume": turnover,
                            "category": category,
                            "timestamp": datetime.now(timezone.utc),
                            "metadata": {
                                "sport": sport,
                                "league": league,
                                "country": country,
                                "starts_at": starts_at,
                                "url": f"https://azuro.org/events/{game_id}",
                            },
                        })

        logger.info(f"Azuro: fetched {len(results)} prices from {len(games)} games")
        return results
