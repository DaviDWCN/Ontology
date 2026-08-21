import os
import pickle
import networkx as nx
from typing import List, Dict, Any, Optional
from pydantic import ValidationError

from insurance_kg.schema import NodeLabel, RelationType, BaseNodeProps, ClauseNodeProps, CoverageExclusionNodeProps

class InsuranceKG:
    def __init__(self, path: str = "insurance_kg/data/graph/kg.gpickle"):
        self.path = path
        self.graph = nx.MultiDiGraph()

    def add_node(self, node_id: str, label: str, **attrs) -> None:
        """
        Adds a node to the graph with basic property validation based on its label.
        """
        # Optionally validate attributes based on label using our schema
        try:
            if label == NodeLabel.CLAUSE:
                ClauseNodeProps(**attrs)
            elif label in (NodeLabel.COVERAGE, NodeLabel.EXCLUSION):
                CoverageExclusionNodeProps(**attrs)
            else:
                BaseNodeProps(**attrs)
        except ValidationError as e:
            # We log or handle validation error. For a simple graph store,
            # we can raise it or print a warning and still insert if we want flexibility.
            # Here, we raise it to enforce strictness, but we can also be lenient.
            raise ValueError(f"Invalid attributes for node {node_id} of label {label}: {e}")

        # Add node label to attrs
        attrs['label'] = str(label.value) if isinstance(label, NodeLabel) else str(label)
        self.graph.add_node(node_id, **attrs)

    def add_edge(self, src: str, dst: str, rel_type: str, **attrs) -> None:
        """
        Adds an edge between src and dst.
        """
        rel_type_str = str(rel_type.value) if isinstance(rel_type, RelationType) else str(rel_type)
        attrs['rel_type'] = rel_type_str
        self.graph.add_edge(src, dst, key=rel_type_str, **attrs)

    def upsert_from_extraction(self, entities: List[Dict[str, Any]], relations: List[Dict[str, Any]]) -> None:
        """
        Upserts multiple nodes and edges from extracted lists.
        entities: [{'id': 'prod_1', 'label': 'Product', 'name': '某重疾险2025'}, ...]
        relations: [{'src': 'prod_1', 'dst': 'clause_1', 'rel_type': 'HAS_CLAUSE'}, ...]
        """
        for entity in entities:
            node_id = entity.pop('id')
            label = entity.pop('label')
            # Add or update node
            if self.graph.has_node(node_id):
                # Update attributes
                for k, v in entity.items():
                    self.graph.nodes[node_id][k] = v
            else:
                self.add_node(node_id, label, **entity)

        for relation in relations:
            src = relation.pop('src')
            dst = relation.pop('dst')
            rel_type = relation.pop('rel_type')
            rel_type_str = str(rel_type.value) if isinstance(rel_type, RelationType) else str(rel_type)
            # We only add if this specific rel_type doesn't already exist between src and dst
            if not self.graph.has_edge(src, dst, key=rel_type_str):
                self.add_edge(src, dst, rel_type, **relation)

    def get_neighbors(self, node_id: str, rel_types: Optional[List[str]] = None, direction: str = "both") -> List[Dict[str, Any]]:
        """
        Gets neighbors of a node.
        direction can be "out", "in", or "both".
        """
        if not self.graph.has_node(node_id):
            return []

        neighbors = []
        rel_types_str = [str(r.value) if isinstance(r, RelationType) else str(r) for r in rel_types] if rel_types else None

        if direction in ("out", "both"):
            for dst, keys_dict in self.graph.succ[node_id].items():
                for key, edge_attrs in keys_dict.items():
                    if rel_types_str is None or key in rel_types_str:
                        neighbors.append({'node_id': dst, 'node_attrs': self.graph.nodes[dst], 'edge_attrs': edge_attrs, 'direction': 'out'})

        if direction in ("in", "both"):
            for src, keys_dict in self.graph.pred[node_id].items():
                for key, edge_attrs in keys_dict.items():
                    if rel_types_str is None or key in rel_types_str:
                        neighbors.append({'node_id': src, 'node_attrs': self.graph.nodes[src], 'edge_attrs': edge_attrs, 'direction': 'in'})

        return neighbors

    def multi_hop(self, start_id: str, path_pattern: List[str], max_depth: int = 3) -> List[List[str]]:
        """
        A simple multi-hop query.
        path_pattern: list of relation types to follow, e.g., ['DEFINES', 'EXCLUDES']
        Returns a list of paths (lists of node IDs).
        For simplicity, this implementation specifically follows the exact path_pattern sequence.
        """
        if not self.graph.has_node(start_id) or not path_pattern:
            return []

        if len(path_pattern) > max_depth:
            path_pattern = path_pattern[:max_depth]

        paths = [[start_id]]

        path_pattern_str = [str(r.value) if isinstance(r, RelationType) else str(r) for r in path_pattern]

        for rel_type in path_pattern_str:
            new_paths = []
            for path in paths:
                current_node = path[-1]
                # Find out-edges matching rel_type
                if self.graph.has_node(current_node):
                    for dst, keys_dict in self.graph.succ[current_node].items():
                        if rel_type in keys_dict:
                            new_paths.append(path + [dst])
            paths = new_paths
            if not paths:
                break

        return paths

    def find_by_property(self, label: str, **filters) -> List[Dict[str, Any]]:
        """
        Finds nodes matching a label and specific property values.
        """
        label_str = str(label.value) if isinstance(label, NodeLabel) else str(label)
        results = []
        for node_id, data in self.graph.nodes(data=True):
            if data.get('label') != label_str:
                continue
            match = True
            for k, v in filters.items():
                if data.get(k) != v:
                    match = False
                    break
            if match:
                res = {'id': node_id}
                res.update(data)
                results.append(res)
        return results

    def get_exclusion_chain(self, coverage_id: str) -> List[Dict[str, Any]]:
        """
        责任 -> 对应免责
        Returns the exclusion nodes connected to the given coverage node via the EXCLUDES relation.
        """
        exclusions = []
        if self.graph.has_node(coverage_id):
            for dst, keys_dict in self.graph.succ[coverage_id].items():
                if str(RelationType.EXCLUDES.value) in keys_dict:
                    node_data = self.graph.nodes[dst].copy()
                    node_data['id'] = dst
                    exclusions.append(node_data)
        return exclusions

    def get_related_clauses(self, disease: str) -> List[Dict[str, Any]]:
        """
        Given a disease node ID, find related clauses.
        Typically Disease -> APPLIES_TO -> Coverage/Exclusion <- DEFINES <- Clause
        """
        related_clauses = []
        if not self.graph.has_node(disease):
            return related_clauses

        # 1. Get Coverages/Exclusions this disease applies to
        for cov_exc, keys_dict in self.graph.succ[disease].items():
            if str(RelationType.APPLIES_TO.value) in keys_dict:
                # 2. Find clauses that define this coverage/exclusion
                for clause, incoming_keys in self.graph.pred[cov_exc].items():
                    if str(RelationType.DEFINES.value) in incoming_keys:
                        clause_data = self.graph.nodes[clause].copy()
                        clause_data['id'] = clause
                        related_clauses.append(clause_data)
        return related_clauses

    def save(self) -> None:
        """
        Saves the graph to a gpickle file.
        """
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        with open(self.path, 'wb') as f:
            pickle.dump(self.graph, f, pickle.HIGHEST_PROTOCOL)

    def load(self) -> None:
        """
        Loads the graph from a gpickle file.
        """
        if os.path.exists(self.path):
            with open(self.path, 'rb') as f:
                self.graph = pickle.load(f)
        else:
            print(f"No graph found at {self.path}, starting fresh.")

    def export_graphml(self, path: str) -> None:
        """
        Exports the graph to GraphML format.
        """
        os.makedirs(os.path.dirname(path), exist_ok=True)
        nx.write_graphml(self.graph, path)

    def to_dict(self) -> Dict[str, Any]:
        """
        Returns a dictionary representation of the graph.
        """
        return nx.node_link_data(self.graph)
