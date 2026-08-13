import pytest
from pydantic import ValidationError
from insurance_ontology import (
    InsuranceProductOntology,
    Coverage,
    InsuredObject,
    ObjectType,
    LocationScope,
    FinancialRule,
    DeductibleType,
    SpecialClause,
    Exclusion,
    InsuredHazard,
    SchemaVersion,
)


# ==========================================
# 1. 一致性与约束校验测试 (Consistency & Constraints)
# ==========================================

def test_financial_rule_validation_success():
    """测试有效的财务与免赔规则数值"""
    rule = FinancialRule(
        id="rule:001",
        deductible_type=DeductibleType.ABSOLUTE_AMOUNT,
        deductible_amount=5000.0,
        deductible_rate=0.10,
        payout_ratio=0.90,
    )
    assert rule.deductible_amount == 5000.0
    assert rule.deductible_rate == 0.10
    assert rule.payout_ratio == 0.90


def test_financial_rule_validation_failure_negative_amount():
    """测试免赔额不能为负数"""
    with pytest.raises(ValidationError) as excinfo:
        FinancialRule(
            id="rule:err_neg",
            deductible_amount=-500.0,
        )
    assert "deductible_amount cannot be negative" in str(excinfo.value)


def test_financial_rule_validation_failure_rate_out_of_bounds():
    """测试免赔率和给付比例必须在 [0, 1] 之间"""
    with pytest.raises(ValidationError) as excinfo1:
        FinancialRule(id="rule:err_rate_high", deductible_rate=1.1)
    assert "deductible_rate must be between 0.0 and 1.0" in str(excinfo1.value)

    with pytest.raises(ValidationError) as excinfo2:
        FinancialRule(id="rule:err_rate_low", deductible_rate=-0.01)
    assert "deductible_rate must be between 0.0 and 1.0" in str(excinfo2.value)

    with pytest.raises(ValidationError) as excinfo3:
        FinancialRule(id="rule:err_ratio_high", payout_ratio=1.5)
    assert "payout_ratio must be between 0.0 and 1.0" in str(excinfo3.value)


# ==========================================
# 2. 真实场景建模与能力问题测试 (CQs & Scenarios)
# ==========================================

@pytest.fixture
def complex_property_policy() -> InsuranceProductOntology:
    """
    构建一个复杂的企财险保险产品图谱场景：
    - 保障标的物：1号生产车间 (不动产) 和 关键生产线设备 (动产)
    - 地点：北京市朝阳区高新产业园
    - 责任一（主险）：财产基本损失责任
      - 涵盖危险：火灾 (意外), 爆炸 (意外)
      - 免赔规则：5000元绝对免赔额
    - 责任二（附加险）：水管爆裂与自然灾害责任
      - 涵盖危险：暴雨 (自然灾害), 洪水 (自然灾害)
      - 免赔规则：以高者为准 (HigherOf) - 5000元或损失的10%
      - 特别约定：72小时巨灾时间窗口条款
      - 责任免除：地震、战争免责
    """
    # 1. 标的物
    workshop = InsuredObject(
        id="obj:workshop_01",
        name="1号生产车间",
        object_type=ObjectType.REAL_ESTATE,
        declared_value=12000000.0,
        description="钢筋混凝土结构主厂房"
    )
    equipment = InsuredObject(
        id="obj:equip_01",
        name="智能制造精密生产线",
        object_type=ObjectType.EQUIPMENT,
        declared_value=8000000.0,
        description="德产高精密光刻与拼装设备"
    )

    # 2. 坐落地点
    loc = LocationScope(
        id="loc:beijing_chaoyang",
        address="北京市朝阳区高新产业园A区12号",
        territory_code="CN"
    )

    # 3. 危险因数
    hazard_fire = InsuredHazard(
        id="haz:fire",
        hazard_name="火灾",
        hazard_category="Accident"
    )
    hazard_explosion = InsuredHazard(
        id="haz:explosion",
        hazard_name="爆炸",
        hazard_category="Accident"
    )
    hazard_rain = InsuredHazard(
        id="haz:heavy_rain",
        hazard_name="暴雨",
        hazard_category="NaturalDisaster"
    )
    hazard_flood = InsuredHazard(
        id="haz:flood",
        hazard_name="洪水",
        hazard_category="NaturalDisaster"
    )

    # 4. 理算与免赔规则
    rule_main = FinancialRule(
        id="rule:main_deductible",
        deductible_type=DeductibleType.ABSOLUTE_AMOUNT,
        deductible_amount=5000.0,
        payout_ratio=1.0
    )
    rule_rider = FinancialRule(
        id="rule:rider_deductible",
        deductible_type=DeductibleType.HIGHER_OF,
        deductible_amount=5000.0,
        deductible_rate=0.10,
        rule_logic_expr="MAX(5000.0, LossAmount * 0.10)"
    )

    # 5. 特约与条款
    clause_72h = SpecialClause(
        id="clause:72_hour",
        clause_name="72小时巨灾特别约定",
        time_window_hours=72,
        raw_text="连续72小时内发生的由暴雨、洪水造成的损失视为一次保险事故。"
    )

    # 6. 免责
    ex_earthquake = Exclusion(
        id="ex:earthquake",
        exclusion_name="地震及海啸责任免除",
        raw_text="由于地震、海啸及地陷导致的任何财产损失不予赔偿。"
    )
    ex_war = Exclusion(
        id="ex:war",
        exclusion_name="战争与军事行动免除",
        raw_text="因战争、军事冲突或暴乱引起的损失属于除外责任。"
    )

    # 7. 保障责任定义
    cov_main = Coverage(
        id="cov:main_property",
        coverage_name="财产基本险主险责任",
        is_main_coverage=True,
        sum_insured=20000000.0,
        applies_to_objects=[workshop, equipment],
        covers_hazards=[hazard_fire, hazard_explosion],
        locations=[loc],
        financial_rules=[rule_main],
    )

    cov_rider = Coverage(
        id="cov:rider_weather",
        coverage_name="附加水管爆裂及自然灾害责任",
        is_main_coverage=False,
        sum_insured=5000000.0,
        applies_to_objects=[workshop],
        covers_hazards=[hazard_rain, hazard_flood],
        locations=[loc],
        financial_rules=[rule_rider],
        special_clauses=[clause_72h],
        exclusions=[ex_earthquake, ex_war],
    )

    # 8. 产品根节点
    product = InsuranceProductOntology(
        id="prod:enterprise_all_risk",
        product_code="PAR-2026-V1",
        product_name="企业综合财产守护计划2026",
        coverages=[cov_main, cov_rider]
    )
    return product


# ==========================================
# 3. 能力问题 (Competency Questions) 专项测试
# ==========================================

def test_cq1_total_sum_insured(complex_property_policy):
    """
    CQ1: 产品下所有保障责任的最高赔偿限额总和是多少？
    """
    total_si = sum(cov.sum_insured for cov in complex_property_policy.coverages if cov.sum_insured is not None)
    assert total_si == 25000000.0  # 2000万主险 + 500万附加险


def test_cq2_coverages_for_insured_object(complex_property_policy):
    """
    CQ2: 哪些保障责任作用于特定的标的物 "1号生产车间"？哪些作用于 "智能制造精密生产线"？
    """
    # 查询作用于 "1号生产车间" 的责任
    covs_for_workshop = [
        cov.coverage_name
        for cov in complex_property_policy.coverages
        if any(obj.name == "1号生产车间" for obj in cov.applies_to_objects)
    ]
    assert "财产基本险主险责任" in covs_for_workshop
    assert "附加水管爆裂及自然灾害责任" in covs_for_workshop

    # 查询作用于 "智能制造精密生产线" 的责任
    covs_for_equip = [
        cov.coverage_name
        for cov in complex_property_policy.coverages
        if any(obj.name == "智能制造精密生产线" for obj in cov.applies_to_objects)
    ]
    assert "财产基本险主险责任" in covs_for_equip
    assert "附加水管爆裂及自然灾害责任" not in covs_for_equip  # 精密设备不承担水管及自然灾害附加险


def test_cq3_exclusions_for_coverage(complex_property_policy):
    """
    CQ3: "附加水管爆裂及自然灾害责任" 责任下有哪些责任免除（Exclusion）事项？
    """
    target_coverage = next(
        cov for cov in complex_property_policy.coverages
        if cov.id == "cov:rider_weather"
    )
    exclusions = [ex.exclusion_name for ex in target_coverage.exclusions]
    assert "地震及海啸责任免除" in exclusions
    assert "战争与军事行动免除" in exclusions


def test_cq4_special_clause_time_window(complex_property_policy):
    """
    CQ4: 附加险责任是否包含特定的时间窗口约束（如 72小时巨灾条款）？
    """
    target_coverage = next(
        cov for cov in complex_property_policy.coverages
        if cov.id == "cov:rider_weather"
    )
    # 查找是否有 time_window_hours 存在的特约
    time_windows = [
        clause.time_window_hours
        for clause in target_coverage.special_clauses
        if clause.time_window_hours is not None
    ]
    assert len(time_windows) == 1
    assert time_windows[0] == 72


def test_cq5_deductible_rules_and_expressions(complex_property_policy):
    """
    CQ5: 附加险责任下的免赔额逻辑是什么？它的计算表达式是怎样的？
    """
    target_coverage = next(
        cov for cov in complex_property_policy.coverages
        if cov.id == "cov:rider_weather"
    )
    rule = target_coverage.financial_rules[0]
    assert rule.deductible_type == DeductibleType.HIGHER_OF
    assert rule.deductible_amount == 5000.0
    assert rule.deductible_rate == 0.10
    assert rule.rule_logic_expr == "MAX(5000.0, LossAmount * 0.10)"


def test_cq6_covered_hazards(complex_property_policy):
    """
    CQ6: 主险责任涵盖哪些具体的危险事件/风险？这些危险属于什么大类？
    """
    target_coverage = next(
        cov for cov in complex_property_policy.coverages
        if cov.id == "cov:main_property"
    )
    hazard_info = {haz.hazard_name: haz.hazard_category for haz in target_coverage.covers_hazards}
    assert "火灾" in hazard_info
    assert "爆炸" in hazard_info
    assert hazard_info["火灾"] == "Accident"
    assert hazard_info["爆炸"] == "Accident"


# ==========================================
# 4. 人身健康险领域建模测试 (Health Insurance Scenario)
# ==========================================

def test_health_insurance_scenario():
    """
    测试人身健康险本体：
    - 标的物：PersonSubject
    - 包含 ICD-10 标准编码的重大疾病诊断危险
    """
    insured_person = InsuredObject(
        id="obj:insured_person_01",
        name="张三",
        object_type=ObjectType.PERSON,
        description="出生日期 1985-05-12, 职业分类: 1类"
    )

    hazard_cancer = InsuredHazard(
        id="haz:cancer_01",
        hazard_name="恶性肿瘤-重度",
        hazard_category="Disease",
        standard_code="ICD-10 C80.000"
    )

    rule_health = FinancialRule(
        id="rule:health_payout",
        deductible_type=DeductibleType.NONE,
        deductible_amount=0.0,
        payout_ratio=1.0,
    )

    cov_health = Coverage(
        id="cov:severe_illness",
        coverage_name="重大疾病给付责任",
        is_main_coverage=True,
        sum_insured=500000.0,
        applies_to_objects=[insured_person],
        covers_hazards=[hazard_cancer],
        financial_rules=[rule_health]
    )

    health_product = InsuranceProductOntology(
        id="prod:severe_illness_guardian",
        product_code="HLTH-2026-01",
        product_name="终身重大疾病守护计划",
        coverages=[cov_health]
    )

    assert health_product.product_name == "终身重大疾病守护计划"
    assert health_product.coverages[0].covers_hazards[0].standard_code == "ICD-10 C80.000"
    assert health_product.coverages[0].applies_to_objects[0].object_type == ObjectType.PERSON
