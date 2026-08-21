"""
Visualization Utilities for Insurance Clause Knowledge Graph using PyVis and Matplotlib.
"""

from __future__ import annotations
import os
import logging
from typing import Optional
import networkx as nx

from insurance_kg.graph_store import InsuranceKG
from insurance_kg.schema import NodeLabel

logger = logging.getLogger(__name__)

# Node color palette per label
LABEL_COLORS = {
    NodeLabel.PRODUCT.value: "#1f77b4",     # Blue
    NodeLabel.CLAUSE.value: "#ff7f0e",      # Orange
    NodeLabel.COVERAGE.value: "#2ca02c",    # Green
    NodeLabel.EXCLUSION.value: "#d62728",   # Red
    NodeLabel.CONDITION.value: "#9467bd",   # Purple
    NodeLabel.DISEASE.value: "#8c564b",     # Brown
    NodeLabel.OCCUPATION.value: "#e377c2",  # Pink
    NodeLabel.BENEFIT.value: "#7f7f7f",     # Grey
    NodeLabel.REGULATION.value: "#bcbd22",  # Yellow-green
    NodeLabel.CONCEPT.value: "#17becf",     # Cyan
}


def visualize_pyvis(kg: InsuranceKG, output_path: str = "insurance_kg/data/graph/kg_vis.html") -> str:
    """
    Generates interactive HTML visualization using PyVis.
    """
    try:
        from pyvis.network import Network
    except ImportError:
        logger.error("pyvis package is not installed. Run 'pip install pyvis'.")
        raise

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    net = Network(height="750px", width="100%", directed=True, notebook=False)

    for n_id, data in kg.graph.nodes(data=True):
        label_val = data.get("label", "Concept")
        color = LABEL_COLORS.get(label_val, "#97c2fc")
        name = data.get("name", n_id)
        c_num = data.get("clause_number", "")
        title_hover = f"ID: {n_id}<br>Type: {label_val}<br>Name: {name}"
        if c_num:
            title_hover += f"<br>Clause: {c_num}"

        net.add_node(n_id, label=name, title=title_hover, color=color)

    for src, dst, key, data in kg.graph.edges(keys=True, data=True):
        rel_type = data.get("rel_type", key)
        net.add_edge(src, dst, title=rel_type, label=rel_type)

    net.save_graph(output_path)
    logger.info(f"PyVis visualization saved to {output_path}")
    return output_path


def visualize_matplotlib(kg: InsuranceKG, output_path: str = "insurance_kg/data/graph/kg_vis.png") -> str:
    """
    Generates static network plot using Matplotlib.
    """
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        logger.error("matplotlib is not installed.")
        raise

    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    plt.figure(figsize=(12, 8))
    pos = nx.spring_layout(kg.graph, seed=42)

    # Color mapping
    node_colors = [
        LABEL_COLORS.get(data.get("label"), "#97c2fc")
        for _, data in kg.graph.nodes(data=True)
    ]

    labels = {
        n_id: data.get("name", n_id)
        for n_id, data in kg.graph.nodes(data=True)
    }

    nx.draw_networkx_nodes(kg.graph, pos, node_color=node_colors, node_size=1200, alpha=0.9)
    nx.draw_networkx_edges(kg.graph, pos, arrowstyle="->", arrowsize=15, edge_color="gray", alpha=0.6)
    nx.draw_networkx_labels(kg.graph, pos, labels=labels, font_size=8, font_family="sans-serif")

    plt.title("Insurance Clause Knowledge Graph")
    plt.axis("off")
    plt.tight_layout()
    plt.savefig(output_path, dpi=300)
    plt.close()

    logger.info(f"Matplotlib visualization saved to {output_path}")
    return output_path
