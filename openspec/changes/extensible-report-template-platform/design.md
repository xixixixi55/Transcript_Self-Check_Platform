# Design: Extensible Report and Template Platform

## Context

当前生产仍以“HTML/JSON 解析 → `InspectionReport` legacy DTO → 最终 Manifest 投影/附件计划 → 填充 `template.docx`”为正式输出主链：

- `packages/backend/app/repository/report_format_adapter.py`、`html_parser.py` 和 `device_field_parser.py` 已经积累了旧/新报告识别、字段候选和回归保护。
- `report_parser_service.py` 仍组装 legacy DTO 和解析缓存；解析阶段只建立 `ArchiveContext`，真实压缩由独立归档执行入口触发。解析/清缓存请求已具备存活性边界，解析缓存只覆盖解析器实际依赖的数据。
- `ArchivePlanner`、WinRAR executor/validator、有限向上 replan 和最终 `ArchiveManifest` 已进入归档生产能力；D1 容量合同与 D2.1 七项超时、完整性、进程终止、Manifest 兼容、锁生命周期、环境变量 warning 和 Export Gate 序列化治理已经完成，剩余真实大容量与人工验收边界见 `tasks.md`。
- `record_controller.py` 仍接收 `InspectionReport`，校验最终 Manifest、投影 legacy 字段并调用 `template_filler_service.py`；`document_builder_service.py` 只保留为无 Manifest 场景的 officecli batch 回退，带 Manifest 的正式导出失败不会静默回退。
- Canonical 模型、双向兼容适配器、`PipelineOrchestrator` 和 Shadow 比较器已有实现；Shadow 已接入真实生产 Controller 的旁路观测，canonical 分支仍显式保持未启用。
- `AttachmentPlan` 与固定 `current-template-v1` TemplateProfile 已被当前 renderer 消费；`DocumentRenderPlan` 尚无生产类型、构造器或消费方。
- `word_templates/template.docx` 是当前运行时模板，已有 VML 文本框、普通分页符、表格和动态占位符；`template-2026` 与 `docx-vml-pagination` 记录了其资产来源和回归约束。
- `InspectionReport` 位于 SharedTypes，前端 `useReportParser`、`useRecordExport`、审核表单和导出测试直接依赖它。

本变更是跨解析、领域规则、持久化、文件执行和 DOCX 的 Level 3 架构变更。设计目标是逐步建立稳定的领域内核，而不是一次性替换所有调用方。

## Goals / Non-Goals

**Goals:**

- 阶段一完整实现当前报告 + 当前模板的已确认规则，并保护新旧解析回归。
- 让 parser 只负责发现/归一化候选，让业务层决定显示、编号、工具、压缩和分页。
- 让压缩结果具有不可变 manifest，使附件一和附件三共享同一份卷数据。
- 让模板成为可登记的 `TemplateProfile`，保留当前 OOXML/VML 资产并使渲染规则可测试。
- 为阶段二的报告结构 Profile 和阶段三的可视化模板 Profile 提供版本化、人工确认、解释和回滚接口。

**Non-Goals:**

- 本设计阶段不修改业务代码、模板、输出、缓存或未跟踪文件。
- 不在阶段一实现任意厂商 JSON 或任意 DOCX 的完整自动化。
- 不引入数据库/云同步；单机存储是阶段一约束。
- 不让推荐、低置信解析或未知模板静默进入最终导出。

## Target Architecture

```text
Raw report directory/archive
        │
        ▼
ReportProfile / ReportAdapter
        │  candidates + FieldProvenance
        ▼
CanonicalInspectionCase
        ├── InspectionReport projection → existing frontend/export contract
        ├── Domain rules: material display / tools / inspectors / disc sequence
        ├── ArchivePlanner → ArchivePlan → WinRarExecutor → ArchiveManifest
        └── AttachmentPlanner → Attachment1/Photo/Attachment3 plans
                                      │
                                      ▼
                              DocumentRenderPlan
                                      │
                              fixed TemplateProfile
                                      │
                              DOCX Renderer

Legacy InspectionReport input/history ──► LegacyReportInputAdapter ──► CanonicalInspectionCase
```

职责边界：

| 层 | 职责 | 禁止承担 |
|---|---|---|
| ReportAdapter/Repository | 识别结构、读取源文件、字段候选、来源和原始值 | 决定 Word 显示、附件分页、调用 WinRAR |
| Canonicalizer/Service | 校验并形成规范化案件、分配稳定 ID、记录问题 | 直接写 OOXML |
| Domain planning/Service | 手机/平板标识政策、软件工具、人员快照、光盘序列、压缩和附件页面 | 读取 Word XML |
| Archive executor/Repository | 执行 WinRAR、读取卷、MD5、连续性和大小验证 | 计算案件业务字段 |
| Render planner/Service | 把业务对象映射为模板无关的字段/块/图片/分页计划 | 直接猜模板 XML |
| TemplateProfile/Repository | 保存模板资产、结构定位和约束 | 业务字段计算 |
| DOCX Renderer/Service | 按 Profile 应用计划、保留 OOXML/VML 并校验输出 | 重新解析原始报告 |

依赖方向遵守项目架构：SharedTypes → SharedConstants/Utils；后端 Repository → Services → Controllers → Routes；前端只通过 API DTO 通信。规划对象先放在后端领域服务和 SharedTypes 契约中，避免 React 组件直接依赖 Python 实现。主迁移方向是 `ReportAdapter → CanonicalInspectionCase → InspectionReport → 现有前端和导出`；legacy DTO 进入 canonical 只属于兼容/历史迁移路径。

## Domain Models and Interfaces

以下是实现阶段应落在 SharedTypes/后端领域模型中的最小契约。字段名可以按项目现有 Python/TypeScript 命名约定分别采用 snake_case/camelCase，但序列化名称必须稳定。

### `CanonicalInspectionCase`

```text
CanonicalInspectionCase {
  caseId: string
  schemaVersion: string
  source: { reportId, adapterId, profileId?, files[], fingerprint }
  case: { name, number?, entrustUnit, entrustPersons[], summary }
  times: { createdAt, reportedAt, inspectionStart, inspectionEnd, sourceRefs[] }
  materials: Material[]
  mainSoftware: SoftwareTool
  softwareTools: SoftwareTool[]       // 规范化后只含允许的三类
  inspectors: InspectorSnapshot[]      // 有序、不可变于本报告
  requirements: { inspection, method, place }
  rawFieldIssues: FieldIssue[]
}
```

`inspectionStart/inspectionEnd` 明确取报告创建时间/报告时间；光盘日期只进入附件日期字段。`case.name` 同时作为归档基础名称，但在文件系统层必须经过安全文件名规范化，并保留原始案件名用于正文。

### `Material` and generic identifiers

```text
Material {
  materialId: string
  evidenceNumber: string
  kind: "phone" | "tablet" | "pending_confirmation"
  name: string
  model?: string
  identifiers: Identifier[]
  classification: { source, ruleId, confidence, confirmed }
  provenance: FieldProvenance[]
}

Identifier {
  type: "imei1" | "imei2" | "serialNumber" | string
  value: string
  normalizedValue: string
  valid: boolean
  source: FieldProvenance
}
```

解析层可以保留未来标识类型，但阶段一的 `MaterialDisplayPolicy` 只输出手机的合法 IMEI1/IMEI2 或平板的合法序列号。分类必须优先使用报告明确且可靠的类型；无可靠类型时保持 `pending_confirmation`，由审核页面确认，不能仅根据 IMEI 存在与否推断手机。最终导出前每个材料必须是 `phone` 或 `tablet`；原始 identifiers 始终保留，不在渲染层补字段或删除数据。

统一的 `ExportGate` 在审核保存和正式导出之间提供一致校验结果。它允许存在阻断项时继续上传、解析、审核和编辑，但只有材料类型、主取证软件、图片数量、光盘编号、WinRAR 可用性和最终归档清单全部满足要求时才允许正式导出；返回稳定阻断代码和可操作提示，不由各 parser/service/renderer 分散实现。

### `Inspector`, `InspectorSnapshot`, `SoftwareTool`

```text
Inspector { inspectorId, name, unit, policeNumber, createdAt, updatedAt }
InspectorSnapshot { inspectorId, name, unit, policeNumber, selectedOrder, capturedAt, sourceVersion }
SoftwareTool {
  toolId, role: "mainForensic" | "winrar" | "pythonHashlib"
  name, version, source: "report" | "runtime"
  provenance?: FieldProvenance
}
```

`mainForensic` 的 `name` 和 `version` 都必须有报告来源；适配器低置信或缺失时标记为待确认，审核页面允许分别填写/修正名称和版本，确认前由 `ExportGate` 阻止正式导出。不得使用历史固定软件或从普通组件猜测；仅有 WinRAR/Python hashlib 时工具列表仍不完整。WinRAR 和 Python hashlib 只作为执行工具记录，可取运行时版本。`softwareTools` 由角色白名单去重，不能把报告中的其他软件直接带入模板。`InspectorSnapshot` 始终保持结构化的 `unit`、`name`、`police_number` 序列化字段，默认单文本框格式由 TemplateProfile 配置为 `单位　姓名（警号）`；多个单元格时由 Profile 分别绑定三字段。

### `ReportProfile` and `FieldProvenance`

```text
ReportProfile {
  profileId, version, vendor?, product?, productVersion?
  structureFingerprint, adapterId, adapterVersion
  fileSelectors: [{ logicalName, glob, required }]
  fields: Record<CanonicalFieldPath, FieldMapping>
  createdAt, updatedAt, status: "draft" | "confirmed" | "retired"
}

FieldMapping {
  sourceFile, jsonPath, adaptationRuleId
  normalize: string[], required: boolean
  confidence: { score, level, evidence[] }
  confirmation: "auto" | "userConfirmed" | "needsReview"
}

FieldProvenance {
  sourceFile, jsonPath, rawValueHash?, adaptationRuleId
  confidenceScore, confidenceLevel, evidence[], capturedAt
}
```

`ReportAdapter` 接口分为 `detect(input)`, `discover(input)`, `parse(input, profile)` 三步。`discover` 只能生成候选和证据；`parse` 在 Profile 未确认或低置信字段上返回 issue。Profile 命中顺序为精确结构指纹 → 厂商/版本/结构兼容指纹 → 人工确认；不能以文件名、案件名称或目录顺序作为唯一识别。

### `ArchivePlan`, `ArchivePart`, `DiscSequence`

```text
ArchivePlan {
  plan_id, case_display_name, archive_base_name
  source_entries[], total_input_bytes
  volume_size_bytes, volume_tier_gb
  expected_part_count, max_part_count
  first_disc_number?, expected_disc_numbers[]
  max_replan_attempts: 2
  status: "planned" | "blocked", diagnostics[]
}

ArchivePart {
  part_id, part_number, filename, size_bytes, md5
  disc_number, disc_date, disc_capacity_bytes, volume_size_bytes, continuity_check
}

ArchiveManifest {
  manifest_id, plan_id, archive_base_name
  volume_size_bytes, volume_tier_gb, max_part_count
  total_input_bytes, actual_archive_bytes, retry_count
  parts: ArchivePart[], created_at, winrar_capability
  validation_status, continuity_check
}

DiscSequence { prefix, date, start_number, number_width, first_disc_number }
```

档位采用十进制字节值。规划初始候选由输入总字节数计算：`ceil(total / volume_size_bytes) <= max_part_count` 时选择该档位。4GB 档最多 2 卷（≤8GB），22GB 档最多 2 卷（≤44GB），45GB 档最多 3 卷（≤135GB）。`ArchivePlan` 只表示预计方案；WinRAR 执行和 validator 产生实际结果，最多允许 `maxReplanAttempts = 2` 次向上重试。

分卷档位（WinRAR `-v` 参数）与每卷光盘容量是两个独立概念。`volume_size_bytes` 表达本次档位的每卷上限，`size_bytes` 表达 WinRAR 实际 part 文件大小；`disc_capacity_bytes` 在 Manifest 组装时根据每卷 `size_bytes` 独立计算最小可容纳容量：≤4GB→4GB, ≤22GB→22GB, ≤45GB→45GB, >45GB→验证失败。不得用 manifest 级档位值替代。

只有归档结果绑定 `DiscSequence` 后才组装最终 `ArchiveManifest`，因此 manifest 中的实际 part 大小、光盘容量、光盘编号、刻录日期和连续性结果都是最终数据。最终 Manifest 是 Word 正文、附件一和附件三归档字段的唯一事实源；实际结果超出计划且重试耗尽时阻止导出，不使用预计值或重新扫描所得的第二份卷列表生成 Word。

`DiscSequence` 从 `GPyyyyMMdd-序号` 解析；后续序号只递增数字部分，按首编号位宽左补零，溢出即阻止。`ArchiveManifest.parts[i].part_id` 是附件一、附件三唯一的关联键，`part_number` 只表达卷顺序；光盘序号由 manifest 顺序映射，不由附件渲染器自行计数。附件一、附件三只接收最终 `ArchiveManifest`，不得接收 `ArchivePlan`。

导出前的首次 Manifest 校验必须对每个实际分卷执行存在性、大小和完整 MD5 校验；在同一次校验中，已得到的 MD5 传给后续结构校验，避免同一次导出把 135GB 分卷重复读取两遍。当前实现不使用大小、mtime 或文件标识替代哈希，也没有用不具备内容安全保证的快捷缓存：Word 失败后的同一请求不会重新执行 WinRAR，但新的导出请求复用 Manifest 时仍会重新读取并校验所有分卷 MD5。这样保留了“文件未变化”的内容级证据，代价是大分卷重试可能再次产生完整读取成本。后续若引入性能优化，必须保存受保护的文件身份快照并说明其安全边界，不能无条件跳过变化检测。

### Archive input authorization mode and context boundary

归档输入保留既有固定根目录、精确目录令牌和路径安全实现，但由浏览器首页的持久化用户偏好选择是否启用授权边界。具体案件目录不要求统一搬迁到一个总目录，也不要求系统移动、复制或删除用户原始取证数据。

1. 授权开启时：`UPLOAD_BASE` 始终加入允许集合，部署者可用 Windows 分号分隔的 `BIJI_ALLOWED_INPUT_ROOTS` 增加多个数据父目录。每个案件目录必须是配置根目录的真实、严格子目录；精确令牌仍只绑定一个具体目录，不绑定父目录或磁盘。
2. 授权关闭时：登记请求跳过配置根目录和精确令牌的授权判断，允许任意本机绝对报告目录继续进入后续报告结构校验和上下文创建。该模式不删除、不绕过路径解析、reparse point、输入/输出隔离和报告结构校验代码；后续重新开启即可恢复授权边界。
3. 首页开关只持久化在当前浏览器的本地存储中；案件工作台和重新登记组件不提供第二个开关，而是在请求发送时读取同一偏好。直接未携带偏好字段的 API 调用默认保持授权开启，避免旧客户端静默扩大范围。
4. 前后端请求字段的共享事实源是 `packages/shared/types/sourceAuthorization.ts`；当前前端生产路由使用工作台登记/来源替换链路，deprecated `/reports/parse` 没有直接调用页面。若恢复 legacy 目录解析页面，必须使用 `useSourceAuthorizationRequests.ts` 构造携带当前偏好的请求。

5. 本机选择器采用后端受控的 Windows 桌面桥接：工作台调用无路径参数的“选择目录并登记案件”端点，后端通过 Windows 原生文件夹对话框取得路径后，立即调用现有 `SourceRecordService.register_report_directory` 和 `CaseDraftService.submit`。绝对路径只存在于当前后端请求栈和既有受控 locator，不进入浏览器 DTO、日志或异常；选择器不设置桌面目录白名单，是否启用配置根授权仍由首页持久化偏好决定。浏览器 `webkitdirectory` 不作为实现，因为它会上传文件并且不能向后端提供真实绝对路径。

6. 选择器进程使用固定的本机 PowerShell/WinForms 原生命令，不拼接用户输入；取消以无副作用结果返回，进程启动失败、非交互桌面和超时映射为稳定错误码。后端端点保持同步阻塞选择行为，由 FastAPI 的同步线程池承载，选择成功后才登记来源和 dispatch 解析；所有既有来源路径安全、报告结构和授权校验继续生效。

固定根目录配置仍在进程启动时统一读取一次：Windows 分号分隔，空项忽略，真实路径按大小写不敏感方式去重。不存在、不可访问、不是目录、相对路径或特殊路径配置不会扩大授权范围；该项被忽略并记录不含路径的 `ARCHIVE_CONFIGURED_ROOT_INVALID` 安全 warning。授权关闭时这些配置不会阻止用户登记目录，但重新开启后继续生效。

`report_dir` 只作为 deprecated 的一次性上下文创建兼容参数。后端先做绝对路径、规范真实路径和输入/输出/staging/cache 隔离检查，再建立随机 UUID `archive_context_id`。后续 `ArchivePlan`、WinRAR、分卷校验、MD5、`ArchiveManifest`、失败重试和 DOCX 导出只接受该上下文标识，不再接受或信任 `report_dir`。公共响应只包含上下文标识、文件数、总字节数、状态和创建/过期时间；不返回案件目录、允许根目录、用户主目录或 WinRAR 安装路径。

输入根目录及清单中的每一级目录和文件都拒绝 symlink、junction、mount point、其他 reparse point、UNC、`\\?\\` 和 `\\.\\` 设备路径。路径关系使用真实路径相对关系而不是字符串前缀。输入目录不能与输出、staging 或缓存区域互相包含，RAR、DOCX、缓存和临时生成物不能递归回到输入清单。上下文建立时和 WinRAR 调用前各做一次快照/指纹校验；新增、删除、大小/修改指纹变化、链接变化或授权范围变化均返回稳定错误并且不调用 WinRAR。

上下文当前只保存在进程内存中：过期返回 `ARCHIVE_CONTEXT_EXPIRED`，不存在返回 `ARCHIVE_CONTEXT_NOT_FOUND`，同一上下文并发返回 `ARCHIVE_CONTEXT_BUSY`；服务重启后不伪造恢复能力，旧上下文按不存在处理，要求重新解析。清理只删除系统元数据和系统生成的临时目录，不删除精确授权的原始案件目录。Word 失败时保留已验证 Manifest 和同一次成功归档供安全重试，但输入快照、首个光盘编号或审核数据变化后不得复用旧 Manifest。

### Attachment plans

```text
Attachment1Plan {
  pages: [{ pageIndex, pageKind: "archive_rows" | "inspector_final",
            showLabel, showHeader, rows[], sourceBox, extractionBox,
            signatureBlankRowCount, keepTogether }]
}
PhotoPagePlan {
  pages: [{ pageIndex, layout: "two-centered" | "grid-2x2",
            materialGroups: MaterialPhotoGroup[],
            inspectionResultMaterialNumbers[] }]
  pageMaster: { source: "current-template-v1:first-attachment2-page",
                titleAnchorReserved: true, fit: "contain",
                consistentAcrossPages: true }
}
MaterialPhotoGroup {
  materialId, materialNumber, displayText,
  images: [orderedImage1, orderedImage2], sourceOrder
}
Attachment3Plan {
  pages: [{ page_index, show_label, part_id, filename, size_bytes, md5,
            disc_number, disc_date }]
}
```

附件规划器只接收 final manifest、canonical case、光盘序列和审核后的显式 photo group manifest，不接收原始报告目录。附件一按 manifest 切成每页最多四行，第一页拥有表头和 label；来源/提取方式按数据页生成。`signatureBlankRowCount` 由规划器明确写入：总分卷数为1时最后页为2，总分卷数为2时最后页为1，总分卷数至少3时所有页面为0；数据页恰好四行时追加一个不含分卷行的 `inspector_final` 页面且其值为0。因此 1、2、3、4、5、6、8、9 个分卷的数据页分别为 `[1]`、`[2]`、`[3]`、`[4]`、`[4,1]`、`[4,2]`、`[4,4]`、`[4,4,1]`，其中满四行数据页后的签字页单独计入附件一页数。固定手写行不写入动态检查人员，正文检查人员仍由有序 `InspectorSnapshot[]` 动态生成。正式检查结果由同一个 manifest-driven `AttachmentPlan` 提供有序检材编号和全部 part 的文件名、MD5、实际大小及光盘编号；Renderer 不得使用报告中的单个旧分卷字段覆盖 manifest。附件二零张不生成附件二页面；有图片时先按 `MaterialPhotoGroup` 保持检材顺序，再按每页最多两组分页：一组为两张图片左右居中，两组为两行两列且每组图片左右相邻，说明文字使用独立行框；双检材页将两个完整检材组放入页面剩余区域的上、下等高区域并分别居中，组间使用独立固定间隔，不依赖连续行高碰巧形成对称；单组续页通过当前模板分页锚点的显式 after spacing 将图片组垂直居中，不依赖 Word 自动挤压或随机空段落；多页时只有第一页显示“附件2”且后续页面版式一致；附件三每个 part 一页且只首张显示“附件3”，附件二缺失不触发编号重排。

### `DocumentRenderPlan` and `TemplateProfile`

本节定义未来统一渲染合同。当前生产 renderer 的实际输入仍为 `InspectionReport` 兼容数据 + 最终 `ArchiveManifest` + `AttachmentPlan` + `current-template-v1` TemplateProfile；尚无生产 `DocumentRenderPlan` 构造与消费，不得把下列结构定义视为已启用能力。

```text
DocumentRenderPlan {
  planId, templateId: "current-template-v1", templateVersion
  scalarFields: [{ fieldPath, value, formatRule, visibility }]
  blocks: [{ blockId, source, repeat, condition, keepTogether }]
  tables: [{ anchorId, rows, mergedCells, headerPolicy }]
  imageAreas: [{ anchorId, photoPage, box, fit }]
  pageBreaks: [{ beforeAnchor, kind: "ordinary" }]
  attachments: { attachment1, photoPages, attachment3 }
  archiveManifestId, generatedAt
}

TemplateProfile {
  templateId, version, assetPath, fingerprintAlgorithm, packageFingerprint, recordType
  rawAssetSha256Diagnostic?
  anchors: [{ anchorId, kind: "paragraph" | "table" | "cell" | "contentControl" | "vmlTextbox",
              selector, fingerprint, allowedFields[] }]
  inspectorBindings: { unit, name, police_number, displayRule? }
  repeatBlocks[], imageAreas[], pageRules[], colorPolicy, rendererVersion
}
```

`selector` 不应只依赖表格序号；至少组合 OOXML part、结构指纹、邻近文本和稳定的 content control/shape 标识，并保存 fallback selector。VML 文本框记录所在 part、shape/textbox 结构和占位符路径。`current-template-v1` 的 Profile 指向现有模板资产，使用版本化 OOXML 包指纹而不是 ZIP 原始字节哈希。

### DOCX 包指纹与输出副本卫生

`current-template-v1` 使用 `ooxml-package-sha256-v1`。算法先安全读取有效 DOCX ZIP，拒绝加密、重复或大小写折叠冲突条目、绝对路径、反斜杠路径和 `..` 路径；然后按完整条目名称排序，将条目名称长度、名称、解压内容长度和解压后的原始内容与固定域标记一起计算 SHA-256。它忽略 ZIP 压缩参数、条目顺序和容器时间戳，但不忽略任何实际包部件，也不做 XML 语义归一化。原始 DOCX SHA-256 仅用于诊断，不参与 Profile 匹配。

HEAD 模板与工作区中仅发生无语义 ZIP 重打包的模板具有相同包指纹；甲方认可参考文件作为视觉基准但因实际 OOXML 部件不同而不匹配 `current-template-v1`。本轮不修改正式模板源文件，不需要提交该无语义二进制差异。

Renderer 先写入临时输出副本，再原子替换正式输出。输出副本完整删除评论部件、评论标记、评论关系和对应内容类型覆盖，删除未使用的自定义属性及关系，删除不依赖的 `docVars`，并将核心属性净化为通用系统名、空标题和重置 revision；不产生修订。模板中用于固定手写行布局的通用隐藏文字（一个“份”和四个空格）保留，不含业务数据；源模板中的孤立评论引用只在输出副本清理，不改动正文、VML、表格或模板资产。

## Key Decisions

### 1. 领域规则放在业务规划层

手机/平板的“显示哪些标识”不是解析事实，也不是模板偶然布局。解析层保存候选和来源；规范化层确定 `Material.kind`；业务层输出 `DisplayMaterial`、`Attachment*Plan` 和工具列表；渲染层只消费已决定的值。这样换模板不会改变法律/业务口径，换 JSON 结构也不会把业务规则复制到多个 parser。

备选方案：在 parser 直接删除序列号/IMEI。拒绝原因：同一解析结果无法服务预览、导出和未来模板，也会把不确定分类静默当成事实；在模板层判断则会在不同模板中重复规则。

### 2. 单向迁移与兼容 DTO 投影

主迁移路径固定为：

```text
ReportAdapter → CanonicalInspectionCase → InspectionReport → 现有前端和导出
```

新增两个方向职责不同的适配器：

- `canonical_to_inspection_report(case, renderContext)`：主路径的兼容投影，为现有预览/编辑页面生成 `InspectionReport`；不能表达的 archive parts/plan 通过扩展响应或服务端 manifest 保存。
- `inspection_report_to_canonical(dto, context)`：仅处理旧前端提交和历史数据迁移，返回 best-effort canonical case + issues，不承诺完整回填。
- 现有 `ParseReportResponse` 先保持 `report`, `parsed_files`, `rar_info` 字段；可选增加 `case_id`, `archive_manifest_id`, `warnings`，前端旧代码忽略未知字段。

反向兼容输入可能缺少或无法恢复：字段来源和 JSON 路径、通用 `Identifier` 类型及其置信信息、有序 `InspectorSnapshot[]`、实际 `ArchiveManifest`（文件名/大小/MD5/连续性/光盘绑定）、`TemplateProfile`/模板版本、规划状态和未被 `InspectionReport` 表示的新字段。后端必须在 issues/diagnostics 中标记这些缺失，不能把默认值伪装成原始事实。后端导出入口在旧 DTO 模式下先转换为 canonical；待前端改用 canonical/plan API 并通过验收后，才考虑收紧公共契约。

### 3. 单机人员库采用后端封装的版本化 JSON Repository

阶段一使用操作系统应用数据目录中的 `inspectors.json`、`inspectors.json.bak` 和临时写入文件；目录不得位于仓库根目录，开发 fallback 也必须加入忽略规则，人员库内容不得进入 Git。只有后端 `InspectorRepository` 能访问该文件，Controller 通过服务接口调用，前端只能访问 HTTP DTO。写入前校验 schema、唯一 ID、姓名/单位/警号非空和基础长度/字符规则；写入采用临时文件、flush/fsync、原子 replace 和上一份备份。任何写入失败都保留原文件。报告 JSON/缓存中保存有序 `InspectorSnapshot[]`，不保存人员库路径。上层 `InspectorRepository` 接口保持稳定，未来替换为 SQLite 或服务端存储不改变 Service/Controller/前端契约。

备选方案：直接把人员数组嵌入每份报告。拒绝原因：无法复用和维护人员；只用内存则重启丢失。SQLite 可作为未来多人并发迁移目标，但阶段一没有必要引入数据库和迁移成本。

### 4. 压缩规划、执行、校验和最终清单四段式

`ArchivePlanner` 纯函数只根据源大小和策略生成 `ArchivePlan`；`WinRarExecutor` 只负责 staging 中的命令执行；`ArchiveValidator` 只读取输出并生成实际卷结果；`ArchiveManifestAssembler` 在绑定 `DiscSequence` 后生成最终清单。解析阶段只建立带随机 `archive_context_id` 的后端输入快照，不执行真实压缩；审核完成后由导出动作按 `execute_archive → export_document` 顺序同步执行。执行命令使用精确十进制字节参数（例如 `-v4000000000b`），基础名来自安全化案件名，结果统一到 `case.part1.rar` 格式。WinRAR 不存在或无法调用时阶段一返回 `winrar_unavailable`，允许报告继续上传、解析和编辑，但禁用自动压缩、阻止最终导出且不创建任何 `ArchiveManifest`；不得使用 ZIP 降级。现有旧解析入口的 ZIP/RAR 上传解析能力保持不变，但不被当作自动分卷产物。

公共 `ArchivePlan` 只发布业务决策和脱敏输入条目：计划 ID、案件展示名、安全基础名、相对路径、大小、容量档位、预计卷数、预计光盘编号、状态和安全诊断。输入绝对路径、输出目录、staging 目录、缓存目录、WinRAR 安装路径以及运行时文件映射只存在于后端执行上下文，不能进入 Shared 类型、Controller 响应、前端状态、日志、异常或 Shadow 比较。

每次尝试写到独立 staging 目录。分卷大小采用非对称规则：每个实际分卷必须满足 `0 < actual_size <= volume_size_bytes`，允许合法的向下偏差，不设置人为最小填充比例或固定向下误差；任何超过容量上限的分卷均返回 `ARCHIVE_PARTS_INVALID`。validator 还必须解析数字卷号、校验从 `part1` 开始连续且无重复/缺号、确认实际卷数不超过当前档位上限，并对第一卷执行 WinRAR `t` 完整性测试；不能仅根据进程退出码或文件大小推断归档完整。卷数超限、跳号、命名不符、卷大小异常、完整性测试失败或 MD5 缺失时，销毁该 staging 结果并在 `maxReplanAttempts = 2` 内执行下一档；实际卷数少于预计卷数但满足连续性、非零、容量和完整性要求时按实际卷数接受。重试仍失败时返回明确错误。最终 manifest 至少保存每卷实际文件名、实际大小、MD5、分卷序号、光盘容量、光盘编号、刻录日期和连续性校验结果；附件一和附件三只能消费该 manifest，不能消费 plan 或自行重新计算。

### 5. 先页面计划、后模板渲染

附件分页是可测试的业务布局，不应由 Word 自动分页“碰巧得到”。规划阶段输出 page index、显示条件、合并框、图片 fit、keepTogether 和普通分页点；renderer 将其应用到模板 Profile。这样可以在没有 Word GUI 的情况下验证卷数、图片 0/偶数/奇数规则、标题显示次数和跨页边界，再做 OOXML/人工视觉验收。无图片时不生成附件二页面，附件三仍从自身计划显示“附件3”，不重排编号。

#### 当前模板的附件分页与固定手写区域

`Attachment1PagePlan` 规划 `archive_rows` 和必要的 `inspector_final`。附件一固定手写行复制甲方认可模板的原始文字、单元格、合并、边框、字体、字号和留白，不写入 `InspectorSnapshot[]`。`signatureBlankRowCount` 由规划器决定，Renderer 只按该值复制模板空白行：总分卷数至少3时始终为0；若总分卷数为1或2，最后数据页分别为2或1。若最后一个数据页恰好四条，则追加独立且无空白行的 `inspector_final` 页面。正文“（八）检查人员”仍由有序快照动态生成。

章节起页唯一由 `AttachmentPlan → Renderer` 负责：摘要、附件一、存在图片时的附件二、附件三各自从新页开始；无图片时跳过附件二且附件三仍命名为“附件3”。每个边界只保留一个明确分页动作，不叠加模板残留分页符、`pageBreakBefore`、空段落撑页或重复分页。附件一续页不重复“附件1”和“电子数据提取固定清单”，附件三续页不重复标题。

附件三每个 manifest part 对应一页，五项元数据沿用当前模板 VML 文本框的上下行样式，顺序为文件名、检验单位、光盘编号、文件哈希、刻录时间；每页末尾复制甲方模板的光盘说明锚点并替换为该页 `disc_number`。文件名、MD5、光盘编号和刻录日期均来自后端重新验证的 `ArchiveManifest.part`，不使用客户端或预计值。附件摘要第三项同样使用 manifest 首尾光盘编号、实际 part 数和附件三计划页数。

页脚使用 `PAGE` 和 `NUMPAGES` 正式字段，并在输出副本的 `settings.xml` 设置 `updateFields=true`；不使用 `SECTIONPAGES` 或模板缓存数字。所有节的页码连续性仍需由 Word GUI 最终确认。VML 宿主段落、`v:textbox`、`w:txbxContent`、关系和唯一 shape ID 必须保留。

### 6. `current-template-v1` 是阶段一唯一固定 Profile

阶段一只登记并使用固定的 `current-template-v1` 和固定 TemplateProfile；只允许当前 DOCX Renderer 的受控扩展。通用模板设计器、通用重复块 DSL、任意 DOCX 自动绑定、可视化模板编辑和无标记模板识别全部是阶段三接口预留，不在阶段一实现或静默启用。阶段一复制/读取现有模板并校验哈希，不修改 `word_templates/template.docx` 或甲方参考 DOCX。模板填充只在 Profile 允许的段落、表格、文本框和图片区内进行；保留 VML 宿主段落、关系、普通分页符和表格边框。

officecli batch 只保留为无 Manifest 的兼容分支；当前 `/records/export` 要求有效 Manifest，带 Manifest 的当前确定性 Renderer 失败时不得回退 officecli。未来 canonical 正式模式的 renderer 出错时同样直接返回明确失败，不能自动静默切回 legacy，也不能悄悄产出与 manifest/plan 不一致的附件。

### 7. 阶段三推荐必须是可解释草稿

模板解析器先建立 DOCX AST 和元素指纹，再按标签相似度、字段别名、表格列语义、邻近标题、段落样式、重复结构和图片区尺寸产生 `Recommendation`。每项保存评分分解和证据，输出 `TemplateProfileDraft`。用户确认/修正后才升为 active Profile；任何修改生成新版本，旧 Profile 可回滚。

### 8. 集中式 pipeline mode 和 Shadow 比较

`pipeline_mode` 由后端应用启动入口 `packages/backend/app/main.py` 统一读取并注入同一个 `PipelineSettings`，默认 `legacy`，可选 `shadow`、`canonical`；配置读取 `BIJI_PIPELINE_MODE`，非法值安全回退到 `legacy`。Repository、Service 和 Renderer 不各自读取环境变量或维护布尔开关。配置读取位置、配置版本和 schemaVersion 已由实现前门禁固定。

- `legacy`：旧管线产生唯一正式输出；不执行新 renderer。
- `shadow`：旧管线产生唯一正式输出；新管线在后台旁路中复用同一解析报告、已验证 Manifest、输入快照和 Legacy AttachmentPlan，生成内存中的 canonical/plan 投影与脱敏比较结果，不生成第二份正式 Word，不替换正式归档，不调用 WinRAR，也不执行真实重复压缩。结果通过带容量和 TTL 的脱敏诊断 Store 及按 `archive_context_id` 查询接口查看；投影不得伪装成最终 manifest。
- `canonical`：新管线产生唯一正式输出；数据正确性错误直接失败，不自动 fallback。人工运维将集中配置改回 `legacy` 才能回滚。

Shadow 比较至少覆盖案件字段、检材类型、IMEI1/IMEI2或序列号、检查时间、主软件、检查人员顺序、ArchiveManifest 和附件一/二/三页面数量。比较器只输出字段名、一致性、脱敏来源和诊断代码，严禁完整案件、人员、IMEI、序列号和原始 JSON 进入日志。

## Migration Plan

当前检查点（2026-07-23）：Legacy 生产稳定化基本完成，包含旧/同厂商新版报告兼容、请求存活性、解析缓存生命周期和受 TTL/容量限制的 `ArchiveContext` metadata 快照；正式归档安全边界未降低。Shadow 生产接线已完成，真实样本差异治理的基础机制已完成但真实样本治理未完成。正式输出仍是 legacy DTO 管线；导出观测点不宣称完整最终渲染输入比较，Legacy DOCX 失败会记录失败诊断。归档最终 Manifest 当前没有解压树清单，因此根目录保留合同明确记为 `not_comparable`，待 14A.6 真实 WinRAR 列表/解压验收补证。Canonical 正式生产切换尚未开始；延期大容量验收不阻塞 Canonical 代码和只读预览、编辑门控、候选输出隔离、回滚演练等预切换开发与验证，但在补测通过或风险接受前不能切换为默认唯一正式输出；`DocumentRenderPlan`、15.1/15.1T 完整人工验收和 OpenSpec 归档仍未完成。

### Stage 0: Contracts and shadow pipeline

1. 在不改变现有端点的前提下新增 SharedTypes、领域服务接口、schemaVersion 和集中 `pipeline_mode` 配置；默认 `legacy`。
2. 按 `ReportAdapter → CanonicalInspectionCase → InspectionReport` 建立兼容投影；旧 DTO 输入/历史迁移只走 best-effort `LegacyReportInputAdapter`，不作为主路径。
3. 为 `current-template-v1` 建立只读 Profile 和模板资产哈希；不替换运行时模板。
4. 为压缩、附件规划和 renderer 增加纯函数测试、合成 fixture 和 XML 检查。

### Stage 1: Required delivery

1. 接入手机/平板显示政策、报告来源主软件、人员库/快照、光盘序列和分卷 manifest。
2. 将附件一/二/三全部从 final manifest/page plans 渲染；保留旧 DTO 输入，officecli batch 仅保留为无 Manifest 兼容分支。
3. 在 `shadow` 模式下由旧管线产生唯一正式输出，新管线只在后台旁路生成内存中的 canonical、plans、非执行性的 manifest 投影和脱敏比较结果；不得调用 WinRAR 或执行真实重复压缩，不产生第二份正式文书。解析、归档/预览和导出三阶段诊断通过受限查询接口统一查看，Shadow 失败不得改变 Legacy 响应。
4. Shadow 比较至少覆盖案件字段、检材类型、IMEI/序列号、检查时间、主软件、人员顺序、ArchiveManifest 和附件页数；人工确认正文、VML、分页、颜色、图片和附件。
5. 正式切换前允许继续开发和验证 Canonical 只读预览、编辑门控、候选输出隔离与回滚演练；只有延期资源型验收补测通过或发布负责人明确接受风险后，才可把集中配置切换为 `canonical`，使其成为默认唯一正式输出；保留将同一配置改回 `legacy` 的人工回滚路径。

### Stage 2: Arbitrary report, current template

1. 增加结构发现 API、候选确认 UI、ReportProfile Repository 和 provenance 审计。
2. 仅对已确认 Profile 自动适配同类报告；未知/低置信字段仍需确认。
3. 将 canonical DTO/问题列表逐步暴露给前端，旧 `InspectionReport` 继续作为兼容投影。

### Stage 3: Arbitrary report, arbitrary template

1. 增加 DOCX AST、可视化元素选择、TemplateProfile 草稿和绑定编辑器。
2. 增加重复区、图片区、显示条件、分页和 keepTogether 的可视化配置。
3. 无标记模板只生成推荐草稿；用户确认后运行 renderer，支持版本化比较、撤销和回滚。

### Rollback

- 通过集中 `pipeline_mode=legacy|shadow|canonical` 回退；默认初始值为 `legacy`，配置从后端应用统一运行时设置读取，不能由各 parser/service/renderer 分别覆盖。
- 原始解析缓存按 source fingerprint、adapter/schema/profile 版本复用；shadow/canonical 的 plan、manifest、render 和正式输出缓存按 pipeline mode、plan、template 版本隔离或失效。Shadow 结果永远不能作为正式 Word 缓存。
- canonical 发生数据正确性错误时直接失败，不自动切回 legacy；人工运维修改集中配置后重新处理，避免自动回退掩盖错误。
- 归档采用 staging + manifest 原子提交，任何规划/校验失败都不替换已有产物。
- 模板 Profile 以 ID/版本和 sha256 选择；新 Profile 失败可切回 `current-template-v1`，未知资产不自动接管。
- 解析缓存携带 canonical/adapter/profile/schema 版本，版本不匹配即重建，不复用旧语义缓存。

## Risks / Trade-offs

- [风险] 现有 `template_filler_service.py` 超过文件上限且承担多种职责。→ [缓解] 按 Repository/Service/Renderer/Plan 拆分，每个新模块 ≤250 行；旧文件仅作为迁移适配层逐步削薄。
- [风险] WinRAR 输出命名、分卷边界和压缩比受版本/参数影响。→ [缓解] staging、精确字节参数、真实卷验证、升级重试和合成大文件测试；不以源字节数冒充最终卷大小。
- [风险] VML/页眉/普通分页的 OOXML 被 python-docx 改写。→ [缓解] 资产哈希、ZIP/XML 回归、保留宿主段落、固定 renderer 版本和 Word 人工验收。
- [风险] “手机/平板”分类在部分报告中不明确。→ [缓解] provenance + confidence；低置信时阻止导出并要求确认，不在模板层猜测。
- [风险] 人员 JSON 损坏或多进程写入。→ [缓解] schema 校验、原子写、备份恢复和单机写锁；报告使用快照。
- [风险] 新旧模型在 Shadow 比较中产生不一致。→ [缓解] canonical 作为新管线事实来源，兼容 DTO 只作为投影/旧输入；集中 Shadow 比较器只记录脱敏诊断，canonical 正式错误不自动 fallback。
- [风险] Shadow 日志泄漏案件、人员或设备标识。→ [缓解] 比较器只允许字段名、一致性、脱敏来源和诊断代码，测试扫描日志中不得出现完整敏感值。
- [风险] 自动模板推荐误绑字段。→ [缓解] 推荐必须可解释、人工确认、版本化和可回滚，未知绑定默认禁用。
- [取舍] 阶段一暂不接受所有任意 JSON/DOCX，牺牲即时通用性换取当前模板和法律文书版式的可验证性。

### 人工 Word 验收证据记录（2026-07-19）

- 正式模板源文件存在既有孤立 comment 引用；本轮不修改模板正文资产，Renderer 只在输出副本中清理无效 comment 引用。该清理不应影响正文、VML、表格或其他有效内容，必须由 Microsoft Word GUI 验收确认清理后无修复提示。
- 同一次 Manifest 校验中每个实际 part 只计算一次 MD5：首次 DOCX 导出前验证文件存在性、大小和完整 MD5，并将已得到的 MD5 传给后续结构校验，避免同一请求重复读取同一 part。Word 生成失败后的重试可能再次验证大文件；最大 135GB 时重新读取全部分卷可能产生明显成本。
- 当前正确性优先，不建设复杂持久化哈希缓存。未来如引入受控复用，必须基于安全文件身份、大小、mtime 和已验证 Manifest 设计，并保留实际变化检测；不得为了性能跳过变化检测。

## Resolved Business Decisions

- `0` 张图片允许导出且不生成附件二图片页；正偶数正常生成，奇数阻止导出；附件二缺失不重排附件三编号。
- 检材阶段一只允许 `phone`/`tablet`；可靠类型可预选，无法可靠判断时在审核页确认，不得仅根据 IMEI 推断。
- WinRAR 未安装或不可调用时允许上传、解析和编辑，但禁止自动压缩和最终正式导出，不生成 `ArchiveManifest`，不降级 ZIP。
- 主取证软件正常由报告适配器识别；无法可靠识别时可在审核页填写/修正名称和版本，确认前禁止最终正式导出。

### Stage-one implementation clarifications

- 检材自动候选只读取报告明确的 `device_type` 语义字段，不搜索报告全文，也不读取案件名称、单位、文件名、目录名、设备型号、IMEI 或序列号作为分类依据。字段值先去除首尾空白并做必要的全半角/英文大小写归一化，再匹配固定词表：`手机`、`智能手机`、`phone`、`smartphone`、`iPhone` 映射 `phone`；`平板`、`平板电脑`、`tablet`、`iPad` 映射 `tablet`。同一字段同时命中两类或没有命中时保持 `unconfirmed`。自动候选的来源和诊断必须保留，状态与人工确认严格区分为 `confirmed_by_report`、`confirmed_by_user`、`unconfirmed`。
- `MaterialDisplayPolicy` 是业务规划层的唯一标识显示决策：`phone` 只返回合法 `imei1`/`imei2`，`tablet` 只返回合法 `serial_number`，`unconfirmed` 不返回推测标识；Canonical/解析层始终完整保留原始 identifiers，Renderer 不重新判断。
- 单机人员库正式使用 `BIJI_APP_DATA_DIR` 覆盖目录；未设置时 Windows 使用 `%LOCALAPPDATA%\\文枢\\data`，默认目录由后端创建，正式文件为 `inspectors.json`，最近有效备份为 `inspectors.json.bak`。写入采用同目录临时文件、flush/fsync、原子替换和进程内锁；测试必须显式传入临时目录，日志和错误不得暴露完整用户主目录。
- `InspectionReport.introduction.inspector_snapshots` 是新增可选的唯一权威快照字段。新审核页只编辑该数组，保存时按其顺序派生 legacy `introduction.inspectors` 投影，字段映射为 `police_number` → `badge_number`。读取旧 DTO 时，若没有快照但有 `inspectors`，按原顺序 best-effort 转换，不伪造人员库 ID、确认来源或当前人员库关系；两者冲突时快照优先并重建兼容投影。人员库变化不反向修改既有快照。
- 当前检查人员库数据持久化到本地应用数据目录。报告中的 `InspectorSnapshot[]` 在当前审核会话和最终导出请求中保持有序；当前系统尚无独立报告草稿持久化接口，因此刷新页面或重新进入页面后，未正式保存的整个报告编辑状态不会自动恢复。该限制不属于人员库缺陷，也不作为 Task 3.1 → 4.2 的验收项；可登记为后续“本地报告草稿/任务持久化”候选任务，本轮不实现。

## Remaining Implementation Questions

1. 附件一“来源”和“提取方法”合并框的文字是否按每页第一卷、每页相同值，还是需要按卷/页分别编辑？

## Expected File Changes During Implementation

本次只创建当前变更包文档。后续实现预计新增/调整以下类别，路径是迁移计划而非本次已修改文件：

- `packages/shared/types/`：canonical、plans、profiles、API DTO 类型。
- `packages/shared/constants/` 与 `packages/shared/utils/`：档位、编号、图片和显示规则纯函数。
- `packages/backend/app/repository/`：report adapters、inspector library、archive executor/validator、profile/template asset repository。
- `packages/backend/app/services/`：canonicalizer、domain planners、render planner、profile confirmation orchestration、legacy adapter。
- `packages/backend/app/main.py` 及集中运行时配置：只在应用启动时读取 `pipeline_mode` 和相关版本，不让下层模块自行读取环境变量。
- `packages/backend/app/controllers/` 与 `routes/`：兼容端点扩展及阶段二/三新 API。
- `packages/frontend/src/hooks|components|pages/`：人员选择、光盘号、规划错误、Profile 确认和模板可视化配置。
- `tests/` 与前端同目录测试：模型/规划单元、后端集成、OOXML 回归、E2E 和人工验收记录。
- `word_templates/`：只在实现阶段新增版本登记/资产元数据；当前正式模板本体不在本变更设计阶段修改。
