## MODIFIED Requirements

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

## ADDED Requirements

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
