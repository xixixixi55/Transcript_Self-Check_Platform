## ADDED Requirements

### Requirement: Level 2 change artifact contract

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

#### Scenario: 执行当前变更包严格检查

- **WHEN** 执行 `verify:docs:strict -- --change <name>`
- **THEN** 只检查指定变更包的 workflow level、tasks 和 delta spec
- **AND** 其他活跃变更包的迁移债务不阻断当前变更

#### Scenario: 执行全局严格检查

- **WHEN** 执行 `verify:docs:strict:all`
- **THEN** 检查全部活跃变更包，并排除 `openspec/changes/archive/`

### Requirement: Mirrored agent workflow files

#### Scenario: `.agents` 与 `.claude` 保持一致

- **WHEN** Harness 或 OpenSpec 命令、Skill 被更新
- **THEN** `.agents` 与 `.claude` 中对应文件同时更新
- **AND** 缺失文件或内容差异被文档门控报告

## ADDED Requirements

### Requirement: Candidate freeze follows applicable manual acceptance

#### Scenario: 变更需要真实界面或桌面环境验收

- **WHEN** UI 视觉、真实 Word/PDF、桌面工具或真实业务流程无法由自动化可靠覆盖
- **THEN** Agent 在候选冻结前完成并记录人工验收
- **AND** 人工反馈补丁继续归入同一变更包并运行受影响的定向验证
- **AND** 最终 Review 与完整门控只在候选冻结后执行

#### Scenario: 变更不需要人工验收

- **WHEN** 自动化测试能够可靠覆盖全部受影响行为
- **THEN** 人工验收记录为 `N/A`
- **AND** Agent 可在定向验证通过后冻结候选

### Requirement: Full verification environment preflight

#### Scenario: 验证环境不满足最低条件

- **WHEN** 完整门控使用的临时目录不可写、路径过长或可用空间低于仓库配置
- **THEN** `verify:full` 在运行工程检查前失败
- **AND** 输出失败检查项与可执行的环境修复提示

#### Scenario: Windows 默认使用项目所在卷的短临时路径

- **WHEN** Windows 上运行完整门控且未显式设置 `HARNESS_TEMP_ROOT`
- **THEN** 系统在项目所在卷根目录选择 `harness-temp-root`
- **AND** 预检按需创建该目录，并将子进程的 `TEMP`、`TMP` 与 npm cache 指向该目录
- **AND** 显式设置 `HARNESS_TEMP_ROOT` 时仍优先使用配置值

### Requirement: Compact full verification output

#### Scenario: 完整门控阶段通过

- **WHEN** 一个完整门控阶段退出码为零
- **THEN** 命令只输出阶段名称、PASS 状态和耗时摘要
- **AND** 不输出该阶段逐条通过日志

#### Scenario: 完整门控阶段失败

- **WHEN** 一个完整门控阶段退出码非零或无法启动
- **THEN** 命令输出 FAIL 摘要和有限的诊断尾部
- **AND** 将完整输出保存在独立日志文件并报告其路径
- **AND** 停止后续阶段
