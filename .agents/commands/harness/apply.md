---
name: "Harness: Apply"
description: "按任务清单开发，遵循 Harness 开发节奏和门控约束"
argument-hint: "[变更包名称]"
---

按 Harness Engineering 迭代闭环的 ④ 步骤执行开发（Level 3 完整开发节奏）。
内部调用 OpenSpec apply 选择变更包和读取上下文，并在其上注入 Harness 开发节奏和门控。
**不覆盖根目录 AGENTS.md 的级别规则。**

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

   对 Bug/回归任务，必须先按根目录 `AGENTS.md` §3 的变更包关联规则确认是否已有匹配的活跃变更包；未完成关联判断前不得新建或直接修改变更包。
   - specs/、design.md 等上下文文件

   如果 `/opsx:apply` 命令不可用，降级为手动定位：
   - 扫描 `openspec/changes/` 下活跃变更包
   - 读取 tasks.md + specs/ + design.md
   - MUST 遵循 `openspec/config.yaml` 中 `rules` 定义的质量标准

   Level 2 必须同时读取 `tasks.md` 和至少一个 `specs/<能力>/spec.md` 精简 delta；`workflow_level: 2` 是已完成分级结论，不能通过 proposal/design 是否存在反向猜测。

2. **按顺序执行 Task（Harness 开发节奏）**

   **MUST** 按以下节奏完成未完成任务（这是 Harness 注入的，OpenSpec apply 不管这些）：

   a. **写代码**
      - 遵循 `architecture.md` 的分层约束和导出规则
      - 遵循 `AGENTS.md` 的命名约定
      - 文件不超过 250 行

   b. **运行架构检查 + 类型检查**
      - 执行 npx tsx scripts/lint-arch.ts 和类型检查
      - 失败 → 阅读错误，自主修复，重新运行
      - **连续失败 3 次 → 停止，报告问题**

   c. **补充受影响行为的测试**
      - 改变交互、业务行为或数据处理时必须补充对应测试
      - 纯样式、文案、图标和不改变交互的展示调整不强制新增测试
      - 测试分层对应：详见 `architecture.md` 测试文件组织

   d. **运行测试**
      - 所有自动化测试（pytest、Vitest、模块测试和完整门控子命令）先读取退出码、最终汇总和失败数量；通过时不逐条读取通过用例
      - pytest 默认使用 `-q --tb=short`，前端 Vitest 优先使用非 verbose 模式；失败时只阅读失败用例及其 traceback；修复后先重跑失败用例，再按需重跑受影响模块
      - **连续失败 3 次 → 停止，报告问题**

   e. **按需验证测试有效性**
      - 核心业务逻辑、权限、安全和关键数据转换必须验证断言具有区分度
      - 普通组件、页面、样式、文案和低风险适配不强制执行突变式验证

   f. **标记已完成的必选 Task 为 `[x]`**，进入下一个

   Level 2 收尾必须核对 delta 与最终行为，然后按 `delta spec → 实现核对 → sync → living spec 检查` 完成同步；未同步主规格不得正式归档。该流程不增加 proposal、design、verify 或 review 要求。

3. **全部实现完成后冻结候选版本**
   - Level 3 统一进行一次 Code Review，不按 Task 启动
   - 驳回且修改了被审查实现时复审；复审通过后执行 `npm run verify:full -- --change <变更包名称>`
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
