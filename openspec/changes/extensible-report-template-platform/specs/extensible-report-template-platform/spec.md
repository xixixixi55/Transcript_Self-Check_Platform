# OpenSpec Delta: extensible-report-template-platform

本 delta 为 `spec-driven` CLI 提供能力入口；完整的阶段边界、模型字段、场景和兼容约束见本变更根目录的 [`spec.md`](../../spec.md)。本文件不复制根规范，避免两份需求文本发生漂移。

## ADDED Requirements

### Requirement: Stage-one review and export gate has fixed business boundaries

阶段一 MUST 只允许最终检材类型 `phone`/`tablet`，允许报告明确类型自动预选，无法可靠判断时由审核页面确认；不得仅根据 IMEI 推断类型。主取证软件无法可靠识别时允许审核页面分别编辑名称和版本，但确认前不得正式导出。WinRAR 缺失或不可调用时允许上传、解析和编辑，禁止自动压缩、禁止最终正式导出、不生成 `ArchiveManifest`，且不降级 ZIP。0 张图片不生成附件二页面，正偶数图片按页面计划生成，奇数图片阻止导出；附件二缺失不重排附件三编号。人员快照按用户选择顺序一人一行，人员框只能作为附件一最后页不可拆块。`shadow` 不调用 WinRAR、不执行真实重复压缩、不产生第二份正式文书。

#### Scenario: Stage-one blockers do not prevent review editing

- **WHEN** 检材类型、主软件、图片数量或 WinRAR 存在未解决阻断项
- **THEN** 用户仍可上传、解析、审核、保存和编辑中间结果
- **AND** 统一导出门控返回明确阻断代码和可操作提示
- **AND** 最终正式导出被拒绝直到阻断项清除

### Requirement: The extensible pipeline is staged and gated

系统 MUST 按根 `spec.md` 定义的三阶段边界交付：阶段一实现当前报告 + `current-template-v1` 的确定性能力，主迁移方向为 `ReportAdapter → CanonicalInspectionCase → InspectionReport → 现有前端和导出`；阶段二只在用户确认字段候选后保存/复用 `ReportProfile`；阶段三只在用户可视化确认/修正后启用 `TemplateProfile`。`InspectionReport → CanonicalInspectionCase` 仅用于旧 DTO 输入和历史迁移，不承担 canonical 的完整回填。任何阶段的规划、模板资产、Profile 或导出门控失败都 MUST 阻止错误结果提交，并保留可回滚的旧路径。

#### Scenario: Stage one is ready for implementation

- **WHEN** 变更包被 OpenSpec 校验并进入实现阶段
- **THEN** 阶段一的 parser compatibility、canonical model、archive/page plan、`current-template-v1` renderer、测试和人工验收任务可独立执行，阶段二/三不会被隐式宣称已完成

#### Scenario: Later-stage automation is not silently enabled

- **WHEN** 报告结构或模板没有已确认的 Profile
- **THEN** 系统展示候选/推荐及来源和置信信息，要求用户确认或修正；在确认前不得静默解析、套用或导出
