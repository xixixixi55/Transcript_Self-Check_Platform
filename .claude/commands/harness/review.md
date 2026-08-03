---
name: "Harness: Review"
description: "对照 spec 场景验证代码实现的需求覆盖性（语义层面验证）"
argument-hint: "[变更包名称]"
---

三维度验证：完整性 + 正确性 + 一致性。融合 OpenSpec verify spec（[opsx-verify-skill](https://github.com/Fission-AI/OpenSpec/blob/main/openspec/specs/opsx-verify-skill/spec.md)）的验证模型，并增加 Harness 架构约束检查。
**不覆盖根目录 AGENTS.md 的级别规则。** 本命令服务于 Level 3 需求验证（Level 2 可选）。

与 `/harness:verify`（工程验证）互补：verify 检查结构（自动化脚本），review 检查语义（Agent 审查）。

**前置读取**（MUST 在开始前阅读）：
- 当前变更包的 `specs/` 目录下所有 spec 文件
- 当前变更包的 `tasks.md`
- 当前变更包的 `design.md`（如存在）
- `harness/architecture.md` — 分层约束（一致性维度需要）

**Input**：可选指定变更包名称。省略时自动推断。

---

**步骤**

1. **选择变更包**
   - 有名称则使用，否则推断当前活跃变更包
   - 如果变更包没有 tasks.md 或为空，报告 "No tasks to verify"

2. **维度一：完整性（Completeness）**
   > 来源：OpenSpec verify spec — Requirement 2

   a. **任务完成检查**
      - 读取 tasks.md；普通 checklist 任务默认必选
      - 同一任务行末尾明确标记 `[OPTIONAL]`、`[DEFERRED]` 或 `[N/A]` 时，不把未勾选标记为 CRITICAL
      - 报告必选任务完成数量，并列出未完成必选任务

   b. **spec 覆盖检查**
      - 如果变更包有 specs/，提取所有需求
      - 在代码库中搜索每个需求的实现
      - 报告已实现和缺失的需求

3. **维度二：正确性（Correctness）**
   > 来源：OpenSpec verify spec — Requirement 3

   a. **需求实现映射**
      - 对 specs/ 中每个需求，搜索代码实现
      - 识别相关文件和位置
      - 评估是否满足需求

   b. **场景覆盖检查**
      - 对每个 WHEN/THEN 场景：
        - 检查代码是否处理了场景条件
        - 检查是否有覆盖该场景的测试
      - 标记：✅ 已覆盖 / ⚠️ 部分覆盖 / ❌ 未覆盖

   c. **结果判定**
      - 实现符合 spec → 标记需求为已覆盖
      - 实现与 spec 不符 → **WARNING**，解释差异
      - 缺失实现 → **CRITICAL**，建议实施

4. **维度三：一致性（Consistency）**
   > 来源：OpenSpec verify spec — Requirement 4 + Harness 架构约束

   a. **design.md 遵循检查**（来源：OpenSpec verify spec）
      - 提取 design.md 中的关键决策
      - 验证代码是否遵循这些决策
      - 违反设计决策 → **WARNING**
      - 无 design.md → 跳过并备注

   b. **Harness 架构约束检查**（来源：Harness）
      - 验证代码是否遵循 `architecture.md` 的分层规则
      - 新增代码的层级归属是否正确
      - 跨层引用是否符合依赖矩阵
      - 偏差标记为 **SUGGESTION**

   c. **代码模式一致性**（来源：OpenSpec verify spec）
      - 新代码是否遵循项目已有模式
      - 显著偏差标记为 **SUGGESTION**

5. **生成验证报告**
   > 来源：OpenSpec verify spec — Requirement 5

   ```
   ## 验证报告

   ### 记分卡
   | 维度 | 状态 |
   |------|------|
   | 完整性 | ✅ 通过 / ❌ X 个关键问题 |
   | 正确性 | ✅ 通过 / ⚠️ X 个警告 |
   | 一致性 | ✅ 通过 / ⚠️ X 个警告 |

   ### CRITICAL（归档前必须修复）
   - [C1] 缺失实现：<需求> — 建议：<具体修复建议>
   - [C2] 未完成任务：<任务> — 建议：完成或标记完成

   ### WARNING（应该修复）
   - [W1] 偏离 spec：<差异描述> — 建议：更新实现或更新 spec
   - [W2] 违反设计决策：<决策> — 建议：更新实现或 design.md

   ### SUGGESTION（最好修复）
   - [S1] 模式不一致：<描述> — 建议：<改进方向>

   ### 归档建议
   - 全部通过: "All checks passed. Ready for `/harness:archive`."
   - 有 CRITICAL: "X critical issue(s) found. Fix before archiving."
   - 仅 WARNING/SUGGESTION: "No critical issues. Ready for `/harness:archive` (with noted improvements)."
   ```

**灵活的工件处理**
> 来源：OpenSpec verify spec — Requirement 6

- **仅有 tasks.md**：只验证任务完成度，跳过 spec 和 design 检查
- **有 specs/ 无 design.md**：验证完整性 + 正确性，跳过 design 遵循检查，仍检查 Harness 架构约束
- **完整变更包**：执行所有三维度验证

**Guardrails**
- 只做审查，不修改代码
- 以 Spec 为仲裁——代码不符合 Spec 改代码，Spec 有误改 Spec
- 不要求 100% 覆盖——未覆盖场景可标记为后续迭代，但 MUST 明确列出
- CRITICAL 问题存在时 MUST NOT 建议归档
