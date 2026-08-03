---
name: "Harness: Code Review"
description: "对候选版本启动独立 Sub-Agent 代码审查（生成者与评估者分离）"
argument-hint: "[变更包名称或文件路径]"
---

启动独立的 Code Review Sub-Agent，对当前候选版本的实现变更进行审查。
实现 Harness Engineering「生成者与评估者分离」原则。
**不覆盖根目录 AGENTS.md 的级别规则。** Level 1 默认不启用；Level 2 按需启用；Level 3 在候选版本级别统一审查一次。

**前置读取**（MUST 在开始前阅读）：
- `harness/code-review-agent.md` — 审查清单和输出格式

**Input**：可选指定变更包名称或文件路径。省略时审查当前候选版本。

---

**步骤**

1. **确定审查范围**
   - 有变更包名称 → 从该变更包 `tasks.md` 汇总涉及文件
   - 有文件路径 → 直接审查指定文件
   - 无输入 → 使用当前候选版本的 Git 变更范围

2. **准备审查上下文**

   收集以下信息，作为 Review Sub-Agent 的输入：
   - 变更包目标、所属级别和验收标准
   - 变更文件列表（新增 / 修改）
   - 上下文文件列表：`AGENTS.md`、`harness/architecture.md`、相关 specs/、design.md

3. **启动 Review Sub-Agent**

   使用 Task 工具启动独立 Sub-Agent，prompt 包含：

   a. **角色定义**：
      ```
      你是一个严格的代码审查者。你倾向于严格评估，宁可误报也不漏报。
      你不共享开发者的上下文，需要独立理解代码。只输出审查结论，不修改代码。
      ```

   b. **审查指令**：
      - 读取 `harness/code-review-agent.md` 获取完整审查清单
      - 读取 `AGENTS.md` 和 `harness/architecture.md` 了解项目约束
      - 读取变更文件，按 5 个维度逐项审查
      - 输出结构化报告（通过 / 驳回 + 具体问题）

   c. **变更文件列表**：附上需要审查的文件路径

4. **处理审查结果**
   - **通过** → 保留审查证据，进入最终自动化验证
   - **驳回** → 按报告中 MUST FIX 项修复，修复后重跑验证，再次提交审查
   - 修改了被审查源码、接口、数据模型或行为时原结论失效，必须复审；只改文档、格式、命名或注释等测试元数据可不复审；修改测试断言、fixture、mock、覆盖范围或预期结果时必须复审
   - 连续两轮修复仍未通过 → 停止，请求人类介入

**Guardrails**
- Review Sub-Agent MUST 是独立上下文（通过 Task 工具启动）
- Review Sub-Agent MUST NOT 修改任何文件，只输出报告
- 连续两轮修复仍未通过即停止，请求人类介入
- 审查未通过时，MUST NOT 进入最终自动化门控
