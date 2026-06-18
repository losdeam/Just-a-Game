"""Rule engine with YAML declarative rules and Python registered rules."""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any, Callable

import yaml

from jag.core.events import EventBus, EventType, GameEvent


@dataclass
class RuleCondition:
    """A condition for a rule to match."""

    attribute: str  # e.g., "source.property", "target.state"
    operator: str = "eq"  # eq, ne, gt, lt, gte, lte, in, not_in, contains
    value: Any = None


@dataclass
class RuleEffect:
    """An effect to apply when a rule matches."""

    action: str  # set_state, emit_event, modify_attribute, create_item, destroy_item
    target: str = ""
    value: Any = None


@dataclass
class Rule:
    """A game rule."""

    name: str
    conditions: list[RuleCondition] = field(default_factory=list)
    effects: list[RuleEffect] = field(default_factory=list)
    probability: float = 1.0
    priority: int = 0
    max_chain_depth: int = 5
    tags: list[str] = field(default_factory=list)


@dataclass
class RuleContext:
    """Context passed to rule evaluation."""

    source: dict[str, Any] = field(default_factory=dict)
    target: dict[str, Any] = field(default_factory=dict)
    actor: dict[str, Any] = field(default_factory=dict)
    world: dict[str, Any] = field(default_factory=dict)
    turn: int = 0

    def get_value(self, path: str) -> Any:
        """Get a value from context using dot notation."""
        parts = path.split(".")
        if len(parts) < 2:
            return None
        obj_name = parts[0]
        attr_path = parts[1:]
        obj = getattr(self, obj_name, None)
        if obj is None:
            return None
        current = obj
        for part in attr_path:
            if isinstance(current, dict):
                current = current.get(part)
            else:
                current = getattr(current, part, None)
            if current is None:
                return None
        return current


PythonRuleHandler = Callable[[RuleContext], list[RuleEffect]]

# Global registry for Python rules
_python_rules: dict[str, PythonRuleHandler] = {}


def rule(name: str) -> Callable[[PythonRuleHandler], PythonRuleHandler]:
    """Decorator to register a Python rule handler."""

    def decorator(func: PythonRuleHandler) -> PythonRuleHandler:
        _python_rules[name] = func
        return func

    return decorator


def get_python_rule(name: str) -> PythonRuleHandler | None:
    """Get a registered Python rule handler."""
    return _python_rules.get(name)


class YAMLLoader:
    """Load rules from YAML files."""

    @staticmethod
    def load(path: str) -> list[Rule]:
        """Load rules from a YAML file."""
        with open(path) as f:
            data = yaml.safe_load(f) or []

        rules = []
        for entry in data:
            conditions = [
                RuleCondition(
                    attribute=c.get("attribute", ""),
                    operator=c.get("operator", "eq"),
                    value=c.get("value"),
                )
                for c in entry.get("conditions", [])
            ]
            effects = [
                RuleEffect(
                    action=e.get("action", ""),
                    target=e.get("target", ""),
                    value=e.get("value"),
                )
                for e in entry.get("effects", [])
            ]
            rules.append(
                Rule(
                    name=entry["name"],
                    conditions=conditions,
                    effects=effects,
                    probability=entry.get("probability", 1.0),
                    priority=entry.get("priority", 0),
                    tags=entry.get("tags", []),
                )
            )
        return rules


class RuleEngine:
    """Evaluate and apply game rules."""

    def __init__(self, event_bus: EventBus | None = None, max_chain_depth: int = 5) -> None:
        self._rules: list[Rule] = []
        self._event_bus = event_bus
        self._max_chain_depth = max_chain_depth
        self._rng = random.Random()

    def add_rule(self, rule: Rule) -> None:
        """Add a rule."""
        self._rules.append(rule)
        self._rules.sort(key=lambda r: r.priority, reverse=True)

    def load_rules(self, path: str) -> None:
        """Load rules from YAML."""
        for r in YAMLLoader.load(path):
            self.add_rule(r)

    def _check_condition(self, condition: RuleCondition, context: RuleContext) -> bool:
        """Check if a single condition matches."""
        actual = context.get_value(condition.attribute)
        if actual is None:
            return False

        expected = condition.value
        op = condition.operator

        if op == "eq":
            return actual == expected
        elif op == "ne":
            return actual != expected
        elif op == "gt":
            return actual > expected
        elif op == "lt":
            return actual < expected
        elif op == "gte":
            return actual >= expected
        elif op == "lte":
            return actual <= expected
        elif op == "in":
            return actual in (expected if isinstance(expected, list) else [expected])
        elif op == "not_in":
            return actual not in (expected if isinstance(expected, list) else [expected])
        elif op == "contains":
            return expected in actual if isinstance(actual, (list, str)) else False
        elif op == "has_property":
            if isinstance(actual, dict):
                return actual.get(expected, False) is True
            return False
        return False

    def _match_rule(self, rule: Rule, context: RuleContext) -> bool:
        """Check if all conditions of a rule match."""
        return all(self._check_condition(c, context) for c in rule.conditions)

    def _apply_effect(self, effect: RuleEffect, context: RuleContext) -> dict[str, Any]:
        """Apply a single effect and return state changes."""
        changes: dict[str, Any] = {}

        if effect.action == "set_state":
            target_obj = context.get_value(effect.target)
            if target_obj is not None:
                changes[effect.target] = effect.value

        elif effect.action == "emit_event":
            if self._event_bus:
                # Will be handled async outside
                changes["_emit_event"] = GameEvent(
                    event_type=EventType.ENVIRONMENT,
                    source_id=context.source.get("id", ""),
                    target_id=context.target.get("id", ""),
                    description=f"Rule triggered: {effect.target}",
                    data={"effect": effect.action, "value": effect.value},
                    turn=context.turn,
                )

        elif effect.action == "modify_attribute":
            target_obj = context.get_value(effect.target)
            if target_obj is not None and isinstance(effect.value, (int, float)):
                changes[effect.target] = target_obj + effect.value

        return changes

    def evaluate(self, context: RuleContext) -> list[dict[str, Any]]:
        """Evaluate all rules against context, return list of changes."""
        all_changes: list[dict[str, Any]] = []

        for r in self._rules:
            if not self._match_rule(r, context):
                continue

            # Probability check
            if r.probability < 1.0 and self._rng.random() > r.probability:
                continue

            # Apply effects
            for effect in r.effects:
                changes = self._apply_effect(effect, context)
                if changes:
                    changes["_rule"] = r.name
                    all_changes.append(changes)

            # Check Python rule handler
            handler = get_python_rule(r.name)
            if handler:
                extra_effects = handler(context)
                for effect in extra_effects:
                    changes = self._apply_effect(effect, context)
                    if changes:
                        changes["_rule"] = f"{r.name} (python)"
                        all_changes.append(changes)

        return all_changes
