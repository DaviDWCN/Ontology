"""
Insurance Clause Knowledge Graph Package.
Provides NetworkX-based local knowledge graph store, extraction, ingestion, query engine, and visualization tools.
"""

from insurance_kg.schema import (
    NodeLabel,
    RelationType,
    LayerType,
    NodeSchema,
    EdgeSchema,
    validate_node,
    validate_edge,
)
from insurance_kg.graph_store import InsuranceKG
from insurance_kg.extractor import ClauseExtractor
from insurance_kg.ingest import IngestionPipeline
from insurance_kg.query import KGQueryEngine
from insurance_kg.visualize import visualize_pyvis, visualize_matplotlib

__all__ = [
    "NodeLabel",
    "RelationType",
    "LayerType",
    "NodeSchema",
    "EdgeSchema",
    "validate_node",
    "validate_edge",
    "InsuranceKG",
    "ClauseExtractor",
    "IngestionPipeline",
    "KGQueryEngine",
    "visualize_pyvis",
    "visualize_matplotlib",
]
