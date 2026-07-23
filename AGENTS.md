# AGENTS.md — 笔录自检平台（文枢）

> Agent 项目级工作规则入口。工具专属命令、Skill、Harness 指南与本文件冲突时以本文件为准。

---

## 1. 项目目标

电子数据检查笔录自动生成平台（React 18 + TypeScript + FastAPI + officecli），面向民警使用。

---

## 1.1 仓库资产与合规

**本仓库经过敏感数据清理（历史重写完成于 2026-07-21）。**

- 仓库资产政策：`harness/repository-assets.md`
- 所有测试数据必须是明确合成数据（使用 SYNTHETIC/TEST/FIXTURE 标记）
- 禁止提交真实案件数据、人员信息、设备编号、生成输出
- 资产检查门控：`npx tsx scripts/check-repository-assets.ts`（已接入 `verify:quick`）
- **所有协作者必须从重写后的远端重新 clone**，禁止从旧 clone 推送

---

## 2. 规则优先级

**工作流程规则**（冲突时按此顺序）：
1. 安全与法律合规 — 不可覆盖
2. 根目录 AGENTS.md — Agent 工作流程最高规则来源
3. Harness 运营文档（`harness/`）— 架构约束、熵治理详情
4. 工具命令与 Skill（`.claude/`、`.agents/`）— 快捷入口，不得覆盖以上

**行为预期**：当前任务要求 + 有效 OpenSpec / 产品文档描述预期行为。
**实现事实**：代码、Git 状态、测试、构建和实际运行结果为当前实现状态的判断依据。

规格与实现冲突 → 报告差异，根据任务决定修改实现还是更新规格。不确定时暂停请求人类判定。

---

## 3. 任务开始前检查

按需读取，不得一次性加载所有 `harness/` 和 `openspec/`：

| 优先级 | 内容 | 何时读取 |
|:------:|------|---------|
| P0 | 直接相关源文件和测试 | 每个任务 |
| P1 | `harness/architecture.md` | 涉及新建文件或跨层引用 |
| P2 | 本文件的级别判断规则 | 不确定级别时 |
| P3 | 其他 `harness/` 详情 | 仅明确需要时 |

---

## 4. 任务级别判断

根据行为变化、影响范围、公共契约、调用范围和回滚风险判断，不得根据文件数量或代码行数机械判断。新增局部字段（即使改 3 个文件）可能仍是 Level 1；修改公共组件（影响多个页面）可能是 Level 2；修改核心 Schema 或公共 API 可能是 Level 3。

**无法明确判断时默认采用较轻级别。**

以下内容判断前**必须先搜索调用范围**：公共组件、公共接口、核心数据模型、共享类型、跨模块行为、鉴权和安全边界、持久化数据格式、模板公共语法。确认影响范围较大或回滚风险显著时才升级。级别可在实施中调整，升级时只补充真正必要的治理材料。

---

## 5. Level 1 — 轻量修改

**适用**：局部 Bug、文案、样式、错误提示、配置默认值、局部字段映射、模板占位符调整、单模块小重构、不改变公共接口和架构的修改。

**流程**：检查 Git → 读相关代码和测试 → 搜索调用范围 → 最小修改 → 针对性验证（相关测试或 `lint:arch` + `typecheck`）→ 检查 diff → 汇报。不创建 OpenSpec change、proposal/spec/design、迭代记录。不要求读取 `iteration-guide.md`、独立 Code Review Agent、归档。

---

## 6. Level 2 — 普通功能或中等影响修改

**适用**：引入新的可观察行为或扩大现有能力，影响范围中等，但仍保持现有公共契约和总体架构。模块数和文件数仅作参考。

**默认创建** `openspec/changes/<name>/tasks.md`（含目标、验收标准、任务列表、必要说明）。设计说明写入 tasks.md，不自动扩大为变更包。默认不强制 proposal.md、独立 spec.md、design.md、完整归档门控。

---

## 7. Level 3 — 重大变更

**适用**：公共 API 变化、核心 Schema 变化、架构变化、跨模块大规模重构、框架/引擎更换、数据库/队列引入、部署方式重大变化、安全边界变化、持久化格式迁移。

**完整流程**：proposal → spec → design → tasks → implementation → verify → review → archive。默认读取完整 Harness 迭代、评审和熵治理文档。

---

## 8. 测试有效性验证（所有级别按风险判断）

| 风险 | 范围 | 要求 |
|------|------|:----:|
| 高 | 核心业务逻辑、权限、安全、关键数据转换、高风险算法 | **MUST** |
| 低 | 普通 UI、样式、文案、低风险适配 | **SHOULD** |

验证方式：注释核心逻辑 → 跑测试确认失败 → 恢复代码。

---

## 9. Code Review Agent

| 级别 | 要求 |
|:----:|------|
| Level 1 | 默认不启用 |
| Level 2 | 高风险任务（公共接口/核心数据/安全边界）按需启用 |
| Level 3 | 默认启用；可在重要实现完成后统一审查，不要求每 Task 启动 |

默认关闭（`harness.config.yaml` → `code_review_agent: false`）。详见 `harness/code-review-agent.md`。

---

## 10. 验证与治理范围

| 级别 | 验证命令 | OpenSpec | 归档 |
|:----:|------|---------|:----:|
| Level 1 | `verify:quick`（lint:arch + typecheck + docs:quick） | 不创建 | 不归档 |
| Level 2 | `verify:quick` + `verify:frontend` 或 `verify:backend` | 仅 tasks.md | 不强制 |
| Level 3 | `verify:full`（全部检查 + build + 严格文档） | 完整变更包 | 完整归档协议 |

不推荐常规使用 `git commit --no-verify`（仅限人工确认后的异常处理）。
`verify:quick` → 默认模式文档检查；`verify:docs:strict` → 严格模式（Level 3/归档）。

### 完整 Harness 门控的执行者确认

准备运行 `verify:full` 或项目定义的等价完整 Harness 门控前，必须先询问人类是否希望亲自执行。该规则只适用于完整 Harness 门控：

- 人类选择亲自执行时，提供准确命令并等待结果，不自行运行或重复执行。
- 人类授权 Agent 执行时，再由 Agent 运行完整 Harness 门控。
- 人类已明确指定执行者时，按指定执行，不重复询问。
- 定向测试、必要架构检查和按改动范围执行的模块验证可直接运行；Git 提交钩子自动执行的轻量门控不需要询问。

---

## 11. 工具兼容 + 旧变更包迁移

- `.claude/`、`.agents/` 下命令和 Skill 是工具快捷入口，不得维护与本文件冲突的流程规则。
- `/harness:fix` 支持 Level 1（不创建 OpenSpec change）。
- **现有活跃变更包**不自动删除或降级，继续按原约定处理或后续逐个评估迁移。新三级规则默认适用于新任务。

---

## 12. 架构约束（摘要）

详见 `harness/architecture.md`。

**分层方向**：SharedTypes(0)→Constants(1)→Utils(2)；FE Hooks(10)→Components(11)→Pages(12)；BE Repo(20)→Services(21)→Controllers(22)→Routes(23)。前后端仅通过 SharedTypes API 契约通信。

**文件**：≤250 行、命名导出、TS camelCase/PascalCase、Python snake_case。新增目录后更新 `harness/directory.md`。

**测试**：Utils/Repo/Services → 单元测试；Hooks/Components → Vitest+RTL；Pages/Routes → E2E；Controllers → 集成测试。

---

## 13. 任务完成标准

- lint:arch + typecheck 通过 / 针对本次修改的测试通过 / `git diff` 仅含预期变更
- Level 2：tasks.md 标记完成；Level 3：完整门控通过

---

## 14. 禁止事项

- ❌ 以文件数量或代码行数作为风险判断标准
- ❌ 不确定时自动扩大流程 / 在工具命令中独立定义流程规则
- ❌ 多个文件复制同一信息（用"详见 xxx"）/ 硬编码会变的数字
- ❌ 假设代码或 Spec 任一方天然正确 / 批量跳过测试

---

## 15. 文档索引

| 路径 | 用途 |
|------|------|
| `harness/iteration-guide.md` | 六步闭环详情（Level 3） |
| `harness/architecture.md` | 分层规则、依赖矩阵 |
| `harness/entropy-rules.md` | 归档门控、教训反哺（Level 3） |
| `harness/code-review-agent.md` | 审查维度和流程 |
| `harness/directory.md` | 目录结构 |
| `openspec/specs/` | 能力 spec |
| `openspec/specs/data-model.md` | 实体定义 |
