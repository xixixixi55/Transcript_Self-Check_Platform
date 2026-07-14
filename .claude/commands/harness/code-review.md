---
name: "Harness: Code Review"
description: "启动独立 Sub-Agent 对指定 Task 的代码进行独立审查（生成者与评估者分离）"
argument-hint: "[Task ID 或文件路径]"
---

启动独立的 Code Review Sub-Agent，对当前或指定 Task 的代码变更进行审查。
实现 Harness Engineering「生成者与评估者分离」原则。
**不覆盖根目录 AGENTS.md 的级别规则。** Level 1 默认不启用；Level 2 高风险任务按需启用；Level 3 默认启用。

**前置读取**（MUST 在开始前阅读）：
- `harness/code-review-agent.md` — 审查清单和输出格式

**Input**：可选指定 Task ID 或文件路径。省略时审查最近完成的 Task。

---

**步骤**

1. **确定审查范围**
   - 有 Task ID → 从变更包 `tasks.md` 定位涉及文件
   - 有文件路径 → 直接审查指定文件
   - 无输入 → 定位最近一个 `[x]` 标记的 Task

2. **准备审查上下文**

   收集以下信息，作为 Review Sub-Agent 的输入：
   - Task 信息（ID、描述、所属层级）
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
   - **通过** → 继续标记 Task `[x]`
   - **驳回** → 按报告中 MUST FIX 项修复，修复后重跑验证，再次提交审查
   - **第 3 次驳回** → 停止，请求人类介入

**Guardrails**
- Review Sub-Agent MUST 是独立上下文（通过 Task 工具启动）
- Review Sub-Agent MUST NOT 修改任何文件，只输出报告
- 最多 2 轮修复-重审循环，第 3 次驳回停止
- 审查不通过时，MUST NOT 标记 Task 为 `[x]`
