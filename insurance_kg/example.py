from insurance_kg.graph_store import InsuranceKG
from insurance_kg.schema import NodeLabel, RelationType

def main():
    print("Initializing InsuranceKG...")
    kg = InsuranceKG()

    print("Adding nodes and edges...")
    # Add Product
    kg.add_node("prod_zhongji_2025", NodeLabel.PRODUCT, name="某重疾险2025")

    # Add Clause
    kg.add_node("c_3_2_1", NodeLabel.CLAUSE, name="重大疾病保险金", clause_number="3.2.1", text="若被保险人初次确诊患有本合同约定的重大疾病，我们将给付重大疾病保险金...")
    kg.add_edge("prod_zhongji_2025", "c_3_2_1", RelationType.HAS_CLAUSE)

    # Add Coverage
    kg.add_node("cov_cancer", NodeLabel.COVERAGE, name="恶性肿瘤-重度", limit="1000000")

    # Add Exclusion
    kg.add_node("exc_carcinoma_in_situ", NodeLabel.EXCLUSION, name="原位癌")
    kg.add_node("exc_pre_existing", NodeLabel.EXCLUSION, name="既往症")

    # Add relations
    kg.add_edge("c_3_2_1", "cov_cancer", RelationType.DEFINES)
    kg.add_edge("cov_cancer", "exc_carcinoma_in_situ", RelationType.EXCLUDES)
    kg.add_edge("cov_cancer", "exc_pre_existing", RelationType.EXCLUDES)

    # Add Disease & Concept
    kg.add_node("dis_cancer_C80", NodeLabel.DISEASE, name="恶性肿瘤-重度(C80)")
    kg.add_edge("dis_cancer_C80", "cov_cancer", RelationType.APPLIES_TO)

    print("Saving graph...")
    kg.save()

    # Optional: export to graphml for visualization in tools like Gephi
    kg.export_graphml("insurance_kg/data/graph/kg.graphml")

    print("\n--- Testing Queries ---")

    print("1. Get Exclusion Chain for 'cov_cancer':")
    exclusions = kg.get_exclusion_chain("cov_cancer")
    for exc in exclusions:
        print(f"  - [{exc.get('id')}] {exc.get('name')}")

    print("\n2. Get Related Clauses for disease 'dis_cancer_C80':")
    clauses = kg.get_related_clauses("dis_cancer_C80")
    for clause in clauses:
        print(f"  - Clause {clause.get('clause_number')}: {clause.get('name')}")

    print("\n3. Find by property (Label=EXCLUSION, name='原位癌'):")
    res = kg.find_by_property(NodeLabel.EXCLUSION, name="原位癌")
    print(f"  Result: {res}")

    print("\n4. Multi-hop path from Clause 'c_3_2_1' following DEFINES -> EXCLUDES:")
    paths = kg.multi_hop("c_3_2_1", [RelationType.DEFINES, RelationType.EXCLUDES])
    for path in paths:
        # Resolve names for display
        names = [kg.graph.nodes[nid].get('name', nid) for nid in path]
        print(f"  Path: {' -> '.join(names)}")

if __name__ == "__main__":
    main()
