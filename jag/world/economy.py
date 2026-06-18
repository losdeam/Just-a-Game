"""Economy simulation: supply, demand, price fluctuation."""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Commodity:
    """A tradeable commodity."""

    id: str
    name: str
    base_price: float = 10.0
    current_price: float = 10.0
    supply: float = 100.0
    demand: float = 100.0


@dataclass
class Market:
    """A market at a location."""

    location_id: str
    commodities: dict[str, Commodity] = field(default_factory=dict)


class EconomySimulator:
    """Simulate economy dynamics."""

    def __init__(self, volatility: float = 0.1) -> None:
        self.markets: dict[str, Market] = {}
        self.volatility = volatility
        self._rng = random.Random()
        self.transactions: list[dict[str, Any]] = []

    def add_market(self, market: Market) -> None:
        self.markets[market.location_id] = market

    def add_commodity(self, location_id: str, commodity: Commodity) -> None:
        if location_id not in self.markets:
            self.markets[location_id] = Market(location_id=location_id)
        self.markets[location_id].commodities[commodity.id] = commodity

    def get_price(self, location_id: str, commodity_id: str) -> float:
        market = self.markets.get(location_id)
        if market and commodity_id in market.commodities:
            return market.commodities[commodity_id].current_price
        return 0.0

    def buy(self, location_id: str, commodity_id: str, quantity: float, buyer_id: str) -> float:
        """Buy commodity, returns total cost."""
        market = self.markets.get(location_id)
        if not market or commodity_id not in market.commodities:
            return 0.0

        c = market.commodities[commodity_id]
        cost = c.current_price * quantity
        c.supply -= quantity
        c.demand += quantity * 0.5
        c.supply = max(0, c.supply)
        self.transactions.append({"type": "buy", "buyer": buyer_id, "commodity": commodity_id, "quantity": quantity, "cost": cost})
        return cost

    def sell(self, location_id: str, commodity_id: str, quantity: float, seller_id: str) -> float:
        """Sell commodity, returns total revenue."""
        market = self.markets.get(location_id)
        if not market or commodity_id not in market.commodities:
            return 0.0

        c = market.commodities[commodity_id]
        revenue = c.current_price * quantity * 0.8  # sell at 80%
        c.supply += quantity
        c.demand = max(0, c.demand - quantity * 0.3)
        self.transactions.append({"type": "sell", "seller": seller_id, "commodity": commodity_id, "quantity": quantity, "revenue": revenue})
        return revenue

    def tick(self, world_state: Any = None) -> list[dict[str, Any]]:
        """Update prices based on supply/demand. Returns events."""
        events = []
        for market in self.markets.values():
            for c in market.commodities.values():
                if c.supply > 0:
                    ratio = c.demand / c.supply
                else:
                    ratio = 2.0
                noise = 1.0 + self._rng.uniform(-self.volatility, self.volatility)
                c.current_price = max(0.1, c.base_price * ratio * noise)
                c.current_price = round(c.current_price, 2)

                # Significant price changes generate events
                if abs(c.current_price - c.base_price) > c.base_price * 0.5:
                    events.append({
                        "type": "price_shift",
                        "location": market.location_id,
                        "commodity": c.name,
                        "price": c.current_price,
                        "base": c.base_price,
                    })

        return events
