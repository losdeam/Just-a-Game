"""Quest generator: dynamic quests from world state."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any


@dataclass
class QuestObjective:
    """A quest objective."""

    description: str
    completed: bool = False


@dataclass
class Quest:
    """A game quest."""

    id: str
    title: str
    description: str = ""
    quest_type: str = "side"
    status: str = "available"
    giver_id: str = ""
    objectives: list[QuestObjective] = field(default_factory=list)
    rewards: dict[str, Any] = field(default_factory=dict)
    source: str = ""


@dataclass
class QuestTemplate:
    """Template for generating quests."""

    name: str
    title_template: str
    description_template: str
    quest_type: str = "side"
    trigger_conditions: dict[str, Any] = field(default_factory=dict)
    objectives: list[str] = field(default_factory=list)
    rewards: dict[str, Any] = field(default_factory=dict)


class QuestGenerator:
    """Generate quests based on world state."""

    def __init__(self) -> None:
        self.templates: list[QuestTemplate] = []
        self.active_quests: dict[str, Quest] = {}
        self._default_templates()

    def _default_templates(self) -> None:
        """Register default quest templates."""
        self.templates.extend([
            QuestTemplate(
                name="escort",
                title_template="Escort {npc_name} to {location}",
                description_template="{npc_name} needs safe passage to {location}.",
                trigger_conditions={"type": "npc_need", "need": "safety"},
                objectives=["Escort the NPC safely", "Reach the destination"],
                rewards={"xp": 50, "gold": 20},
            ),
            QuestTemplate(
                name="eliminate",
                title_template="Eliminate the {threat} at {location}",
                description_template="A {threat} has been spotted near {location}. Deal with it.",
                trigger_conditions={"type": "threat_nearby"},
                objectives=["Find the threat", "Eliminate it"],
                rewards={"xp": 80, "gold": 30},
            ),
            QuestTemplate(
                name="delivery",
                title_template="Deliver {item} to {npc_name}",
                description_template="{giver_name} needs {item} delivered to {npc_name}.",
                trigger_conditions={"type": "npc_need", "need": "item"},
                objectives=["Obtain the item", "Deliver to the NPC"],
                rewards={"xp": 30, "gold": 15},
            ),
            QuestTemplate(
                name="investigate",
                title_template="Investigate the {event} at {location}",
                description_template="Something strange happened at {location}. Investigate.",
                trigger_conditions={"type": "world_event"},
                objectives=["Travel to the location", "Investigate the event"],
                rewards={"xp": 60, "gold": 25},
            ),
        ])

    def add_template(self, template: QuestTemplate) -> None:
        self.templates.append(template)

    def check(self, world_state: Any, events: list[dict[str, Any]] | None = None) -> list[Quest]:
        """Check world state and generate new quests."""
        new_quests: list[Quest] = []

        if events:
            for event in events:
                for template in self.templates:
                    if self._matches_trigger(template, event):
                        quest = self._generate_quest(template, event)
                        if quest:
                            new_quests.append(quest)
                            self.active_quests[quest.id] = quest

        return new_quests

    def _matches_trigger(self, template: QuestTemplate, event: dict[str, Any]) -> bool:
        """Check if an event matches a quest template's trigger conditions."""
        conditions = template.trigger_conditions
        if not conditions:
            return False
        return all(event.get(k) == v for k, v in conditions.items() if k != "need")

    def _generate_quest(self, template: QuestTemplate, event: dict[str, Any]) -> Quest | None:
        """Generate a quest from a template and event."""
        quest_id = f"quest_{uuid.uuid4().hex[:8]}"
        title = template.title_template.format(
            npc_name=event.get("npc_name", "someone"),
            location=event.get("location", "somewhere"),
            threat=event.get("threat", "danger"),
            item=event.get("item", "package"),
            giver_name=event.get("giver_name", "someone"),
            event=event.get("event_type", "mystery"),
        )
        description = template.description_template.format(
            npc_name=event.get("npc_name", "someone"),
            location=event.get("location", "somewhere"),
            threat=event.get("threat", "danger"),
            item=event.get("item", "package"),
            giver_name=event.get("giver_name", "someone"),
        )

        return Quest(
            id=quest_id,
            title=title,
            description=description,
            quest_type=template.quest_type,
            status="available",
            giver_id=event.get("source_id", ""),
            objectives=[QuestObjective(description=obj) for obj in template.objectives],
            rewards=dict(template.rewards),
            source=event.get("type", ""),
        )

    def complete_objective(self, quest_id: str, objective_index: int) -> None:
        """Mark a quest objective as completed."""
        quest = self.active_quests.get(quest_id)
        if quest and 0 <= objective_index < len(quest.objectives):
            quest.objectives[objective_index].completed = True
            if all(obj.completed for obj in quest.objectives):
                quest.status = "completed"
