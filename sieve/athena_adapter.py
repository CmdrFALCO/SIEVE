"""ATHENA Adapter — Convert SIEVE output to ATHENA hypergraph nodes.

Transforms FilteredContent into structured knowledge graph nodes
that ATHENA can ingest. Handles deduplication, source quality weighting,
and relationship extraction.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional
from hashlib import sha256
import json
from pathlib import Path

from .models import FilteredContent, SignalClass


@dataclass
class AthenaNode:
    """A knowledge node for the ATHENA hypergraph."""
    id: str                        # Deterministic hash-based ID
    concept: str                   # The concept name
    node_type: str                 # tool, method, claim, architecture, finding, person, project, source
    description: str
    connections: list[str] = field(default_factory=list)  # IDs or concept names

    # Provenance
    source_url: str = ""
    source_author: Optional[str] = None
    source_date: Optional[str] = None
    source_quality: float = 0.0    # 0.0 to 1.0, from signal_score
    signal_class: str = ""

    # Metadata
    domains: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

    # Content
    claims: list[dict] = field(default_factory=list)
    open_questions: list[str] = field(default_factory=list)


@dataclass
class AthenaEdge:
    """A relationship between ATHENA nodes."""
    source_id: str
    target_id: str
    relation: str         # "uses", "extends", "critiques", "implements", "connects_to"
    weight: float = 1.0   # Higher = stronger connection
    evidence: str = ""    # Why this connection exists


def _make_node_id(concept: str, source_url: str = "") -> str:
    """Generate a deterministic ID for a node."""
    raw = f"{concept.lower().strip()}:{source_url}"
    return sha256(raw.encode()).hexdigest()[:12]


def _signal_to_quality(signal_class: SignalClass, score: float) -> float:
    """Convert signal classification to a quality weight for ATHENA."""
    base = {
        SignalClass.HIGH_SIGNAL: 0.8,
        SignalClass.MODERATE_SIGNAL: 0.5,
        SignalClass.LOW_SIGNAL: 0.2,
        SignalClass.NOISE: 0.05,
    }.get(signal_class, 0.3)
    # Blend base with score
    return round(base * 0.6 + score * 0.4, 3)


def filtered_to_athena_nodes(item: FilteredContent) -> list[AthenaNode]:
    """Convert a single FilteredContent into ATHENA nodes.

    Each knowledge_node from the LLM filter becomes an AthenaNode.
    The source's signal quality propagates to node quality.
    """
    quality = _signal_to_quality(item.signal_class, item.signal_score)
    nodes = []

    for kn in item.knowledge_nodes:
        concept = kn.get("concept", "").strip()
        if not concept:
            continue

        node = AthenaNode(
            id=_make_node_id(concept, item.url),
            concept=concept,
            node_type=kn.get("type", "concept"),
            description=kn.get("description", ""),
            connections=kn.get("connections", []),
            source_url=item.url,
            source_author=item.author,
            source_date=item.date,
            source_quality=quality,
            signal_class=item.signal_class.value,
            domains=item.related_domains,
            tags=[],
            claims=[
                {
                    "statement": c.statement,
                    "evidence": c.evidence_type,
                    "confidence": c.confidence,
                }
                for c in item.key_claims
                if c.evidence_type != "none"
            ],
            open_questions=item.open_questions,
        )
        nodes.append(node)

    # Also create a source node representing the content itself
    source_node = AthenaNode(
        id=_make_node_id(item.title or item.url, item.url),
        concept=item.title or item.url,
        node_type="source",
        description=item.summary,
        connections=[n.concept for n in nodes] + item.connections_to_existing,
        source_url=item.url,
        source_author=item.author,
        source_date=item.date,
        source_quality=quality,
        signal_class=item.signal_class.value,
        domains=item.related_domains,
        open_questions=item.open_questions,
    )
    nodes.append(source_node)

    return nodes


def filtered_to_athena_edges(
    item: FilteredContent,
    nodes: list[AthenaNode],
) -> list[AthenaEdge]:
    """Generate edges between nodes from a single filtered item."""
    edges = []
    quality = _signal_to_quality(item.signal_class, item.signal_score)

    # Connect each knowledge node to its connections
    for node in nodes:
        for conn_name in node.connections:
            conn_id = _make_node_id(conn_name)
            edges.append(AthenaEdge(
                source_id=node.id,
                target_id=conn_id,
                relation="connects_to",
                weight=quality,
                evidence=f"From: {item.url}",
            ))

    # Connect all knowledge nodes to the source node
    source_node = next((n for n in nodes if n.node_type == "source"), None)
    if source_node:
        for node in nodes:
            if node.node_type != "source":
                edges.append(AthenaEdge(
                    source_id=source_node.id,
                    target_id=node.id,
                    relation="mentions",
                    weight=quality,
                ))

    return edges


class AthenaExporter:
    """Accumulates SIEVE results and exports to ATHENA format."""

    def __init__(self):
        self.nodes: dict[str, AthenaNode] = {}  # id -> node (deduplicates)
        self.edges: list[AthenaEdge] = []

    def ingest(self, item: FilteredContent):
        """Ingest a filtered content item."""
        nodes = filtered_to_athena_nodes(item)
        edges = filtered_to_athena_edges(item, nodes)

        for node in nodes:
            if node.id in self.nodes:
                # Merge: keep higher quality, union connections
                existing = self.nodes[node.id]
                if node.source_quality > existing.source_quality:
                    # Upgrade node but keep union of connections
                    merged_conns = list(set(existing.connections + node.connections))
                    node.connections = merged_conns
                    self.nodes[node.id] = node
                else:
                    # Keep existing but add new connections
                    existing.connections = list(
                        set(existing.connections + node.connections)
                    )
            else:
                self.nodes[node.id] = node

        self.edges.extend(edges)

    def ingest_batch(self, items: list[FilteredContent]):
        """Ingest multiple items."""
        for item in items:
            self.ingest(item)

    def export_json(self, path: str):
        """Export to JSON file for ATHENA ingestion."""
        data = {
            "meta": {
                "exported_at": datetime.now().isoformat(),
                "node_count": len(self.nodes),
                "edge_count": len(self.edges),
            },
            "nodes": [asdict(n) for n in self.nodes.values()],
            "edges": [asdict(e) for e in self.edges],
        }

        Path(path).write_text(
            json.dumps(data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        print(f"[ATHENA] Exported {len(self.nodes)} nodes, {len(self.edges)} edges to {path}")

    def export_cypher(self, path: str):
        """Export as Cypher statements for Neo4j ingestion."""
        lines = [
            "// ATHENA knowledge graph import from SIEVE",
            f"// Generated: {datetime.now().isoformat()}",
            f"// Nodes: {len(self.nodes)}, Edges: {len(self.edges)}",
            "",
        ]

        for node in self.nodes.values():
            label = node.node_type.capitalize()
            props = {
                "id": node.id,
                "concept": node.concept,
                "description": node.description,
                "source_quality": node.source_quality,
                "source_url": node.source_url,
                "signal_class": node.signal_class,
                "domains": node.domains,
            }
            props_str = json.dumps(props, ensure_ascii=False)
            lines.append(
                f'MERGE (n:{label} {{id: "{node.id}"}}) '
                f'SET n += {props_str};'
            )

        lines.append("")

        for edge in self.edges:
            rel = edge.relation.upper().replace(" ", "_")
            lines.append(
                f'MATCH (a {{id: "{edge.source_id}"}}), (b {{id: "{edge.target_id}"}}) '
                f'MERGE (a)-[r:{rel} {{weight: {edge.weight}}}]->(b);'
            )

        Path(path).write_text("\n".join(lines), encoding="utf-8")
        print(f"[ATHENA] Exported Cypher to {path}")

    def stats(self) -> dict:
        """Get summary statistics."""
        by_type = {}
        by_quality = {"high": 0, "medium": 0, "low": 0}

        for node in self.nodes.values():
            by_type[node.node_type] = by_type.get(node.node_type, 0) + 1
            if node.source_quality >= 0.7:
                by_quality["high"] += 1
            elif node.source_quality >= 0.4:
                by_quality["medium"] += 1
            else:
                by_quality["low"] += 1

        return {
            "total_nodes": len(self.nodes),
            "total_edges": len(self.edges),
            "nodes_by_type": by_type,
            "nodes_by_quality": by_quality,
        }
