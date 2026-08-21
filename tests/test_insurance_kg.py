"""
Comprehensive Unit Tests for Insurance Knowledge Graph (insurance_kg).
"""

import os
import tempfile
import pytest
from pydantic import ValidationError

import insurance_kg as ikg
from insurance_kg.schema import NodeLabel, RelationType, NodeSchema, EdgeSchema, validate_node, validate_edge


# ==========================================
# 1. Schema & Validation Tests
# ==========================================

def test_schema_valid_node():
    node_data = validate_node("p1", NodeLabel.PRODUCT, "Product 1", clause_number="1.0")
    assert node_data["id"] == "p1"
    assert node_data["label"] == "Product"
    assert node_data["name"] == "Product 1"


def test_schema_invalid_label():
    with pytest.raises(ValidationError) as excinfo:
        NodeSchema(id="n1", name="Test", label="InvalidLabel")
    assert "Invalid label" in str(excinfo.value)


def test_schema_invalid_relation():
    with pytest.raises(ValidationError) as excinfo:
        EdgeSchema(src="n1", dst="n2", rel_type="INVALID_REL")
    assert "Invalid relation type" in str(excinfo.value)


# ==========================================
# 2. Graph Store Operations Tests
# ==========================================

def test_kg_crud_and_queries():
    with tempfile.TemporaryDirectory() as tmpdir:
        kg_path = os.path.join(tmpdir, "test_kg.gpickle")
        kg = ikg.InsuranceKG(kg_path)

        # Add nodes
        kg.add_node("prod_01", NodeLabel.PRODUCT, name="重疾险2025")
        kg.add_node("c_1", NodeLabel.CLAUSE, name="基本保障条款", clause_number="3.1")
        kg.add_node("cov_1", NodeLabel.COVERAGE, name="重大疾病责任", limit="50万元")
        kg.add_node("ex_1", NodeLabel.EXCLUSION, name="既往症免责", text="既往症不予赔偿")

        # Add edges
        kg.add_edge("prod_01", "c_1", RelationType.HAS_CLAUSE)
        kg.add_edge("c_1", "cov_1", RelationType.DEFINES)
        kg.add_edge("cov_1", "ex_1", RelationType.EXCLUDES)

        # Property search
        prods = kg.find_by_property(NodeLabel.PRODUCT.value)
        assert len(prods) == 1
        assert prods[0]["name"] == "重疾险2025"

        # Neighbors
        c1_neighbors = kg.get_neighbors("c_1", rel_types=[RelationType.DEFINES.value], direction="out")
        assert len(c1_neighbors) == 1
        assert c1_neighbors[0]["node_id"] == "cov_1"

        # Multi-hop
        paths = kg.multi_hop("prod_01", path_pattern=[RelationType.HAS_CLAUSE.value, RelationType.DEFINES.value, RelationType.EXCLUDES.value])
        assert len(paths) == 1
        assert paths[0][-1]["to"] == "ex_1"

        # Domain Exclusion chain
        chain = kg.get_exclusion_chain("cov_1")
        assert len(chain) == 1
        assert chain[0]["exclusions"][0]["id"] == "ex_1"


# ==========================================
# 3. Persistence Tests
# ==========================================

def test_kg_persistence():
    with tempfile.TemporaryDirectory() as tmpdir:
        pickle_path = os.path.join(tmpdir, "kg.gpickle")
        graphml_path = os.path.join(tmpdir, "kg.graphml")

        kg = ikg.InsuranceKG(pickle_path)
        kg.add_node("prod_test", NodeLabel.PRODUCT, name="测试险种")
        kg.add_node("c_test", NodeLabel.CLAUSE, name="测试条款")
        kg.add_edge("prod_test", "c_test", RelationType.HAS_CLAUSE)

        # Save and Reload
        kg.save()
        assert os.path.exists(pickle_path)

        kg_loaded = ikg.InsuranceKG(pickle_path)
        assert len(kg_loaded.graph.nodes) == 2
        assert len(kg_loaded.graph.edges) == 1

        # Export GraphML
        kg.export_graphml(graphml_path)
        assert os.path.exists(graphml_path)

        # To dict / From dict
        data_dict = kg.to_dict()
        assert "nodes" in data_dict and ("links" in data_dict or "edges" in data_dict)

        kg_from_dict = ikg.InsuranceKG(os.path.join(tmpdir, "kg_dict.gpickle"))
        kg_from_dict.from_dict(data_dict)
        assert len(kg_from_dict.graph.nodes) == 2


# ==========================================
# 4. Extractor and Ingestion Tests
# ==========================================

def test_extractor_rule_based():
    extractor = ikg.ClauseExtractor()
    sample_text = """
    第1条 重大疾病保险金
    等待期 90 天后，首次患恶性肿瘤给付 100万元。
    第2条 责任免除
    既往症与遗传病不属于赔偿范围。
    """
    res = extractor.extract_from_text(sample_text, product_id="prod_demo", product_name=" Demo险")
    assert "entities" in res and "relations" in res
    assert len(res["entities"]) >= 2


def test_extractor_mock_llm():
    def mock_llm(sys_prompt, user_prompt):
        return """```json
        {
          "entities": [
            {"id": "p_mock", "label": "Product", "name": "Mock险"},
            {"id": "c_mock", "label": "Clause", "name": "Mock条款", "clause_number": "1.0"}
          ],
          "relations": [
            {"src": "p_mock", "dst": "c_mock", "rel_type": "HAS_CLAUSE"}
          ]
        }
        ```"""

    extractor = ikg.ClauseExtractor(llm_callable=mock_llm)
    res = extractor.extract_from_text("some text")
    assert len(res["entities"]) == 2
    assert res["entities"][0]["id"] == "p_mock"


def test_ingestion_pipeline():
    with tempfile.TemporaryDirectory() as tmpdir:
        kg_path = os.path.join(tmpdir, "kg.gpickle")
        file_path = os.path.join(tmpdir, "clause.md")

        with open(file_path, "w", encoding="utf-8") as f:
            f.write("第1条 医疗保险责任\n给付50万元赔偿金。")

        kg = ikg.InsuranceKG(kg_path)
        pipeline = ikg.IngestionPipeline(kg=kg)
        ingest_res = pipeline.ingest_file(file_path, product_id="prod_med", product_name="医疗险")

        assert ingest_res["nodes_count"] > 0
        assert len(kg.graph.nodes) > 0


# ==========================================
# 5. Agent Query Engine Tests
# ==========================================

def test_agent_query_engine():
    with tempfile.TemporaryDirectory() as tmpdir:
        kg_path = os.path.join(tmpdir, "kg.gpickle")
        kg = ikg.InsuranceKG(kg_path)

        kg.add_node("c_cov", NodeLabel.COVERAGE, name="恶性肿瘤给付责任", limit="50万元", source_url="https://lexiang.com/doc/1")
        kg.add_node("ex_cancer", NodeLabel.EXCLUSION, name="原位癌免责", text="原位癌除外")
        kg.add_edge("c_cov", "ex_cancer", RelationType.EXCLUDES)

        engine = ikg.KGQueryEngine(kg=kg)

        evidence = engine.query_exclusion_evidence("恶性肿瘤")
        assert evidence["evidence_count"] >= 1
        assert evidence["evidence_chain"][0]["source_url"] == "https://lexiang.com/doc/1"

        context_str = engine.query_for_llm_context("恶性肿瘤")
        assert "节点: 恶性肿瘤给付责任" in context_str


# ==========================================
# 6. Visualization Tests
# ==========================================

def test_visualization():
    with tempfile.TemporaryDirectory() as tmpdir:
        kg = ikg.InsuranceKG(os.path.join(tmpdir, "kg.gpickle"))
        kg.add_node("n1", NodeLabel.PRODUCT, name="产品1")
        kg.add_node("n2", NodeLabel.CLAUSE, name="条款1")
        kg.add_edge("n1", "n2", RelationType.HAS_CLAUSE)

        html_file = os.path.join(tmpdir, "vis.html")
        png_file = os.path.join(tmpdir, "vis.png")

        res_html = ikg.visualize_pyvis(kg, html_file)
        assert os.path.exists(res_html)

        res_png = ikg.visualize_matplotlib(kg, png_file)
        assert os.path.exists(res_png)
