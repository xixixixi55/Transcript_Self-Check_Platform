# Harness 工作流

## Purpose

定义变更关联与分级、风险相称验证、Level 2 固定工件、候选冻结、验证环境和日志输出，以及根规则预算与工具镜像一致性。

## Requirements

### Requirement: 新方案遵循项目内稳定先例优先

Harness MUST 要求新增或扩展能力在设计与实现前识别项目内已经稳定解决同类问题的先例，并默认复用其已验证的处理模式、阶段边界与非功能约束。稳定先例 MUST 具有现行规格、自动化回归、生产使用或明确验收证据；未完成实验、已知技术债和仅仅更早出现的代码不自动成为先例。相似性 MUST 按用户结果、核心调用链、输入输出和安全、性能、缓存、一致性等约束判断，不得只按文件名、目录或数据格式判断。输入格式不同本身不得作为重新发明处理方法的充分理由；偏离稳定先例时 MUST 记录实质差异、原模式不适用的原因和能够区分该偏离必要性的验证证据。

#### Scenario: 为已有能力增加新的输入格式

- **WHEN** 新需求只是在现有能力上增加一种输入格式、厂商或协议变体
- **THEN** Agent 先定位现有稳定实现并提取可复用的入口选择、处理阶段、统一输出、错误处理和非功能边界
- **AND** 默认保持这些不变量，只把格式差异封装在必要的适配边界内

#### Scenario: 项目内存在相同用户结果的稳定链路

- **WHEN** 新实现与既有链路具有相同用户结果或核心处理目标，但表面文件结构或技术细节不同
- **THEN** Agent 不得仅因表面差异创建竞争性处理方法
- **AND** tasks 或适用设计工件记录参考先例、复用的不变量和仍需独立实现的真实差异

#### Scenario: 稳定先例确实不适用

- **WHEN** 安全、正确性、规模、生命周期或平台约束证明既有模式无法满足新需求
- **THEN** Agent 可以采用不同方案，但必须记录拒绝复用的具体证据和权衡
- **AND** 验证能够区分新方案的必要性，而不是只证明新代码可以运行

### Requirement: Level 2 变更工件合同

项目 MUST 将局部低风险行为调整作为 Level 1 候选；只有正式 Requirement/Scenario 变化或中等范围能力进入 Level 2，并使用项目内 Level 2 schema 维护实现任务、差异规格与现行规格同步闭环。

#### Scenario: 局部低风险行为调整

- **WHEN** 修改恢复既有预期或只调整单一能力内部的低风险行为，且不新增公共契约、持久化格式或安全边界
- **THEN** 需求可以按 Level 1 处理
- **AND** 不因用户可观察到变化而自动创建 Level 2 变更包

#### Scenario: 创建新的 Level 2 变更包

- **WHEN** 需求被判定为 Level 2
- **THEN** 变更包使用项目内 `level2` schema
- **AND** 变更包包含 `tasks.md` 和至少一个 `specs/<capability>/spec.md`
- **AND** `tasks.md` 持久化记录 `workflow_level: 2`
- **AND** delta spec 只记录新增、修改或删除的正式行为及关键场景
- **AND** OpenSpec 状态不等待 proposal 或 design

#### Scenario: Level 2 没有正式行为变化

- **WHEN** 修改不需要新增或改变正式 Requirement/Scenario，也不引入中等范围能力
- **THEN** 需求按 Level 1 处理
- **AND** 不创建 Level 2 变更包或使用 `Spec impact: N/A` 绕过 delta spec

### Requirement: 限定范围的 Level 2 文档门控

严格文档门控 MUST 使用 tasks.md 中持久化的 `workflow_level`，并将当前变更包范围、选定归档范围与全局活跃变更包范围分开。

#### Scenario: 执行当前变更包严格检查

- **WHEN** 执行 `verify:docs:strict -- --change <name>`
- **THEN** 只检查指定变更包的 workflow level、tasks、delta spec 和完成态同步元数据
- **AND** 其他活跃变更包的迁移债务不阻断当前变更

#### Scenario: 执行全局严格检查

- **WHEN** 执行 `verify:docs:strict:all`
- **THEN** 检查全部活跃变更包，并排除 `openspec/changes/archive/`
- **AND** 报告完成但未归档的变更包和超过预算的活跃 tasks 文档

### Requirement: 活跃变更生命周期健康

Harness MUST 使活跃 change 表达待执行工作，而不是无限增长的完成历史；`lifecycle_status` 是归档意图的事实源，checkbox 只表达任务义务。

#### Scenario: 活跃变更仍有延期或验收工作

- **WHEN** change 没有未完成的必选 checklist，但仍有显式延期、验收或候选冻结工作
- **THEN** `lifecycle_status` 保持 `in-progress`
- **AND** Harness 不根据 checkbox 自动推断该 change 可以归档

#### Scenario: 变更准备归档

- **WHEN** change 的必选任务完成、适用延期已明确处置且 delta 已与 living spec 对账
- **THEN** `lifecycle_status` 设置为 `ready-to-archive`
- **AND** `spec_sync_status` 必须为 `reconciled`
- **AND** `spec_sync_evidence` 必须指向对账后的 living spec 证据
- **AND** 全局活跃变更检查将该包报告为待归档

#### Scenario: 任务文档持续累积历史

- **WHEN** 活跃 `tasks.md` 超过检查器配置的行数预算
- **THEN** 全局严格检查报告生命周期漂移
- **AND** 应通过完成归档、重新分级或把历史移入迭代记录来恢复健康

### Requirement: Living spec 严格校验进入快速门控

项目 MUST 在快速工程门控中严格校验全部 living specs 的 OpenSpec 结构，且该校验不依赖其他活跃 change 的任务完成状态。

#### Scenario: 执行快速验证

- **WHEN** 执行 `npm run verify:quick`
- **THEN** 运行 `openspec validate --specs --strict --no-interactive`
- **AND** OpenSpec CLI 由项目锁定的开发依赖提供
- **AND** 任一 living spec 结构错误会使快速验证失败

### Requirement: 选定归档与全局发布分离

归档门控 MUST 只阻断当前选定目标；一次选择多个已完成变更时逐个验证，全部活跃 change 的共同健康仅由全局发布门控检查。

#### Scenario: 选定多个已完成变更归档

- **WHEN** 操作者选择一个或多个已完成变更进行归档
- **THEN** 对每个目标运行 `--change <name>` scoped gate
- **AND** 无关在途变更的未完成任务不阻断所选目标

#### Scenario: 执行全局发布

- **WHEN** 执行全局发布门控
- **THEN** 运行 `verify:full:all` 或 `verify:docs:strict:all`
- **AND** 全部活跃 change 的生命周期漂移都必须收敛

### Requirement: Agent 工作流文件镜像

Harness 和 OpenSpec 等仓库管理的工具入口 MUST 在 `.agents` 与 `.claude` 中保持对应内容一致；未纳入 Git 管理且已明确忽略的本机配置和 provider 专用安装产物不属于仓库镜像合同。

#### Scenario: `.agents` 与 `.claude` 保持一致

- **WHEN** Harness 或 OpenSpec 命令、Skill 被更新
- **THEN** Git 管理且未被忽略的 `.agents` 与 `.claude` 对应命令或 Skill 文件同时更新
- **AND** 缺失文件或内容差异被文档门控报告

#### Scenario: 本机 provider 工具不参与仓库镜像

- **WHEN** 本机安装的 provider 专用 Skill 或 settings 文件未被 Git 管理且已明确忽略
- **THEN** 文档门控不把不同 provider 的路径、命令前缀或本机 Hook 配置报告为仓库镜像漂移
- **AND** 已纳入仓库管理的 Harness、OpenSpec 及项目 Skill 镜像检查保持不变

### Requirement: 候选冻结须在适用人工验收之后

最终审查和完整门控 MUST 基于需求理解、实现与适用人工验收均已收敛的冻结候选。

#### Scenario: 变更需要真实界面或桌面环境验收

- **WHEN** UI 视觉、真实 Word/PDF、桌面工具或真实业务流程无法由自动化可靠覆盖
- **THEN** Agent 在候选冻结前完成并记录人工验收
- **AND** 人工反馈补丁继续归入同一变更包并运行受影响的定向验证
- **AND** 最终 Review 与完整门控只在候选冻结后执行

#### Scenario: 变更不需要人工验收

- **WHEN** 自动化或静态验证能够可靠覆盖全部受影响风险
- **THEN** 人工验收记录为 `N/A`
- **AND** Agent 可在定向验证通过后冻结候选

#### Scenario: 活跃 Level 3 变更包执行增量任务

- **WHEN** Level 3 变更包仍在开发或反馈收敛阶段
- **THEN** 每个增量任务按自身风险运行定向验证
- **AND** 不因任务归属于 Level 3 变更包立即运行最终 Review 或 `verify:full`

#### Scenario: 候选准备最终审查和完整门控

- **WHEN** 实现、适用人工验收和已知反馈全部收敛并冻结候选
- **THEN** Level 3 统一执行一次最终 Review 和完整门控
- **AND** 冻结后发生修改时先解冻并完成受影响验证，待再次收敛后统一重新冻结

### Requirement: 活跃变更关联遵循行为范围

未归档变更的关联 MUST 依据正式能力、用户结果、验收场景、核心调用链和反馈生命周期，不以关键词完全相同为前提。

#### Scenario: 新任务延续未归档变更目标

- **WHEN** 新任务与未归档变更共享正式能力、用户结果、验收场景、核心调用链或候选冻结前反馈
- **THEN** Agent 将该变更作为关联候选并按需读取其 tasks 与 delta
- **AND** 同目标任务继续使用原变更包，不因措辞、文件或任务边界不同创建重复包

#### Scenario: 创建新的 Level 2 或 Level 3 变更包

- **WHEN** Agent 排除已有未归档候选后仍需创建新变更包
- **THEN** Agent 在结果中记录主要候选及排除理由
- **AND** 不以无关键词命中或目录名称不同作为无关联的充分证据

### Requirement: 风险相称的验证证据

增量验证 MUST 由本次修改风险和现有覆盖缺口决定，不继承所在变更包 Level，也不以行为变化为由机械追加测试。

#### Scenario: 现有测试已经覆盖本次风险

- **WHEN** 本次修改可以由现有测试、类型检查、构建、静态检查或适用人工验收可靠区分
- **THEN** Agent 复用、修改或合并现有验证证据
- **AND** 不仅因为发生行为变化或前后端同时修改就新增测试

#### Scenario: 高风险行为或现有覆盖缺口

- **WHEN** 修改涉及安全、权限、持久化、关键数据转换、公共契约，或现有验证不能区分新增风险
- **THEN** Agent 增加与缺口相称的自动化回归
- **AND** 避免在多个层重复验证同一实现细节

### Requirement: AGENTS 策略文件行数预算

根目录 `AGENTS.md` MUST 保持为紧凑决策入口，详细执行说明下沉到 Harness 专用文档。

#### Scenario: 运行任一文档一致性检查

- **WHEN** 根目录 `AGENTS.md` 超过 250 行
- **THEN** 文档检查失败并报告 `agents-md-line-budget`
- **AND** 详细执行规则应下沉到现有 Harness 专用文档而不是继续扩充根规则入口

### Requirement: 完整验证环境预检

完整门控 MUST 在工程检查前验证其临时目录运行条件，避免将环境故障误判为实现失败。

#### Scenario: 验证环境不满足最低条件

- **WHEN** 完整门控使用的临时目录不可写、路径过长或可用空间低于仓库配置
- **THEN** `verify:full` 在运行工程检查前失败
- **AND** 输出失败检查项与可执行的环境修复提示

#### Scenario: Windows 默认使用项目所在卷的短临时路径

- **WHEN** Windows 上运行完整门控且未显式设置 `HARNESS_TEMP_ROOT`
- **THEN** 系统在项目所在卷根目录选择 `harness-temp-root`
- **AND** 预检按需创建该目录，并将子进程的 `TEMP`、`TMP` 与 npm cache 指向该目录
- **AND** 显式设置 `HARNESS_TEMP_ROOT` 时仍优先使用配置值

### Requirement: 紧凑的完整验证输出

完整门控 MUST 默认提供阶段级结果，并将详细输出留在可下钻日志中。

#### Scenario: 完整门控阶段通过

- **WHEN** 一个完整门控阶段退出码为零
- **THEN** 命令只输出阶段名称、PASS 状态和耗时摘要
- **AND** 不输出该阶段逐条通过日志

#### Scenario: 完整门控阶段失败

- **WHEN** 一个完整门控阶段退出码非零或无法启动
- **THEN** 命令输出 FAIL 摘要和有限的诊断尾部
- **AND** 将完整输出保存在独立日志文件并报告其路径
- **AND** 停止后续阶段

### Requirement: 渐进式 Harness 上下文路由

高频 Harness 入口 MUST 先关联 change 和判断 Level，再按当前风险与阶段加载资料；不得以保证质量为由在普通需求入口无条件预读全部 Harness 或 OpenSpec 正文。

#### Scenario: Level 1 或 Level 2 普通任务进入实现

- **WHEN** 任务不涉及重大架构或高风险迁移
- **THEN** Agent 只加载根规则、直接相关源码/测试，以及 Level 2 匹配包的 tasks 与相关 delta
- **AND** 不预读完整 `harness/iteration-guide.md`、`harness/architecture.md`、proposal 或 design

#### Scenario: 出现架构或阶段专属信号

- **WHEN** 任务新建文件、跨层引用、改变公共契约、存在架构风险，或 Level 3 进入特定阶段
- **THEN** Agent 加载对应架构或阶段专用章节和工件
- **AND** 验证、Review 与归档资料仅在对应阶段加载

#### Scenario: 高频入口恢复无条件全量预读

- **WHEN** propose、apply、fix 或 verify 命令缺少渐进式上下文合同，或重新要求启动前完整预读文档
- **THEN** 默认文档门控失败并报告 `harness-context-loading-regression`
- **AND** `.agents` 与 `.claude` 镜像门控继续生效

### Requirement: 渐进式路由保留质量门控

减少上下文加载 MUST NOT 删除风险判断、规格核对、受影响验证、同步或候选冻结门控。

#### Scenario: 任务沿轻量路径完成

- **WHEN** Level 1 或 Level 2 任务完成实现
- **THEN** Agent 仍执行该级别的定向验证、工程检查和适用文档同步
- **AND** 上下文路由只改变资料加载时机，不跳过质量证据

#### Scenario: 对路由改造执行端到端审计

- **WHEN** 渐进式上下文路由首次落地
- **THEN** 使用一个真实需求记录关联、Level、读取资料、实现和正常收尾门控
- **AND** 可额外运行一次限定范围完整门控证明全仓库质量未退化，但该审计不改变普通 Level 2 的默认门控
