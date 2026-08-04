# Harness 工作流

## Purpose

定义 Level 2 轻量变更包的固定工件、范围化文档门控、历史 living spec 迁移和 `.agents`/`.claude` 工具镜像一致性。

## Requirements

### Requirement: Level 2 change artifact contract

Level 2 变更 MUST 同时维护实现任务和最终行为 delta，不因轻量流程省略 living spec 同步闭环。

#### Scenario: 创建新的 Level 2 变更包

- **WHEN** 需求被判定为 Level 2
- **THEN** 变更包包含 `tasks.md` 和至少一个 `specs/<capability>/spec.md`
- **AND** `tasks.md` 持久化记录 `workflow_level: 2`
- **AND** delta spec 只记录新增、修改或删除的正式行为及关键场景
- **AND** 不因增加 delta spec 创建 proposal 或 design

#### Scenario: Level 2 没有正式行为变化

- **WHEN** 修改不新增或改变正式行为
- **THEN** 需求按 Level 1 处理
- **AND** 不创建 Level 2 变更包或使用 `Spec impact: N/A` 绕过 delta spec

### Requirement: Scoped Level 2 documentation gate

严格文档门控 MUST 使用 tasks.md 中持久化的 `workflow_level`，并将当前变更包范围与全局活跃变更包范围分开。

#### Scenario: 执行当前变更包严格检查

- **WHEN** 执行 `verify:docs:strict -- --change <name>`
- **THEN** 只检查指定变更包的 workflow level、tasks 和 delta spec
- **AND** 其他活跃变更包的迁移债务不阻断当前变更

#### Scenario: 执行全局严格检查

- **WHEN** 执行 `verify:docs:strict:all`
- **THEN** 检查全部活跃变更包，并排除 `openspec/changes/archive/`

### Requirement: Mirrored agent workflow files

Harness 和 OpenSpec 工具入口 MUST 在 `.agents` 与 `.claude` 中保持对应内容一致。

#### Scenario: `.agents` 与 `.claude` 保持一致

- **WHEN** Harness 或 OpenSpec 命令、Skill 被更新
- **THEN** `.agents` 与 `.claude` 中对应文件同时更新
- **AND** 缺失文件或内容差异被文档门控报告
