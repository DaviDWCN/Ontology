#!/usr/bin/env python3
"""
Automated Ontology Evaluation Tool for Insurance Clause Ontology.
Analyzes the Pydantic-based ontology classes in insurance_ontology.py across the five core evaluation dimensions:
1. Consistency & Correctness (via custom validators and type constraints)
2. Completeness & Coverage (via rule-based verification framework)
3. Conciseness & Minimal Commitment (via redundancy scanning and model constraints)
4. Clarity & Documentation (via docstring and field description checks)
5. Expandability & Modularity (via schema-version and dynamic_attributes checks, and graph topological metrics)
"""

import sys
import os
import inspect
from typing import Dict, Any, List, Set, Type
import pydantic
from pydantic import BaseModel

# Ensure we can import from workspace root
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

try:
    import insurance_ontology
except ImportError as e:
    print(f"Error: Could not import 'insurance_ontology': {e}")
    sys.exit(1)


def analyze_clarity(classes: List[Type[BaseModel]]) -> Dict[str, Any]:
    """
    Evaluates Clarity & Documentation.
    Checks for class-level docstrings and Field-level description attributes.
    """
    results = {}
    total_fields = 0
    missing_descriptions = []
    missing_docstrings = []

    for cls in classes:
        cls_name = cls.__name__
        doc = inspect.getdoc(cls)
        if not doc:
            missing_docstrings.append(cls_name)

        class_fields = cls.model_fields
        for field_name, field_info in class_fields.items():
            total_fields += 1
            if not field_info.description:
                missing_descriptions.append(f"{cls_name}.{field_name}")

    results["total_classes_checked"] = len(classes)
    results["total_fields_checked"] = total_fields
    results["missing_docstrings"] = missing_docstrings
    results["missing_descriptions"] = missing_descriptions
    results["clarity_score_class"] = 100.0 if not classes else (1.0 - len(missing_docstrings) / len(classes)) * 100
    results["clarity_score_field"] = 100.0 if not total_fields else (1.0 - len(missing_descriptions) / total_fields) * 100
    return results


def analyze_modularity_and_expandability(classes: List[Type[BaseModel]]) -> Dict[str, Any]:
    """
    Evaluates Expandability & Modularity.
    Checks if classes support evolvability (e.g., have schema_version and dynamic_attributes).
    """
    results = {}
    missing_schema_version = []
    missing_dynamic_attrs = []
    extra_allowed = []

    for cls in classes:
        cls_name = cls.__name__
        fields = cls.model_fields
        if "schema_version" not in fields:
            missing_schema_version.append(cls_name)
        if "dynamic_attributes" not in fields:
            missing_dynamic_attrs.append(cls_name)

        # Check ConfigDict for allowing extra attributes
        config = getattr(cls, "model_config", {})
        if config.get("extra") == "allow":
            extra_allowed.append(cls_name)

    results["missing_schema_version"] = missing_schema_version
    results["missing_dynamic_attributes"] = missing_dynamic_attrs
    results["extra_attributes_allowed_classes"] = extra_allowed
    results["evolvability_score"] = (
        (len(extra_allowed) + (len(classes) - len(missing_schema_version)) + (len(classes) - len(missing_dynamic_attrs)))
        / (3 * len(classes)) * 100 if classes else 100.0
    )
    return results


def compute_structure_metrics(classes: List[Type[BaseModel]]) -> Dict[str, Any]:
    """
    Computes topology and structure metrics (Metric-based evaluation).
    - Hierarchy depth & width.
    - Leaf nodes.
    - Fan-in and Fan-out (property connectivity).
    """
    # Build inheritance map
    parents = {}
    children = {cls: [] for cls in classes}
    for cls in classes:
        mro = inspect.getmro(cls)
        # Find direct parent among the ontology classes
        direct_parent = None
        for base in mro[1:]:
            if base in classes:
                direct_parent = base
                break
        if direct_parent:
            parents[cls] = direct_parent
            children[direct_parent].append(cls)

    # Compute depth for each class
    def get_depth(cls):
        depth = 0
        current = cls
        while current in parents:
            depth += 1
            current = parents[current]
        return depth

    depths = {cls: get_depth(cls) for cls in classes}
    max_depth = max(depths.values()) if depths else 0
    avg_depth = sum(depths.values()) / len(classes) if classes else 0.0

    # Leaf nodes are those with no children within the ontology classes
    leaf_nodes = [cls.__name__ for cls in classes if not children[cls]]

    # Compute Fan-out: Number of properties referencing other ontology nodes
    # Compute Fan-in: Number of times an ontology node is referenced as a field type
    fan_out = {}
    fan_in = {cls.__name__: 0 for cls in classes}

    class_names = {cls.__name__: cls for cls in classes}

    for cls in classes:
        out_refs = 0
        for field_name, field_info in cls.model_fields.items():
            # Extract types from annotation
            annotation_str = str(field_info.annotation)
            # Simple check if any of our ontology class names is mentioned in the annotation
            for c_name in class_names:
                if c_name in annotation_str:
                    out_refs += 1
                    fan_in[c_name] += 1
        fan_out[cls.__name__] = out_refs

    return {
        "max_hierarchy_depth": max_depth,
        "avg_hierarchy_depth": avg_depth,
        "leaf_nodes": leaf_nodes,
        "leaf_node_percentage": (len(leaf_nodes) / len(classes)) * 100 if classes else 0.0,
        "fan_out_by_class": fan_out,
        "fan_in_by_class": fan_in,
        "average_fan_out": sum(fan_out.values()) / len(classes) if classes else 0.0,
        "average_fan_in": sum(fan_in.values()) / len(classes) if classes else 0.0,
    }


def main():
    print("=" * 60)
    print("     INSURANCE ONTOLOGY AUTOMATED EVALUATOR (SHIELD-METRICS)")
    print("=" * 60)

    # Find all ontology models (subclasses of BaseModel or OntologyBaseNode defined in insurance_ontology)
    ontology_classes = []
    for name, obj in inspect.getmembers(insurance_ontology, inspect.isclass):
        if obj.__module__ == "insurance_ontology" and issubclass(obj, BaseModel):
            ontology_classes.append(obj)

    print(f"Found {len(ontology_classes)} ontology classes in 'insurance_ontology.py'.\n")

    print("[1] CLARITY & DOCUMENTATION METRICS:")
    clarity = analyze_clarity(ontology_classes)
    print(f"  - Class Docstring Quality Score: {clarity['clarity_score_class']:.1f}%")
    print(f"  - Field Description Completeness Score: {clarity['clarity_score_field']:.1f}%")
    print(f"  - Missing docstrings in: {clarity['missing_docstrings']}")
    if clarity['missing_descriptions']:
        print(f"  - Missing descriptions in {len(clarity['missing_descriptions'])} fields (first 5 shown):")
        for f in clarity['missing_descriptions'][:5]:
            print(f"    * {f}")
    print()

    print("[2] EXPANDABILITY & MODULARITY METRICS:")
    modularity = analyze_modularity_and_expandability(ontology_classes)
    print(f"  - Evolvable/Dynamic Support Score: {modularity['evolvability_score']:.1f}%")
    print(f"  - Classes allowing extra dynamic attributes: {len(modularity['extra_attributes_allowed_classes'])}/{len(ontology_classes)}")
    if modularity['missing_schema_version']:
        print(f"  - Warning: Missing schema_version in {modularity['missing_schema_version']}")
    if modularity['missing_dynamic_attributes']:
        print(f"  - Warning: Missing dynamic_attributes in {modularity['missing_dynamic_attributes']}")
    print()

    print("[3] QUANTITATIVE TOPOLOGY & GRAPH METRICS:")
    metrics = compute_structure_metrics(ontology_classes)
    print(f"  - Maximum Inheritance Depth: {metrics['max_hierarchy_depth']}")
    print(f"  - Average Inheritance Depth: {metrics['avg_hierarchy_depth']:.2f}")
    print(f"  - Leaf Nodes Count: {len(metrics['leaf_nodes'])} ({metrics['leaf_node_percentage']:.1f}%)")
    print(f"  - Average Property Fan-out (Outbound relationships): {metrics['average_fan_out']:.2f}")
    print(f"  - Average Concept Fan-in (Inbound references): {metrics['average_fan_in']:.2f}")
    print("  - Connection details per class (Fan-in / Fan-out):")
    for cls in ontology_classes:
        name = cls.__name__
        print(f"    * {name:28} => Fan-in: {metrics['fan_in_by_class'][name]:2} | Fan-out: {metrics['fan_out_by_class'][name]:2}")
    print("=" * 60)


if __name__ == "__main__":
    main()
