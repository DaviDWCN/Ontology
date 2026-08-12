"""
Insurance Clause Ontology Specification - Python Pydantic v2 Implementation
Version: 2.0.0
Author: Knowledge Engineering Team
"""

from __future__ import annotations
from enum import Enum
from typing import List, Optional, Dict, Any, Union
from pydantic import BaseModel, Field, ConfigDict


# ==========================================
# 1. 枚举类型定义 (Enumerations)
# ==========================================

class SchemaVersion(str, Enum):
    V2_0_0 = "v2.0.0"

class ObjectType(str, Enum):
    REAL_ESTATE = "RealEstate"          # 建筑物/厂房
    EQUIPMENT = "Equipment"            # 机器设备
    INVENTORY = "Inventory"            # 存货/原材料
    LIABILITY = "Liability"            # 第三者/雇主责任
    PERSON = "Person"                  # 人身/被保险人
    BUSINESS_PROFIT = "BusinessProfit" # 营业中断利润

class DeductibleType(str, Enum):
    ABSOLUTE_AMOUNT = "AbsoluteAmount"      # 绝对免赔额
    ABSOLUTE_PERCENT = "AbsolutePercentage"  # 绝对免赔率
    HIGHER_OF = "HigherOfAmountOrPercent"   # 两者取高
    LOWER_OF = "LowerOfAmountOrPercent"     # 两者取低
    NONE = "None"

class TimeUnit(str, Enum):
    HOUR = "Hour"
    DAY = "Day"
    MONTH = "Month"
    YEAR = "Year"


# ==========================================
# 2. 动态演进基类 (Evolvable Core)
# ==========================================

class OntologyBaseNode(BaseModel):
    """支持版本控制与动态属性扩充的本体基类"""
    model_config = ConfigDict(
        extra="allow",  # 捕获未知属性，防止 LLM 抽取崩溃
        populate_by_name=True
    )

    id: str = Field(..., description="节点的全局唯一标识符 (URI/UUID)")
    schema_version: SchemaVersion = Field(default=SchemaVersion.V2_0_0, description="本体规范版本")
    dynamic_attributes: Dict[str, Any] = Field(
        default_factory=dict,
        description="未纳入当前本体强类型的未知属性缓冲池，用于后续迭代聚类"
    )


# ==========================================
# 3. 领域核心节点类 (Domain Entities)
# ==========================================

class InsuredObject(OntologyBaseNode):
    """保险标的物/对象"""
    name: str = Field(..., description="标的物名称，如：1号生产车间大楼及机械设备")
    object_type: ObjectType = Field(..., description="标的物分类")
    declared_value: Optional[float] = Field(None, description="声明/投保价值 (元)")
    description: Optional[str] = Field(None, description="标的物补充描述")


class LocationScope(OntologyBaseNode):
    """坐落地点与地理管辖范围"""
    address: str = Field(..., description="详细地址或坐落位置")
    territory_code: str = Field(default="CN", description="国家/地区 ISO 编码")
    is_transit: bool = Field(default=False, description="是否为运输途中的动态路线")


class FinancialRule(OntologyBaseNode):
    """理算与免赔规则（可计算节点）"""
    deductible_type: DeductibleType = Field(default=DeductibleType.NONE, description="免赔额类型")
    deductible_amount: float = Field(default=0.0, description="绝对免赔金额 (元)")
    deductible_rate: float = Field(default=0.0, description="免赔比例 (0.0-1.0)")
    payout_ratio: float = Field(default=1.0, description="赔付比例/不足额投保比例 (0.0-1.0)")
    rule_logic_expr: Optional[str] = Field(None, description="伪代码/表达式，如 MAX(5000, Loss * 0.1)")


class SpecialClause(OntologyBaseNode):
    """特别约定与扩展条款"""
    clause_name: str = Field(..., description="特约/批条名称，如：72小时巨灾条款")
    time_window_hours: Optional[int] = Field(None, description="时间限制窗口(小时)")
    raw_text: str = Field(..., description="特约原文文本")


class Exclusion(OntologyBaseNode):
    """责任免除事项"""
    exclusion_name: str = Field(..., description="免责简述，如：地震及海啸免责")
    raw_text: str = Field(..., description="免责原文文本")


class InsuredHazard(OntologyBaseNode):
    """危险因数/风险事件/疾病诊断"""
    hazard_name: str = Field(..., description="危险名称，如：暴雨、火灾、重型再生障碍性贫血")
    hazard_category: str = Field(..., description="危险大类，如：NaturalDisaster/Accident/Disease")
    standard_code: Optional[str] = Field(None, description="标准编码，如 ICD-10 编码 D61.0")


# ==========================================
# 4. 聚合责任与产品树 (Aggregate Composite)
# ==========================================

class Coverage(OntologyBaseNode):
    """保险责任/给付节点"""
    coverage_name: str = Field(..., description="责任名称，如：财产基本责任、水管爆裂扩展责任")
    is_main_coverage: bool = Field(default=True, description="是否为主险责任")
    sum_insured: Optional[float] = Field(None, description="该项责任的保额/最高赔偿限额")

    # 拓扑图关系挂载
    applies_to_objects: List[InsuredObject] = Field(..., description="作用的标的物列表")
    covers_hazards: List[InsuredHazard] = Field(..., description="涵盖的危险因数列表")
    locations: List[LocationScope] = Field(default_factory=list, description="生效地点限制")
    financial_rules: List[FinancialRule] = Field(default_factory=list, description="绑定的理算/免赔规则")
    special_clauses: List[SpecialClause] = Field(default_factory=list, description="修饰该责任的特约")
    exclusions: List[Exclusion] = Field(default_factory=list, description="排除的免责事项")


class InsuranceProductOntology(OntologyBaseNode):
    """完整产品/保单知识图谱抽取根节点"""
    product_code: str = Field(..., description="产品/保单代码")
    product_name: str = Field(..., description="产品官方名称")
    coverages: List[Coverage] = Field(..., description="包含的所有责任树节点")