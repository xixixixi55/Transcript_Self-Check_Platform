# 迭代记录：Harness 生命周期健康与就绪变更归档

> 日期：2026-09-11
> 变更包：
> - `openspec/changes/archive/2026-09-11-device-company-software-prefix/`
> - `openspec/changes/archive/2026-09-11-review-page-modern-government-ui/`
> - `openspec/changes/archive/2026-09-11-harness-change-lifecycle-health/`
> Spec：`openspec/specs/electronic-inspection-record/spec.md`、`openspec/specs/harness-workflow/spec.md`

## 📋 迭代概览

- 为 Level 2 增加项目内 schema，使 OpenSpec 状态只跟踪 delta specs 与 tasks。
- 将 living spec 严格校验接入快速门控，并固定项目 OpenSpec 工具版本。
- 为全部活跃 change 补充显式 `lifecycle_status`，把归档意图与 checklist 完成状态分离。
- 逐包通过 scoped 文档门控与 OpenSpec strict 后，归档三个 `ready-to-archive` 包；已同步的 living specs 未被重复覆盖。

## ⚠️ 遇到的问题

### 问题：checkbox 完成状态被误当作归档状态

- **现象**：首版健康检查把没有必选未完成项的包全部报告为待归档，但其中多个包正文仍明确保留人工验收、最终 Review 或候选冻结工作。
- **根因**：`[DEFERRED]` 正确表达“不阻塞普通必选任务门控”，却无法表达整个 change 是否已经准备归档。
- **修复方式**：引入 `lifecycle_status: in-progress | ready-to-archive`；归档工具只选择显式 ready 的包，checkbox 继续只表达任务义务。

### 问题：批量归档被无关在途包阻断

- **现象**：全局严格检查会聚合所有活跃包的未完成任务，导致已完成目标无法独立收尾。
- **根因**：选定归档与全局发布共用了全局门控语义。
- **修复方式**：选定单包或批量归档逐包运行 scoped gate；只有全局发布检查全部活跃 change。

### 问题：Level 2 工件合同与默认 schema 不一致

- **现象**：Harness 只要求 delta specs 与 tasks，OpenSpec 默认状态仍等待 proposal 与 design。
- **根因**：流程文档改变后没有同步可执行 schema。
- **修复方式**：增加项目内 `level2` schema、迁移活跃 Level 2 元数据，并在创建入口强制选择该 schema。

## 💡 沉淀的经验

1. checklist、工件完整度和生命周期状态是三个不同维度，不应互相推断。
2. scoped gate 负责证明目标 change 可收尾；全局 gate 负责证明整个仓库可发布。
3. 工作流规则必须同时落到 schema、入口命令和自动化检查，只有文字约定会再次漂移。

## ✅ 已反哺到 Harness（第 2 层 — 项目级）

- `AGENTS.md` 与 `harness/entropy-rules.md` 已定义显式生命周期状态及 scoped/global 边界。
- `openspec/specs/harness-workflow/spec.md` 已成为正式行为合同。
- `.agents` 与 `.claude` 的 propose/apply/archive/verify 入口已保持镜像一致。
- `scripts/check-docs.ts` 与治理测试已覆盖状态合法性、ready 前置条件、完成未归档和 active tasks 行数预算。

## 🔼 可反哺到模板（第 1 层 — 通用级）

TEMPLATE_CANDIDATE

- [x] 教训描述：不要用 checklist 完成率推断 change 是否可以归档；使用显式、可校验的生命周期状态。
- [x] 建议写入模板的哪个文件：变更生命周期 schema、apply 收尾规则和 archive 候选选择规则。
- [ ] 状态：pending

## 📊 与上次迭代的对比

- 活跃区不再把保留延期验收的包误报为已完成。
- 完成未归档和超预算 tasks 的存量健康漂移已清零；全局剩余提示只对应真实未完成的必选任务。
