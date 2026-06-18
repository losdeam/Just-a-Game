"""Knowledge graph using NetworkX for entity relationships and reasoning."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import networkx as nx


@dataclass
class Inference:
    """An inference result from knowledge graph reasoning."""

    source_id: str
    target_id: str
    relation_type: str
    confidence: float = 1.0
    reasoning: str = ""


class KnowledgeGraph:
    """Entity relationship graph with reasoning capabilities."""

    def __init__(self) -> None:
        self.g = nx.DiGraph()

    # ── CRUD ────────────────────────────────

    def add_entity(self, entity_id: str, **attrs: Any) -> None:
        """Add or update an entity node."""
        self.g.add_node(entity_id, **attrs)

    def remove_entity(self, entity_id: str) -> None:
        """Remove an entity and all its relations."""
        if entity_id in self.g:
            self.g.remove_node(entity_id)

    def add_relation(
        self, source_id: str, target_id: str, relation_type: str, **attrs: Any
    ) -> None:
        """Add a directed relation between entities."""
        # Ensure nodes exist
        if source_id not in self.g:
            self.g.add_node(source_id)
        if target_id not in self.g:
            self.g.add_node(target_id)
        self.g.add_edge(source_id, target_id, relation_type=relation_type, **attrs)

    def remove_relation(self, source_id: str, target_id: str, relation_type: str | None = None) -> None:
        """Remove a relation."""
        if self.g.has_edge(source_id, target_id):
            if relation_type is None:
                self.g.remove_edge(source_id, target_id)
            else:
                edge_data = self.g.get_edge_data(source_id, target_id)
                if edge_data and edge_data.get("relation_type") == relation_type:
                    self.g.remove_edge(source_id, target_id)

    def get_entity(self, entity_id: str) -> dict[str, Any] | None:
        """Get entity attributes."""
        if entity_id in self.g:
            return dict(self.g.nodes[entity_id])
        return None

    def has_entity(self, entity_id: str) -> bool:
        return entity_id in self.g

    # ── Queries ─────────────────────────────

    def query(self, entity_id: str, relation_type: str | None = None) -> list[dict[str, Any]]:
        """Query relations from an entity."""
        if entity_id not in self.g:
            return []

        results = []
        for _, target, data in self.g.out_edges(entity_id, data=True):
            if relation_type is None or data.get("relation_type") == relation_type:
                results.append({
                    "target": target,
                    "relation_type": data.get("relation_type", ""),
                    **{k: v for k, v in data.items() if k != "relation_type"},
                })
        return results

    def query_reverse(self, entity_id: str, relation_type: str | None = None) -> list[dict[str, Any]]:
        """Query relations pointing to an entity."""
        if entity_id not in self.g:
            return []

        results = []
        for source, _, data in self.g.in_edges(entity_id, data=True):
            if relation_type is None or data.get("relation_type") == relation_type:
                results.append({
                    "source": source,
                    "relation_type": data.get("relation_type", ""),
                    **{k: v for k, v in data.items() if k != "relation_type"},
                })
        return results

    def get_all_entities(self) -> list[str]:
        """Get all entity IDs."""
        return list(self.g.nodes)

    def get_all_relations(self) -> list[tuple[str, str, str]]:
        """Get all (source, target, relation_type) tuples."""
        return [
            (s, t, d.get("relation_type", ""))
            for s, t, d in self.g.edges(data=True)
        ]

    # ── Reasoning ───────────────────────────

    def infer(self, event: dict[str, Any]) -> list[Inference]:
        """Infer relationship changes from a game event.

        Example:
          event = {"type": "death", "entity_id": "goblin_king"}
          → entities that HATE goblin_king get +happy
          → entities ALLIED_WITH goblin_king get +distressed
        """
        inferences: list[Inference] = []
        event_type = event.get("type", "")
        entity_id = event.get("entity_id", "")

        if event_type == "death":
            # Find entities with relations to the dead entity
            for source, _, data in self.g.in_edges(entity_id, data=True):
                rel = data.get("relation_type", "")
                if rel == "hates":
                    inferences.append(Inference(
                        source_id=source,
                        target_id="",
                        relation_type="celebrating",
                        confidence=0.8,
                        reasoning=f"{source} hated {entity_id} who is now dead",
                    ))
                elif rel in ("allied_with", "likes"):
                    inferences.append(Inference(
                        source_id=source,
                        target_id="",
                        relation_type="mourning",
                        confidence=0.8,
                        reasoning=f"{source} was allied with {entity_id} who is now dead",
                    ))

        elif event_type == "combat":
            attacker = event.get("attacker_id", "")
            defender = event.get("defender_id", "")
            # Allies of defender become hostile to attacker
            for source, _, data in self.g.in_edges(defender, data=True):
                if data.get("relation_type") == "allied_with":
                    inferences.append(Inference(
                        source_id=source,
                        target_id=attacker,
                        relation_type="hostile",
                        confidence=0.6,
                        reasoning=f"{source} is allied with {defender} who was attacked by {attacker}",
                    ))

        return inferences

    def apply_inference(self, inference: Inference) -> None:
        """Apply an inference to the graph."""
        if inference.target_id:
            self.add_relation(
                inference.source_id,
                inference.target_id,
                inference.relation_type,
                confidence=inference.confidence,
            )

    # ── Serialization ───────────────────────

    def to_dict(self) -> dict[str, Any]:
        """Serialize graph to dict for persistence."""
        nodes = []
        for node_id, attrs in self.g.nodes(data=True):
            nodes.append({"id": node_id, **attrs})

        edges = []
        for source, target, data in self.g.edges(data=True):
            edges.append({"source": source, "target": target, **data})

        return {"nodes": nodes, "edges": edges}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> KnowledgeGraph:
        """Deserialize graph from dict."""
        kg = cls()
        for node in data.get("nodes", []):
            node_id = node.pop("id")
            kg.add_entity(node_id, **node)
        for edge in data.get("edges", []):
            source = edge.pop("source")
            target = edge.pop("target")
            kg.add_relation(source, target, **edge)
        return kg
