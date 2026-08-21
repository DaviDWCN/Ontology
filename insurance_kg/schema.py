from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class NodeLabel(str, Enum):
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
    HAS_CLAUSE = "HAS_CLAUSE"         # Product -> Clause
    DEFINES = "DEFINES"               # Clause -> Coverage / Exclusion / Condition
    EXCLUDES = "EXCLUDES"             # Coverage -> Exclusion
    REQUIRES = "REQUIRES"             # Coverage -> Condition
    APPLIES_TO = "APPLIES_TO"         # Disease -> Coverage / Exclusion
    REFERENCES = "REFERENCES"         # Clause -> Regulation
    RELATED_TO = "RELATED_TO"         # Concept <-> Concept (同义、上下位)
    VERSION_OF = "VERSION_OF"         # Clause -> Clause (版本演进)
    BELONGS_TO = "BELONGS_TO"         # Clause -> Product


class BaseNodeProps(BaseModel):
    """通用节点属性"""
    name: str = Field(..., description="节点名称")
    layer: Optional[str] = Field(None, description="所属层: fact | ontology | rule")
    source: Optional[str] = Field(None, description="来源文档ID或本地文件路径")
    source_url: Optional[str] = Field(None, description="乐享链接或源链接，方便溯源")
    text: Optional[str] = Field(None, description="原文片段")
    version: Optional[str] = Field(None, description="版本")
    effective_date: Optional[str] = Field(None, description="生效日期")

class ClauseNodeProps(BaseNodeProps):
    """条款特有属性"""
    clause_number: str = Field(..., description="条款编号, 如 '3.2.1'")
    clause_type: Optional[str] = Field(None, description="条款类型: coverage | exclusion | definition")

class CoverageExclusionNodeProps(BaseNodeProps):
    """保障责任/免责特有属性"""
    limit: Optional[str] = Field(None, description="保额/限额")
    deductible: Optional[str] = Field(None, description="免赔额")
    waiting_period: Optional[int] = Field(None, description="等待期天数")
