"""
Insurance Clause Knowledge Graph Schema Definitions and Validation.
Supports node labels, relation types, and node/edge property validation using Pydantic v2.
"""

from __future__ import annotations
from enum import Enum
from typing import Dict, Any, Optional, Union, List
from pydantic import BaseModel, Field, ConfigDict, field_validator


# ==========================================
# 1. Node Labels and Relation Types
# ==========================================

class NodeLabel(str, Enum):
    """Insurance Knowledge Graph Node Labels."""
    PRODUCT = "Product"          # 保险产品（如“某重疾险2025版”）
    CLAUSE = "Clause"            # 条款条目（带条款编号）
    COVERAGE = "Coverage"        # 保障责任
    EXCLUSION = "Exclusion"      # 免责/除外责任
    CONDITION = "Condition"      # 条件/等待期/投保要求
    DISEASE = "Disease"          # 疾病/病种定义
    OCCUPATION = "Occupation"    # 职业
    BENEFIT = "Benefit"          # 给付/理赔条件
    REGULATION = "Regulation"    # 监管文件/法规引用
    CONCEPT = "Concept"          # 抽象概念（如“既往症”“等待期”）


class RelationType(str, Enum):
    """Insurance Knowledge Graph Relation Types."""
    HAS_CLAUSE = "HAS_CLAUSE"     # Product -> Clause
    DEFINES = "DEFINES"           # Clause -> Coverage / Exclusion / Condition
    EXCLUDES = "EXCLUDES"         # Coverage -> Exclusion
    REQUIRES = "REQUIRES"         # Coverage -> Condition
    APPLIES_TO = "APPLIES_TO"     # Disease -> Coverage / Exclusion
    REFERENCES = "REFERENCES"     # Clause -> Regulation
    RELATED_TO = "RELATED_TO"     # Concept <-> Concept
    VERSION_OF = "VERSION_OF"     # Clause -> Clause
    BELONGS_TO = "BELONGS_TO"     # Clause -> Product


class LayerType(str, Enum):
    """Knowledge Graph Layer (LegalGraphRAG alignment)."""
    FACT = "fact"
    ONTOLOGY = "ontology"
    RULE = "rule"


# ==========================================
# 2. Node Property Validation Schema
# ==========================================

class NodeSchema(BaseModel):
    """Schema model for Insurance Knowledge Graph Node."""
    model_config = ConfigDict(extra="allow")

    id: str = Field(..., description="Unique node ID, e.g. 'product_xxx_clause_3.2.1'")
    name: str = Field(..., description="Node display name")
    label: str = Field(..., description="Node type label")
    layer: str = Field(default="fact", description="Knowledge layer: 'fact', 'ontology', or 'rule'")
    source: Optional[str] = Field(None, description="Source document ID or path")
    source_url: Optional[str] = Field(None, description="Source document URL")
    text: Optional[str] = Field(None, description="Raw text snippet")
    version: Optional[str] = Field(None, description="Version string")
    effective_date: Optional[str] = Field(None, description="Effective date string (YYYY-MM-DD)")

    # Entity-specific properties
    clause_number: Optional[str] = Field(None, description="Clause number, e.g. '3.2.1'")
    clause_type: Optional[str] = Field(None, description="Clause type, e.g. 'coverage', 'exclusion'")
    limit: Optional[str] = Field(None, description="Coverage limit / sum insured string")
    deductible: Optional[str] = Field(None, description="Deductible description")
    waiting_period: Optional[int] = Field(None, description="Waiting period in days")

    @field_validator("label")
    @classmethod
    def validate_label(cls, v: str) -> str:
        valid_labels = {item.value for item in NodeLabel}
        if v not in valid_labels:
            raise ValueError(f"Invalid label '{v}'. Must be one of: {sorted(list(valid_labels))}")
        return v

    @field_validator("layer")
    @classmethod
    def validate_layer(cls, v: str) -> str:
        valid_layers = {item.value for item in LayerType}
        if v not in valid_layers:
            raise ValueError(f"Invalid layer '{v}'. Must be one of: {sorted(list(valid_layers))}")
        return v


# ==========================================
# 3. Edge Property Validation Schema
# ==========================================

class EdgeSchema(BaseModel):
    """Schema model for Insurance Knowledge Graph Edge."""
    model_config = ConfigDict(extra="allow")

    src: str = Field(..., description="Source node ID")
    dst: str = Field(..., description="Target node ID")
    rel_type: str = Field(..., description="Relation type")
    weight: float = Field(default=1.0, description="Edge weight")
    description: Optional[str] = Field(None, description="Relation description")

    @field_validator("rel_type")
    @classmethod
    def validate_rel_type(cls, v: str) -> str:
        valid_types = {item.value for item in RelationType}
        if v not in valid_types:
            raise ValueError(f"Invalid relation type '{v}'. Must be one of: {sorted(list(valid_types))}")
        return v


# ==========================================
# 4. Helper Validation Functions
# ==========================================

def validate_node(node_id: str, label: str | NodeLabel, name: str, **attrs) -> Dict[str, Any]:
    """Validates node arguments and returns clean attribute dictionary."""
    if isinstance(label, NodeLabel):
        label_str = label.value
    else:
        label_str = str(label)

    node_data = {
        "id": node_id,
        "name": name,
        "label": label_str,
        **attrs,
    }
    validated = NodeSchema(**node_data)
    return validated.model_dump(exclude_none=False)


def validate_edge(src: str, dst: str, rel_type: str | RelationType, **attrs) -> Dict[str, Any]:
    """Validates edge arguments and returns clean attribute dictionary."""
    if isinstance(rel_type, RelationType):
        rel_str = rel_type.value
    else:
        rel_str = str(rel_type)

    edge_data = {
        "src": src,
        "dst": dst,
        "rel_type": rel_str,
        **attrs,
    }
    validated = EdgeSchema(**edge_data)
    return validated.model_dump(exclude_none=False)
