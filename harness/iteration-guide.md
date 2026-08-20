# 🔄 Harness Engineering + OpenSpec 迭代流程

> **适用范围**：本指南默认用于 **Level 3 重大变更**。
> Level 1 和 Level 2 按仓库根目录 `AGENTS.md` 的轻量工作流执行。
> 本文件与 `AGENTS.md` 冲突时，以 `AGENTS.md` 为准。
>
> **OpenSpec** 负责需求规划与管理（做什么），**Harness** 负责约束与验证（做对）。

## 渐进式上下文加载

Harness 入口先完成 change 关联与 Level 路由，再加载当前阶段资料；质量来自不可跳过的决策点和可执行门控，不来自一次性阅读全部文档。

- Level 1：根规则 + 直接源码/测试。
- Level 2：再加载匹配包 tasks、相关 delta；生成或校验工件时读 OpenSpec rules。
- Level 3：按 proposal、design、implementation、verify/review、archive 当前阶段读取对应章节和工件。
- 架构文档只在新文件、跨层、公共契约或架构风险出现时读取；验证、Review、归档专用文档到对应阶段再读取。
- 默认文档门控检查关键入口的渐进式标记，并阻止恢复“启动前完整预读全部 Harness”的旧模式。

---

## 迭代闭环（6 步）

> **仅 Level 3 重大变更执行完整六步闭环。** Level 1 和 Level 2 按 `AGENTS.md` 的轻量路径执行。

```
① 需求定义 (OpenSpec)  →  ② 影响分析 (OpenSpec)  →  ③ 任务拆解 (OpenSpec)
          ↑                                                    ↓
⑥ 归档同步 (OpenSpec+Harness)  ←  ⑤ 验证门控 (Harness)  ←  ④ Agent 开发 (OpenSpec+Harness)
```

---

## OpenSpec 命令参考（基于 1.5.0）

### Core Profile（标准工作流）

| 命令 | 作用 | 对应步骤 |
|------|------|---------|
| `/opsx:explore` | 初始化项目配置（生成 `config.yaml`） | 项目初始化时 |
| `/opsx:propose "<描述>"` | 创建变更包（proposal + specs + design + tasks） | ① ② ③ |
| `/opsx:apply` | 按 tasks.md 逐步执行代码实现 | ④ |
| `/opsx:archive` | 归档变更（合并 specs + 移入 archive） | ⑥ |

### Expanded Profile（按需使用）

| 命令 | 作用 | 使用时机 |
|------|------|---------|
| `/opsx:new` | 创建空的变更目录 | 手动组织变更包时 |
| `/opsx:verify` | 验证变更是否符合 spec 规范 | ⑤ 与 Harness 验证配合使用 |
| `/opsx:sync` | 同步 `openspec/specs/` 与代码实际状态 | 代码先行改了但 spec 没更新时 |
| `/opsx:continue` | 继续未完成的变更包 | 变更做到一半中断后恢复 |
| `/opsx:bulk-archive` | 批量归档多个已完成变更 | 积压了多个变更时 |
| `/opsx:onboard` | 从现有项目代码生成初始 specs | 棕地项目接入 OpenSpec 时 |

> **注**：本仓库不依赖未在 `.agents/commands/` 中定义的 OpenSpec 快捷命令。命令不可用时，按 `AGENTS.md` 的级别规则手动创建对应工件。
>
> 本命令参考基于 OpenSpec 1.5.0。如版本升级导致命令变更，以 OpenSpec 官方文档为准，并同步更新此表。

---

## ① 需求定义（OpenSpec: `/opsx:propose`）

**执行**：Level 3 运行 `/opsx:propose "<功能描述>"` 或手动创建完整变更包；Level 1/2 按 `AGENTS.md` 的轻量路径执行

**产出物**：Level 3 为 `openspec/changes/<功能名>/` 目录下的完整变更包；Level 2 固定创建 `tasks.md` + `specs/<能力>/spec.md` 精简 delta，Level 1 不创建变更包

```
openspec/changes/<功能名>/
├── proposal.md       ← Why + What + Non-Goals + Capabilities + Impact
├── specs/            ← 增量 spec（按能力拆分，标记 ADDED）
├── design.md         ← 技术设计（数据模型、架构决策、备选方案）
└── tasks.md          ← 任务清单
```

**检查清单**（参照 `openspec/config.yaml` 中的 rules）：
- [ ] proposal.md 包含 Non-Goals 和 Capabilities
- [ ] 每条 Requirement 至少一个可测试的 Scenario
- [ ] 覆盖正常路径和异常路径
- [ ] 与 `openspec/specs/` 中现有 spec 没有冲突

---

## ② 影响分析（OpenSpec: proposal.md 的 Impact + design.md）

**目标**：确定新功能涉及哪些架构层，是否需要修改现有文件

**检查矩阵**：

| 层级 | 目录 | 是否需要新增 | 是否需要修改 |
|------|------|:----------:|:----------:|
| Layer 0: SharedTypes | `packages/shared/types/` | ? | ? |
| Layer 1: SharedConstants | `packages/shared/constants/` | ? | ? |
| Layer 2: SharedUtils | `packages/shared/utils/` | ? | ? |
| Layer 10: FE_Hooks | `packages/frontend/src/hooks/` | ? | ? |
| Layer 11: FE_Components | `packages/frontend/src/components/` | ? | ? |
| Layer 12: FE_Pages | `packages/frontend/src/pages/` | ? | ? |
| Layer 20: BE_Repository | `packages/backend/app/repository/` | ? | ? |
| Layer 21: BE_Services | `packages/backend/app/services/` | ? | ? |
| Layer 22: BE_Controllers | `packages/backend/app/controllers/` | ? | ? |
| Layer 23: BE_Routes | `packages/backend/app/routes/` | ? | ? |

**关键问题**：
- 是否需要新的数据存储结构？（需要评估迁移影响）
- 是否需要新的页面/路由/端点？
- 是否影响现有接口/Props？
- 是否需要新的第三方依赖？

---

## ③ 任务拆解（OpenSpec: 变更包内的 tasks.md）

**产出物**：Level 2 的 `openspec/changes/<功能名>/tasks.md`（含 `workflow_level: 2`）与至少一个 `specs/<能力>/spec.md` delta；Level 3 的完整 tasks.md

**规则**：详见 `openspec/config.yaml` 中的 `rules.tasks`

---

## ④ Agent 开发（Level 3 完整开发节奏）

**执行**：运行 `/opsx:apply` 或手动按 tasks.md 顺序实现

**Harness 约束**（Agent 开发时自动生效）：
- 详见 `AGENTS.md`（架构依赖方向、命名约定）+ `harness/architecture.md`（文件大小限制、导出规则、测试规则）+ `harness/verification-strategy.md`（候选冻结、人工验收与环境预检）


**前置条件**（Level 3 MUST 在写第一个 Task 代码前完成）：
- 确认测试基础设施可用（测试框架配置、环境 mock、路径别名）
- 前端迭代：MUST 先配置 DOM 测试环境 + 框架测试插件 + setup 文件（mock 运行时环境差异）
- 后端迭代：MUST 确认数据库测试环境可用
- 运行一个最小测试确认测试链路通畅后再开始正式开发

**开发节奏**（Level 3 的实现阶段）：
1. Agent 写代码
2. Agent **MUST** 运行本次源码变化适用的架构检查 + 类型检查
   - 失败 → Agent 阅读错误信息，自主修复，重新运行，直到通过
   - **MUST**: 连续失败 3 次 → 停止，报告问题，请求人类介入
3. Agent 按 `harness/verification-strategy.md` 选择验证证据：先搜索并复用、修改或合并现有测试；只有现有证据无法区分新增风险时才新增用例
4. Agent **MUST** 运行本次风险适用的验证
   - 运行失败用例或最小受影响定向测试；同一候选版本不重复运行已经覆盖且未改变的模块套件
   - 所有自动化测试（pytest、Vitest、模块测试和完整门控子命令）先读取退出码、最终汇总和失败数量；通过时不逐条读取通过用例
   - pytest 默认使用 `-q --tb=short`，前端 Vitest 优先使用非 verbose 模式；失败时只阅读失败用例及其 traceback，自主修复后先重跑失败用例，再按需重跑受影响模块
   - **MUST**: 连续失败 3 次 → 停止，报告问题，请求人类介入
5. Agent **SHOULD** 验证新增/修改断言的区分度（**Level 3 核心业务逻辑为 MUST**）：可临时破坏本次核心逻辑并重新运行测试
   - 测试失败 → 好，测试有效，恢复源码，进入下一步
   - 测试仍通过 → 测试无效，Agent 补充更有意义的断言，回到第 4 步
   - 完成后 **MUST** 恢复源码到注释前的状态
   - **核心业务逻辑、权限、安全、关键数据转换和高风险算法为 MUST**；普通组件、页面、Repository、样式、文案和低风险适配不强制突变式验证
6. 标记 Task 为 `[x]`，进入下一个

**硬性终止条件**：
- **MUST**: 单个 Task 的总验证循环次数（步骤 2 + 步骤 4 + 步骤 5 的累计重试）**MUST NOT** 超过 **10 次**
- 达到上限时 **MUST** 立即停止，生成问题摘要（涉及文件、已尝试的修复、失败原因），请求人类介入

**介入后反哺**（人类介入解决问题后 **MUST** 执行）：

人类介入不是终点，而是改进 Harness 的触发点。每次介入 **MUST** 判定根因类别并沉淀，防止同类问题重复出现：

| 根因类别 | 反哺目标 | 示例 |
|---------|---------|------|
| 约束缺失 — Harness 没有覆盖这类问题 | 新增规则到 `harness/` 对应文件 | 发现 Agent 绕过中间层直接调底层 → 在 `architecture.md` 加禁止规则 |
| 约束过严 — Harness 规则阻碍了合理实现 | 修改或放宽 `harness/` 中的规则 | 文件行数上限太低导致无法实现 → 调整 `FILE_MAX_LINES` |
| Spec 不清晰 — 需求描述有歧义导致实现偏差 | 更新 `openspec/specs/` 中的 Spec | 场景描述缺少边界条件 → 补充 WHEN/THEN |
| 知识盲区 — Agent 缺乏特定领域知识 | 在 `AGENTS.md` 或 `harness/` 中添加上下文提示 | Agent 不知道某个 API 的正确用法 → 在架构文档中补充约定 |
| 工具/环境问题 — 非 Agent 能力问题 | 记录到迭代记录，不改 Harness | 第三方服务宕机 → 仅在迭代记录中标注 |

Agent **MUST** 在人类介入完成后：
1. 确认根因类别（可请人类协助判定）
2. 将教训写入对应的 Harness 文件或 OpenSpec Spec
3. 在迭代记录（`harness/archive/iterations/`）中记录：问题现象 → 根因 → 反哺位置
4. 如果教训具有跨项目通用性，标记为 `TEMPLATE_CANDIDATE`

> **关键原则**：Agent 不能仅凭自我判断宣告完成，MUST 通过实际运行验证命令确认。
> 验证失败时，优先分析是代码问题还是约束问题（详见⑤验证门控）。

**节奏**：
- Phase 内的 `[P]` 任务可以批量发出
- 每个 Phase 完成后跑架构检查
- 全部完成后跑综合验证

- **MUST NOT**: 批量跳过本次风险适用的验证步骤。类型检查不能替代必要的行为测试，但也不得因流程机械新增无覆盖价值的测试。

---

## ⑤ 验证门控（OpenSpec: `/opsx:verify` + Harness: `pre-commit`）

**OpenSpec 验证**：
- 运行 `/opsx:verify` 检查代码是否符合 spec 中定义的场景

**Harness 自动验证**（命令唯一来源是根目录 `package.json`）：

```bash
npm run verify:quick           # Level 1/2 共用的轻量工程检查
npm run test:frontend          # Level 2 前端受影响模块
npm run test:backend           # Level 2 后端受影响模块
npm run verify:preflight       # 单独检查完整门控使用的临时目录环境
npm run verify:full -- --change <name>  # 全仓库自动化工程检查；严格任务状态限定当前变更
npm run verify:full -- --change <name> --dry-run  # 只输出最终命令列表，不执行检查
npm run verify:full:all                 # 全局发布/集中归档完整门控
npm run verify:docs:strict -- --change <name>  # 当前变更严格文档检查
npm run verify:docs:strict:all               # 全局严格文档检查
```

`verify:full -- --change <name>` 先执行环境预检，再以阶段摘要方式执行全仓库架构、类型、治理、资产、测试和构建检查，但严格任务状态只检查指定变更包；`verify:full:all` 才检查全部活跃变更包。两者都不包含当前未启用的 E2E、mypy、真实桌面环境和 Word/PDF 人工验收。候选冻结与日志下钻细则见 `harness/verification-strategy.md`。

**门控分级**：

| 时机 | 跑什么 | 触发方式 | 说明 |
|------|--------|---------|------|
| 开发中 | 最小定向验证 | 手动 | 按实际风险复用现有证据，秒级反馈 |
| pre-commit | `npm run verify:quick` 轻量检查 | Git Hook（Husky）自动触发 | 不通过则阻断 `git commit`；不替代 Level 2/3 模块或完整门控 |
| 手动/CI | E2E 测试 | 手动或 CI pipeline | 完整验证 |

> **Git Hook 绑定**：`pre-commit` 门控通过 Husky 绑定到 `git commit`，确保每次提交前自动运行。
> 配置位于 `.husky/pre-commit`，执行 npm run pre-commit。
> 安装依赖时 `prepare` script 自动初始化 Husky。

**如果验证失败**：
- 分析是 Agent 的代码问题还是 Harness 的约束问题
- 如果是代码问题 → 补充 Prompt 让 Agent 修复
- 如果是约束问题 → 更新 Linter 规则或架构文档

**测试有效性**：
核心业务逻辑、权限、安全和关键数据转换必须验证断言具有区分度；普通组件、页面、Repository、样式和文案按实际行为变化判断，不强制执行突变式验证。

---

## ⑥ 归档同步（Level 3 — OpenSpec: `/opsx:archive` + Harness: `check-docs`）

**核心原则**：信息只存在一处（DRY），其他地方用链接引用。

### OpenSpec 归档

运行 `/opsx:archive <功能名>` 完成变更包归档。具体的归档操作（spec 合并、文件迁移）由 OpenSpec 工作流自动处理。

### Harness 文档同步

**Step 1 — 自动化门控（MUST 全部通过）：**

运行当前变更的 `npm run verify:docs:strict -- --change <name>`；全局归档运行 `npm run verify:docs:strict:all`。以下检查自动执行（详见 `harness/entropy-rules.md` E-A1 ~ E-A7）：
- [ ] directory.md 与文件系统一致
- [ ] 数据模型 Spec 与类型定义一致
- [ ] 文档链接引用有效
- [ ] OpenSpec 版本一致
- [ ] 迭代记录教训反哺完整性

严格模式的任务状态规则：普通 checklist 任务默认必选；同一行末尾明确标记 `[OPTIONAL]`、`[DEFERRED]` 或 `[N/A]` 时可不勾选。Level 2 和 Level 3 当前变更收尾传 `--change <变更包名称>`，只检查当前变更包；全局发布/集中归档使用 `verify:full:all` 或 `verify:docs:strict:all`。脚本读取 tasks.md 的 `workflow_level` 和 delta 结构，但不自动判断代码与规格的完整语义一致性。

**Step 2 — Agent 自治检查（自动执行 + 自动修复）：**

Agent **自主执行**以下确定性检查，发现问题直接修复，无需人工介入（详见 `harness/entropy-rules.md`）：
- [auto] **E-M1 规则摘要一致性** — 对比 AGENTS.md 与 harness/ 详情，不一致则自动更新
- [auto] **E-M3 硬编码扫描** — 扫描运营文档中会变的数字，自动替换为引用
- [auto] **E-M4 教训反哺确认** — 检查教训是否已写入 Harness 文件，未写入则自动补充

**Step 3 — Agent 辅助 + 人工快速确认：**

Agent 输出分析报告，人工快速审阅确认（详见 `harness/entropy-rules.md`）：
- [ ] **E-M2 规则冲突排查** — Agent 输出疑似冲突列表 + 建议，人工确认
- [ ] **E-M5 模板反哺判定** — Agent 输出通用性评估 + 建议，人工确认

### 文档分层规则

| 层 | 目录 | 受众 | 维护频率 |
|----|------|------|---------|
| OpenSpec | `openspec/` | Agent + 人类 | 每次迭代由 OpenSpec 工作流管理 |
| Harness 运营文档 | `harness/*.md` | Agent + 人类 | 每次迭代 MUST 更新 |
| 归档 | `harness/archive/` + `openspec/changes/archive/` | 参考 | 只追加不修改 |

### 绝对不要做的事

- ❌ 不要在多个文件中复制目录树（用 `详见 harness/directory.md` 代替）
- ❌ 不要在 AGENTS.md 中写教育性内容（"为什么"放独立文档，AGENTS.md 只写"是什么"和"怎么做"）
- ❌ 不要先手工修改 `openspec/specs/` 再执行 sync。Level 2 和历史漂移优先走 delta spec → 核对实现 → sync → 检查 living spec；只有现有 sync 无法完成历史修复时，才允许一次性手工 reconciliation，并登记迁移台账。

---

## 📌 快速参考：常见迭代场景

> 以下场景使用 `/harness:*` 命令作为入口。Harness 命令内部会调用对应的 OpenSpec 命令（`/opsx:*`）。

### 场景 A：新增一个功能

```
① 扫描活跃变更包，确认没有同目标或重叠范围的现有变更
② 按 AGENTS.md 判断级别：Level 1 直接修改；Level 2 创建 tasks.md + delta spec；Level 3 使用 /harness:propose
③ Level 2 核对 tasks.md + delta spec；Level 3 审阅 proposal.md 的 Impact、design.md 的架构决策和 tasks.md
④ 按对应级别开发：Level 1 直接修改；Level 2 按 tasks.md 对照 delta；Level 3 使用 /harness:apply
⑤ 按对应级别验证：Level 1 定向验证；Level 2 verify:quick + 受影响测试 + scoped strict docs
⑥ Level 2 完成 delta → 实现核对 → sync → living spec 检查后方可正式归档；Level 3 执行 /harness:archive
```

### 场景 B：修改现有功能的行为

```
① 扫描活跃变更包，确认是否属于已有需求；匹配时继续原变更包
② 无匹配时按 AGENTS.md 判断级别：Level 1 直接修改；Level 2 创建 tasks.md + delta spec；Level 3 使用 /harness:propose，并在 specs/ 中标记 MODIFIED
③ 审阅对应级别的影响范围和任务
④ 按对应级别开发；Level 3 使用 /harness:apply
⑤ 按对应级别运行验证和回归测试
⑥ Level 2 收尾先 sync 并检查 living spec；需要正式归档时必须先通过 sync；Level 3 执行 /harness:archive
```

### 场景 C：修 Bug

**Level 1（局部 Bug 修复）**：
```
① 先扫描活跃变更包并确认没有匹配或重叠候选
② 检查 Git 状态，阅读直接相关代码和测试，搜索调用范围
③ 实施最小修改
④ 运行针对性测试或 lint:arch + typecheck
⑤ 检查 git diff
⑥ 汇报结果，不创建 OpenSpec change
```

**Level 2/3（复杂 Bug，影响范围较大）**：
```
① 先扫描活跃变更包；匹配时在原包内修复，多个候选无法排除时请求用户选择
② 无匹配时按正式合同、行为影响、调用范围和回滚风险判断 Level；不确定时采用较轻级别
③ Level 2 创建 tasks.md + delta spec；Level 3 创建完整变更包
④ 定位到具体文件和层级并实施修复
⑤ Level 2：verify:quick + 受影响模块验证 + scoped strict docs；Level 3 开发中只做定向验证，候选冻结后统一 Review + verify:full
⑥ Level 2 只执行 scoped strict docs，完成 delta→实现核对→sync→living spec 检查；Level 3 按完整归档协议执行
```

### 场景 D：从现有项目接入 OpenSpec

> 此场景直接使用 OpenSpec 命令（`/opsx:*`），Harness 无对应封装。

```
① /opsx:onboard → 从现有代码自动生成初始 specs
② 审阅并修正生成的 specs
③ /opsx:explore → 生成或更新 config.yaml
```

---

## ⚠️ 迭代中的常见陷阱

- **Level 3 跳过 Spec 直接写代码** — 没有合同的架构级开发等于盲写，Agent 会按自己理解来。Level 3 变更的正确流程：发现问题 → 更新变更包文档（proposal+spec+design）→ 代码实现 → 验证 → 归档。Level 1 小修改和 Level 2 普通功能按 AGENTS.md 轻量路径执行
- **忘记影响分析** — 新功能可能需要修改 Types，这会级联影响所有层
- **积累多个功能一起验证** — 应该每个功能独立走完闭环再开始下一个
- **不更新文档** — 下一次迭代时 Agent 读到过时文档会犯错
- **修改现有文件时不先 read_file** — 修改比新建风险高。修改前 MUST 先读取文件确认当前内容
- **对同一文件多次零散替换** — 应尽量合并为一次替换
- **迭代教训只在聊天中说没有沉淀** — Level 3 每次迭代 MUST 写迭代记录到 `harness/archive/iterations/`。Level 2 建议记录，Level 1 可选
- **同一信息写在多个文件中（DRY 违反）** — 只能有一个真相源，其他用链接引用
- **运营文档和学习文档混在一起** — 教育性内容和运营内容分离
- **文档没有和代码同等级别的约束** — 数据模型与类型一致性等，全部由自动检查覆盖
- **文档中硬编码会变的数字** — 只写"详见 xxx"的链接引用，或让脚本自己输出
- **绕过 sync 直接改 living spec** — Level 2 和历史漂移先写 delta、核对实现，再使用实际支持的 sync；只有 sync 无法完成历史修复时才做一次性手工 reconciliation，并记录迁移台账。
- **照搬 PRD 的数据模型建议** — PRD §数据模型是产品视角的参考，技术方案应从业务需求（用户要看什么/做什么/筛选什么）独立推导实体和关系，区分编译时常量 vs 运行时配置
- **机械追加测试** — 先搜索现有覆盖并复用、修改或合并；仅在现有证据不能区分新增风险时新增用例，纯展示不增加低价值测试
- **Spec 要求抛出的错误被降级为 warn/log** — Spec 中 WHEN/THEN 明确要求 throw 的场景，代码 MUST 抛出对应错误，不可用 try-catch 吞掉或降级为日志。开发时 MUST 逐条对照 Spec 场景

---

## 📂 迭代记录规则

Level 3 功能迭代完成后，MUST 在 `harness/archive/iterations/` 下创建一份迭代记录。Level 2 建议记录，Level 1 可选。

### 迭代记录模板

```markdown
# 迭代记录：<功能名称>

> 日期：YYYY-MM-DD
> 变更包：`openspec/changes/archive/<日期-功能名>/`
> Spec：`openspec/specs/<能力>/spec.md`

## 📋 迭代概览
（新增/修改文件数、涉及层级、错误统计）

## ⚠️ 遇到的问题
（每个问题：现象 → 根因 → 修复方式 → 耗时）

## 💡 沉淀的经验
（通用性教训，可反哺到 iteration-guide.md 的"常见陷阱"中）

## ✅ 已反哺到 Harness（第 2 层 — 项目级）
（列出本次教训写入了 Harness 的哪个文件哪条规则，确保 Agent 下次能读到）

## 🔼 可反哺到模板（第 1 层 — 通用级）
（这条教训是否跨项目通用？如果是，标记为 TEMPLATE_CANDIDATE）
- [ ] 教训描述：...
- [ ] 建议写入模板的哪个文件：...
- [ ] 状态：pending / merged

## 📊 与上次迭代的对比
（趋势观察：错误率是在下降吗？哪类问题在重复？）
```
