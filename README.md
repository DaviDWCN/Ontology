# 保险条款本体规范与终极架构建议

这份文档包含一份**落地效果最好、工程可行性最高、ROI（投入产出比）最佳的终极实施建议**，并附上一份**可以直接交付给工程团队落地的企业级《保险条款本体规范说明书（Ontology Specification Document）》**。

---

## 第一部分：综合最佳落地建议与技术选型

### 1. 终极架构路线：本体驱动的“双态”GraphRAG 方案
不要做纯向量 RAG，也不要做复杂的纯符号推理。最优雅的 SOTA 架构是 **“神经-符号双态混合架构”**：
* **静态事实（符号态）**：利用 **Protégé + Neo4j** 存储经过 Ontology 严格约束的产品、责任、免责、条件关系链，确保涉及赔付计算、免赔额判定时 **零幻觉**。
* **动态语义（神经态）**：利用 **Qdrant/Milvus + Vector Chunk** 存储原始文本片段与诊断标准细节，利用大模型做语义泛化与同义词泛化。

### 2. 端到端开源技术栈最佳组合（Production Stack）

| 阶段 | 推荐开源软件/工具 | 选型理由 |
| :--- | :--- | :--- |
| **本体建模与评审** | **Protégé + WebVOWL** | 工业标准，图形化绘制 Ontology，支持导出 JSON/OWL；WebVOWL 用于生成可视化网页给保险精算/核保专家评审。 |
| **文档解析** | **Docling / MinerU** | 目前开源界版面还原（PDF/Docx）最好的工具，能精准保留条款的表格、章节树状层级。 |
| **结构化抽取** | **DeepSeek-R1/V3 + Instructor** | 利用 Instructor (Python) + Pydantic v2 强行约束 LLM 按本体 Schema 输出 JSON，DeepSeek 推理能力强且成本极低。 |
| **本体代码集成** | **Owlready2 + Pydantic v2** | 用 Python 原生代码操作 OWL 本体，兼具面向对象开发效率与语义网推理能力。 |
| **图与向量存储** | **Neo4j + Qdrant** | Neo4j 存储拓扑结构（可直接运行 Cypher）；Qdrant 存储原始条款 Chunk 和医学/法律定义向量。 |
| **检索与推理** | **LightRAG / LlamaIndex** | 结合 Text-to-Cypher 图检索与向量检索，实现轻量级混合 RAG 问答。 |

### 3. 本体动态演进闭环机制（如何做到可迭代）
1. **缓冲池设计**：在提取代码中强制留出 `dynamic_attributes` JSON 字典，LLM 抽到 Schema 之外的新字段不报错、不丢弃，直接压入缓冲池。
2. **月度挖掘**：每月运行脚本聚类分析 `dynamic_attributes` 中的高频新词（例如突然出现的“网络安全中断损失”）。
3. **版本晋升**：由知识工程师在 Protégé 中把高频新词提炼为正式的 Class/Property，发布 Ontology `vX.Y` 版本，更新 Pydantic Schema，实现零停机升级。

---

## 第二部分：企业级保险条款本体规范说明书 (Ontology Specification Spec v2.0)

> **文档状态**：Draft for Release (可直接作为工程团队与 AI 团队的标准 RFC)
> **面向领域**：全险种（重点覆盖财产险、工程险、责任险、健康险与寿险）
> **兼容标准**：OWL 2, W3C RDF, Pydantic v2, ICD-10, GB/T 职业分类

---

### 1. 规范概述与架构原则

#### 1.1 命名空间 (Namespaces)
* **Default Prefix**: `ins:` (`http://ontology.enterprise.com/insurance/v2#`)
* **OWL/RDF Prefixes**: `owl:`, `rdf:`, `rdfs:`, `xsd:`, `sh:`

#### 1.2 架构原则
1. **高聚类低耦合**：解耦“标的物”、“危险因数”、“理算规则”，支持多责任交叉组合。
2. **强类型计算**：绝对免赔额、百分比、时间窗口强制存为数值类型（Float/Int）加单位（Enum），拒绝纯文本。
3. **版本自适应**：包含 `SchemaVersion` 与 `DynamicAttributes` 属性，确保代码与数据的向下兼容性。

---

### 2. 概念模型层级 (Class Hierarchy)

```text
ins:InsuranceOntologyRoot
 ├── ins:InsuranceProduct (保险产品/方案)
 ├── ins:InsuredObject (保险标的物)
 │    ├── ins:RealProperty (不动产/建筑物/厂房)
 │    ├── ins:PersonalProperty (动产/设备/存货)
 │    ├── ins:LiabilitySubject (责任标的/雇主责任/公众责任)
 │    └── ins:PersonSubject (人身标的/被保险人)
 ├── ins:LocationScope (坐落地点/地理与管辖范围)
 ├── ins:Coverage (保障责任)
 │    ├── ins:MainCoverage (主险责任)
 │    └── ins:RiderCoverage (附加险责任)
 ├── ins:InsuredHazard (风险事件/危险因数)
 │    ├── ins:NaturalHazard (自然灾害: 暴雨/地震等)
 │    ├── ins:AccidentalHazard (意外事故: 火灾/爆炸/碰撞)
 │    └── ins:DiseaseHazard (疾病/诊断事件)
 ├── ins:FinancialRule (财务理算与免赔规则)
 │    ├── ins:DeductibleRule (免赔额/免赔率规则)
 │    └── ins:CoinsuranceRule (比例赔付/不足额投保理算)
 ├── ins:SpecialClause (特别约定与扩展条款)
 └── ins:Exclusion (责任免除/不赔事项)
```

---

### 3. 属性与关系拓扑规范 (Property Topology Spec)

#### 3.1 对象属性 (Object Properties / Edges)

| 关系 (URI) | 源节点 (Domain) | 目标节点 (Range) | 基数 | 语义说明 |
| :--- | :--- | :--- | :--- | :--- |
| `ins:hasCoverage` | `InsuranceProduct` | `Coverage` | 1..* | 产品包含的具体保障责任 |
| `ins:appliesToObject` | `Coverage` | `InsuredObject` | 1..* | 该责任作用的具体标的物/对象 |
| `ins:coversHazard` | `Coverage` | `InsuredHazard` | 1..* | 该责任涵盖的危险因数/疾病事故 |
| `ins:locatedAt` | `InsuredObject` | `LocationScope` | 0..* | 标的物生效的地理限定/坐落地址 |
| `ins:governedByRule` | `Coverage` | `FinancialRule` | 0..* | 该责任受限于的免赔/赔付理算规则 |
| `ins:modifiedByClause`| `Coverage` | `SpecialClause` | 0..* | 该责任被特别约定扩展或修饰 |
| `ins:excludedBy` | `Coverage` | `Exclusion` | 0..* | 该责任排除的免责事项 |

#### 3.2 数据属性 (Data Properties)

* **`ins:FinancialRule` 数据属性**：
  * `ins:deductibleType` (Enum: `AbsoluteAmount`, `AbsolutePercentage`, `HigherOf`, `LowerOf`)
  * `ins:deductibleAmount` (xsd:decimal): 绝对免赔额数值
  * `ins:deductibleRate` (xsd:decimal): 免赔比例（0.0 ~ 1.0）
  * `ins:payoutRatio` (xsd:decimal): 给付/赔偿比例（0.0 ~ 1.0）
* **`ins:SpecialClause` 数据属性**：
  * `ins:timeWindowHours` (xsd:integer): 时间窗口（如 72 小时条款）
  * `ins:clauseText` (xsd:string): 特约原文

---

### 4. 复杂理算与判定建模规范

#### 4.1 复合免赔额计算表达式 (HigherOf 逻辑)
对于“免赔额 5,000 元或损失金额的 10%，以高者为准”的典型财产险条款，转换为逻辑表达式属性 `ins:ruleLogicExpr`：
$$\text{Deductible} = \max(5000.0, \text{LossAmount} \times 0.10)$$

#### 4.2 巨灾时间窗口逻辑 (72-Hour Clause)
针对自然灾害累积判定，在 `SpecialClause` 节点定义 `timeWindowHours: 72`，并在规则引擎中编译为时间窗口聚合判定逻辑。

---

### 5. 企业级 Python 实现代码规范 (Pydantic v2 Production Code)

完整的 Pydantic v2 实现代码已放入 `insurance_ontology.py` 文件中，可以直接投入生产环境。

---

### 6. 数据质量与 SHACL 校验规范

在数据入库（Neo4j/Jena）前，必须通过 **SHACL (Shapes Constraint Language)** 自动化质检脚本校验：

```turtle
@prefix sh: <http://www.w3.org/ns/shacl#> .
@prefix ins: <http://ontology.enterprise.com/insurance/v2#> .

# 规则 1: 任何 Coverage 节点必须至少挂载 1 个 InsuredObject
ins:CoverageShape
    a sh:NodeShape ;
    sh:targetClass ins:Coverage ;
    sh:property [
        sh:path ins:appliesToObject ;
        sh:minCount 1 ;
        sh:message "错误：保险责任(Coverage)必须至少绑定一个保险标的物(InsuredObject)！" ;
    ] .

# 规则 2: 免赔数值不能为负数
ins:FinancialRuleShape
    a sh:NodeShape ;
    sh:targetClass ins:FinancialRule ;
    sh:property [
        sh:path ins:deductibleAmount ;
        sh:minInclusive 0.0 ;
        sh:message "错误：免赔额数值不能为负数！" ;
    ] .
```

---

### 7. 实施 Roadmap 建议

1. **第 1~2 周（准备期）**：下载安装 **Protégé**，导入上述 Spec 结构，微调出公司内部第一版 `.owl` 本地文件；部署 **Docling** 解析工具。
2. **第 3~4 周（PoC 验证期）**：抽取 10 份典型条款（5份重疾 + 5份企财险），利用 **DeepSeek + Instructor** + 上述 Python Spec 进行结构化抽取，写入 **Neo4j**。
3. **第 5~6 周（评估与迭代）**：利用 **SHACL** 进行自动化质检，分析 `dynamic_attributes` 识别漏掉的字段，完成 Ontology 从 `v2.0` 到 `v2.1` 的首次闭环迭代。