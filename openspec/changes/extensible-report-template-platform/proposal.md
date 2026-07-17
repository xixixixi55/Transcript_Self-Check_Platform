# extensible-report-template-platform

## Why

当前系统把解析结果、业务规则、压缩执行和 DOCX 排版都直接耦合在 `InspectionReport`、`report_parser_service.py` 与 `template_filler_service.py` 中。甲方已经确认报告结构、检材展示、分卷压缩、三类附件和模板选择都将继续变化；如果继续在现有字段和唯一模板上叠加条件分支，将无法同时保护新旧报告兼容性和版式验收结果。

本变更建立“报告适配 → 规范化案件 → 业务规划 → 文档渲染计划 → 模板 Profile → DOCX Renderer”的稳定边界。阶段一先完整实现当前报告与当前正式模板，阶段二、三只预留可落地的 Profile 和人工确认接口，不把未来能力伪装成当前自动化能力。

## What Changes

- 新增 `CanonicalInspectionCase` 及相关领域模型，作为解析 DTO 和 Word 模板之间的内部唯一事实来源。
- 明确主迁移方向为 `ReportAdapter → CanonicalInspectionCase → InspectionReport → 现有前端和导出`；`InspectionReport → CanonicalInspectionCase` 只作为旧前端提交/历史数据迁移的兼容入口，不承诺完整回填。
- 将手机/平板的标识展示规则、检查人员顺序、软件工具来源、光盘编号和附件分页规则移入业务规划层。
- 新增单机检查人员库，并在报告中保存有序的 `InspectorSnapshot`，防止人员库后续修改影响历史报告。
- 新增 `ArchivePlan`、`ArchivePart`、`ArchiveManifest`、`DiscSequence`，把 WinRAR 分卷规划、执行、校验和重新规划分离。
- 新增 `Attachment1Plan`、`PhotoPagePlan`、`Attachment3Plan` 和 `DocumentRenderPlan`，先生成确定的页面/字段计划，再交给模板渲染器。
- 将当前正式模板登记为 `current-template-v1`；保留 VML 文本框、现有分页和模板资产，渲染器只按 Profile 允许的区域修改内容，并统一动态字体颜色为黑色。
- 阶段一只落地固定的 `current-template-v1`、固定 `TemplateProfile` 和当前 DOCX Renderer 的受控扩展；通用模板设计器、重复块 DSL、任意 DOCX 自动绑定、可视化编辑和无标记模板识别均留到阶段三。
- 增加集中式 `pipeline_mode = legacy | shadow | canonical`；Shadow 只生成隔离的规范化/规划/比较结果，不产生第二份正式文书，也不调用 WinRAR 或执行真实重复压缩。
- 阶段一采用统一最终导出门控：报告可以继续上传、解析、审核和编辑，但检材类型、主取证软件、图片数量、WinRAR 可用性或最终归档清单存在阻断项时不得正式导出；WinRAR 不可用时不生成 `ArchiveManifest`，也不降级为 ZIP 分卷。
- 预留 `ReportProfile`/`FieldProvenance`，支持阶段二的结构发现、字段候选、人工确认和同类报告复用。
- 预留 `TemplateProfile` 和可解释的字段位置推荐，支持阶段三的可视化绑定、重复块、图片区、显示条件和分页配置。
- 增补跨层接口、缓存版本、失败回滚、审计信息和阶段化测试/人工验收门槛。

## Capabilities

### New Capabilities

- `canonical-report-model`: 规范化报告、检材标识、检查人员快照和软件工具模型。
- `archive-planning-and-execution`: 十进制分卷规划、WinRAR 执行、卷校验、MD5 和重新规划。
- `attachment-page-planning`: 附件一、二、三的页面规划、分页和显示条件。
- `template-profile-rendering`: 模板 Profile、渲染计划、当前正式模板登记和 DOCX/VML 兼容渲染。
- `report-profile-adaptation`: 阶段二的报告结构发现、来源追踪、候选确认和 Profile 复用接口。
- `template-visual-configuration`: 阶段三的可视化模板绑定、推荐、确认、修正和回滚接口。
- `inspector-library`: 单机检查人员库、报告有序选择和历史快照。
- `shadow-pipeline-comparison`: 旧管线正式输出与新管线规范化/规划结果的脱敏比较和切换门控。

### Modified Capabilities

- `electronic-inspection-record`: 修改现有电子数据检查笔录的检材展示、软件列表、光盘编号、压缩包、附件分页、图片校验和模板选择要求。现有能力的完整行为以本变更 `spec.md` 的兼容约束为准，旧 `InspectionReport` 请求仍受支持。

## Impact

- SharedTypes：增加规范化模型、Profile、规划和渲染计划类型；保留现有 `InspectionReport`/`ParseReportResponse`。
- 后端 Repository：拆分报告适配、单机人员库、WinRAR 执行/校验、模板 Profile 存储和 DOCX OOXML 读取职责。
- 后端 Services：增加规范化、业务规则、规划、渲染编排服务；逐步缩小现有解析和模板填充服务职责。
- Controllers/Routes：阶段一可通过兼容现有端点承载内部新管线；阶段二、三再增加 Profile、人员库、模板配置 API。
- 前端：阶段一只增加必要的人员选择、光盘首编号、分卷/图片错误提示；继续消费旧 DTO。阶段二、三增加候选确认和模板可视化配置页面。
- 模板与输出：不改动甲方当前模板资产；新增模板登记/校验元数据和版本化输出清单。现有输出、缓存、未跟踪文件不在本变更中清理或迁移。
- 依赖：阶段一继续使用本地文件系统、python-docx 和已存在的 officecli/WinRAR；不新增数据库、云存储或异步队列。

## Non-Goals

- 本阶段不修改业务代码、当前模板、已有输出、解析缓存或未跟踪资产；这些是后续 implementation 阶段的任务。
- 不把 `CanonicalInspectionCase` 完整回投为 `InspectionReport` 作为领域事实。兼容投影可能缺少字段来源、通用 identifiers、`InspectorSnapshot`、`ArchiveManifest`、`TemplateProfile` 信息及其他新模型字段；这些内容必须保留在 canonical/plan/manifest 中并明确标记不可表示。
- 阶段一不支持任意厂商、任意 JSON 结构的静默自动解析；未知结构必须进入候选/确认路径或明确阻止导出。
- 阶段一不支持任意 DOCX 的自动套版；`current-template-v1` 之外的模板只登记接口，不承诺渲染。
- 不用环境检测结果替代报告中的主取证软件名称和版本。
- 阶段一不实现 ZIP 自动分卷降级；现有 ZIP/RAR 上传解析能力不等同于本次 WinRAR 自动分卷产物。
- 不在本变更中引入登录、联网人员同步、数据库迁移、并发多机协作或新的文书类型。
- 不以模板推荐结果代替用户确认；阶段三禁止静默套用普通无标记模板。
- 不允许前端直接读取、写入或解析检查人员 JSON 文件；人员库只能通过后端 Repository 暴露的接口访问。

## Acceptance Boundary

- 阶段一是本变更的必须实现范围，必须通过自动化测试、DOCX XML/分页检查和甲方人工视觉验收后才允许切换默认管线。
- 阶段二、阶段三的接口和数据模型必须可序列化、可版本化、可回滚，但不以“支持任意报告/任意模板”作为阶段一验收条件。
