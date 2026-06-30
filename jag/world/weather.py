"""Weather simulation: state machine with seasonal influence."""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Any


WEATHER_STATES = ["clear", "cloudy", "rain", "storm", "snow", "fog"]

WEATHER_NAMES = {
    "clear": "晴朗",
    "cloudy": "多云",
    "rain": "下雨",
    "storm": "暴风雨",
    "snow": "下雪",
    "fog": "大雾",
}

# Transition probabilities per season: {season: {current_weather: {next_weather: prob}}}
TRANSITION_WEIGHTS: dict[str, dict[str, dict[str, float]]] = {
    "spring": {
        "clear": {"clear": 0.5, "cloudy": 0.3, "rain": 0.2},
        "cloudy": {"clear": 0.3, "cloudy": 0.4, "rain": 0.3},
        "rain": {"cloudy": 0.4, "rain": 0.4, "storm": 0.1, "clear": 0.1},
        "storm": {"rain": 0.5, "cloudy": 0.4, "clear": 0.1},
        "fog": {"clear": 0.4, "cloudy": 0.4, "fog": 0.2},
        "snow": {"cloudy": 0.5, "clear": 0.3, "snow": 0.2},
    },
    "summer": {
        "clear": {"clear": 0.7, "cloudy": 0.2, "rain": 0.1},
        "cloudy": {"clear": 0.4, "cloudy": 0.4, "rain": 0.2},
        "rain": {"cloudy": 0.4, "rain": 0.3, "storm": 0.2, "clear": 0.1},
        "storm": {"rain": 0.4, "cloudy": 0.4, "clear": 0.2},
        "fog": {"clear": 0.5, "cloudy": 0.4, "fog": 0.1},
        "snow": {"clear": 0.8, "cloudy": 0.2},
    },
    "autumn": {
        "clear": {"clear": 0.4, "cloudy": 0.3, "rain": 0.2, "fog": 0.1},
        "cloudy": {"clear": 0.2, "cloudy": 0.4, "rain": 0.3, "fog": 0.1},
        "rain": {"cloudy": 0.3, "rain": 0.4, "storm": 0.2, "clear": 0.1},
        "storm": {"rain": 0.5, "cloudy": 0.3, "clear": 0.2},
        "fog": {"clear": 0.3, "cloudy": 0.4, "fog": 0.3},
        "snow": {"cloudy": 0.4, "snow": 0.4, "clear": 0.2},
    },
    "winter": {
        "clear": {"clear": 0.4, "cloudy": 0.3, "snow": 0.2, "fog": 0.1},
        "cloudy": {"clear": 0.2, "cloudy": 0.3, "snow": 0.3, "fog": 0.2},
        "rain": {"cloudy": 0.3, "rain": 0.2, "snow": 0.3, "storm": 0.2},
        "storm": {"snow": 0.4, "cloudy": 0.3, "rain": 0.3},
        "fog": {"clear": 0.2, "cloudy": 0.3, "fog": 0.3, "snow": 0.2},
        "snow": {"snow": 0.4, "cloudy": 0.3, "clear": 0.2, "storm": 0.1},
    },
}

# Weather effect modifiers for perception, travel, etc.
WEATHER_EFFECTS: dict[str, dict[str, float]] = {
    "clear": {"perception": 1.0, "travel": 1.0, "combat": 1.0},
    "cloudy": {"perception": 0.9, "travel": 1.0, "combat": 1.0},
    "rain": {"perception": 0.7, "travel": 0.8, "combat": 0.9},
    "storm": {"perception": 0.4, "travel": 0.5, "combat": 0.7},
    "snow": {"perception": 0.6, "travel": 0.6, "combat": 0.8},
    "fog": {"perception": 0.3, "travel": 0.7, "combat": 0.9},
}


@dataclass
class WeatherState:
    """Current weather state for a region."""

    region_id: str
    current: str = "clear"
    temperature: float = 20.0
    wind_speed: float = 0.0


class WeatherSimulator:
    """Simulate weather changes per region."""

    def __init__(self) -> None:
        self.states: dict[str, WeatherState] = {}
        self._rng = random.Random()

    def add_region(self, region_id: str, initial_weather: str = "clear", temperature: float = 20.0) -> None:
        self.states[region_id] = WeatherState(region_id=region_id, current=initial_weather, temperature=temperature)

    def get_weather(self, region_id: str) -> WeatherState:
        return self.states.get(region_id, WeatherState(region_id=region_id))

    def get_effects(self, region_id: str) -> dict[str, float]:
        """Get gameplay effect modifiers for a region's weather."""
        state = self.get_weather(region_id)
        return WEATHER_EFFECTS.get(state.current, WEATHER_EFFECTS["clear"])

    def tick(self, season: str = "spring") -> list[dict[str, Any]]:
        """Advance weather for all regions. Returns events."""
        events = []
        for region_id, state in self.states.items():
            season_weights = TRANSITION_WEIGHTS.get(season, TRANSITION_WEIGHTS["spring"])
            current_weights = season_weights.get(state.current, {})

            if not current_weights:
                continue

            # Weighted random transition
            weathers = list(current_weights.keys())
            weights = list(current_weights.values())
            new_weather = self._rng.choices(weathers, weights=weights, k=1)[0]

            old_weather = state.current
            state.current = new_weather

            # Update temperature
            base_temps = {"spring": 15, "summer": 25, "autumn": 12, "winter": 0}
            target = base_temps.get(season, 15)
            weather_mod = {"clear": 3, "cloudy": 0, "rain": -3, "storm": -5, "snow": -10, "fog": -2}
            target += weather_mod.get(new_weather, 0)
            state.temperature += (target - state.temperature) * 0.3
            state.temperature = round(state.temperature, 1)

            if old_weather != new_weather:
                old_name = WEATHER_NAMES.get(old_weather, old_weather)
                new_name = WEATHER_NAMES.get(new_weather, new_weather)
                events.append({
                    "type": "weather_change",
                    "region": region_id,
                    "from": old_weather,
                    "to": new_weather,
                    "temperature": state.temperature,
                    "description": f"天气由{old_name}转为{new_name}，气温约{state.temperature}度。",
                })

        return events
