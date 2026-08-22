"""
Agent Query Interface Engine for Insurance Knowledge Graph.
Provides high-level graph query interfaces tailored for Researcher, Auditor, and Adjudicator Agents.
"""

from __future__ import annotations
import logging
from typing import Dict, Any, List, Optional
from insurance_kg.graph_store import InsuranceKG
from insurance_kg.schema import NodeLabel, RelationType

logger = logging.getLogger(__name__)


class KGQueryEngine:
    """Agent query engine wrapping InsuranceKG for hybrid retrieval and structured evidence formatting."""

    def __init__(self, kg: Optional[InsuranceKG] = None):
        self.kg = kg or InsuranceKG()

    def search_coverage_with_rules(self, coverage_query: str) -> List[Dict[str, Any]]:
        """
        Query for Researcher Agent:
        Finds coverage nodes matching name or ID along with defined conditions and limits.
        """
        nodes = self.kg.find_by_property(label=NodeLabel.COVERAGE.value, name=coverage_query)
        if not nodes:
            # Fallback search across all nodes
            nodes = self.kg.find_by_property(name=coverage_query)

        results = []
        for n in nodes:
            n_id = n["id"]
            # Outgoing neighbors (Conditions, Exclusions)
            conditions = self.kg.get_neighbors(n_id, rel_types=[RelationType.REQUIRES.value, RelationType.DEFINES.value], direction="out")
            exclusions = self.kg.get_neighbors(n_id, rel_types=[RelationType.EXCLUDES.value], direction="out")
            # Incoming neighbors (Clause, Disease)
            clauses = self.kg.get_neighbors(n_id, rel_types=[RelationType.DEFINES.value, RelationType.HAS_CLAUSE.value], direction="in")

            results.append({
                "coverage_node": n,
                "clauses": [c["node"] for c in clauses],
                "conditions": [cond["node"] for cond in conditions],
                "exclusions": [ex["node"] for ex in exclusions],
            })

        return results

    def query_exclusion_evidence(self, query_term: str) -> Dict[str, Any]:
        """
        Query for Auditor & Adjudicator Agents:
        Provides structured evidence on coverage exclusion chains, including clause numbers and source URLs.
        """
        chains = self.kg.get_exclusion_chain(query_term)

        evidence_items = []
        for chain in chains:
            cov = chain.get("coverage", {})
            exclusions = chain.get("exclusions", [])

            clause_num = cov.get("clause_number") or cov.get("id")
            source_url = cov.get("source_url") or cov.get("source") or ""

            for ex in exclusions:
                evidence_items.append({
                    "coverage_id": cov.get("id"),
                    "coverage_name": cov.get("name"),
                    "exclusion_id": ex.get("id"),
                    "exclusion_name": ex.get("name"),
                    "exclusion_text": ex.get("text", ""),
                    "clause_number": clause_num,
                    "source_url": source_url,
                })

        return {
            "query": query_term,
            "evidence_count": len(evidence_items),
            "evidence_chain": evidence_items,
        }

    def multi_hop_query(self, start_node_id: str, path_pattern: Optional[List[str]] = None, max_depth: int = 3) -> Dict[str, Any]:
        """Runs multi-hop traversal and returns path steps with full node details."""
        paths = self.kg.multi_hop(start_id=start_node_id, path_pattern=path_pattern, max_depth=max_depth)
        return {
            "start_id": start_node_id,
            "path_count": len(paths),
            "paths": paths,
        }

    def query_for_llm_context(self, query_str: str) -> str:
        """
        Formats relevant graph facts into a structured markdown string for LLM RAG prompt context.
        """
        matched_nodes = self.kg.find_by_property(name=query_str)
        if not matched_nodes:
            return f"### 图谱检索结果\n未找到与 '{query_str}' 直接匹配的节点。"

        lines = [f"### 图谱检索结果 (匹配关键词: '{query_str}')\n"]

        for n in matched_nodes[:5]:
            n_id = n["id"]
            lines.append(f"#### 节点: {n.get('name')} [{n.get('label')}] (ID: {n_id})")
            if n.get("clause_number"):
                lines.append(f"- **条款编号**: {n.get('clause_number')}")
            if n.get("limit"):
                lines.append(f"- **保额/限额**: {n.get('limit')}")
            if n.get("source_url"):
                lines.append(f"- **来源链接**: {n.get('source_url')}")
            if n.get("text"):
                lines.append(f"- **条款原文片段**: {n.get('text')}")

            # Adjacent edges
            neighbors = self.kg.get_neighbors(n_id, direction="both")
            if neighbors:
                lines.append("- **关联拓扑边**:")
                for neighbor in neighbors[:8]:
                    direction_str = "->" if neighbor["direction"] == "out" else "<-"
                    rel = neighbor["relation"]
                    nb_node = neighbor["node"]
                    lines.append(f"  - {direction_str} [{rel}] {nb_node.get('name')} ({nb_node.get('label')})")
            lines.append("")

        return "\n".join(lines)
