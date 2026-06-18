"""Perception system — filter world state for player visibility."""

from __future__ import annotations

import math
from dataclasses import dataclass, field


@dataclass
class PerceptionContext:
    """Context for perception calculation."""

    observer_id: str
    observer_location_id: str
    light_level: int = 5  # 0-10
    weather_modifier: float = 1.0  # 0.0-1.0
    observer_perception_skill: int = 10  # WIS-based
    stealth_values: dict[str, int] = field(default_factory=dict)  # entity_id -> stealth


@dataclass
class VisibleEntity:
    """An entity visible to the observer."""

    entity_id: str
    entity_type: str  # character, item, location_feature
    name: str
    description: str = ""
    distance: float = 0.0
    detail_level: str = "full"  # full, partial, vague, hidden
    is_notable: bool = False


@dataclass
class PerceptionResult:
    """Filtered view of the world for a player."""

    visible_entities: list[VisibleEntity] = field(default_factory=list)
    visible_events: list[str] = field(default_factory=list)
    ambient_description: str = ""
    hidden_count: int = 0

    @property
    def entity_ids(self) -> list[str]:
        return [e.entity_id for e in self.visible_entities]


class PerceptionFilter:
    """Filter world state based on perception factors."""

    # Distance thresholds (in location units)
    NEAR_DISTANCE = 1.0
    MEDIUM_DISTANCE = 3.0
    FAR_DISTANCE = 5.0

    # Light level thresholds
    DARK = 2
    DIM = 4
    NORMAL = 7
    BRIGHT = 9

    def calculate_visibility(
        self,
        entity_id: str,
        entity_type: str,
        entity_name: str,
        entity_description: str,
        distance: float,
        entity_stealth: int,
        context: PerceptionContext,
    ) -> VisibleEntity | None:
        """Calculate if and how an entity is visible."""
        # Base perception score
        score = context.observer_perception_skill

        # Light modifier
        if context.light_level <= self.DARK:
            score -= 8
        elif context.light_level <= self.DIM:
            score -= 4
        elif context.light_level >= self.BRIGHT:
            score += 2

        # Weather modifier
        score = int(score * context.weather_modifier)

        # Distance modifier
        if distance <= self.NEAR_DISTANCE:
            score += 4
        elif distance <= self.MEDIUM_DISTANCE:
            score += 0
        elif distance <= self.FAR_DISTANCE:
            score -= 4
        else:
            score -= 8

        # Stealth check
        effective_stealth = entity_stealth
        stealth_diff = score - effective_stealth

        if stealth_diff < -5:
            return None  # Hidden
        elif stealth_diff < 0:
            detail = "vague"
        elif stealth_diff < 5:
            detail = "partial"
        else:
            detail = "full"

        is_notable = detail == "full" and distance <= self.NEAR_DISTANCE

        return VisibleEntity(
            entity_id=entity_id,
            entity_type=entity_type,
            name=entity_name,
            description=entity_description if detail != "vague" else "",
            distance=distance,
            detail_level=detail,
            is_notable=is_notable,
        )

    def filter_entities(
        self,
        entities: list[dict[str, str | int | float]],
        context: PerceptionContext,
    ) -> PerceptionResult:
        """Filter a list of entities for visibility."""
        result = PerceptionResult()
        hidden = 0

        for entity in entities:
            visible = self.calculate_visibility(
                entity_id=str(entity.get("id", "")),
                entity_type=str(entity.get("type", "character")),
                entity_name=str(entity.get("name", "Unknown")),
                entity_description=str(entity.get("description", "")),
                distance=float(entity.get("distance", 0)),
                entity_stealth=int(entity.get("stealth", 0)),
                context=context,
            )
            if visible:
                result.visible_entities.append(visible)
            else:
                hidden += 1

        result.hidden_count = hidden

        # Generate ambient description based on light/weather
        result.ambient_description = self._generate_ambient(context)

        return result

    def _generate_ambient(self, context: PerceptionContext) -> str:
        """Generate ambient description based on perception context."""
        parts = []

        if context.light_level <= self.DARK:
            parts.append("几乎一片漆黑")
        elif context.light_level <= self.DIM:
            parts.append("光线昏暗")
        elif context.light_level >= self.BRIGHT:
            parts.append("光线充足")

        if context.weather_modifier < 0.5:
            parts.append("恶劣的天气影响了视线")
        elif context.weather_modifier < 0.8:
            parts.append("天气有些阴沉")

        return "，".join(parts) if parts else "环境正常"
