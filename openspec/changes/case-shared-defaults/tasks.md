# 案件共享默认值持久化

workflow_level: 2
legacy_migration: true
spec_sync_status: reconciled
spec_sync_evidence: openspec/specs/electronic-inspection-record/spec.md REQ-007; openspec/specs/data-model.md SharedDefaults

## 级别与范围

- 级别：Level 2。
- 本变更独立于 `persistent-case-workbench-and-archive-coordination`，只维护本文件；不创建 proposal、spec 或 design。
- 目标是修正并收敛现有共享默认值实现，不扩大字段范围，不改变既有案件，不改变 Legacy Parser、Word/VML、分页、Manifest 或归档合同。
- 当前作用域为部署实例/本地操作者：后端以 `deployment_instance_id` 作为持久化隔离边界；当前没有完整用户账户体系，不宣称已实现多用户隔离。
- 本次不实现文号自动递增、文号拆分、光盘编号自动递增、USN/Canonical/Shadow 缓存或无关重构。

## 当前实现盘点

### 六个字段的实际映射

| 业务字段 | 报告/表单字段 | 当前共享默认值字段 | 约束 |
|---|---|---|---|
| 文号 | `report.document_number` | `document_number` | 记忆完整用户输入，不拆分、不递增 |
| 检查地点 | `report.introduction.inspection_place` | `inspection_place` | 只记忆当前表单字段 |
| 检查方法 | `report.inspection.method` | `inspection_method` | 只记忆当前表单字段 |
| 检查硬件设备 | `report.inspection.hardware_device` | `hardware_device` | 不关联来源设备、被检查对象或附件设备 |
| 检查人员 | `report.introduction.inspectors` / `inspector_snapshots` | `inspector_order` | 保持当前数组和顺序；现有持久化投影为 `name|unit|badge_number` 字符串数组 |
| 光盘编号前缀 | `report.attachments.disc_number` 的既有解析结果中的 `prefix` | `disc_number_prefix` | 只持久化前缀；案件编号、日期、序号/后缀继续走既有逻辑 |

### 已有存储与调用链

- 后端已有 `shared_defaults` SQLite 表：`deployment_instance_id`、`schema_version`、`revision`、`values_json`、迁移状态和更新时间。
- 后端已有 `SharedDefaultsRepository`、`SharedDefaultsService` 及 `/api/v1/workbench/defaults` GET/PUT API；本变更需把该接口收敛为六字段白名单的安全增量更新。
- 草稿保存入口为 `CaseLifecycleService.save_draft`，当前先保存草稿，再尝试保存客户端传入的 `shared_defaults`；默认值失败不得回滚已经成功的草稿。
- 新案件解析初始化入口为 `CaseDraftService.run_parse_task` → `_initialize_draft` → `SharedDefaultsService.get`。当前初始化已处理部分字段，但检查人员未完整应用，光盘前缀不能直接替代完整光盘编号。
- 工作台前端通过 `useCaseRecordSession` 获取后端默认值，通过 `useCaseDraftAutosave` 在草稿保存请求中携带共享值；旧 `useReportDefaults` 仍是 localStorage 兼容辅助，不得成为工作台唯一事实源。
- 固定数据摘要由现有 `DEFAULT_DATA_SUMMARY = `即时通讯、手机信息`` 和既有 Parser/Word 链路负责，不进入共享默认值。

## 补充契约（实施前确认）

### 稀疏 patch 与用户明确修改

- 共享默认值只能由用户在本轮草稿编辑中明确修改共享字段后触发更新；普通草稿自动保存不得把当前案件六字段全量回写。
- 前端提交 `shared_defaults_patch` 稀疏对象：未明确修改的字段不出现；检查人员被修改时提交完整的新数组，未修改时不提交。
- Parser 自动填充值、旧案件已有值、案件切换和只修改图片/案件名称均不得产生共享默认值 patch。
- 后端只合并请求中明确出现且合法的字段；请求中未出现的字段保持旧值。

### 新案件默认值应用时机与优先级

- 共享默认值必须在实际创建新案件/新草稿时由后端应用；若当前架构由 `_initialize_draft` 完成初始化，则解析前必须能通过后端读取并显示共享默认值。
- 最终业务优先级为：当前案件用户手工修改 > Parser 非空解析值 > 非空共享默认值 > 系统默认值或空值。
- Parser 的非空真实值优先用于当前新案件；仅当对应字段为空、纯空格、缺失或空数组时，才使用非空共享默认值补齐。Parser 值不得自动更新共享默认值。
- 已存在案件重新解析不得因为共享默认值改变既有草稿。

### 草稿与默认值的部分成功

- 草稿保存是主要操作，默认值 patch 是附属操作；草稿成功而默认值失败时仍返回草稿成功。
- `shared_defaults_save_status` 使用稳定状态：`updated`、`unchanged`、`failed`、`revision_conflict`；失败附带稳定错误码，不暴露路径、SQL、PID 或内部异常。
- 默认值失败不得触发整体草稿重复保存、重复 revision 或自动保存循环；后续用户再次修改/保存相关共享字段时可以重试。

### 部署实例与 API 拒绝语义

- `deployment_instance_id` 由服务端稳定配置/部署标识决定，不在后端启动时随机生成；浏览器和客户端不得指定、切换或伪造隔离边界。
- GET、PUT 和草稿保存均由服务端解析当前部署实例；公共 DTO 不提供可让客户端伪造部署实例的写入口。
- 未知字段统一拒绝，返回稳定白名单错误码，不发生部分写入；生命周期、路径、PID、revision、Manifest、RAR 和内部字段均按未知/禁止字段处理。
- 现有 PUT 继续保留时，语义明确为六字段白名单的稀疏增量合并，而不是完整替换；空值和纯空格表示“不更新”，不表示清空。

### 光盘前缀与并发

- `disc_number_prefix` 只能作为既有光盘编号解析/组合链路的前缀组件，禁止执行 `disc_number = disc_number_prefix`。
- 案件日期、案件独有编号、序号、位宽和后缀继续走既有逻辑；不复制上一案件完整编号，不新增自动递增；Word 使用当前案件最终完整光盘编号。
- “最后一次成功保存”必须同时满足草稿 revision 校验成功、草稿事务提交和随后服务端接受稀疏共享默认值 patch。
- 草稿 revision 冲突请求不得更新共享默认值；同案件旧请求晚到必须因冲突失败。不同案件并发时，以服务端成功提交共享默认值事务的先后顺序决定最终值。

## 验收标准

- [x] 第一个案件修改六个字段并成功保存后，第二个由后端创建的新案件使用最新非空合法共享默认值预填（含 Parser 系统默认值让位于共享默认值）。
- [x] 第二个案件成功保存新值后，第三个新案件使用第二个案件的最新成功保存值。
- [x] 共享默认值更新只影响以后创建的新案件，既有案件的草稿、revision、来源、图片和状态保持不变。
- [x] 空字符串、纯空格、校验失败和草稿保存失败均不得覆盖已有共享默认值。
- [x] 解析过程中的临时值、尚未成功保存的输入和前端失败重试状态不得更新共享默认值。
- [x] 草稿保存成功而共享默认值更新失败时，草稿保持成功；接口返回稳定的默认值失败诊断，下一次成功保存可再次尝试。
- [x] 旧案件只修改图片或案件名称时，不覆盖已有共享默认值；案件切换不会静默提交六字段。
- [x] 自动保存重试不扩大默认值 patch；Parser 自动填充值未经用户明确修改不更新共享默认值。
- [x] 新建空白案件/初始草稿时即可获得共享默认值；Parser 缺失地点保留共享值，Parser 非空地点只覆盖当前案件；重新解析既有案件不被共享值改写。
- [x] 草稿成功而默认值失败时，后端返回稳定的草稿与共享默认值分别保存结果，不触发整体草稿重复保存；审核编辑界面不展示保存状态（展示移除变更包已去除界面显示）。
- [x] 服务端重启或 repository 重建后仍读取同一部署实例的默认值；客户端不能伪造 `deployment_instance_id`。
- [x] 未知字段请求整体拒绝且不发生部分写入；合法六字段采用稀疏增量合并，空值不清空旧值。
- [x] 光盘前缀不会直接成为完整编号；不会继承上一案件日期/案件号/序号/后缀，不同案件不会因同一前缀生成重复完整编号，Word 使用当前案件完整编号。
- [x] 只修改一个共享字段时，其他五个默认值保持不变。
- [x] 并发保存以最后一次成功保存的有效值为准；revision 冲突不会覆盖较新的共享默认值。
- [x] 后端重启、浏览器刷新和关闭重开浏览器后仍能读取同一部署实例的共享默认值。
- [x] API 只接受六个白名单字段；未知字段、案件生命周期、路径、PID、revision、内部状态、Manifest、RAR 和运行时字段统一拒绝且不部分写入。
- [x] 文号保存完整输入值，不自动递增、不拆分年份/单位/编号；新案件只预填最近一次成功保存值。
- [x] 光盘默认值只保存前缀；新案件不会复制其他案件完整编号、序号或后缀，不新增自动递增逻辑，并继续使用既有光盘解析/生成逻辑。
- [x] 检查人员保持现有数组或字符串格式、顺序和 Word/DTO 分隔规则，不改变公共填充格式。
- [x] 检查硬件设备只来自表单字段，不记忆来源设备、被检查对象或附件设备信息。
- [x] 除六字段外，案件名称、被检查对象、时间、来源目录、图片附件、数据摘要、案件/草稿/来源/归档状态、RAR、Manifest、路径、PID 和进程字段均不会进入共享默认值。
- [x] 数据摘要仍使用现有固定业务默认值 `即时通讯、手机信息`，不受共享默认值接口影响。
- [x] Legacy Parser、Word 预览、Word 导出、VML、分页、Manifest 和归档合同回归通过。

## 任务列表

### 只读盘点与契约收敛

- [x] 将本盘点中的六字段映射、部署实例/本地操作者作用域和“不记忆字段”固化为实现依据；确认工作台不以 localStorage 作为事实源。
- [x] 审计共享默认值 GET/PUT、草稿 PATCH、后端创建新案件和现有前端 session 的完整调用链；确保所有写入均经过六字段白名单和服务端校验。
- [x] 明确共享默认值 API 的增量更新语义：仅接受非空合法值，空值/空白不覆盖旧值；未知字段不写入；保持 revision 冲突保护和稳定错误码。

### 后端持久化与新案件初始化

- [x] 在现有 `shared_defaults` 表及必要迁移中保持部署实例作用域和后端事实源；如字段结构无需升级，不新增无关 schema。
- [x] 调整 `SharedDefaultsRepository/Service`，使合法非空值按白名单增量合并，保存失败不改变旧值；审计只记录稳定元数据，不记录路径、PID、完整报告或运行时数据。
- [x] 将后端 API 与草稿 PATCH 的默认值载荷统一为 `shared_defaults_patch` 稀疏对象；未知键整体拒绝，空值只产生 `unchanged`，不触发清空；服务端以当前配置校验 deployment instance 身份。
- [x] 将六字段应用接入 `CaseDraftService._initialize_draft` 的后端新案件初始化链。此项历史实现当时采用“共享默认值优先于 Parser”的合同；该合同已被下方“最终优先级合同修正”取代，不作为当前行为依据。
- [x] 检查人员按既有数组/字符串模型持久化并按原顺序恢复；不改变 `InspectionReport` 公共 DTO 或 Word 投影。
- [x] 光盘编号只从既有完整编号解析前缀并预填前缀语义；完整编号的日期、案件独有序号/后缀继续由当前逻辑生成或由用户填写，不新增递增规则。
- [x] 保持固定数据摘要和现有 Parser/Word/归档链路独立，不把 `data_summary` 或任何非白名单字段送入共享默认值。

### 草稿保存与前端调用

- [x] 将草稿成功保存作为共享默认值更新前提；草稿失败、冲突或未完成时不得写默认值；默认值失败不回滚已成功草稿。
- [x] 让后端草稿保存响应稳定表达部分成功：草稿 `saved` 时即使默认值为 `failed`/`revision_conflict` 也返回草稿结果，不抛出整体失败；默认值 patch 只来自用户修改字段。
- [x] 保持下一次成功保存可以重试默认值更新，并以最后一次成功保存的有效字段值为准；前端不得按键级别直接写默认值。
- [x] 工作台刷新、关闭重开浏览器和后端重启均从后端读取默认值；旧 localStorage helper 只能保留兼容测试用途，不参与工作台事实判断。
- [x] 调整默认值状态反馈和重试行为，区分草稿保存成功、共享默认值未改变、失败和 revision conflict；不提供会违反“空值不覆盖”的清空动作。

### 回归测试与门控

- [x] 后端测试覆盖：六字段首次保存/新案预填、第二案更新/第三案预填、既有案件不变、空白/非法/草稿失败不覆盖、默认值失败不影响草稿、重启持久化、后端直接创建、API 白名单和并发 revision。
- [x] 后端测试覆盖：旧案件只改非共享字段、Parser 自动值/空值、创建前可读默认值、既有案件重新解析不变、草稿成功/默认值失败部分成功、伪造 deployment ID、未知字段整体拒绝、单字段 patch 保留其他五字段。
- [x] 后端测试覆盖：文号不递增/不拆分、光盘只继承前缀、完整编号不重复、检查人员数组/顺序保持、硬件字段不串源、固定数据摘要不被记忆。
- [x] 前端测试覆盖：刷新/重开恢复、草稿保存后才触发默认值状态、默认值失败重试、案件切换不串案、六字段映射不扩大、localStorage 不是事实源。
- [x] 前端测试覆盖：明确修改字段集合生成稀疏 patch、旧案件非共享编辑不提交 patch、切换案件不回写、自动保存重试不扩大 patch、部分成功 UI 和 localStorage 冲突不能覆盖后端事实。
- [x] 运行相关后端/前端定向测试、typecheck、架构检查、必要构建、严格文档检查、资产检查和 `git diff --check`；不修改 `word_templates/template.docx`，不产生运行资产。
- [x] 完成人工验收：创建两个以上案件，分别修改六字段，验证后续新案预填、既有案件不变、刷新/重启恢复、光盘编号不重复、Legacy/Word/VML/分页/归档合同不变。

### 人工验收问题修复

- [x] 来源 `pending` 轮询改为后台详情刷新，不重复进入整页加载态；仅在案件或服务端草稿 revision 变化且本地没有未保存修改时重建编辑器。
- [x] 新案件初始化曾按当时合同改为非空共享默认值优先于 Parser 值；此处保留为历史验收问题修复记录，当前有效合同已由下方最终修正替代。
- [x] 补充来源 pending 编辑保护、案件切换、默认值优先级、Parser 回退、检查人员和保存循环回归测试。

### 最终优先级合同修正（2026-07-29）

- [x] 记录并统一最终优先级：当前案件用户手工修改 > Parser 非空解析值 > 非空共享默认值 > 系统默认值或空值；共享默认值只补齐新案件中的空白、缺失和空数组。
- [x] 增加旧实现下失败的测试，覆盖 Parser 非空优先、Parser 空值回退、六字段外不受影响、人员结构/顺序和光盘完整编号不被其他案件前缀改写。
- [x] 最小修正后端新案件初始化，不改变稀疏共享 patch、草稿成功前提、revision 冲突、已有案件、Legacy Parser、Word、Manifest 或归档合同。
- [x] 复用现有前后端测试证明：用户修改刷新后保留、Parser 不自动写默认值、已有案件不回写、空值不清除和保存失败/冲突不更新默认值。
- [x] 运行相关定向测试、typecheck、架构检查、严格文档检查、资产检查和 `git diff --check`；不执行 `1D-017R`、最终人工验收、Review 或归档。

验证记录：新增测试在旧实现下得到 `2 failed, 5 passed`，分别捕获标量字段和检查人员被共享默认值覆盖；修正后共享默认值定向测试包含在工作台组中并通过。2026-07-29 最终验证共运行后端定向回归 `238 passed, 3 warnings`：共享默认值/工作台保存恢复 `41 passed, 1 warning`，Legacy Parser/Word/VML/分页 `91 passed`，Manifest/附件投影/显式归档 `106 passed, 2 warnings`；前端优先级、稀疏 patch、刷新保护和自动保存回归 `16 passed`。typecheck、`lint:arch`、前端生产构建、`verify:docs:strict`、`check:repository-assets` 和 `git diff --check` 均通过。构建仅保留既有 chunk 大于 500 kB 警告，后端仅保留既有 `ARCHIVE_CONFIGURED_ROOT_INVALID` warning。未运行前后端全量测试或完整 Harness，未执行本次正式人工验收、最终 Review 或归档。

### 统一保存当前草稿与共享默认值

- [x] 记录本次人工验收未通过：手动保存可与自动保存并发使用同一旧 draft revision；默认值独立重试入口可绕开当前案件草稿保存。
- [x] 合并同一变更的进行中自动保存与“保存修改”请求，确保只提交一次 draft revision，并以同一稀疏 patch 更新共享默认值。
- [x] 移除案件编辑页面“只保存/只重试共享默认值”的调用入口；共享字段只能随当前草稿成功保存后更新。
- [x] 草稿成功、默认值失败时保留草稿成功状态和可重试字段，不触发草稿自动重试；默认值 revision conflict 返回服务端当前 revision。
- [x] 补充统一保存、部分成功、空值、revision conflict、检查人员、光盘前缀、案件切换与刷新回归测试。
- [x] 运行定向与前后端全量测试、TypeScript、`lint:arch`、生产构建、严格文档、资产和 diff 门控；后端全量由用户独立运行并报告通过。
- [x] 重新完成人工验收：当前案件与后续新案均得到预期值，其他既有案件不变，页面不存在独立默认值保存入口。
- [x] 在人工验收通过后由用户独立运行新的完整 Harness，并报告门控通过。

### 最新验证记录

- 后端全量测试：用户独立运行并报告通过；本轮未提供测试数量和 warning 明细，不在文档中推测。
- 完整 Harness：用户独立运行并报告通过；本轮未提供退出码和分项统计，不在文档中推测。
- 人工验收：用户确认统一保存、共享默认值和相关 Demo 主路径通过。

### Parser 系统默认值优先级契约修正（2026-08-07）

- [x] 记录本次集成人工验收未通过：在旧案件更新文号并成功保存后，新创建案件仍显示 Parser 硬编码文号 `SYN-TEST〔2026〕000号`，未使用共享默认值预填。
- [x] 根因定位：`report_parser_service.py` 对文号、检查地点、检查方法、检查硬件设备 4 个共享字段硬编码系统默认值，按既有 `_select_value` 逻辑被当作“Parser 非空解析值”排在共享默认值之前，导致共享默认值永远无法预填新案件。
- [x] 修复：将 4 个系统默认值收敛为 `report_defaults_service.py` 常量（`DEFAULT_DOCUMENT_NUMBER`、`DEFAULT_INSPECTION_PLACE`、`DEFAULT_INSPECTION_METHOD`、`DEFAULT_HARDWARE_DEVICE`），Parser 复用常量；`case_draft_service._initialize_draft`/`_select_value` 在 Parser 值等于系统默认常量时视为系统默认值（最低优先级），非空共享默认值预填优先，Parser 提取的真实非空值仍保持 report 来源优先；无共享默认值时保留 Parser 系统默认值。
- [x] 补充回归测试：Parser 值为系统默认值且共享默认值存在 → 共享默认值预填且 `source=system_default`；Parser 值为系统默认值且无共享默认值 → 保留系统默认值且 `source=system_default`。
- [x] 验证：`test_case_shared_defaults.py`、`test_workbench_services.py`、`test_report_parser_service.py`、`test_workbench_controller.py` 后端回归 98 passed；前端定向测试、typecheck、`lint:arch`、`npm run verify:quick`、scoped strict docs、`git diff --check` 通过；同步主 spec REQ-007 优先级场景并新增“新案件系统默认值让位于共享默认值”场景。

## 非目标与边界

- 不修改 `word_templates/template.docx`，不改变既有 Word 内容、VML、分页和附件页码合同。
- 不实现文号生成、流水号递增、年份/单位/编号拆分或新的光盘编号自动递增。
- 不扩大共享默认值字段范围，不记忆案件、来源、图片、附件、摘要、状态、revision、归档、Manifest、RAR、路径、PID 或进程信息。
- 不实现多用户账户隔离；当前仅按部署实例/本地操作者合同工作。
- 不修改任何已有案件，不归档本变更包或 Phase 1D 变更包，不 commit、不 push。

## 当前状态

历史统一保存修复、后端全量、完整 Harness 和当时人工验收均已通过；2026-07-29 最终业务合同的 Parser/共享默认值优先级修正实现完成、自动验证通过。2026-08-07 集成人工验收发现并修复：Parser 硬编码系统默认值被误当作“Parser 非空解析值”排在共享默认值之前，导致文号等字段无法预填；已按契约纠正为“Parser 真实值 > 共享默认值 > 系统默认值”，后端全量 948 passed，主 spec REQ-007 已同步。2026-08-07 人工验收通过：在旧案件更新文号等共享字段并成功保存后，新建案件按共享默认值预填。历史及本轮结果均不代表 Phase 1D Production Review 或 OpenSpec 归档通过。未 commit、未 push、未归档。
