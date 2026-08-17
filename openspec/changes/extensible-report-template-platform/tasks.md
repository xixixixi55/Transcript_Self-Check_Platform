
# Implementation Tasks: extensible-report-template-platform

workflow_level: 3

## 验证执行节奏（本变更约束）

- 开发过程中运行定向测试和必要架构检查；
- 功能收敛后，根据改动范围运行必要的模块验证；
- 代码复审和人工验收完成后，提交前只统一运行一次完整 Harness 门控。若模块验证与完整门控高度重复，可以省略中间的模块级完整验证。

本节只约束验证执行节奏，不改变当前 Shadow 旁路、Legacy 正式链路或 Canonical 未启用的业务范围。

本清单对应根目录 `spec.md` 和 `design.md`，只记录实际实现、自动化证据和人工验收状态；批准的业务合同见 `spec.md`，设计决策、字段语义和兼容策略见 `design.md`。`openspec/specs/` 下的 living spec 只描述当前生产已经具备的能力。代码和测试是实现证据，用于核对文档漂移，但不能简单替代批准后的业务合同。当前 47/56 项已完成。正式生产输出仍由 legacy DTO 管线生成；Shadow 已接入解析、归档/预览和 Legacy DOCX 成功后的导出输入观测，诊断通过受限查询接口统一查看，Canonical 仍未启用，`DocumentRenderPlan` 未生产实现。当前自动化测试使用脱敏合成数据，不能替代真实解析、WinRAR、DOCX 和人工视觉验收；14A.6、15（完整人工 Word 验收）、16（canonical 切换）和 17（阶段二/三接口预留）保持未完成。阶段二/三只保留契约和扩展点，不把通用能力纳入阶段一门槛。

## 路线图和当前状态（2026-07-23）

| 工作流 | 当前状态 | 说明 |
|---|---|---|
| Legacy 生产稳定化 | 基本完成 | 旧版/同厂商新版报告兼容、请求存活性、解析缓存和 `ArchiveContext` metadata 快照已接入；正式归档仍执行完整安全校验。 |
| Shadow 生产接线 | 已完成 | 解析、归档/预览和 Legacy DOCX 成功后的导出输入均有旁路观测；Shadow 不生成第二份正式产物、不调用 WinRAR、不阻塞 Legacy。 |
| Shadow 真实样本差异治理 | 基础机制完成，真实样本治理未完成 | 脱敏比较、受限诊断查询和失败诊断已具备；真实样本矩阵、差异解释和人工收敛仍待完成。 |
| Canonical 预切换开发与验证 | 可继续进行 | 延期验收不阻塞 Canonical 代码、只读预览、编辑门控、候选输出隔离或回滚演练；这些工作完成也不等于正式切换。 |
| Canonical 默认唯一正式生产输出 | 未开始且受发布门槛约束 | Canonical 仍返回 `CANONICAL_NOT_ENABLED`，不产生正式 DOCX；须待延期验收补测通过或发布负责人明确接受风险，且不得以类型、单测或 Shadow 接线代替正式切换。 |
| 最终人工验收与 OpenSpec 归档 | 未完成 | `15.1/15.1T` 不勾选；真实大容量边界、完整人工验收和归档门控仍待完成。回滚演练本身不被延期验收阻塞，但完成回滚演练不解除正式生产切换门槛。 |

上述资源型验收不阻塞日常 Legacy/Shadow 功能开发和维护，不阻塞 Shadow 真实样本差异治理，也不阻塞 Canonical 代码及预切换验证；但它们阻塞 Canonical 成为默认唯一正式生产输出，并阻塞本变更最终验收和 OpenSpec 归档。只有在有足够资源的验收机器上补测通过，或由发布负责人明确记录风险接受后，才可解除该门槛。若未来单独发布 Legacy-only 维护版本，延期项目必须由人类明确记录为接受的发布风险，本清单不将其写成已完成。

## 0. 变更前门禁

- [x] 0.1 读取并记录实现前 Git 状态、现有活跃 OpenSpec、模板/输出资产和测试基础设施；集中定义 `pipeline_mode`、schemaVersion、adapter/template/plan 版本，默认 `legacy`，不得删除或覆盖既有工作区内容。输入：当前仓库状态；输出：实现前门禁记录和配置契约；验收：状态快照、`git diff --check`、配置评审。
- [x] 0.1T 为 0.1 增加门禁测试和配置读取测试，确认默认值、非法 mode 回退到 `legacy`、版本字段齐全且不读取分散的模块级开关；验收：最小配置单测。

## 1. Canonical 模型及兼容适配器（Layer 0/20/21）

- [x] 1.1 在 `packages/shared/types/` 和 `packages/backend/app/services/` 实现 `CanonicalInspectionCase`、`Material`、通用 `Identifier`、`InspectorSnapshot`、`SoftwareTool`、`FieldProvenance`、问题模型及 `ReportAdapter` 接口。输入：现有旧/新解析结果；输出：版本化 canonical case 和来源/置信信息；验收：主路径为 `ReportAdapter → CanonicalInspectionCase → InspectionReport`。
- [x] 1.1T 增加旧/新/混合/不支持报告 fixture、类型 round-trip 和 provenance 测试；验收：旧报告字段优先级不回归，缺失来源/字段明确进入 issue，真实案件不进入 fixture。
- [x] 1.2 实现 `canonical_to_inspection_report` 兼容投影和 `inspection_report_to_canonical` 旧 DTO 输入/历史迁移适配器。输入：canonical case 或旧 `InspectionReport`；输出：现有前端 DTO 或 best-effort canonical + issues；验收：不把反向路径描述为完整转换，明确标记字段来源、通用 identifiers、InspectorSnapshot、ArchiveManifest、TemplateProfile 等不可从旧 DTO 恢复的内容。
- [x] 1.2T 增加兼容投影测试，覆盖现有前端请求字段、未知扩展字段、不可表示字段 diagnostics 和历史迁移失败；验收：现有解析/导出 DTO 编译和接口回归通过。

## 2. Shadow 比较框架（Layer 21/22）

Shadow 工作包的输出只能是隔离的规范化、规划和脱敏比较结果；不得调用 WinRAR、不得执行真实重复压缩，也不得把非执行性的清单投影当作最终 `ArchiveManifest`。

- [x] 2.1 实现集中 `pipeline_mode = legacy | shadow | canonical` 的运行时配置和 Shadow orchestration。输入：旧管线结果、canonical case、plans、已验证 Manifest；输出：旧管线唯一正式输出和内存中的新管线比较输入；验收：legacy 只跑旧管线，shadow 不产生第二份正式 Word，canonical 当前基础层显式保持未启用。
- [x] 2.1T 增加 mode 行为、隔离目录、正式文件数量和缓存命名测试；验收：Shadow 结果不能被当作正式 Word/manifest 缓存。
- [x] 2.2 实现脱敏 `ShadowComparison`，比较案件字段、检材类型、IMEI1/IMEI2或序列号、检查时间、主软件、检查人员顺序、ArchiveManifest 和附件一/二/三页面数量。输入：两侧结构化结果；输出：字段名、一致性、脱敏来源、诊断代码；验收：日志不包含完整案件、人员、IMEI、序列号或原始 JSON。
- [x] 2.2T 为比较器增加字段差异、敏感值扫描和诊断代码测试；验收：每个指定比较维度均有可区分断言。

## 3. 手机/平板业务规则（Layer 2/21）

阶段一最终类型只允许 `phone`/`tablet`；报告明确且可靠时可预选，否则审核页面保持待确认。不得仅根据 IMEI 推断手机；审核保存可继续，但统一导出门控要求每个检材完成确认。

- [x] 3.1 实现 `Material.kind` 分类确认和 `MaterialDisplayPolicy`。自动候选只能读取报告明确的 `device_type` 语义字段，经全半角/大小写归一化后匹配受控词表：`手机`、`智能手机`、`phone`、`smartphone`、`iPhone` → `phone`；`平板`、`平板电脑`、`tablet`、`iPad` → `tablet`。同一字段同时命中两类或未命中时为 `unconfirmed`；分类记录报告来源、诊断和 `confirmed_by_report`/`confirmed_by_user`/`unconfirmed` 状态，不使用 IMEI、序列号、型号、案件名、文件名或全文搜索。输入：ReportAdapter 的原始标识候选、设备类型来源和确认状态；输出：手机只保留 IMEI1/IMEI2、平板只保留序列号的结构化展示数据和 `select_display_identifiers(material)` 结果；验收：规则位于业务规划层，parser 不删除候选，renderer 不重新判断。
- [x] 3.1T 增加手机、平板、大小写/全半角、首尾空白、缺失标识、非法标识、冲突分类、低置信阻止和人工确认状态测试；验收：不出现两组标识混排，错误可解释且 `unconfirmed` 阻止导出，多检材 blocker 指向稳定材料 ID/字段路径。

## 4. 检查人员 Repository 与有序快照（Layer 20/21）

当前模板按快照顺序一人一行；附件一人员整框只在最后一页，人员过多时必须通过增加整框高度或预留末页空间保持整框不可拆。

- [x] 4.1 实现后端 `InspectorRepository` 和服务接口，数据优先使用 `BIJI_APP_DATA_DIR`，否则使用 Windows `%LOCALAPPDATA%\\文枢\\data`，再进入不暴露完整用户主目录的安全回退目录；正式文件为 `inspectors.json`，最近有效备份为 `inspectors.json.bak`。使用唯一 ID、姓名/单位/警号基础校验、临时文件、flush/fsync、原子替换、单进程写锁和备份恢复；输入：后端 CRUD 请求；输出：带 `schema_version` 的版本化人员记录；验收：前端不能直接访问 JSON，仓库目录不进入 Git，写入失败保留原文件，损坏 JSON 不被静默覆盖。
- [x] 4.1T 增加 Repository 单测，覆盖空白/超长/非法字段、唯一 ID、损坏文件、临时文件清理、原子替换失败、备份恢复、UTF-8 中文、配置目录覆盖和并发写入；验收：失败路径不改变原文件，测试只使用临时目录。
- [x] 4.2 实现按报告选择顺序生成 `introduction.inspector_snapshots?: InspectorSnapshot[]`，以快照作为唯一权威数据源，并自动派生现有 `introduction.inspectors` 的 legacy 投影（`police_number → badge_number`）；旧 DTO 仅有 `inspectors` 时按原顺序 best-effort 转为快照，不伪造人员库 ID/确认来源。人员库后续变化不重新读取历史报告；输入：有序人员 ID；输出：有序快照；验收：Word 顺序只由快照顺序决定，未来替换 SQLite/服务端时上层接口不变。
- [x] 4.2T 增加任意人数、重复选择、顺序、人员库修改、历史重导出、快照与兼容投影冲突和前端管理/审核选择测试；验收：快照中 `unit`、`name`、`police_number` 可独立绑定，停用/删除人员不改变已生成快照。

阶段一验收边界说明：当前检查人员库数据持久化到本地应用数据目录。报告中的 `InspectorSnapshot[]` 在当前审核会话和最终导出请求中保持有序；当前系统尚无独立报告草稿持久化接口，因此刷新页面或重新进入页面后，未正式保存的整个报告编辑状态不会自动恢复。该限制不属于人员库缺陷，不作为本轮验收项；可登记为后续“本地报告草稿/任务持久化”候选任务，本轮不实现。

## 5. 主取证软件归一化（Layer 20/21）

主软件无法可靠识别时，审核页面允许分别填写或修正名称和版本；确认前只能编辑和保存中间结果，不能正式导出。不能使用历史固定软件或从普通组件猜测，只有 WinRAR/Python 的工具列表不完整。

- [x] 5.1 将主取证软件名称和版本归一化为报告来源；只生成主取证软件、WinRAR、Python hashlib 三类 `SoftwareTool`。输入：报告软件候选和运行时版本；输出：带 source/provenance 的工具列表；验收：环境检测不能覆盖报告主软件，冲突候选进入确认/阻止。
- [x] 5.1T 增加明确、冲突、缺失和环境版本差异测试；验收：工具白名单和报告权威来源均有断言。

## 6. 光盘编号和日期（Layer 2/21）

- [x] 6.1 实现 `DiscSequence` 解析、日期校验、首编号输入、序号递增和前导零保留。输入：`GPyyyyMMdd-序号`；输出：按最终卷序生成的光盘编号、光盘日期和附件日期；验收：附件摘要/附件三使用光盘日期，正文检查起止时间仍来自报告创建/报告时间。
- [x] 6.1T 增加非法日期、非法格式、位宽、溢出和三卷连续编号测试；验收：非法输入在压缩前阻止处理。

6.1 回归修复证据（2026-08-10）：附件摘要“检查人签名”下方日期不再读取系统当前日期；Legacy 输入复用 `attachments.burning_date`，正式 manifest 导出复用经验证的首张光盘日期，并保持 `YYYY年M月D日` 格式。定向测试覆盖两条生成链路。

## 7. ArchivePlanner（Layer 2/21）

- [x] 7.1 实现纯函数 `ArchivePlanner`，生成只含预计方案的 `ArchivePlan`。输入：案件名、源目录逻辑大小和策略；输出：4GB/22GB/45GB 档位、预计卷数、十进制容量、`maxReplanAttempts=2`；验收：4GB最多2卷、22GB最多2卷、45GB最多3卷，超过135GB预先阻止。
- [x] 7.1T 增加 8GB、8GB+1、44GB、44GB+1、135GB、135GB+1 边界测试；验收：不调用 WinRAR 即可验证档位和上限。

## 8. WinRAR Executor 及最终 ArchiveManifest（Layer 20/21）

WinRAR 缺失或不可调用是明确阻断项：允许上传、解析、审核和编辑，禁止自动压缩和最终正式导出，不生成 `ArchiveManifest`，不降级 ZIP，并返回可操作的安装/调用错误。

- [x] 8.1 实现 `WinRarExecutor`、`ArchiveValidator` 和 `ArchiveManifestAssembler`。输入：ArchivePlan、WinRAR staging 结果和 DiscSequence；输出：最终不可变 `ArchiveManifest`；验收：manifest 至少含实际文件名、实际大小、MD5、分卷序号、光盘容量、光盘编号、刻录日期和连续性校验结果；附件一/三渲染仍由后续任务负责。
- [x] 8.1T 增加 mock/真实小 fixture 测试，覆盖 `-v...b`、`.partN.rar`、跳号、卷数、大小、MD5、连续性和 staging 清理；验收：预计文件名/大小/卷数不能进入最终 Manifest。
- [x] 8.2 实现实际结果不符合计划时的有限重规划：最多两次重试，重试仍失败返回明确错误且不提交归档/Word。输入：执行结果与 ArchivePlan；输出：最终 manifest 或阻止错误；验收：4→22→45 的升级和耗尽路径可回归。
- [x] 8.2T 增加压缩比导致少卷、超卷、无下一档和重试耗尽测试；验收：不会静默降级 ZIP 或自动回退 legacy。
- [x] 8.3 实现归档输入授权与不透明 `archive_context_id` 生命周期：保留 `UPLOAD_BASE`、`BIJI_ALLOWED_INPUT_ROOTS`、精确目录令牌和后续规划/执行/Manifest 只接受上下文标识的既有能力；路径安全和上下文生命周期保持不变。需求6通过 8.4 增加可恢复的授权模式切换，不删除本任务的实现。
- [x] 8.3T 增加固定根目录、前缀相邻目录、大小写、相对/穿越、链接/reparse、UNC/设备路径、输入输出重叠、精确授权令牌、上下文摘要/过期/并发/清理、解析接口稳定错误码测试；验收：公共响应和错误不包含完整本地路径，原始案件不会被清理。

8.3/8.3T 的完成边界：本轮完成固定根目录生产能力、精确目录授权安全模型/令牌验证/拒绝边界及其自动化测试；本机目录选择器和可信桌面桥接由 8.5 单独承接，不改变 8.3 的路径安全合同。

- [x] 8.4 在 `packages/frontend/src/hooks/useSourceAuthorizationPreference.ts`、`packages/frontend/src/pages/CaseWorkbenchPage.tsx`、`packages/frontend/src/hooks/useCaseWorkbench.ts`、`packages/frontend/src/hooks/useCaseRecordSession.ts`、`packages/backend/app/controllers/record_controller.py`、`packages/backend/app/controllers/workbench_controller.py`、`packages/backend/app/controllers/source_controller.py`、`packages/backend/app/services/source_record_service.py`、`packages/backend/app/services/archive_authorization_service.py` 和 `packages/backend/app/repository/archive_authorization_repository.py` 增加可持久化的 `source_authorization_enabled` 模式开关。首页默认关闭授权根校验，用户选择保存在浏览器本地；登记/重新登记请求读取该偏好；关闭时仅跳过根目录/精确令牌边界，路径安全、输出隔离和报告结构校验继续执行，开启时恢复既有授权规则。验证：前后端请求契约、页面刷新持久化、任意本机目录登记和重新开启后的根目录拒绝。
- [x] 8.4T 在 `tests/test_archive_authorization.py`、`tests/test_workbench_services.py`、`tests/test_record_controller.py`、`tests/test_workbench_controller.py`、`packages/frontend/src/hooks/useSourceAuthorizationPreference.test.tsx` 和 `packages/frontend/src/pages/CaseWorkbenchPage.test.tsx` 增加关闭/开启两种模式、持久化和安全边界断言；同时移除来源授权就绪状态说明测试。验证：关闭模式允许合成的根目录外报告目录，开启模式仍返回 `ARCHIVE_INPUT_ROOT_NOT_ALLOWED`，非法/链接/输出重叠路径在两种模式均被拒绝。

8.4 验证证据：后端受影响测试 98 passed、前端受影响测试 22 passed；`lint:arch`、`typecheck` 和核心授权分支突变有效性验证通过。共享请求 DTO 位于 `packages/shared/types/sourceAuthorization.ts`，legacy 目录解析请求构造器位于 `packages/frontend/src/hooks/useSourceAuthorizationRequests.ts`；当前前端生产路由没有直接调用 deprecated `/reports/parse` 的页面，直接 API 缺省仍保持开启。

## 8.5 本地 Windows 文件夹选择桥接（新增需求）

- [x] 8.5.1 **SharedTypes / Constants**：新增“选择报告目录并登记案件”请求/结果契约和工作台端点常量；结果成功时只返回现有 `CaseSubmission` 摘要，取消时返回无副作用的取消标记，不返回绝对路径。验证：shared typecheck。
- [x] 8.5.2 **FE Hook**：在 `useCaseWorkbench` 增加选择目录并提交案件的方法，携带案件名称、案件编号和首页持久化的来源授权偏好；取消选择不创建案件，成功后沿用现有案件列表刷新和任务同步。验证：Hook 测试覆盖成功、取消和错误传播。
- [x] 8.5.3 **FE Component / Page**：新增类似审核编辑检查人员加号卡片的“上传报告目录/添加案件”入口，移除工作台报告路径输入框和独立登记按钮；点击卡片调用后端原生选择桥接，保留可选案件字段和刷新入口，卡片显示加载/错误可恢复状态。验证：组件/页面测试覆盖点击、取消、成功和失败状态，确认不使用 `webkitdirectory` 上传文件。
- [x] 8.5.4 **BE Service**：新增 Windows 本机目录选择服务，通过本机原生文件夹选择窗口取得真实绝对路径；取消返回空选择，窗口不可用/超时返回稳定错误；不硬编码桌面目录、不上传或复制报告内容，路径只传给既有来源登记服务。验证：Service 单测覆盖成功、取消、不可用、非法选择和超时。
- [x] 8.5.5 **BE Controller / Composition**：新增选择目录并登记案件端点，后端在同一请求内选择目录、登记 `SourceRecord`、创建 `CaseShell`/解析任务并 dispatch；公共响应和错误不得包含完整路径，继续使用既有来源授权、路径安全和报告结构校验。验证：Controller 集成测试覆盖根目录外有效目录（授权关闭）、取消无副作用、路径安全错误和解析任务创建。
- [ ] 8.5.6 **真实验收与门控**：使用本地 Windows 应用流程验证卡片点击后弹出原生文件夹窗口，选择任意有效本机报告目录后直接进入排队/解析，取消不创建案件；运行受影响前后端测试、`lint:arch`、typecheck、`verify:quick`、资产检查和 `git diff --check`。 [DEFERRED]

## 9. 附件一页面计划（Layer 21）

附件一固定手写行是甲方模板的最后结束区域，不属于动态检查人员渲染；正文仍保留有序 `InspectorSnapshot[]`。

- [x] 9.1 实现 `Attachment1Plan`，只接收 final ArchiveManifest。输入：manifest、报告来源/工具和模板 Profile；输出：第一页标题、后续页无标题、每页完整来源/提取方法、最后页保留模板固定手写行所需容量。`inspector_final` 是历史内部名称，当前语义为固定手写行最终页（不填充 InspectorSnapshot，不生成动态检查人员框）；建议后续重命名为 `handwritten_final` 或 `signature_final`。验收：行数严格等于 manifest 卷数，不生成 `INSPECTOR_BLOCK_OVERFLOW`。
- [x] 9.1T 增加 1/2/4/5/8/9 卷边界、固定手写行复制、动态人员仅正文、标题/清单文字可见次数和无附件二章节测试；验收：不读取 ArchivePlan 或原始目录。

## 10. 附件二图片页面计划（Layer 21）

0 张图片不生成附件二页面；现有图片 renderer 的回归范围确认有效图片章节独立起页、附件三仍显示“附件3”和关系完整性；本轮扩展为每页最多4张，2张组成同一居中图片组，4张按上两张/下两张上下对齐，超过4张继续分页。偶数门禁表达每个检材需正反两张图片；审核后的检材顺序与图片顺序一一对应，每两张图片绑定一个检材，并在该图片对下方显示对应文字。计划输入必须是显式 `photo_groups`，Renderer 不得从扁平图片数组位置或文件名猜测归属。

- [x] 10.1 实现 `Attachment2PagePlan` 和 `MaterialPhotoGroup`，支持零张兼容、任意正偶数、每页最多4张、每页最多两个检材组、2张组成同一居中图片组、4张按上两张/下两张上下对齐、每组恰好两张审核后的有序图片、current-template-v1 页面母版内的 contain 区域和稳定图片顺序。输入：审核后的显式 `photo_groups` 映射；输出：页面/检材组/布局/槽位/当前页检材编号/安全显示名计划；验收：奇数、组内图片数非法、缺失归属、重复归属、顺序交叉或图片组与检材数不一致时以稳定错误码直接阻止导出。
- [x] 10.1T 增加 0/1/2/3/4/5/6/8/10 张、1/2/3/4/5 个检材组、组内顺序、跨组交叉、缺失/重复 material_id、空 material_number、横图/竖图/方图/超尺寸图、损坏图片、比例完整显示、固定网格、关系和分页衔接测试；验收：不裁剪、不拉伸、2张在整宽居中单元格中组成图片组并在下方显示对应检材文字、4张为上两张/下两张2×2表格且每行图片下方有对应检材文字、检查结果仅显示当前页检材编号、无半成品 DOCX。
- [x] 10.1R 修复无 `ArchiveManifest` 的普通 Word 导出路径：复用显式 `photo_groups` 的检材两图分组和附件二分页，使三个检材上传六张图片时第一页两个检材、第二页一个检材且编号不丢失；验证：`tests/test_template_filler_service.py::test_report_only_export_keeps_three_material_photo_groups`。
- [x] 10.1S 修正附件二图片几何：按 current-template-v1 页面母版的统一图片区域计算等比例最大化尺寸并居中，同页图片保持统一槽位和对称对齐，不裁剪、不拉伸；验证：`tests/test_attachment2_image_service.py`、附件二渲染尺寸测试和普通导出横竖图回归测试。
- [x] 10.1U 统一附件二首/续页母版：仅第一页显示“附件2”，续页保留同等高度的空白标题锚点；所有页面沿用相同的分页锚点间距、图片区域、列宽和行高，不因续页标题为空而重新放大；每组说明文字使用独立可读行框，双检材页按相同上下区域和固定组间间隔排列，避免文字被图片框遮挡或两组贴合；验证：首/续页 `pPr`、表格几何、说明行框和普通导出三检材回归测试。
- [x] 10.1V 修正双检材页垂直分布：保持单检材页现状不变；双检材页将两个完整检材组分别放入页面剩余区域的上、下等高区域并居中，图片区域随区域放大且仍 contain，检材说明文字独立占行；验证：双检材真实 Word 截图中一个检材位于上半区、一个检材位于下半区，且组间与上下边界对称。
- [x] 10.1W 修正单检材页图片偏小：单检材复用双检材页每个检材组已经验收的图片行高度，保持两图等比例 contain、左右对称和说明文字独立占行；按页面剩余区域重新计算标题锚点后的间距，使放大后的完整检材组上下留白基本对称，双检材页几何保持不变。文件：`packages/backend/app/services/attachment2_image_service.py`、`tests/test_attachment2_image_service.py`、`tests/test_attachment_docx_renderer.py`；验证：图片几何与 DOCX XML 定向测试、合成单/双检材 Word 结构和视觉对照。

## 11. 附件三页面计划（Layer 21）

- [x] 11.1 实现 `Attachment3Plan`，只接收 final ArchiveManifest。输入：manifest 和 DiscSequence；输出：一卷一页、第一页显示“附件3”、每页五行上下元数据、每页对应实际文件/MD5/光盘号/刻录日期和底部光盘说明；验收：不重新扫描目录或计算卷列表。
- [x] 11.1T 增加一卷、三卷、重规划后 manifest 绑定、分卷日期和附件一/三 partId 一致性测试；验收：只有第一页有标题、每页底部编号与当前 part 一致且页面数量等于 manifest 卷数。

## 12. current-template-v1 受控渲染（Layer 21）

Renderer 当前正式渲染输入为 `InspectionReport` 兼容数据 + `ArchiveManifest` + `AttachmentPlan` + `current-template-v1` TemplateProfile。`DocumentRenderPlan` 是后续统一渲染合同目标，当前尚未完成生产实现。

- [x] 12.1 建立固定 `current-template-v1` TemplateProfile 和资产 hash/anchor 检查；实现当前 DOCX Renderer 对正文结构化检查人员字段、固定手写行、表格、VML、图片、章节独立起页和普通分页的受控扩展。输入：canonical、final manifest、三类 page plan、固定模板；输出：唯一正式 DOCX；验收：阶段一不实现通用设计器、DSL、任意 DOCX 自动绑定、可视化编辑或无标记识别。

已完成：AttachmentPlan 和 TemplateProfile 基础设施。未完成：统一 `DocumentRenderPlan` 类型、生产构造、Renderer 只消费 RenderPlan。
- [x] 12.1T 增加模板 ZIP/XML、资产漂移、VML 宿主段落、关系、PAGE/NUMPAGES、`updateFields=true`、章节分页、固定手写行、摘要 manifest 计数和页面计划渲染测试；验收：固定 Profile 之外的模板被阻止，manifest/renderer 错误不回退 legacy。
- [x] 12.2 清理当前正式模板中的全部批注和附件二示例图片，同时保留附件二空白定位段落、VML 文本框、分页、表格和动态图片渲染能力；将清理后的资产登记为 `electronic-inspection-record@1.0.1`，保留 `1.0.0` 历史资产和既有案件引用，将历史版限定为只读重导出资产，并把仍使用内置 `1.0.0` 默认值的部署幂等迁移到新版。文件：`scripts/clean_template_docx.py`、`word_templates/template.docx`、`word_templates/template-v1.0.0.docx`、`packages/backend/app/services/template_profile_service.py`、`packages/backend/app/services/workbench_factory_service.py`、`packages/backend/app/repository/shared_defaults_repository.py`、`packages/backend/app/repository/template_registry_repository.py`、`harness/repository-assets.md`、`scripts/check-repository-assets.ts`；验证：新版 `officecli validate` 0 errors；历史资产指纹保持 `616E...14A7`，新版指纹为 `206A...8232`；架构与类型检查通过。
  - 回归修复（2026-08-13）：版本稳定性测试不再把 `HEAD:word_templates/template.docx`（当前 1.0.1 资产）误当作 1.0.0 历史资产；改为分别校验 `template.docx` 与 `template-v1.0.0.docx` 对应已登记的不可变包指纹，并断言两版本不同。模板/注册定向 pytest 41 passed、1 skipped，架构、类型、资产和 diff 检查通过；独立复审 PASS，无 MUST FIX。未修改任一 DOCX 资产。
- [x] 12.4 在模板管理页增加受控的前端模板编辑器：以已校验的当前结构模板为源，只允许修改模板显示名称、文书固定标题、正文默认字体和字号，并在前端显示受控预览。保存时 MUST 生成新的不可变模板版本，不覆盖源资产；后端必须重新执行包指纹、锚点、VML、附件表格和分页结构校验后才批准新版本。文件：`packages/shared/types/template.ts`、`packages/shared/constants/index.ts`、`packages/backend/app/services/template_customization_service.py`、`template_registry_service.py`、`packages/backend/app/controllers/template_controller.py`、`packages/frontend/src/hooks/useTemplateManagement.ts`、`packages/frontend/src/components/TemplateCustomizationEditor.tsx`、`TemplateManager.tsx` 及相关测试。验证：后端服务/控制器 pytest、前端 Hook/组件 Vitest、架构和类型检查、合成 DOCX XML 断言与 `officecli validate`。
  - 证据：后端模板/Profile 定向回归 42 passed、1 skipped；前端 Hook/组件 2 files / 5 passed；合成派生 DOCX 经 `officecli validate` 0 errors。派生过程仅改写 `word/document.xml`，其余 OOXML 部件逐字节保持不变；附件区、表格和 VML 保持不变。独立复审最终 `ACCEPT`，无 MUST FIX；`npm run verify:full -- --change extensible-report-template-platform` 的预检、架构、类型、治理、仓库资产、全仓测试、生产构建和 scoped strict docs 全部通过。
- [x] 12.4T 增加可区分测试：验证新版本保留源版本字节与案件引用，只改写允许的标题/字体/字号，拒绝未审核或历史只读源模板、非白名单字体/字号、重复版本和额外字段；前端验证打开编辑器、预览更新和正确提交派生请求。
  - 测试有效性：临时禁用字体/字号白名单后 2 个越界用例如预期失败；恢复源码后通过。审批写入失败、结构校验失败和同版本并发竞争均验证数据库与资产目录无失败残留；未审批源、历史只读源、首段标题槽清空/移动、额外字段和越界值均被拒绝。
- [x] 12.3 修复当前内置模板整体偏右：保留 `1.0.1` 为 `word_templates/template-v1.0.1.docx` 历史只读资产，发布正文左右排版边界平衡、附件一固定表格相对页面居中的 `1.0.2`；不改变段落可用宽度、表格列宽、分页锚点、VML 或页眉页脚。文件：`scripts/balance_template_layout.py`、`word_templates/template.docx`、`word_templates/template-v1.0.1.docx`、`packages/backend/app/services/template_profile_service.py`、`packages/backend/app/services/workbench_factory_service.py`、模板注册/几何回归测试及仓库资产清单；验证：三版本包指纹稳定且不同，`officecli validate` 0 errors，Microsoft Word 原生渲染保持 6 页并确认正文与附件一居中，定向 pytest、架构、类型、资产和 diff 检查通过；独立复审 `ACCEPT`，`npm run verify:full -- --change extensible-report-template-platform` 全部门控通过。
- [x] 12.5 修正 Word 原生渲染仍暴露的版式锚点：保留 `1.0.2` 为 `word_templates/template-v1.0.2.docx` 历史只读资产，发布主标题真正居中、一级结构标题略突出、同级“检查过程/检查结果”对齐以及首页/页脚粗横线相对页面居中的 `1.0.3`；保持 6 页、分页、段落可用宽度、表格列宽、VML 文本框、页眉页脚内容和线型不变。文件：`scripts/balance_template_layout.py`、版本化模板资产、TemplateProfile/注册、资产清单和 OOXML 回归测试；验证：确定性重建、版本指纹、定向 pytest、架构/类型/资产检查、`officecli validate` 及 Microsoft Word 原生 PDF 视觉复核。
  - 证据：模板/Profile/注册/填充定向回归合计 98 passed、1 skipped；架构、类型、仓库资产、diff 和当前/历史模板 `officecli validate` 检查通过。临时破坏标题居中后确定性重建测试如预期失败，还原后通过。Microsoft Word 原生导出仍为 6 页 A4，逐页确认主标题、一级/同级标题及首页/页脚粗横线相对页面居中或按层级对齐。
- [x] 12.6 增加已审核模板显示名称的独立重命名能力，并移除三个管理页标题下方的冗余说明：SharedTypes/Constants 定义请求与端点；FE Hook/Component 提供带长度校验、提交中状态和失败保留输入的重命名交互；Pages 删除指定副文案；Repository/Service/Controller 只更新显示名称元数据，保持模板资产、指纹、审批、默认状态与案件引用不变。文件：`packages/shared/types/template.ts`、`packages/shared/constants/index.ts`、`packages/frontend/src/hooks/useTemplateManagement.ts`、`packages/frontend/src/components/TemplateManager.tsx`、三个管理页、`packages/backend/app/repository/template_registry_repository.py`、`packages/backend/app/services/template_registry_service.py`、`packages/backend/app/controllers/template_controller.py`。
- [ ] 12.6T 增加可区分的前后端回归测试：有效重命名即时刷新列表；空白、超长及额外字段被拒绝并保持原名；模板 ID/版本、资产指纹、审批、默认状态和案件引用不变；三个说明文案不再渲染。验证：定向 Vitest、pytest、架构检查、类型检查、`npm run verify:quick`、scoped strict docs 和 `git diff --check`。
  - 当前证据：前端 2 files / 7 passed；后端 18 passed；架构、类型、OpenSpec strict validate 和 `git diff --check` 通过。`verify:quick` 的本次 type drift 已清零，但仍被任务开始前已存在的 39 项 `.agents`/`.claude` 未跟踪工具镜像漂移阻断；按工作区保护规则未改写这些本地工具文件，因此本任务暂不勾选。视觉验收按用户要求由用户执行，独立审查按用户要求取消。
  - 启动回归修复：内置模板启动注册沿用已持久化的用户显示名称，同时继续校验版本、资产、指纹、规则和审批元数据的不可变性；新增服务重启测试覆盖名称、指纹、审批及默认模板状态保持。模板控制器与注册仓库定向测试 19 passed；架构和类型检查通过。`verify:quick` 仍仅被上述 39 项既有工具镜像漂移阻断；scoped strict docs 同时报告该漂移和本任务未勾选状态。
- [x] 12.2T 增加确定性模板清理、无批注部件/标记/关系、无模板媒体、附件二锚点保留、历史模板指纹可复现、新默认模板注册、已有案件继续引用 `1.0.0`、自定义默认模板不被覆盖、0/2/4 张动态图片回归测试；受影响后端组合 127 passed / 1 skipped，核心清理逻辑突变验证按预期失败且恢复后通过。人工 Word 视觉验收因当前环境缺少 LibreOffice/Word 渲染器保持待验收，不伪报通过。

## 13. 全黑字体策略（Layer 21）

- [x] 13.1 在受控 renderer 中统一正文、表格、页眉页脚、VML 文本框和动态内容字体为黑色，不改变 VML/边框/图片背景结构。输入：模板 XML 和 render plan；输出：黑色字体 DOCX；验收：黑色策略不由业务模型提前拼接文字实现。
- [x] 13.1T 增加 XML 颜色、VML、表格、页眉页脚和结构保留测试；验收：没有动态彩色文字、空白页或奇偶页分节符回归。

## 14. 新旧报告与双管线回归（Layer 20/21/22）

Shadow 回归只比较新旧结构化结果和非执行性归档投影；测试不得触发真实第二次 WinRAR 压缩或产生第二份正式文书。

- [x] 14.1 将现有新旧报告 fixture 接入 legacy/shadow/canonical 三模式，保留已验收解析优先级和旧前端 DTO。输入：脱敏合成旧/新报告；输出：解析/投影/plan/比较结果；验收：真实案件、人员、IMEI、序列号不进入自动化 fixture。
- [x] 14.1T 运行 parser、service、controller、frontend 和 renderer 回归，并验证 Shadow 比较日志脱敏；验收：新旧报告解析能力无回归，canonical 错误不自动 fallback。

## 14A. 阶段1真实人工测试关联修复（Level 2）

- [x] 14A.1 从 `data_report_info.json.contents[].value` 提取括号主产品名称和其首个绑定版本，隔离后续子模块/插件/组件版本；按检材提取品牌与手机型号/设备型号并生成统一设备名称。
- [x] 14A.2 将真实 WinRAR 归档移至审核预览期异步请求；提供执行状态轮询，正式导出只消费预览阶段 validated Manifest，不再次压缩；普通非归档字段修改不触发重复压缩。
- [x] 14A.3 以报告目录父目录为 WinRAR 工作目录、报告根目录名为输入，删除 `-ep1` 和逐文件列表；快照纳入目录以保留多级结构、不同目录同名文件及业务空目录。
- [x] 14A.4 单卷使用案件名 `.rar`、多卷使用 `.partN.rar`；前端按已验证归档结果的 Manifest parts 展示实际文件名、字节数、MD5、分卷、对应光盘编号与光盘容量，审核编辑页的附件区域同步展示每个分卷与光盘编号的一一对应关系，并以 context/manifest/part 不透明标识逐卷下载。
- [x] 14A.5 下载前和 Word 导出前重新验证同一物理 part；新增软件、设备名、目录结构、Manifest一致性、下载接口及附件2同排双图结构测试。
- [ ] 14A.6 使用指定真实报告完成预览归档、下载后哈希/字节数、WinRAR列表、独立解压目录树与逐文件内容、唯一正式Word和附件2视觉验收；不得以手工RAR的二进制、MD5或压缩后大小作为相等条件。 [DEFERRED]
- [x] 14A.7 将既有 MaterialDisplayPolicy 接入当前审核编辑器、检查过程和正式 legacy Renderer：手机只投影合法 IMEI1/IMEI2，平板只投影序列号且保留原始字段；增加明确列名的浏览器本地六项用户默认设置（文号、检查地点、检查方法、检查硬件设备、有序检查人员、光盘编号前缀）及下次解析套用/清除入口；归档完成后以与Word相同的后端 Manifest 投影刷新前端附件1预览，并在同一工作台完成事务中写入 `case_drafts.report_json.attachments.extract_list`（不新增文件大小列），覆盖单卷、多卷、审核字段未完成和恢复路径，补充前后端回归测试。
- [x] 14A.9 删除附件三元数据框多余的“文件名”行；保留并依次显示检验单位、光盘编号、文件哈希和刻录时间，多卷页面使用各自 Manifest 的 MD5、盘号和日期。文件：`packages/backend/app/services/docx_attachment_xml_service.py`、`attachment_docx_renderer_service.py`、`tests/test_attachment_docx_renderer.py`；验证：受影响后端组合 88 passed，三卷 DOCX XML 断言每页完整非空行恰为四行且无“文件名”，officecli validate 无错误；独立复审 PASS，无剩余 MUST/SHOULD FIX；`npm run verify:full -- --change extensible-report-template-platform` 的预检、架构、类型、治理、仓库资产、全仓测试、生产构建和 scoped strict docs 全部通过。
- [x] 14A.10 修复审核编辑界面单独导出与统一导出的 Word 附件版式分叉：案件已有成功归档时，`/records/export` 复用统一导出的已验证 Manifest、Manifest 绑定计划中的持久化光盘映射和 `AttachmentPlan` 渲染分支；尚无成功归档时保留 report-only 兼容导出，旧浏览器下载与 Shadow 路径不额外读取案件 Manifest。文件：`packages/backend/app/controllers/record_controller.py`、`record_template_context_controller.py`、`packages/backend/app/services/archive_export_service.py`、`packages/backend/app/services/unified_export_service.py`；验证：定向后端 15 passed，架构与类型检查通过，历史任务选择突变测试有效，独立复审 PASS；scoped full gate 的预检/架构/类型/治理/资产检查通过，全仓测试 1133 passed、3 skipped，剩余 3 failed/7 errors 为既有 SQLite 临时数据库只读夹具问题，未伪报全门控通过。
- [x] 14A.11 使附件1“电子数据”和“文件MD5哈希值”数据列在首页与续页均写入 Word 的西文字符级换行属性，保持长 RAR 文件名和 MD5 按图二样式排版，同时保持无 Manifest 兼容导出一致。文件：`packages/backend/app/services/docx_attachment_xml_service.py`、`attachment_docx_renderer_service.py`、`template_filler_service.py`；验证：受影响后端组合 104 passed，属性与 schema 顺序突变测试有效，两份合成 DOCX 均通过 officecli validate，架构、类型、生产构建和独立复审通过。
- [x] 14A.12 使附件1“来源”按图二样式将每个检材编号单独换行显示，除最后一个外保留顿号，并将“检材内提取”放在编号后的独立一行；Manifest 固定渲染与无 Manifest 兼容导出保持一致。文件：`packages/backend/app/services/docx_attachment_xml_service.py`、`attachment_docx_renderer_service.py`、`template_filler_service.py`；验证：5 卷首页/续页的六检材 `w:br` 与 `vMerge` 回归通过，换行逻辑突变测试有效，兼容导出及 officecli validate 通过，独立最终复审 PASS。

### 14A.8 笔录模版管理人工验收补充（Level 2）

- [ ] 14A.8.1 在检查人员管理同级增加“笔录模版管理”导航和页面，支持查看已校验版本、选择默认模版、上传新增模版和安全删除非默认且未被案件引用的版本；案件仍只保存模板 ID/版本，既有案件引用不因默认值变化而改写。 [DEFERRED]
- [ ] 14A.8.2 复用 current-template-v1 资产指纹与结构校验，上传文件只进入受控模板资产目录；删除记录为审批撤销，不物理删除被案件引用的文件；默认模板在新案件解析完成首次创建草稿时写入。 [DEFERRED]
- [ ] 14A.8.3 增加前端导航/管理 Hook/管理组件和后端管理 API 回归：默认选择、上传校验、删除保护、案件引用保护、既有单案模板选择与默认值无回归。 [DEFERRED]

## 15. 人工 Word 验收（跨层）

- [ ] 15.1 准备阶段一脱敏人工验收矩阵：手机/平板标识、人员顺序、主软件、正文/光盘日期、4/22/45GB档位、重规划、附件一/二/三、VML、黑字、图片比例、分页和模板 hash。输入：通过自动化门禁的唯一正式 DOCX；输出：甲方可审阅验收记录；验收：人工打开 Word 确认版式和可读性。 [DEFERRED]
- [ ] 15.1T 固化人工验收证据清单和失败复现入口；验收：未通过项不会标记阶段一完成或切换 canonical。 [DEFERRED]

人工验收记录（2026-07-19）：甲方已在 Microsoft Word GUI 检查一组脱敏Word样例并确认通过。记录结果为：无Word修复提示；附件章节独立起页、附件1标题和固定清单、固定手写行、正文动态检查人员、附件3元数据和底部光盘说明、摘要数量、PAGE/NUMPAGES、VML、无空白页和无末尾空白页均通过。稳定材料和清单保存在被Git忽略的验收目录。

人工验收记录（2026-07-20，认可版本 v8）：甲方已在 Microsoft Word GUI 确认通过。该样例包含两个检材，每个检材两张图片；附件2页面按两个检材组上下排列、每组两张图片左右排列，图片文字与检材一一对应且顺序无交叉。检查结果合并显示当前两个检材编号，Word 无修复提示，附件2标题只出现一次，附件3从下一页衔接，图片比例和页脚通过人工检查。v8 的机器校验和 SHA-256 记录保存在被 Git 忽略的验收目录；本记录只确认 v8 的人工视觉验收，不将 `15.1` 或 `15.1T` 勾选为阶段一全部完成。

15.1/15.1T 暂不勾选：任务原文还包含 4/22/45GB 档位、重规划、全局黑字策略、图片比例等本次五份 Word 样例未逐项人工验收的范围；本记录不将这些未验收范围伪装为已完成，也不改变附件二偶数布局、canonical、Shadow E2E、桌面桥接或阶段一全部完成状态。

### 归档专项完成与延期状态（2026-07-23）

- D1 归档容量合同已完成。
- D2.1 七项历史问题已逐项核销，当前没有需要按旧计划重复实现的代码项：

  | 历史问题 | 当前核销结果 | 代码/测试证据 | 提交与剩余问题 |
  |---|---|---|---|
  | WinRAR 执行超时 | 已修复；按输入大小计算并受上下界约束，超时返回稳定错误并清理 staging。 | `winrar_timeout_policy.py::compute_timeout`、`winrar_executor_repository.py::WinRarExecutor.execute`；`tests/test_winrar_timeout.py::TestExecutionTimeout`、`tests/test_archive_executor_validator.py::test_executor_timeout_is_safe_and_cleans_staging` | `206b5cf`、`e4a946a`；无已知机制缺陷，真实大容量证据仍按延期项管理。 |
  | 完整性校验超时 | 已修复；按全部实际分卷大小计算 `rar t` 超时，超时与损坏使用不同诊断码。 | `winrar_timeout_policy.py::compute_integrity_timeout`、`archive_validator_repository.py::validate_archive_parts`；`TestIntegrityTimeout`、`TestIntegrityTimeoutViaValidator`、`TestIntegrityTimeoutContractChain` | `e4a946a`、`fad7c1e`；22GB 双卷/45GB 真实执行仍未补证。 |
  | 进程树终止 | 已修复；Windows 始终先执行 `taskkill /T /F`，确认失败才回退父进程终止；未确认死亡时不误清理 staging。 | `winrar_executor_repository.py::_terminate_process`；`TestProcessTermination`、`TestTerminationPreventsCleanup`、`TestOSErrorPath` | `3e1e802`、`fad7c1e`；Windows 跨平台可移植性和极端退出后的残留子进程证明仍是技术债。 |
  | 旧 Manifest 兼容 | 已修复有限兼容；缺失 `disc_capacity_bytes` 时根据受信 `size_bytes` 推导，显式非法值仍拒绝，输出使用深拷贝归一化。 | `archive_manifest_service.py::validate_published_manifest`、`archive_manifest_access_service.py::get_valid_manifest`；`TestOldManifestRejectsInvalidDiscCap`、`TestManifestImmutability`、`TestGetValidManifestNormalizes` | `e4a946a`、`fad7c1e`；不承诺任意历史 schema 迁移，非法旧值仍是阻断项。 |
  | 锁增长 | 已修复；WinRAR plan 使用受保护 set，`execute()` 的 `finally` 必然释放，连续执行不增长；解析相关 key lock 使用弱引用并配合容量限制。 | `winrar_executor_repository.py::_active_plans/_release_plan`、`report_parsing_cache_service.py`、`archive_parse_runtime_service.py`；`TestLockLifecycle`、`TestLockRaceWindow`、`test_concurrent_same_directory_builds_once_and_keeps_limit` | `e4a946a`、`3f1b088`；未发现当前增长缺陷，仍需把长期压力观察与真实运行监控作为运维证据。 |
  | 环境变量 warning | 已修复；非法/越界 `BIJI_ARCHIVE_TIMEOUT_SECONDS` 安全回退并每次调用只写一条脱敏 warning，合法/未设置不 warning，不泄漏原始路径和值。 | `winrar_timeout_policy.py::compute_timeout`；`TestEnvTimeoutWarnings` | `e4a946a`、`fad7c1e`；无已知当前缺陷。 |
  | Export Gate 序列化 | 已修复；Python `str Enum` 和 Controller `.value` 输出稳定字符串，完整性超时等新码可跨层传递。 | `export_gate_service.py::ExportGateCode`、`record_controller.py`；`TestIntegrityTimeoutContractChain`、`TestRecordControllerEnum`、`tests/test_export_gate_service.py` | `2cbe606`、`e4a946a`、`fad7c1e`；新增门控码仍需同时补 shared/Python/Controller 回归。 |

- 真实执行目前只有部分证据：4GB 双卷、22GB 单卷已有脱敏真实证据，但不等同于全部档位验收。
- 延期而非失败、取消或完成：22GB 双卷、45GB 真实执行、真实向上 replan；本轮不生成新的 GB 级测试数据。
- 上述延期不构成 Shadow 真实样本差异治理、Canonical 代码开发、只读预览/编辑门控、候选输出隔离或回滚演练的前置阻塞；只构成 Canonical 默认唯一正式输出、最终验收和归档的发布门槛。
- 当前正式模板没有展示每卷 `disc_capacity_bytes` 的独立位置；本批次不修改 Word 布局。
- `15.1`、`15.1T` 继续保持未勾选，以上局部归档验收不得替代完整阶段一人工验收。

### 已知技术债（仅记录，本批次不扩展代码）

- Windows 进程终止测试的跨平台可移植性。
- 极端进程退出后的残留子进程证明问题。
- 少量异常创建路径的 staging 清理问题。
- `ODD_PHOTO_COUNT` 跨语言别名差异。

## 16. canonical 切换和回滚演练（跨层）

预切换的只读预览、编辑门控、候选输出隔离和回滚演练不以延期大容量验收为前置条件；但演练必须覆盖“允许编辑但禁止最终导出”的统一门控，并确认 canonical 正确性失败只返回明确错误，不自动回退 legacy。只有正式发布门槛解除后，才可将 Canonical 设为默认唯一正式输出；回滚仅通过集中 `pipeline_mode` 完成。

- [ ] 16.1 通过集中 `pipeline_mode` 将默认从 `legacy` 经 `shadow` 切换到 `canonical`；设计 canonical 数据错误、模板漂移、manifest 校验失败和缓存污染的人工运维回滚。输入：Shadow 比较通过且阶段一人工验收通过；输出：canonical 唯一正式输出或明确失败；验收：canonical 失败不自动回退，人工改回 legacy 后可重新处理。 [DEFERRED]
- [ ] 16.1T 执行回滚演练和缓存隔离测试；验收：已有输出不被覆盖、Shadow 结果不被当正式缓存、legacy/canonical 模式均可恢复。 [DEFERRED]

## 17. 阶段二/三接口预留（不属于阶段一实现门槛）

- [ ] 17.1 只定义 `ReportProfile`、`FieldProvenance`、结构发现/候选确认接口和版本化存储契约，不在阶段一实现任意报告自动解析。输入：未知结构候选；输出：可序列化的 draft/confirmed Profile 契约；验收：未确认 Profile 不得静默导出。 [DEFERRED]
- [ ] 17.1T 为 Profile 来源文件、JSON 路径、规则、置信度、确认和版本失效增加契约测试；验收：同类复用和低置信人工确认边界明确。 [DEFERRED]
- [ ] 17.2 只定义 `TemplateProfile` 的段落/表格/单元格/内容控件/VML anchor、重复区、图片区、显示条件、分页和推荐草稿扩展点，不在阶段一实现通用模板设计器、无标记识别或自动推荐。输入：固定 current-template-v1 Profile；输出：阶段三可扩展接口；验收：阶段一只接受固定 Profile。 [DEFERRED]
- [ ] 17.2T 为 TemplateProfile round-trip、版本、anchor 和“未确认不可导出”增加契约测试；验收：接口可扩展但阶段一能力边界不扩大。 [DEFERRED]
