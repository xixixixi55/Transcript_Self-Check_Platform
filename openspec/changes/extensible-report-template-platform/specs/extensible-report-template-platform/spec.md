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

### Requirement: Built-in template cleanup preserves versioned exports

内置模板清理 MUST 通过新模板版本交付。清理后的版本 MUST 删除全部批注结构和附件二示例媒体，同时保留动态图片区域锚点、VML、分页、表格与上传图片渲染能力；旧版本资产 MUST 保留供既有案件按原模板引用重导出，并作为历史只读资产禁止新案件选择、设为默认或删除。

当前内置版本 MUST 以 A4 页面中心为基准居中可见主标题和首页/页脚粗横线，并保持结构标题的层级缩进：“一、绪论”“二、检查”略突出于二级标题，“（三）检查过程”“（四）检查结果”与其他二级标题对齐。该修正 MUST 发布为新的不可变版本，不得覆盖旧模板字节或既有案件引用。

#### Scenario: Upgrade from the previous built-in template

- **WHEN** 部署升级且当前默认值仍指向旧内置模板
- **THEN** 系统将后续新案件的默认模板迁移到清理后的新版本
- **AND** 既有案件模板引用不变，用户选择的其他默认模板不被覆盖
- **AND** 旧内置版本不出现在新案件可选列表中，管理接口拒绝将其重新设为默认或删除

#### Scenario: Word-native layout anchors remain visibly centered

- **WHEN** 当前内置模板由 Microsoft Word 原生渲染
- **THEN** 主标题可见字形中心、首页文号下方粗横线和各页页脚上方粗横线均与页面中心一致
- **AND** 结构标题保持一级略突出、同级对齐的缩进层次
- **AND** 页数、分页、表格列宽、VML 文本框、页眉和页脚内容保持不变

### Requirement: Local Windows directory picker preserves the path-based source contract

本地 Windows 案件工作台 MUST 提供点击式“上传报告目录/添加案件”入口。入口 MUST 由后端在本机交互桌面会话中弹出原生文件夹选择窗口；选择成功后 MUST 在同一请求内使用真实绝对路径登记既有 `SourceRecord`、创建案件壳和解析任务。浏览器 MUST NOT 上传或复制报告目录，公共响应、日志和浏览器状态 MUST NOT 暴露绝对路径；选择范围 MUST NOT 被硬编码为桌面目录。取消选择 MUST 是无副作用操作。

#### Scenario: 选择目录后直接登记并解析

- **WHEN** 用户点击工作台的上传报告目录卡片并在 Windows 原生窗口选择有效报告文件夹
- **THEN** 后端直接完成来源登记、案件壳/解析任务持久化和解析 dispatch
- **AND** 前端显示排队或解析中的案件卡片，不再要求先填写路径再点击登记按钮
- **AND** 原始目录仍由既有后端路径合同直接读取，不生成浏览器上传副本

#### Scenario: 取消或无法打开选择器

- **WHEN** 用户取消选择，或 Windows 选择器不可用/超时
- **THEN** 取消不创建任何案件数据；不可用/超时返回稳定错误和可重试状态
- **AND** 错误响应不包含绝对路径、PowerShell 命令或内部异常
