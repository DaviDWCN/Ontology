"""
NetworkX Graph Store for Insurance Clause Knowledge Graph.
Provides node/edge CRUD, multi-hop search, domain queries, and multi-format persistence.
"""

from __future__ import annotations
import os
import pickle
import logging
from typing import Dict, Any, List, Optional, Set, Union
import networkx as nx

from insurance_kg.schema import (
    NodeLabel,
    RelationType,
    validate_node,
    validate_edge,
)

logger = logging.getLogger(__name__)


class InsuranceKG:
    """NetworkX wrapper for Insurance Clause Knowledge Graph."""

    def __init__(self, path: str = "insurance_kg/data/graph/kg.gpickle"):
        self.path = path
        self.graph = nx.MultiDiGraph()
        if os.path.exists(self.path):
            try:
                self.load(self.path)
            except Exception as e:
                logger.warning(f"Could not load graph from {self.path}: {e}. Initialized empty graph.")

    # ==========================================
    # 1. Graph Mutation (Write) Operations
    # ==========================================

    def add_node(self, node_id: str, label: str | NodeLabel, name: str = None, **attrs) -> None:
        """Adds or updates a node with schema validation."""
        if name is None:
            name = attrs.pop("name", node_id)

        clean_attrs = validate_node(node_id, label, name, **attrs)
        self.graph.add_node(node_id, **clean_attrs)

    def add_edge(self, src: str, dst: str, rel_type: str | RelationType, **attrs) -> None:
        """Adds a directed edge between src and dst with schema validation."""
        if not self.graph.has_node(src):
            # Placeholder node if src missing
            self.add_node(src, label=NodeLabel.CONCEPT, name=src)
        if not self.graph.has_node(dst):
            # Placeholder node if dst missing
            self.add_node(dst, label=NodeLabel.CONCEPT, name=dst)

        clean_attrs = validate_edge(src, dst, rel_type, **attrs)
        rel_str = clean_attrs["rel_type"]
        self.graph.add_edge(src, dst, key=rel_str, **clean_attrs)

    def upsert_from_extraction(self, entities: List[Dict[str, Any]], relations: List[Dict[str, Any]]) -> None:
        """Bulk updates graph from extracted entity and relation dicts."""
        for ent in entities:
            node_id = ent.get("id") or ent.get("node_id")
            if not node_id:
                continue
            label = ent.get("label") or ent.get("type", "Concept")
            name = ent.get("name") or node_id
            attrs = {k: v for k, v in ent.items() if k not in ("id", "node_id", "label", "type", "name")}
            self.add_node(node_id, label, name, **attrs)

        for rel in relations:
            src = rel.get("src") or rel.get("source_id") or rel.get("from")
            dst = rel.get("dst") or rel.get("target_id") or rel.get("to")
            rel_type = rel.get("rel_type") or rel.get("relation") or rel.get("type")
            if not (src and dst and rel_type):
                continue
            attrs = {k: v for k, v in rel.items() if k not in ("src", "source_id", "from", "dst", "target_id", "to", "rel_type", "relation", "type")}
            self.add_edge(src, dst, rel_type, **attrs)

    # ==========================================
    # 2. Query Operations
    # ==========================================

    def get_neighbors(
        self,
        node_id: str,
        rel_types: Optional[List[str]] = None,
        direction: str = "both"
    ) -> List[Dict[str, Any]]:
        """Returns adjacent nodes filtered by edge relation types and direction ('out', 'in', 'both')."""
        if not self.graph.has_node(node_id):
            return []

        rel_filter = set(rel_types) if rel_types else None
        results = []

        # Outgoing edges
        if direction in ("out", "both"):
            for _, successor, key, data in self.graph.out_edges(node_id, keys=True, data=True):
                r_type = data.get("rel_type", key)
                if rel_filter is None or r_type in rel_filter:
                    results.append({
                        "node_id": successor,
                        "node": dict(self.graph.nodes[successor]),
                        "relation": r_type,
                        "direction": "out",
                        "edge_data": data,
                    })

        # Incoming edges
        if direction in ("in", "both"):
            for predecessor, _, key, data in self.graph.in_edges(node_id, keys=True, data=True):
                r_type = data.get("rel_type", key)
                if rel_filter is None or r_type in rel_filter:
                    results.append({
                        "node_id": predecessor,
                        "node": dict(self.graph.nodes[predecessor]),
                        "relation": r_type,
                        "direction": "in",
                        "edge_data": data,
                    })

        return results

    def multi_hop(
        self,
        start_id: str,
        path_pattern: Optional[List[str]] = None,
        max_depth: int = 3
    ) -> List[Dict[str, Any]]:
        """
        Multi-hop path exploration.
        If path_pattern is provided (e.g. ['HAS_CLAUSE', 'DEFINES', 'EXCLUDES']), matches specific edge sequences.
        Otherwise explores all paths up to max_depth.
        """
        if not self.graph.has_node(start_id):
            return []

        found_paths = []

        def dfs(current_id: str, current_path: List[Dict[str, Any]], depth: int):
            if path_pattern and depth == len(path_pattern):
                found_paths.append(current_path)
                return
            if not path_pattern and depth > 0:
                found_paths.append(current_path)
            if depth >= max_depth:
                return

            expected_rel = path_pattern[depth] if path_pattern else None

            for _, successor, key, data in self.graph.out_edges(current_id, keys=True, data=True):
                r_type = data.get("rel_type", key)
                if expected_rel and r_type != expected_rel:
                    continue

                step = {
                    "from": current_id,
                    "to": successor,
                    "relation": r_type,
                    "target_node": dict(self.graph.nodes[successor]),
                }
                dfs(successor, current_path + [step], depth + 1)

        dfs(start_id, [], 0)
        return found_paths

    def find_by_property(self, label: Optional[str] = None, **filters) -> List[Dict[str, Any]]:
        """Finds nodes matching specified label and property filter criteria."""
        matched = []
        for n_id, data in self.graph.nodes(data=True):
            if label and data.get("label") != label:
                continue

            match = True
            for k, v in filters.items():
                node_val = data.get(k)
                if isinstance(v, str) and isinstance(node_val, str):
                    if v.lower() not in node_val.lower():
                        match = False
                        break
                elif node_val != v:
                    match = False
                    break

            if match:
                res = dict(data)
                res["id"] = n_id
                matched.append(res)

        return matched

    def get_exclusion_chain(self, coverage_id_or_name: str) -> List[Dict[str, Any]]:
        """
        Retrieves exclusion chain for a coverage responsibility: Coverage -> Exclusion.
        Also searches Clause -> Coverage -> Exclusion if a Clause ID/name is given.
        """
        target_nodes = []
        if self.graph.has_node(coverage_id_or_name):
            target_nodes.append(coverage_id_or_name)
        else:
            # Search by name
            for n_id, data in self.graph.nodes(data=True):
                if coverage_id_or_name.lower() in data.get("name", "").lower():
                    target_nodes.append(n_id)

        chains = []
        for cov_id in target_nodes:
            cov_node = dict(self.graph.nodes[cov_id])

            # Directly attached EXCLUDES
            exclusions = []
            for neighbor in self.get_neighbors(cov_id, rel_types=["EXCLUDES"], direction="out"):
                exclusions.append(neighbor["node"])

            # If node is a Clause, check DEFINES -> Coverage -> EXCLUDES -> Exclusion
            if cov_node.get("label") == NodeLabel.CLAUSE.value:
                defined_covs = self.get_neighbors(cov_id, rel_types=["DEFINES"], direction="out")
                for sub_cov in defined_covs:
                    if sub_cov["node"].get("label") == NodeLabel.COVERAGE.value:
                        sub_exs = self.get_neighbors(sub_cov["node_id"], rel_types=["EXCLUDES"], direction="out")
                        exclusions.extend([s["node"] for s in sub_exs])

            chains.append({
                "coverage_id": cov_id,
                "coverage": cov_node,
                "exclusions": exclusions,
            })

        return chains

    def get_related_clauses(self, disease_id_or_name: str) -> List[Dict[str, Any]]:
        """Retrieves clauses, coverages, and products related to a disease/condition."""
        disease_nodes = []
        if self.graph.has_node(disease_id_or_name):
            disease_nodes.append(disease_id_or_name)
        else:
            for n_id, data in self.graph.nodes(data=True):
                if data.get("label") in (NodeLabel.DISEASE.value, NodeLabel.CONCEPT.value):
                    if disease_id_or_name.lower() in data.get("name", "").lower():
                        disease_nodes.append(n_id)

        results = []
        for d_id in disease_nodes:
            d_node = dict(self.graph.nodes[d_id])

            # Disease -> APPLIES_TO -> Coverage/Exclusion
            connected = self.get_neighbors(d_id, rel_types=["APPLIES_TO"], direction="both")
            related_nodes = [c["node"] for c in connected]

            results.append({
                "disease_id": d_id,
                "disease": d_node,
                "related_entities": related_nodes,
            })

        return results

    # ==========================================
    # 3. Persistence Operations
    # ==========================================

    def save(self, path: Optional[str] = None) -> None:
        """Saves graph to pickle file."""
        target_path = path or self.path
        os.makedirs(os.path.dirname(target_path), exist_ok=True)
        with open(target_path, "wb") as f:
            pickle.dump(self.graph, f)
        logger.info(f"Graph saved to {target_path} ({len(self.graph.nodes)} nodes, {len(self.graph.edges)} edges).")

    def load(self, path: Optional[str] = None) -> None:
        """Loads graph from pickle file."""
        target_path = path or self.path
        if not os.path.exists(target_path):
            raise FileNotFoundError(f"Graph file not found: {target_path}")

        with open(target_path, "rb") as f:
            self.graph = pickle.load(f)
        logger.info(f"Graph loaded from {target_path} ({len(self.graph.nodes)} nodes, {len(self.graph.edges)} edges).")

    def export_graphml(self, path: str) -> None:
        """Exports graph to GraphML format with sanitized scalar attributes."""
        os.makedirs(os.path.dirname(path), exist_ok=True)
        g_copy = self.graph.copy()

        # Sanitize attributes for GraphML compatibility (convert dicts/lists/None to str)
        for _, n_data in g_copy.nodes(data=True):
            for k, v in list(n_data.items()):
                if v is None:
                    n_data[k] = ""
                elif isinstance(v, (dict, list)):
                    n_data[k] = str(v)

        for _, _, _, e_data in g_copy.edges(keys=True, data=True):
            for k, v in list(e_data.items()):
                if v is None:
                    e_data[k] = ""
                elif isinstance(v, (dict, list)):
                    e_data[k] = str(v)

        nx.write_graphml(g_copy, path)
        logger.info(f"Exported GraphML to {path}.")

    def to_dict(self) -> Dict[str, Any]:
        """Converts graph to node-link dict representation for JSON / LLM context."""
        return nx.node_link_data(self.graph)

    def from_dict(self, data: Dict[str, Any]) -> None:
        """Loads graph from node-link dict representation."""
        self.graph = nx.node_link_graph(data)
