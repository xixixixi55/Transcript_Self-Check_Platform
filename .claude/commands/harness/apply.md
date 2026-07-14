---
name: "Harness: Apply"
description: "按任务清单开发，遵循 Harness 开发节奏和门控约束"
argument-hint: "[变更包名称]"
---

按 Harness Engineering 迭代闭环的 ④ 步骤执行开发。
内部调用 OpenSpec apply 选择变更包和读取上下文，并在其上注入 Harness 开发节奏和门控。

**前置读取**（MUST 在开始前阅读）：
- `AGENTS.md` — 架构约束、命名约定、验证硬限制
- `harness/iteration-guide.md` — ④ 开发节奏详细流程
- `harness/architecture.md` — 分层规则、文件大小限制、导出规则
- 当前变更包的 `tasks.md` + `specs/` + `design.md`

**Input**：可选指定变更包名称。省略时自动推断或询问。

---

**步骤**

1. **调用 OpenSpec 获取变更包上下文**

   执行 `/opsx:apply` 的前置步骤（选择变更包 + 读取上下文），获取：
   - 变更包名称和 tasks 列表
   - specs/、design.md 等上下文文件

   如果 `/opsx:apply` 命令不可用，降级为手动定位：
   - 扫描 `openspec/changes/` 下活跃变更包
   - 读取 tasks.md + specs/ + design.md
   - MUST 遵循 `openspec/config.yaml` 中 `rules` 定义的质量标准

2. **按顺序执行 Task（Harness 开发节奏）**

   **MUST** 按以下节奏执行每个未完成的 Task（这是 Harness 注入的，OpenSpec apply 不管这些）：

   a. **写代码**
      - 遵循 `architecture.md` 的分层约束和导出规则
      - 遵循 `AGENTS.md` 的命名约定
      - 文件不超过 250 行

   b. **运行架构检查 + 类型检查**
      - 执行 npx tsx scripts/lint-arch.ts 和类型检查
      - 失败 → 阅读错误，自主修复，重新运行
      - **连续失败 3 次 → 停止，报告问题**

   c. **写配套测试**
      - 测试分层对应：详见 `architecture.md` 测试文件组织
      - E2E/组件测试标注覆盖的 Spec 场景编号

   d. **运行测试**
      - 失败 → 自主修复，重新运行
      - **连续失败 3 次 → 停止，报告问题**

   e. **验证测试有效性**
      - 注释掉核心逻辑，重新运行测试
      - 测试仍通过 → 测试无效，补充断言，回到 d
      - 测试失败 → 好，恢复源码

   <!-- IF:features.code_review_agent -->
   e2. **独立 Code Review（启用 Code Review Agent 增强模块时）**
      - 启动独立 Review Sub-Agent（通过 Task 工具，独立上下文）
      - 输入：Task 信息 + 变更文件列表 + 上下文文件（AGENTS.md、architecture.md、specs/）
      - Review Agent 按 5 维度审查：架构合规 / 代码质量 / Spec 一致 / 测试质量 / 可维护性
      - 通过 → 继续
      - 驳回 → 按报告修复，重跑验证，再次提交审查
      - **最多 2 轮修复-重审，第 3 次驳回 → 停止，请求人类介入**
      - 详见 `harness/code-review-agent.md`
   <!-- ENDIF -->

   f. **标记 Task 为 `[x]`**，进入下一个

3. **全部完成后运行综合验证**
   - 执行 npm run verify
   - 提示：运行 `/harness:review` 进行需求验证，或 `/harness:archive` 归档

**硬性终止条件**
- 单步连续失败 3 次 → 停止，报告问题
- 单 Task 总验证循环（b + d + e 累计）不超过 10 次 → 强制停止
- 启用增强验证时：检测原地踏步（错误指纹相同）→ 换策略或停止

**Guardrails**
- 每个 Phase 完成后跑架构检查
- Task 不明确时暂停询问，不猜测
- 发现设计问题时暂停，建议更新变更包
- 保持代码变更最小化，聚焦每个 Task
