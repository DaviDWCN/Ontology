"""
Ingestion Pipeline for Insurance Documents (Markdown, Plain Text, and Lexiang API payloads).
Extracts knowledge nodes/edges and ingests them into InsuranceKG.
"""

from __future__ import annotations
import os
import logging
from typing import Dict, Any, List, Optional
from insurance_kg.graph_store import InsuranceKG
from insurance_kg.extractor import ClauseExtractor

logger = logging.getLogger(__name__)


class IngestionPipeline:
    """Pipeline for ingesting raw clause documents into InsuranceKG."""

    def __init__(self, kg: Optional[InsuranceKG] = None, extractor: Optional[ClauseExtractor] = None):
        self.kg = kg or InsuranceKG()
        self.extractor = extractor or ClauseExtractor()

    def ingest_text(
        self,
        text: str,
        product_id: str,
        product_name: str,
        source: str = "local_text",
        source_url: str = ""
    ) -> Dict[str, Any]:
        """Ingests unstructured raw text string into graph store."""
        extraction = self.extractor.extract_from_text(
            text=text,
            product_id=product_id,
            product_name=product_name,
            source=source,
            source_url=source_url
        )

        entities = extraction.get("entities", [])
        relations = extraction.get("relations", [])

        self.kg.upsert_from_extraction(entities, relations)
        self.kg.save()

        logger.info(f"Ingested text for product '{product_name}' ({len(entities)} nodes, {len(relations)} relations).")
        return {
            "product_id": product_id,
            "nodes_count": len(entities),
            "relations_count": len(relations),
            "extraction": extraction,
        }

    def ingest_file(
        self,
        filepath: str,
        product_id: Optional[str] = None,
        product_name: Optional[str] = None,
        source_url: str = ""
    ) -> Dict[str, Any]:
        """Ingests a local text or markdown file."""
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"File not found: {filepath}")

        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()

        base_name = os.path.splitext(os.path.basename(filepath))[0]
        prod_id = product_id or f"prod_{base_name}"
        prod_name = product_name or base_name

        return self.ingest_text(
            text=content,
            product_id=prod_id,
            product_name=prod_name,
            source=filepath,
            source_url=source_url
        )

    def ingest_lexiang_document(self, doc_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Ingests document from Tencent Lexiang (腾讯乐享) API output format.
        Expected keys: doc_id, title, content (or markdown), url, version
        """
        doc_id = doc_data.get("doc_id") or doc_data.get("id") or "lexiang_doc"
        title = doc_data.get("title") or "腾讯乐享文档"
        content = doc_data.get("content") or doc_data.get("markdown") or ""
        url = doc_data.get("url") or doc_data.get("source_url") or ""

        product_id = f"prod_lexiang_{doc_id}"

        return self.ingest_text(
            text=content,
            product_id=product_id,
            product_name=title,
            source=f"lexiang_doc:{doc_id}",
            source_url=url
        )
