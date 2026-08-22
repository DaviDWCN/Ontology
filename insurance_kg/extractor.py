"""
LLM and Rule-based Extraction Engine for Insurance Clause Text.
Extracts nodes and relations matching insurance_kg schema from unstructured clause text.
"""

from __future__ import annotations
import re
import json
import logging
from typing import Dict, Any, List, Optional, Callable
from insurance_kg.schema import NodeLabel, RelationType

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are an expert Insurance Ontology Knowledge Graph Extractor.
Extract entities and relations from the provided insurance clause text adhering strictly to the schema below.

Allowed Node Labels:
- Product          # 保险产品名称
- Clause           # 条款条目（带条款编号，如 3.2.1）
- Coverage         # 保障责任
- Exclusion        # 免责/除外责任
- Condition        # 条件/等待期/投保要求
- Disease          # 疾病/病种定义
- Occupation       # 职业
- Benefit          # 给付/理赔条件
- Regulation       # 监管文件/法规引用
- Concept          # 抽象概念（如既往症、等待期）

Allowed Relation Types:
- HAS_CLAUSE       # Product -> Clause
- DEFINES          # Clause -> Coverage / Exclusion / Condition
- EXCLUDES         # Coverage -> Exclusion
- REQUIRES         # Coverage -> Condition
- APPLIES_TO       # Disease -> Coverage / Exclusion
- REFERENCES       # Clause -> Regulation
- RELATED_TO       # Concept <-> Concept
- VERSION_OF       # Clause -> Clause
- BELONGS_TO       # Clause -> Product

Output MUST be a JSON object with two lists: "entities" and "relations".
Example JSON format:
{
  "entities": [
    {
      "id": "prod_01",
      "label": "Product",
      "name": "某重疾险2025",
      "source": "doc_001"
    },
    {
      "id": "c_3_2_1",
      "label": "Clause",
      "name": "重大疾病保险金",
      "clause_number": "3.2.1",
      "clause_type": "coverage",
      "text": "..."
    },
    {
      "id": "cov_cancer",
      "label": "Coverage",
      "name": "恶性肿瘤",
      "limit": "50万元"
    },
    {
      "id": "exc_carcinoma_in_situ",
      "label": "Exclusion",
      "name": "原位癌免责",
      "text": "原位癌不属于本合同保障的重疾"
    }
  ],
  "relations": [
    {
      "src": "prod_01",
      "dst": "c_3_2_1",
      "rel_type": "HAS_CLAUSE"
    },
    {
      "src": "c_3_2_1",
      "dst": "cov_cancer",
      "rel_type": "DEFINES"
    },
    {
      "src": "cov_cancer",
      "dst": "exc_carcinoma_in_situ",
      "rel_type": "EXCLUDES"
    }
  ]
}
"""


class ClauseExtractor:
    """Extractor for converting insurance text to structured graph nodes and relations."""

    def __init__(self, llm_callable: Optional[Callable[[str, str], str]] = None):
        """
        :param llm_callable: Optional custom function f(system_prompt, user_prompt) -> str JSON response.
        """
        self.llm_callable = llm_callable

    def extract_from_text(
        self,
        text: str,
        product_id: str = "prod_default",
        product_name: str = "保险产品",
        source: str = "local_doc",
        source_url: str = ""
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Extracts graph entities and relations from text using LLM if available, otherwise rule-based fallback."""
        if self.llm_callable:
            try:
                user_prompt = f"Product ID: {product_id}\nProduct Name: {product_name}\nSource: {source}\nSource URL: {source_url}\n\nClause Text:\n{text}"
                response_str = self.llm_callable(SYSTEM_PROMPT, user_prompt)
                # Parse JSON block
                clean_str = re.sub(r"```json\s*(.*?)\s*```", r"\1", response_str, flags=re.DOTALL).strip()
                data = json.loads(clean_str)
                if isinstance(data, dict) and "entities" in data and "relations" in data:
                    return data
            except Exception as e:
                logger.warning(f"LLM extraction failed or returned invalid JSON ({e}). Falling back to rule-based parser.")

        return self._rule_based_extract(text, product_id, product_name, source, source_url)

    def _rule_based_extract(
        self,
        text: str,
        product_id: str,
        product_name: str,
        source: str,
        source_url: str
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Rule-based regex parser to build baseline nodes/edges from clause text."""
        entities = []
        relations = []

        # Product node
        entities.append({
            "id": product_id,
            "label": NodeLabel.PRODUCT.value,
            "name": product_name,
            "source": source,
            "source_url": source_url,
        })

        # Regex for clause numbers like "第x条", "1.2", "3.2.1"
        clause_matches = list(re.finditer(r"(?:第\s*[\d一二三四五六七八九十]+\s*条|[\d]+\.[\d]+(?:\.[\d]+)?)\s*([^\n]+)", text))

        if not clause_matches:
            # Fallback single clause
            c_id = f"{product_id}_c1"
            entities.append({
                "id": c_id,
                "label": NodeLabel.CLAUSE.value,
                "name": product_name + "条款条目",
                "clause_number": "1.0",
                "text": text[:200],
                "source": source,
                "source_url": source_url,
            })
            relations.append({
                "src": product_id,
                "dst": c_id,
                "rel_type": RelationType.HAS_CLAUSE.value,
            })
            return {"entities": entities, "relations": relations}

        for idx, match in enumerate(clause_matches):
            raw_title = match.group(0).strip()
            clause_title = match.group(1).strip()
            # Clause number extraction
            num_match = re.search(r"[\d]+\.[\d]+(?:\.[\d]+)?|第\s*[\d一二三四五六七八九十]+\s*条", raw_title)
            c_num = num_match.group(0) if num_match else f"1.{idx+1}"
            c_id = f"{product_id}_c_{c_num.replace('.', '_').replace(' ', '')}"

            # Snippet text
            start_pos = match.start()
            end_pos = clause_matches[idx + 1].start() if idx + 1 < len(clause_matches) else len(text)
            clause_text = text[start_pos:end_pos].strip()

            c_type = "general"
            if "责任" in clause_title or "保障" in clause_title:
                c_type = "coverage"
            elif "免除" in clause_title or "除外" in clause_title:
                c_type = "exclusion"

            entities.append({
                "id": c_id,
                "label": NodeLabel.CLAUSE.value,
                "name": clause_title or f"条款 {c_num}",
                "clause_number": c_num,
                "clause_type": c_type,
                "text": clause_text[:300],
                "source": source,
                "source_url": source_url,
            })

            relations.append({
                "src": product_id,
                "dst": c_id,
                "rel_type": RelationType.HAS_CLAUSE.value,
            })

            # Check for exclusions mentioned in clause text
            if "免除" in clause_text or "除外" in clause_text or "不承担" in clause_text:
                ex_id = f"{c_id}_ex"
                ex_name = f"{clause_title} - 责任免除"
                entities.append({
                    "id": ex_id,
                    "label": NodeLabel.EXCLUSION.value,
                    "name": ex_name,
                    "text": clause_text[:200],
                    "source": source,
                    "source_url": source_url,
                })
                relations.append({
                    "src": c_id,
                    "dst": ex_id,
                    "rel_type": RelationType.DEFINES.value,
                })

            # Check for coverage defined
            if "保险金" in clause_text or "赔偿" in clause_text or "给付" in clause_text:
                cov_id = f"{c_id}_cov"
                cov_name = f"{clause_title} - 给付责任"
                # Check limit or waiting period in text
                limit_match = re.search(r"([\d]+万(?:元)?|[\d]+%)", clause_text)
                limit_val = limit_match.group(1) if limit_match else None

                wp_match = re.search(r"等待期\s*([\d]+)\s*天", clause_text)
                wp_val = int(wp_match.group(1)) if wp_match else None

                cov_attrs = {
                    "id": cov_id,
                    "label": NodeLabel.COVERAGE.value,
                    "name": cov_name,
                    "source": source,
                    "source_url": source_url,
                }
                if limit_val:
                    cov_attrs["limit"] = limit_val
                if wp_val:
                    cov_attrs["waiting_period"] = wp_val

                entities.append(cov_attrs)
                relations.append({
                    "src": c_id,
                    "dst": cov_id,
                    "rel_type": RelationType.DEFINES.value,
                })

        return {"entities": entities, "relations": relations}
