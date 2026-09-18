
# 实现任务：extensible-report-template-platform

workflow_level: 3
lifecycle_status: in-progress

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

阶段一最终类型只允许 `phone`/`tablet`；报告明确且无冲突时可预选。缺少可靠类型时，两个有效、不同的 15 位 IMEI 可兜底推断手机并直接通过类型导出门控；其他情况由审核页面确认。

- [x] 3.1 实现 `Material.kind` 分类确认和 `MaterialDisplayPolicy`。自动候选优先读取报告明确的 `device_type` 语义字段，经全半角/大小写归一化后匹配受控词表：`手机`、`智能手机`、`phone`、`smartphone`、`iPhone` → `phone`；`平板`、`平板电脑`、`tablet`、`iPad` → `tablet`。同一字段同时命中两类时为 `unconfirmed`；缺少可靠类型时仅允许 17F 定义的双 IMEI 兜底，不使用序列号、型号、案件名、文件名或全文搜索。分类记录报告来源、诊断和 `confirmed_by_report`/`confirmed_by_user`/`unconfirmed` 状态。输入：ReportAdapter 的原始标识候选、设备类型来源和确认状态；输出：手机只保留 IMEI1/IMEI2、平板只保留序列号的结构化展示数据和 `select_display_identifiers(material)` 结果；验收：规则位于业务规划层，parser 不删除候选，renderer 不重新判断。
- [x] 3.1T 增加手机、平板、大小写/全半角、首尾空白、缺失标识、非法标识、冲突分类、低置信阻止和人工确认状态测试；验收：不出现两组标识混排，错误可解释且 `unconfirmed` 阻止导出，多检材 blocker 指向稳定材料 ID/字段路径。

## 4. 检查人员 Repository 与有序快照（Layer 20/21）

当前模板按快照顺序一人一行；附件一人员整框只在最后一页，人员过多时必须通过增加整框高度或预留末页空间保持整框不可拆。

- [x] 4.1 实现后端 `InspectorRepository` 和服务接口，数据优先使用 `BIJI_APP_DATA_DIR`，否则使用 Windows `%LOCALAPPDATA%\\文枢\\data`，再进入不暴露完整用户主目录的安全回退目录；正式文件为 `inspectors.json`，最近有效备份为 `inspectors.json.bak`。使用唯一 ID、姓名/单位/警号基础校验、临时文件、flush/fsync、原子替换、单进程写锁和备份恢复；输入：后端 CRUD 请求；输出：带 `schema_version` 的版本化人员记录；验收：前端不能直接访问 JSON，仓库目录不进入 Git，写入失败保留原文件，损坏 JSON 不被静默覆盖。
- [x] 4.1T 增加 Repository 单测，覆盖空白/超长/非法字段、唯一 ID、损坏文件、临时文件清理、原子替换失败、备份恢复、UTF-8 中文、配置目录覆盖和并发写入；验收：失败路径不改变原文件，测试只使用临时目录。
- [x] 4.2 实现按报告选择顺序生成 `introduction.inspector_snapshots?: InspectorSnapshot[]`，以快照作为唯一权威数据源，并自动派生现有 `introduction.inspectors` 的 legacy 投影（`police_number → badge_number`）；旧 DTO 仅有 `inspectors` 时按原顺序 best-effort 转为快照，不伪造人员库 ID/确认来源。人员库后续变化不重新读取历史报告；输入：有序人员 ID；输出：有序快照；验收：Word 顺序只由快照顺序决定，未来替换 SQLite/服务端时上层接口不变。
- [x] 4.2T 增加任意人数、重复选择、顺序、人员库修改、历史重导出、快照与兼容投影冲突和前端管理/审核选择测试；验收：快照中 `unit`、`name`、`police_number` 可独立绑定，停用/删除人员不改变已生成快照。

- [x] 4.3 将人员库正式字段调整为姓名、单位、职位、警号，移除启用/停用状态与状态接口；v1 本地 JSON 中的所有人员统一迁移为可用，职位为空时兼容加载并允许后续补充。职位进入人员选择、案件快照、共享默认值兼容格式和正式文书投影，历史快照缺少职位时继续可读。文件：共享类型、Inspector Repository/Service/Controller、快照/Legacy/Canonical 投影、前端管理与审核选择组件及直接调用链。
- [x] 4.3T 修改现有人员 Repository、Service、Controller、管理组件、选择组件、快照/投影和文书测试，覆盖 v1 停用记录仍返回、职位新增/更新/搜索/快照保留、状态 API 移除、历史无职位数据兼容以及正式文本包含职位。

4.3/4.3T 证据（2026-08-23）：后端受影响定向 113 passed；前端设备/人员/共享默认设置定向 18 passed，案件页与相关投影组合 44 passed；`npm run verify:quick` 通过。历史 v1 `enabled=false` fixture 断言仍返回且职位为空，正式兼容生成断言有职位/无职位两种文本均无重复分隔符。scoped strict docs 仅被本包既存且与本任务无关的未完成必选项 12.6T 阻断；本次是既有 Level 3 包内增量维护，不触发该包未收敛的最终 Review/full gate。

阶段一验收边界说明：当前检查人员库数据持久化到本地应用数据目录。报告中的 `InspectorSnapshot[]` 在当前审核会话和最终导出请求中保持有序；当前系统尚无独立报告草稿持久化接口，因此刷新页面或重新进入页面后，未正式保存的整个报告编辑状态不会自动恢复。该限制不属于人员库缺陷，不作为本轮验收项；可登记为后续“本地报告草稿/任务持久化”候选任务，本轮不实现。

## 5. 主取证软件归一化（Layer 20/21）

主软件无法可靠识别时，审核页面允许分别填写或修正名称和版本；确认前只能编辑和保存中间结果，不能正式导出。不能使用历史固定软件或从普通组件猜测，只有 WinRAR/Python 的工具列表不完整。

- [x] 5.1 将主取证软件名称和版本归一化为报告来源；只生成主取证软件、WinRAR、Python hashlib 三类 `SoftwareTool`。输入：报告软件候选和运行时版本；输出：带 source/provenance 的工具列表；验收：环境检测不能覆盖报告主软件，冲突候选进入确认/阻止。
- [x] 5.1T 增加明确、冲突、缺失和环境版本差异测试；验收：工具白名单和报告权威来源均有断言。

## 6. 光盘编号和日期（Layer 2/21）

- [x] 6.1 实现 `DiscSequence` 解析、日期校验、首编号输入、序号递增和前导零保留。输入：`GPyyyyMMdd-序号`；输出：按最终卷序生成的光盘编号、光盘日期和附件日期；验收：附件摘要/附件三使用光盘日期，正文检查起止时间仍来自报告创建/报告时间。
- [x] 6.1T 增加非法日期、非法格式、位宽、溢出和三卷连续编号测试；验收：非法输入在压缩前阻止处理。

6.1 回归修复证据（2026-08-10）：附件摘要“检查人签名”下方日期不再读取系统当前日期；Legacy 输入复用 `attachments.burning_date`，正式 manifest 导出复用经验证的首张光盘日期，并保持 `YYYY年M月D日` 格式。定向测试覆盖两条生成链路。

## 7. 归档规划器（Layer 2/21）

- [x] 7.1 实现纯函数 `ArchivePlanner`，生成只含预计方案的 `ArchivePlan`。输入：案件名、源目录逻辑大小和策略；输出：4GB/22GB/45GB 档位、预计卷数、十进制容量、`maxReplanAttempts=2`；验收：4GB最多2卷、22GB最多2卷、45GB最多3卷，超过135GB预先阻止。
- [x] 7.1T 增加 8GB、8GB+1、44GB、44GB+1、135GB、135GB+1 边界测试；验收：不调用 WinRAR 即可验证档位和上限。

## 8. WinRAR Executor 及最终 ArchiveManifest（Layer 20/21）

WinRAR 缺失或不可调用是明确阻断项：允许上传、解析、审核和编辑，禁止自动压缩和最终正式导出，不生成 `ArchiveManifest`，不降级 ZIP，并返回可操作的安装/调用错误。

- [x] 8.1 实现 `WinRarExecutor`、`ArchiveValidator` 和 `ArchiveManifestAssembler`。输入：ArchivePlan、WinRAR staging 结果和 DiscSequence；输出：最终不可变 `ArchiveManifest`；验收：manifest 至少含实际文件名、实际大小、MD5、分卷序号、光盘容量、光盘编号、刻录日期和连续性校验结果；附件一/三渲染仍由后续任务负责。
- [x] 8.1T 增加 mock/真实小 fixture 测试，覆盖 `-v...b`、`.partN.rar`、跳号、卷数、大小、MD5、连续性和 staging 清理；验收：预计文件名/大小/卷数不能进入最终 Manifest。
- [x] 8.2 实现实际结果不符合计划时的有限重规划：最多两次重试，重试仍失败返回明确错误且不提交归档/Word。输入：执行结果与 ArchivePlan；输出：最终 manifest 或阻止错误；验收：4→22→45 的升级和耗尽路径可回归。
- [x] 8.2T 增加压缩比导致少卷、超卷、无下一档和重试耗尽测试；验收：不会静默降级 ZIP 或自动回退 legacy。
- [x] 8.3 实现归档输入授权与不透明 `archive_context_id` 生命周期。历史来源白名单和开关由 2026-09-08 反馈移除；路径安全、输入输出隔离和后续规划/执行/Manifest 仅接受上下文标识的边界继续保留。
- [x] 8.3T 增加固定根目录、前缀相邻目录、大小写、相对/穿越、链接/reparse、UNC/设备路径、输入输出重叠、精确授权令牌、上下文摘要/过期/并发/清理、解析接口稳定错误码测试；验收：公共响应和错误不包含完整本地路径，原始案件不会被清理。

8.3/8.3T 的完成边界：本轮完成固定根目录生产能力、精确目录授权安全模型/令牌验证/拒绝边界及其自动化测试；本机目录选择器和可信桌面桥接由 8.5 单独承接，不改变 8.3 的路径安全合同。

- [x] 8.4 来源授权模式的历史实现已由 2026-09-08 反馈替代：移除浏览器偏好和来源白名单，最终请求由 `packages/shared/types/sourceRequests.ts` 和 `packages/frontend/src/hooks/useSourceRequests.ts` 定义。
- [x] 8.4T 原开关/持久化测试已合并为无来源授权参数、旧设置失效和基础安全边界回归，见本文件末尾反馈验证证据。

8.4 历史验证证据：后端 98 passed、前端 22 passed；当时的架构、类型和授权分支验证通过。最终行为以 2026-09-08 反馈为准。

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
- [x] 10.1W 修正单检材页图片偏小：单检材复用双检材页每个检材组已经验收的图片行高度，保持两图等比例 contain、左右对称和说明文字独立占行；按页面剩余区域重新计算标题锚点后的间距，使放大后的完整检材组上下留白基本对称，双检材页几何保持不变。文件：`packages/backend/app/services/attachment/attachment2_image_service.py`、`tests/test_attachment2_image_service.py`、`tests/test_attachment_docx_renderer.py`；验证：图片几何与 DOCX XML 定向测试、合成单/双检材 Word 结构和视觉对照。

## 11. 附件三页面计划（Layer 21）

- [x] 11.1 实现 `Attachment3Plan`，只接收 final ArchiveManifest。输入：manifest 和 DiscSequence；输出：一卷一页、第一页显示“附件3”、每页五行上下元数据、每页对应实际文件/MD5/光盘号/刻录日期和底部光盘说明；验收：不重新扫描目录或计算卷列表。
- [x] 11.1T 增加一卷、三卷、重规划后 manifest 绑定、分卷日期和附件一/三 partId 一致性测试；验收：只有第一页有标题、每页底部编号与当前 part 一致且页面数量等于 manifest 卷数。

## 12. current-template-v1 受控渲染（Layer 21）

Renderer 当前正式渲染输入为 `InspectionReport` 兼容数据 + `ArchiveManifest` + `AttachmentPlan` + `current-template-v1` TemplateProfile。`DocumentRenderPlan` 是后续统一渲染合同目标，当前尚未完成生产实现。

- [x] 12.1 建立固定 `current-template-v1` TemplateProfile 和资产 hash/anchor 检查；实现当前 DOCX Renderer 对正文结构化检查人员字段、固定手写行、表格、VML、图片、章节独立起页和普通分页的受控扩展。输入：canonical、final manifest、三类 page plan、固定模板；输出：唯一正式 DOCX；验收：阶段一不实现通用设计器、DSL、任意 DOCX 自动绑定、可视化编辑或无标记识别。

已完成：AttachmentPlan 和 TemplateProfile 基础设施。未完成：统一 `DocumentRenderPlan` 类型、生产构造、Renderer 只消费 RenderPlan。
- [x] 12.1T 增加模板 ZIP/XML、资产漂移、VML 宿主段落、关系、PAGE/NUMPAGES、`updateFields=true`、章节分页、固定手写行、摘要 manifest 计数和页面计划渲染测试；验收：固定 Profile 之外的模板被阻止，manifest/renderer 错误不回退 legacy。
- [x] 12.2 清理当前正式模板中的全部批注和附件二示例图片，同时保留附件二空白定位段落、VML 文本框、分页、表格和动态图片渲染能力；将清理后的资产登记为 `electronic-inspection-record@1.0.1`，当时保留 `1.0.0` 历史资产和既有案件引用（现已按 12.8 删除）。文件：`scripts/clean_template_docx.py`、`word_templates/template.docx`、TemplateProfile/WorkbenchFactory/默认值与注册 Repository、资产文档和资产检查；验证：新版 `officecli validate` 0 errors，历史与新版指纹稳定，架构与类型检查通过。
  - 回归修复（2026-08-13）：版本稳定性测试分别校验当时的当前与历史资产指纹并断言两版本不同；相关历史资产现已按 12.8 删除。模板/注册定向 pytest 41 passed、1 skipped，架构、类型、资产和 diff 检查通过；独立复审 PASS，无 MUST FIX。
- [x] 12.4 在模板管理页增加受控的前端模板编辑器：以已校验的当前结构模板为源，只允许修改模板显示名称、文书固定标题、正文默认字体和字号，并在前端显示受控预览。保存时 MUST 生成新的不可变模板版本，不覆盖源资产；后端必须重新执行包指纹、锚点、VML、附件表格和分页结构校验后才批准新版本。文件：`packages/shared/types/template.ts`、`packages/shared/constants/index.ts`、`packages/backend/app/services/template/template_customization_service.py`、`packages/backend/app/services/template/template_registry_service.py`、`packages/backend/app/controllers/template_controller.py`、`packages/frontend/src/hooks/useTemplateManagement.ts`、`packages/frontend/src/components/TemplateCustomizationEditor.tsx`、`TemplateManager.tsx` 及相关测试。验证：后端服务/控制器 pytest、前端 Hook/组件 Vitest、架构和类型检查、合成 DOCX XML 断言与 `officecli validate`。
  - 证据：后端模板/Profile 定向回归 42 passed、1 skipped；前端 Hook/组件 2 files / 5 passed；合成派生 DOCX 经 `officecli validate` 0 errors。派生过程仅改写 `word/document.xml`，其余 OOXML 部件逐字节保持不变；附件区、表格和 VML 保持不变。独立复审最终 `ACCEPT`，无 MUST FIX；`npm run verify:full -- --change extensible-report-template-platform` 的预检、架构、类型、治理、仓库资产、全仓测试、生产构建和 scoped strict docs 全部通过。
- [x] 12.4T 增加可区分测试：验证新版本保留源版本字节与案件引用，只改写允许的标题/字体/字号，拒绝未审核或历史只读源模板、非白名单字体/字号、重复版本和额外字段；前端验证打开编辑器、预览更新和正确提交派生请求。
  - 测试有效性：临时禁用字体/字号白名单后 2 个越界用例如预期失败；恢复源码后通过。审批写入失败、结构校验失败和同版本并发竞争均验证数据库与资产目录无失败残留；未审批源、历史只读源、首段标题槽清空/移动、额外字段和越界值均被拒绝。
- [x] 12.3 修复当前内置模板整体偏右：当时保留 `1.0.1` 历史只读资产（现已按 12.8 删除），发布正文左右排版边界平衡、附件一固定表格相对页面居中的 `1.0.2`；不改变段落可用宽度、表格列宽、分页锚点、VML 或页眉页脚。文件：`scripts/balance_template_layout.py`、`word_templates/template.docx`、TemplateProfile/WorkbenchFactory、模板注册/几何回归测试及仓库资产清单；验证：三版本包指纹稳定且不同，`officecli validate` 0 errors，Microsoft Word 原生渲染保持 6 页并确认正文与附件一居中，定向 pytest、架构、类型、资产和 diff 检查通过；独立复审 `ACCEPT`。
- [x] 12.5 修正 Word 原生渲染仍暴露的版式锚点：当时保留 `1.0.2` 历史只读资产（现已按 12.8 删除），发布主标题真正居中、一级结构标题略突出、同级“检查过程/检查结果”对齐以及首页/页脚粗横线相对页面居中的 `1.0.3`；保持 6 页、分页、段落可用宽度、表格列宽、VML 文本框、页眉页脚内容和线型不变。文件：`scripts/balance_template_layout.py`、TemplateProfile/注册、资产清单和 OOXML 回归测试；验证：确定性重建、版本指纹、定向 pytest、架构/类型/资产检查、`officecli validate` 及 Microsoft Word 原生 PDF 视觉复核。
  - 证据：模板/Profile/注册/填充定向回归合计 98 passed、1 skipped；架构、类型、仓库资产、diff 和当前/历史模板 `officecli validate` 检查通过。临时破坏标题居中后确定性重建测试如预期失败，还原后通过。Microsoft Word 原生导出仍为 6 页 A4，逐页确认主标题、一级/同级标题及首页/页脚粗横线相对页面居中或按层级对齐。
- [x] 12.6 增加已审核模板显示名称的独立重命名能力，并移除三个管理页标题下方的冗余说明：SharedTypes/Constants 定义请求与端点；FE Hook/Component 提供带长度校验、提交中状态和失败保留输入的重命名交互；Pages 删除指定副文案；Repository/Service/Controller 只更新显示名称元数据，保持模板资产、指纹、审批、默认状态与案件引用不变。文件：`packages/shared/types/template.ts`、`packages/shared/constants/index.ts`、`packages/frontend/src/hooks/useTemplateManagement.ts`、`packages/frontend/src/components/TemplateManager.tsx`、三个管理页、`packages/backend/app/repository/template/template_registry_repository.py`、`packages/backend/app/services/template/template_registry_service.py`、`packages/backend/app/controllers/template_controller.py`。
- [x] 12.6T 增加可区分的前后端回归测试：有效重命名即时刷新列表；空白、超长及额外字段被拒绝并保持原名；模板 ID/版本、资产指纹、审批、默认状态和案件引用不变；三个说明文案不再渲染。验证：定向 Vitest、pytest、架构检查、类型检查、`npm run verify:quick`、scoped strict docs 和 `git diff --check`。
  - 当前证据：前端 2 files / 7 passed；后端 18 passed；架构、类型、OpenSpec strict validate 和 `git diff --check` 通过。`verify:quick` 的本次 type drift 已清零，但仍被任务开始前已存在的 39 项 `.agents`/`.claude` 未跟踪工具镜像漂移阻断；按工作区保护规则未改写这些本地工具文件，因此本任务暂不勾选。视觉验收按用户要求由用户执行，独立审查按用户要求取消。
  - 启动回归修复：内置模板启动注册沿用已持久化的用户显示名称，同时继续校验版本、资产、指纹、规则和审批元数据的不可变性；新增服务重启测试覆盖名称、指纹、审批及默认模板状态保持。模板控制器与注册仓库定向测试 19 passed；架构和类型检查通过。`verify:quick` 仍仅被上述 39 项既有工具镜像漂移阻断；scoped strict docs 同时报告该漂移和本任务未勾选状态。
  - 阻断解除（2026-08-24）：当前工作区 `npm run verify:quick` 的架构、类型、治理、文档一致性和仓库资产检查全部通过；原工具镜像漂移已不再出现，因此依据既有定向证据勾选本任务。
- [x] 12.7 精简添加模板流程：移除“模板 ID”和“版本”输入项，将“显示名称”标签改为“命名”；上传接口只接收名称和 DOCX，Service 为成功上传生成唯一不透明模板 ID 与内部初始版本 `1.0.0`，保留模板不可变性、审批、默认值和案件引用合同。文件：`packages/frontend/src/components/TemplateManager.tsx`、`packages/frontend/src/hooks/useTemplateManagement.ts`、`packages/backend/app/controllers/template_controller.py`、`packages/backend/app/services/template/template_registry_service.py`。
- [x] 12.7T 更新现有前后端回归：组件断言添加弹窗不出现 ID/版本且以“命名”提交；Hook 断言 multipart 不再发送两个技术字段；Controller 断言仅名称和文件即可注册且系统生成唯一 ID/`1.0.0`。验证：定向 Vitest、pytest、架构检查、类型检查、Impeccable detector 和 `git diff --check`。
  - 证据：前端模板管理组件/Hook 2 files / 7 passed；后端模板控制器 16 passed；架构、TypeScript、OpenSpec strict validate 通过；Impeccable detector 0 findings；本任务文件范围 `git diff --check` 通过。全仓 diff 检查仍报告任务开始前已有的 `AGENTS.md` 末尾空行，未改写该用户变更。
- [x] 12.8 将当前 `template.docx` 收敛为唯一内置模板资产：删除 1.0.0～1.0.2 退役 DOCX 和三个一次性创建脚本；净化当前模板的核心属性、自定义属性和 WPS `docVars`，但逐字节保留所有渲染相关 OOXML 部件；发布新的当前内置版本并将旧内置默认值及案件引用幂等迁移到新版本。文件：`word_templates/`、`scripts/clean_template_docx.py`、`scripts/check-repository-assets.ts`、TemplateProfile/WorkbenchFactory/模板引用 Repository、资产文档与 living spec。
- [x] 12.8T 增加可区分回归：仓库只允许 `template.docx`；模板包不含真实案件媒体、批注、自定义属性、WPS `docVars` 或人员元数据；净化前后正文、页眉页脚、样式、表格、VML、分页及媒体等渲染部件逐字节一致；旧内置默认值和案件引用迁移到当前版本；officecli 校验、当前 Word 生成回归、资产检查、受影响测试、`verify:quick` 与 scoped strict docs 通过。人工验收：Microsoft Word/PDF 视觉基线逐页一致；若当前环境无法可靠执行则明确保留待验收，不伪报。
  - 证据：模板净化前后 21 个渲染相关 OOXML 部件逐字节差异为 0，仅改写核心属性、删除自定义属性关系/内容类型并移除 WPS `docVars`；同一脱敏输入生成的两份 Word 中 24 个渲染相关部件逐字节一致；Microsoft Word 原生导出的两份 PDF 均为 5 页，逐页像素差异为 0，人工查看全部页面未发现裁切、重叠、表格、页眉页脚或分页差异。当前模板 `officecli validate` 0 errors；两份生成文档均报告同一处既有 `tcBorders` 元素顺序告警，未出现净化前后差异。模板清理/包安全 31 passed、1 skipped，模板注册/迁移 16 passed，生成/填充链路 56 passed；`verify:quick` 通过。
- [x] 12.8U 清理规范、设计、源码注释和测试夹具中残留的地域标识，统一使用中性描述或明确标记的测试值；`word_templates/template.docx` 保持逐字节不变。验证：文本扫描零命中、受影响前端测试、共享类型检查、scoped strict docs、模板 SHA-256 前后相同。
  - 证据：当前提交文本扫描零命中；前端 2 files / 7 passed；类型检查、`verify:quick` 及 `audit-edit-enhancement`、`extensible-report-template-platform` 两个 scoped strict docs 均通过；模板未出现在 diff 中，SHA-256 保持 `C2EB8A0E1A5FE45651F75BCFB3C6A70B273D77528A6773C4F9775410662EDE65`。
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
- [x] 14A.9 删除附件三元数据框多余的“文件名”行；保留并依次显示检验单位、光盘编号、文件哈希和刻录时间，多卷页面使用各自 Manifest 的 MD5、盘号和日期。文件：`packages/backend/app/services/attachment/docx_attachment_xml_service.py`、`packages/backend/app/services/attachment/attachment_docx_renderer_service.py`、`tests/test_attachment_docx_renderer.py`；验证：受影响后端组合 88 passed，三卷 DOCX XML 断言每页完整非空行恰为四行且无“文件名”，officecli validate 无错误；独立复审 PASS，无剩余 MUST/SHOULD FIX；`npm run verify:full -- --change extensible-report-template-platform` 的预检、架构、类型、治理、仓库资产、全仓测试、生产构建和 scoped strict docs 全部通过。
- [x] 14A.10 修复审核编辑界面单独导出与统一导出的 Word 附件版式分叉：案件已有成功归档时，`/records/export` 复用统一导出的已验证 Manifest、Manifest 绑定计划中的持久化光盘映射和 `AttachmentPlan` 渲染分支；尚无成功归档时保留 report-only 兼容导出，旧浏览器下载与 Shadow 路径不额外读取案件 Manifest。文件：`packages/backend/app/controllers/record_controller.py`、`record_template_context_controller.py`、`packages/backend/app/services/archive/archive_export_service.py`、`packages/backend/app/services/export/unified_export_service.py`；验证：定向后端 15 passed，架构与类型检查通过，历史任务选择突变测试有效，独立复审 PASS；scoped full gate 的预检/架构/类型/治理/资产检查通过，全仓测试 1133 passed、3 skipped，剩余 3 failed/7 errors 为既有 SQLite 临时数据库只读夹具问题，未伪报全门控通过。
- [x] 14A.11 使附件1“电子数据”和“文件MD5哈希值”数据列在首页与续页均写入 Word 的西文字符级换行属性，保持长 RAR 文件名和 MD5 按图二样式排版，同时保持无 Manifest 兼容导出一致。文件：`packages/backend/app/services/attachment/docx_attachment_xml_service.py`、`packages/backend/app/services/attachment/attachment_docx_renderer_service.py`、`packages/backend/app/services/template/template_filler_service.py`；验证：受影响后端组合 104 passed，属性与 schema 顺序突变测试有效，两份合成 DOCX 均通过 officecli validate，架构、类型、生产构建和独立复审通过。
- [x] 14A.12 使附件1“来源”按图二样式将每个检材编号单独换行显示，除最后一个外保留顿号，并将“检材内提取”放在编号后的独立一行；Manifest 固定渲染与无 Manifest 兼容导出保持一致。文件：`packages/backend/app/services/attachment/docx_attachment_xml_service.py`、`packages/backend/app/services/attachment/attachment_docx_renderer_service.py`、`packages/backend/app/services/template/template_filler_service.py`；验证：5 卷首页/续页的六检材 `w:br` 与 `vMerge` 回归通过，换行逻辑突变测试有效，兼容导出及 officecli validate 通过，独立最终复审 PASS。
- [x] 14A.13 将附件1“提取方法”加入西文字符级换行范围，Manifest 首页/续页与无 Manifest 兼容导出都主动写入 `w:wordWrap w:val="off"`，不依赖模板原有属性。文件：`packages/backend/app/services/attachment/attachment_docx_renderer_service.py`、`packages/backend/app/services/template/template_filler_service.py`；验证：扩展现有首页/续页与兼容填充定向测试。
  - 证据：先扩展断言并确认 Manifest 路径属性值不统一、兼容路径属性缺失；修复后两个原失败项通过，四个受影响测试文件合计 `68 passed`，`verify:quick` 与本变更包 scoped strict docs 通过。
- [x] 14A.14 修复附件1固定手写签名区成为独立页面：修改 `Attachment1Plan` 和 current-template-v1 Renderer，普通数据页最多四行、签名尾页最多两行，使最后一页始终至少包含一条 Manifest 分卷数据与固定手写行；三卷固定规划为 `[2,1]`，四卷固定规划为 `[2,2]`，其他边界按相同尾页容量规划，不再生成零数据 `inspector_final` 页面，并让附件摘要页数与页面计划一致。优先扩展 `tests/test_attachment_plan_service.py`、`tests/test_attachment_docx_renderer.py` 的既有边界测试，补充 officecli validate 和 Microsoft Word 脱敏视觉验收，覆盖 1/2/3/4/5/8/9 卷及长文本换行场景。
  - 证据：先修改边界断言并确认旧实现 8 项失败；修复后附件规划与 DOCX 渲染 76 passed，临时将签名尾页容量改回3后相关分页测试3项失败并已恢复，officecli 回退生成 19 passed，`npm run pre-commit` 通过。1/2/3/4/5/8/9 卷及六检材换行的8份脱敏 DOCX 全部通过 officecli validate；Microsoft Word 后台真实分页及逐页 PDF/PNG 检查确认三卷尾页为“第3卷+签名区”、四卷尾页为“第3、4卷+签名区”、六检材长来源的五卷尾页为“第5卷+签名区”，均无签名孤页、表格断裂或文字重叠。Shadow 集成套件中与应用启动相关的1 failed/7 errors 为既有 SQLite 临时数据库只读环境问题，修改所触达的独立 Shadow 比较用例通过。
- [x] 14A.15 按用户验收反馈修正附件1容量：所有数据页最多三条分卷，最后一个数据页在一至三条分卷后直接附带固定手写签名区；三卷固定为单页 `[3]`，其他边界按 `[1]`、`[2]`、`[3]`、`[3,1]`、`[3,2]`、`[3,3]`、`[3,3,2]`、`[3,3,3]` 规划，且永不生成签名独立页。更新既有规划和 Renderer 回归，使用 officecli validate 与 Microsoft Word 真实分页重新验收 1/2/3/4/5/8/9 卷及长来源场景，并展示全部附件1页面截图。
  - 证据：先将既有规划与 Renderer 边界断言改为三条上限，旧实现得到 `20 failed, 56 passed`；修复后两个定向测试文件 `76 passed`，归档导出、Legacy 投影和独立 Shadow 比较的受影响回归 `31 passed`。根因是模板数据单元格遗留的冗余空段落在“三条分卷 + 首页表头 + 签名区”场景形成不可见高度，Renderer 现仅在该临界页删除冗余空段落并保留实际内容、字体和表格结构。1/2/3/4/5/8/9 卷及六检材长来源共 8 份 SYNTHETIC DOCX 全部通过 officecli validate；Microsoft Word 后台真实分页确认全部附件1表格均未跨物理页，15 张逐页 PNG 人工检查无签名孤页、截断、重叠或断框。现行规格已同步；`npm run pre-commit`、OpenSpec strict validate 和本变更 scoped strict docs 均通过。
- [x] 14A.16 按用户新验收规则提高附件1容量：表头仍只在第一页出现且续页不重复，第一页和后续数据页均最多四条分卷并从前向后优先填满；最后一页直接附带固定手写签名区，总分卷不超过四条时在第一页完成“1～4条分卷+签名区”。五卷及九卷分别固定规划为 `[4,1]`、`[4,4,1]`，不得为均衡末页而回退为 `[3,2]` 或 `[4,3,2]`。更新既有规划与 Renderer 回归，并以 Microsoft Word 真实分页展示 4/5/7/8/9/10 卷效果。
  - 证据：先将规划和 Renderer 断言改为四条上限并确认旧实现 `13 failed, 67 passed`；修复后附件规划与 DOCX 渲染 `80 passed`，归档导出、Legacy 投影和独立 Shadow 比较回归 `31 passed`，文档构建回归 `19 passed`。4/5/7/8/9/10 卷共 6 份 SYNTHETIC DOCX 均通过 officecli validate；Microsoft Word 后台真实分页分别确认 `[4]`、`[4,1]`、`[4,3]`、`[4,4]`、`[4,4,1]`、`[4,4,2]`，13 张附件1逐页 PNG 人工检查无重复表头、签名孤页、截断、重叠或断框。四卷临界页通过关闭文档网格吸附并压缩段落行距，在保留模板字号和表格结构的同时实现“4条分卷+签名区”单页；现行规格已同步，`npm run pre-commit`、OpenSpec strict validate、`git diff --check` 和本变更 scoped strict docs 均通过。
- [x] 14A.17 按最终用户验收规则将附件1容量恢复并固定为每页最多三条分卷：在当前系统最多五卷的正式范围内，前页按三条优先填满，最后一个数据页在一至三条分卷后直接附带固定手写签名区；四卷、五卷分别固定规划为 `[3,1]`、`[3,2]`，永不生成签名独立页，附件1最多两页。删除仅服务于“四条分卷+签名区”单页的紧缩版式逻辑，更新规划、Renderer、附件摘要页数、活动规格与现行规格，并用 Microsoft Word 真实分页生成 3/4/5 卷 SYNTHETIC 图片验收；最终只交付图片，不交付中间 DOCX。
  - 证据：先将规划与 Renderer 断言改为三条上限并确认旧实现 `22 failed, 58 passed`；按当前系统最多五卷收紧正式边界后，两个定向测试文件 `71 passed`，归档导出、Legacy 投影、Shadow 比较和文档构建受影响回归 `49 passed`。临时将容量恢复为四条后，四卷 `[3,1]` 关键测试按预期失败，随后已恢复三条。3/4/5 卷共 3 份 SYNTHETIC 中间 DOCX 均通过 officecli validate；Microsoft Word 后台真实分页分别确认 `[3]`、`[3,1]`、`[3,2]`，5 张附件1逐页 PNG 人工检查无重复表头、签名孤页、截断、重叠或断框。现行规格已同步；`npm run pre-commit`、OpenSpec strict validate、`git diff --check` 和本变更 scoped strict docs 均通过。
- [x] 14A.18 按补充验收图固定附件1末页底部结构：末页少于三卷时，最后一卷的下一行在“电子数据”列显示“以下空白”，其后按需保留普通空白补位行并取消旧斜线；末页只补足三个分卷槽位，恰好三卷时第三卷后直接进入固定手写签名区，不生成第四个“以下空白”行。保持每页最多三卷、3/4/5 卷 `[3]`、`[3,1]`、`[3,2]` 和签名只出现于末页不变；更新规划、Renderer、规格与回归，并用 Microsoft Word 真实分页验收 3/4/5 卷及长来源场景，最终只交付 PNG。
  - 证据：首次更新 1～5 卷规划与 Renderer 断言时，旧实现得到 `14 failed, 59 passed`；补充“三卷后不得有第四行”反馈后，新断言再次得到 `15 failed`，修复后附件规划和 DOCX 渲染 `74 passed`。归档导出、Legacy 投影、Shadow 比较和文档构建受影响回归扩展为 `55 passed, 1 skipped`。MD5 与 SHA-256 的 3/4/5 卷 SYNTHETIC 中间 DOCX 均通过 officecli validate；Microsoft Word 后台真实分页确认两种算法均保持 `[3]`、`[3,1]`、`[3,2]`，三卷页无“以下空白”补位行，四卷末页为第四卷 + “以下空白” + 一条普通空白行，五卷末页为第四、五卷 + “以下空白”，所有补位行无斜线。SHA-256 保持 16 磅字号，仅将哈希字符宽度缩放为 54%，并清除附件1数据单元格的冗余空段落；完整 64 位哈希稳定显示为三行且无字符重叠。额外用六条长检材编号压力测试 4/5 卷：续页补位区按来源行数收缩后，签名区仍贴近页底，附件3紧接下一页，无签名孤页。10 张最终 PNG 人工检查无跨页断表、截断或重叠；最终不交付 DOCX。

### 14A.8 笔录模版管理人工验收补充（Level 2）

- [ ] 14A.8.1 在检查人员管理同级增加“笔录模版管理”导航和页面，支持查看已校验版本、选择默认模版、上传新增模版和安全删除非默认且未被案件引用的版本；案件仍只保存模板 ID/版本，既有案件引用不因默认值变化而改写。 [DEFERRED]
- [ ] 14A.8.2 复用 current-template-v1 资产指纹与结构校验，上传文件只进入受控模板资产目录；删除记录为审批撤销，不物理删除被案件引用的文件；默认模板在新案件解析完成首次创建草稿时写入。 [DEFERRED]
- [ ] 14A.8.3 增加前端导航/管理 Hook/管理组件和后端管理 API 回归：默认选择、上传校验、删除保护、案件引用保护、既有单案模板选择与默认值无回归。 [DEFERRED]
- [x] 14A.8.4 修复删除保护状态的无反馈禁用交互（Level 1 反馈）：`packages/frontend/src/components/TemplateManager.tsx` 中可删除模板继续进入撤销确认；默认模板和案件引用模板的删除入口保持可点击并分别说明保护原因与恢复动作，不放宽后端删除边界。`packages/frontend/src/components/TemplateManager.test.tsx` 增加默认模板提示与不发送删除请求的区分回归；定向 Vitest 4 passed，TypeScript、架构检查和 Impeccable detector 通过。历史内置模板的管理列表投影由后续 14A.8.5 收敛。
- [x] 14A.8.5 仅在笔录模版管理列表保留最新内置版本：修改 `packages/backend/app/services/template/template_registry_service.py`，过滤 `is_historical_builtin_template_ref` 记录，同时保留其注册、审批、DOCX 资产和既有案件引用；更新 `tests/test_template_controller.py`，区分断言管理列表仅含最新内置版本、旧版本仍不可设为默认且既有引用可继续解析。前端沿用现有列表投影和删除确认，不新增并行状态。验证：先运行失败用例，再运行模板控制器定向 pytest、`TemplateManager` 定向 Vitest、类型、架构、`verify:quick`、scoped strict docs 和 `git diff --check`。
  - 证据：管理列表投影过滤历史内置版本，旧版本审批和 `validate` 断言保持有效；模板控制器 16 passed，`TemplateManager` 4 passed；架构、TypeScript、`verify:quick` 和 Impeccable detector 通过；delta 已同步到 `openspec/specs/electronic-inspection-record/spec.md`。测试依赖仅安装于系统临时目录，未写入仓库。

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
  | WinRAR 执行超时 | 已修复；按输入大小计算并受上下界约束，超时返回稳定错误并清理 staging。 | `packages/backend/app/repository/archive/winrar_timeout_policy.py::compute_timeout`、`packages/backend/app/repository/archive/winrar_executor_repository.py::WinRarExecutor.execute`；`tests/test_winrar_timeout.py::TestExecutionTimeout`、`tests/test_archive_executor_validator.py::test_executor_timeout_is_safe_and_cleans_staging` | `206b5cf`、`e4a946a`；无已知机制缺陷，真实大容量证据仍按延期项管理。 |
  | 完整性校验超时 | 已修复；按全部实际分卷大小计算 `rar t` 超时，超时与损坏使用不同诊断码。 | `packages/backend/app/repository/archive/winrar_timeout_policy.py::compute_integrity_timeout`、`archive_validator_repository.py::validate_archive_parts`；`TestIntegrityTimeout`、`TestIntegrityTimeoutViaValidator`、`TestIntegrityTimeoutContractChain` | `e4a946a`、`fad7c1e`；22GB 双卷/45GB 真实执行仍未补证。 |
  | 进程树终止 | 已修复；Windows 始终先执行 `taskkill /T /F`，确认失败才回退父进程终止；未确认死亡时不误清理 staging。 | `packages/backend/app/repository/archive/winrar_executor_repository.py::_terminate_process`；`TestProcessTermination`、`TestTerminationPreventsCleanup`、`TestOSErrorPath` | `3e1e802`、`fad7c1e`；Windows 跨平台可移植性和极端退出后的残留子进程证明仍是技术债。 |
  | 旧 Manifest 兼容 | 已修复有限兼容；缺失 `disc_capacity_bytes` 时根据受信 `size_bytes` 推导，显式非法值仍拒绝，输出使用深拷贝归一化。 | `archive_manifest_service.py::validate_published_manifest`、`archive_manifest_access_service.py::get_valid_manifest`；`TestOldManifestRejectsInvalidDiscCap`、`TestManifestImmutability`、`TestGetValidManifestNormalizes` | `e4a946a`、`fad7c1e`；不承诺任意历史 schema 迁移，非法旧值仍是阻断项。 |
  | 锁增长 | 已修复；WinRAR plan 使用受保护 set，`execute()` 的 `finally` 必然释放，连续执行不增长；解析相关 key lock 使用弱引用并配合容量限制。 | `packages/backend/app/repository/archive/winrar_executor_repository.py::_active_plans/_release_plan`、`report_parsing_cache_service.py`、`packages/backend/app/services/archive/archive_parse_runtime_service.py`；`TestLockLifecycle`、`TestLockRaceWindow`、`test_concurrent_same_directory_builds_once_and_keeps_limit` | `e4a946a`、`3f1b088`；未发现当前增长缺陷，仍需把长期压力观察与真实运行监控作为运维证据。 |
  | 环境变量 warning | 已修复；非法/越界 `BIJI_ARCHIVE_TIMEOUT_SECONDS` 安全回退并每次调用只写一条脱敏 warning，合法/未设置不 warning，不泄漏原始路径和值。 | `packages/backend/app/repository/archive/winrar_timeout_policy.py::compute_timeout`；`TestEnvTimeoutWarnings` | `e4a946a`、`fad7c1e`；无已知当前缺陷。 |
  | Export Gate 序列化 | 已修复；Python `str Enum` 和 Controller `.value` 输出稳定字符串，完整性超时等新码可跨层传递。 | `packages/backend/app/services/export/export_gate_service.py::ExportGateCode`、`record_controller.py`；`TestIntegrityTimeoutContractChain`、`TestRecordControllerEnum`、`tests/test_export_gate_service.py` | `2cbe606`、`e4a946a`、`fad7c1e`；新增门控码仍需同时补 shared/Python/Controller 回归。 |

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

### 17A. 平航手机多路取证报告 v1 确定性适配（Level 2）

本增量复用当前 Level 3 变更包，但实现与验证强度按本次中等范围行为变化独立选择。用户指定样本只作为仓库外只读人工分析输入；任何测试夹具必须重新构造并明确标记 SYNTHETIC，不得复制真实案件名、人员、设备编号、标识符、附件内容、绝对路径或生成输出。

- [x] 17A.1 将已观察的平航 v1 结构、支持边界、字段语义、安全读取、材料顺序、图片排除和现有输出兼容决策写入 `openspec/changes/extensible-report-template-platform/design.md`、根 `spec.md` 与 delta spec。输入：用户指定仓库外样本的脱敏结构观察；输出：`pinghang-mobile-multipath-v1` 确定性合同；验收：明确“不执行脚本、不仅凭文件编号接受页面、不自动导入提取图片、不宣称任意平航版本”。
  - 设计证据（2026-09-12）：OpenSpec strict validate 通过，`git diff --check` 通过；针对仓库外样本中观察到的设备标识、案件值和绝对路径执行定向扫描零命中，未复制或修改样本文件。
- [x] 17A.2 在 Layer 20 新增平航有界探测、严格导航节点读取和安全 JSONP 数据字面量解析，并把现有格式选择重构为唯一匹配的适配器注册表。预计文件：`packages/backend/app/repository/report/report_adapter_registry.py`、`pinghang_report_adapter.py`、`pinghang_jsonp_repository.py`、`report_format_adapter.py`、`report_parse_input_models.py`；验证：先增加失败用例，再覆盖固定前缀、BOM/NUL、字符串内逗号、尾逗号、非法/额外语句、函数表达式、大小/数量/深度限制、路径越界、无匹配和并列匹配。
- [x] 17A.2T 在 `tests/test_pinghang_report_adapter.py` 与现有 `tests/test_report_parse_input_repository.py` 中使用最小 SYNTHETIC 离线报告目录验证结构探测和原始事实提取；测试必须扫描 fixture 和失败日志，确认没有真实样本值或绝对路径进入仓库、响应和日志。
- [x] 17A.3 在 Layer 21 将平航案件页、报告页和全部 `DeviceInfo` 页面映射为 `CanonicalInspectionCase`/`FieldProvenance`，再生成现有 `InspectionReport` 兼容投影；软件名称/版本、材料类型和时间字段遵循现有确认及 ExportGate 规则。预计文件：`packages/backend/app/services/canonical/pinghang_canonical_service.py`、`canonical_adapter_service.py`、`packages/backend/app/services/report/report_parser_service.py`；验证：单材料、多材料导航顺序、重复检材编号、冲突页面、软件待确认、Android 设备不自动等同手机、案件级与设备级时间不混用。
- [x] 17A.3T 复用并扩展 `tests/test_report_parser_service.py`、`tests/test_legacy_report_projection_service.py`、canonical/material/software/export-gate 现有测试，证明平航输入得到可审核 DTO，旧/新现有格式优先级与输出不变，未知平航变体不产生部分正确的正式结果。
- [x] 17A.4 将适配器注册表接入报告目录登记、来源重新校验、解析输入依赖指纹和缓存版本；来源 metadata/缓存键记录 `adapter_id`、`adapter_version`、结构指纹，公共响应和日志不暴露绝对路径或原始敏感值。预计文件：`packages/backend/app/services/source/source_record_service.py`、`packages/backend/app/repository/report/report_parse_input_repository.py`、`packages/backend/app/services/report/report_parse_inflight_service.py` 及其现有测试；验证：原生目录选择成功、取消无副作用、来源变化失效、适配器升级不复用旧缓存、现有格式来源登记回归。
- [x] 17A.4T 运行来源/解析/工作台受影响的 pytest，确认单个有效平航 v1 目录进入现有审核草稿；导航歧义、重复材料、结构漂移和恶意 JSONP 返回稳定安全诊断并阻止正式导出。前端无新增交互时不机械新增组件测试。
- [x] 17A.5 使用用户指定的仓库外单检材样本完成只读人工验收，并另用 SYNTHETIC 多材料 fixture 验证顺序；检查解析字段来源、审核修正、零照片行为、压缩输入范围和现有 Word 输出。真实样本不得复制到仓库或测试目录，验收记录只保存脱敏结构结论。若要宣称支持另一平航版本或真实多设备导出，必须另取得相应样本并新增适配器/Profile 版本，不得沿用 v1 名义推断。
  - 实现与验收证据（2026-09-12）：SYNTHETIC 平航适配器/解析/来源/工作台及 canonical/material/software/export-gate、DOCX 生成定向回归合计 196 passed，架构检查通过。仓库外样本只读探测命中 v1，识别 1 个检材；快速路径收敛为 5 个相对元数据依赖，解析保持材料类型和主软件待确认、照片数为 0。临时生成的 Word 文件非空且 `officecli validate` 通过，验证后关闭 resident 并删除临时产物；未复制样本、未执行报告脚本或工具。
- [x] 17A.6 完成实现核对后同步对应 living spec，运行 `npm run verify:quick`、受影响后端测试、`npm run verify:docs:strict -- --change extensible-report-template-platform` 和 `git diff --check`；仅在全部必选任务和适用人工验收完成后记录本增量证据，不提前切换 `pipeline_mode=canonical`，不运行与本增量风险无关的全局发布门控。
  - 收尾证据（2026-09-12）：平航 v1 最终行为已同步至 `openspec/specs/electronic-inspection-record/spec.md`；`npm run verify:quick`、196 项受影响后端测试、OpenSpec strict validate、限定 strict docs 和 `git diff --check` 通过。敏感样本标识与仓库外绝对路径定向扫描零命中；全局 `pipeline_mode` 保持不变。
- [x] 17A.7 根据超大报告反馈将平航 v1 改为固定核心文件快速路径：报告页由 `0_1.json` 加结构/标签校验确认，案件页由导航“案件信息”节点定位，材料页由 `DeviceInfo` 节点定位；不枚举或读取非核心 ViewData，并补充手机名称/品牌/型号字段别名。验证：SYNTHETIC 1049+ 页目录中含非法/乱码非核心页仍只记录核心依赖，两个仓库外样本只读解析通过，100GB 级报告体量不成为案件初始化上限。
  - 快速路径证据（2026-09-12）：适配器语义版本升级为 1.1.0，避免复用旧缓存。新增 SYNTHETIC 1049 页目录回归，其中非核心页含可执行样式和非法 UTF-8 数据；快照仍只读取入口、导航和 4 个核心页，共 6 个依赖，被选核心页异常仍安全失败。三个仓库外样本均只读解析成功，各记录 5 个依赖；较大样本快照约 0.11 秒、完整事实解析约 0.29 秒，补充样本完整事实解析约 0.30 秒。受影响后端回归 196 passed，未复制样本、未记录真实字段值或绝对路径。
- [x] 17A.8 根据美亚 new 与平航 v1 对比反馈，补齐平航案件页“送检人员”“送检单位”到现有委托字段的映射；检查起止时间改为全部材料中最早取证开始时间至最晚取证结束时间，任一材料时间缺失、非法或倒置时留空；报告未明确硬件时不再套用美亚 FL-901 解析初值。保持主软件、材料类型和附件图片的既有确认边界，适配器语义版本升级并失效旧缓存。
- [x] 17A.8T 扩展现有 SYNTHETIC 平航回归，先证明委托字段、跨材料取证时间和中性硬件初值的失败，再覆盖单材料、多材料、缺失时间、非法时间、倒置时间及美亚旧/新版输出不回归；真实样本只用于只读脱敏存在性复核。
  - 实现与测试证据（2026-09-12）：适配器语义版本升级为 1.2.0；新增 SYNTHETIC 单/多材料及缺失、非法、倒置时间回归，定向平航测试 21 passed，平航/解析/来源/投影/软件策略/导出门控/工作台/HTML 时间解析受影响回归合计 171 passed。两个用户指定的仓库外样本仅作只读脱敏存在性复核：平航委托字段和设备取证时间均可用，美亚 new 原有委托、时间、硬件和多材料结果保持可用；未复制样本、未记录真实字段值。
- [x] 17A.9 核对本轮增量与实现并同步现行规格，运行平航/报告解析/Canonical/工作台受影响测试、`npm run verify:quick`、限定严格文档检查和 `git diff --check`；保持 `lifecycle_status: in-progress`，不触发延期任务、最终 Review 或 scoped full gate。
  - 收尾证据（2026-09-12）：本轮最终行为已同步至 `openspec/specs/electronic-inspection-record/spec.md`；171 项受影响后端测试、`npm run verify:quick`、OpenSpec strict validate、限定 strict docs 与 `git diff --check` 均通过。全局 `pipeline_mode` 和变更包 `lifecycle_status: in-progress` 保持不变，未触发延期任务、最终 Review 或 scoped full gate。
- [x] 17A.10 根据用户确认将平航 v1 主取证软件名称默认为“平航手机多路分析取证软件”，确认状态标记为 `confirmed_by_user`，版本继续取报告“数据取证软件版本”；仅在唯一命中 `pinghang-mobile-multipath-v1` 时应用，不影响美亚或未知报告。适配器语义版本升级并失效旧缓存。
- [x] 17A.10T 扩展现有 SYNTHETIC 平航回归，先证明空名称/待确认状态失败，再覆盖快照、Canonical/legacy 投影、工具列表、检查步骤、结果字段和导出确认状态；保留材料类型待确认边界，并验证美亚旧/新版软件识别不回归。
  - 实现与测试证据（2026-09-12）：适配器语义版本升级为 1.3.0；聚焦回归先以名称为空、状态未确认和旧版本号产生 3 个预期失败，修改后平航 21 passed。平航/解析/来源/投影/软件策略/导出门控/工作台/HTML 时间解析受影响回归合计 171 passed；SYNTHETIC 断言覆盖默认名称、报告版本、`confirmed_by_user`、用户/报告双来源、主工具、步骤4、结果字段和导出确认，同时保持材料类型待确认。仓库外样本仅作只读脱敏布尔复核，未记录真实字段值或复制样本。
- [x] 17A.11 核对本轮增量与实现并同步现行规格，运行平航/软件策略/导出门控/报告解析/Canonical/工作台受影响测试、`npm run verify:quick`、OpenSpec strict validate、限定严格文档检查和 `git diff --check`；保持 `lifecycle_status: in-progress`，不触发延期任务、最终 Review 或 scoped full gate。
  - 收尾证据（2026-09-12）：本轮默认名称行为已同步至 `openspec/specs/electronic-inspection-record/spec.md`；171 项受影响后端测试、`npm run verify:quick`、OpenSpec strict validate、限定 strict docs 与 `git diff --check` 均通过。敏感样本标识定向扫描零命中；全局 `pipeline_mode` 和变更包 `lifecycle_status: in-progress` 保持不变。
- [x] 17A.12 根据用户确认，将平航 v1 材料页明确“数据类型”值 `Android设备`（兼容大小写、全半角和空白差异）映射为手机并标记为报告确认；仅修改 v1 内置适配语义，不接入额外设备技术字段，不改变其他报告格式或未知类型值，适配器语义版本升级并失效旧缓存。
- [x] 17A.12T 修改现有 SYNTHETIC 平航回归，先证明带空格和不带空格的 Android 设备仍待确认，再覆盖 `phone`、`confirmed_by_report`、报告来源及手机标识显示策略；仓库外样本只作只读脱敏复核。
  - 实现与测试证据（2026-09-12）：适配器语义版本升级为 1.4.0；聚焦用例先以 `phone` 预期产生失败，修复后覆盖有空格、无空格、小写和全角四种 Android 设备写法，未知类型仍保持待确认。平航定向回归 24 passed，平航/材料策略/报告解析/Canonical/软件策略/导出门控/来源/工作台受影响回归合计 217 passed。用户指定仓库外样本仅作只读脱敏复核，结果为 1 个 `phone`、`confirmed_by_report`、来源为报告，手机步骤不显示序列号；未复制样本或接入额外技术字段。
- [x] 17A.13 核对本轮增量与实现并同步现行规格，运行平航及材料策略受影响测试、`npm run verify:quick`、OpenSpec strict validate、限定严格文档检查和 `git diff --check`；保持 `lifecycle_status: in-progress`，不触发延期任务、最终 Review 或 scoped full gate。
  - 收尾证据（2026-09-12）：Android 设备映射行为已同步至现行规格；217 项受影响后端测试、`npm run verify:quick`、OpenSpec strict validate、限定严格文档检查与 `git diff --check` 通过。仓库外样本标识定向扫描零命中；全局 `pipeline_mode` 和变更包 `lifecycle_status: in-progress` 保持不变，未触发延期任务、最终 Review 或 scoped full gate。
- [x] 17A.14 根据用户提供的平航 v1 报告反馈，将与单一 `DeviceInfo` 共享顶层设备作用域的唯一“机主信息” Table 作为该检材持有人来源，只读取明确“用户姓名”并写入 `holder_name`；电话、证件和其他人员字段不得替代姓名，同一作用域无法唯一配对时安全失败。适配器语义版本升级并失效旧缓存，不修改报告目录选择层级。
- [x] 17A.14T 扩展 SYNTHETIC 平航单/多材料 fixture，先证明持有人为空，再覆盖跨中间导航节点的作用域配对、材料顺序、电话排除、重复机主页安全失败、无机主页兼容和依赖清单；仓库外真实报告只作只读脱敏复核。
  - 实现与测试证据（2026-09-12）：适配器语义版本升级为 1.5.0；聚焦用例先以空持有人预期失败，修复后平航适配器 26 passed，平航/报告解析/输入快照/Legacy 投影受影响回归 91 passed。用户指定仓库外样本只读复核命中 1 项检材和 1 项非空持有人，依赖从 5 个增至导航明确选择的 6 个且包含唯一机主信息页；未记录姓名、电话、案件标识或绝对路径，未复制或执行报告内容。
- [x] 17A.15 核对本轮增量与实现并同步现行规格，运行 `npm run verify:quick`、OpenSpec strict validate、限定严格文档检查和 `git diff --check`；保持 `lifecycle_status: in-progress`，不触发延期任务、最终 Review 或 scoped full gate。
  - 收尾证据（2026-09-12）：平航机主信息与检材持有人映射已同步至 change delta、批准规格、设计和 living spec；`npm run verify:quick`、OpenSpec strict validate、限定 strict docs 与 `git diff --check` 通过。限定 strict docs 首次仅因 17A.15 门控尚未勾选而按预期报告 1 项 task-incomplete，门控完成并记录本证据后复跑通过；变更包继续保持 `lifecycle_status: in-progress`。

## 2026-09-13 分支审查反馈与轻量化约束（17A 续）

本轮关联 17A 的原验收范围和核心调用链；修复既有预期，轻量化 Scenario 已按用户确认同步 delta、批准规格与 living spec。归档复用问题是当前候选所带直出归档回归，复用现有发布身份校验，不改写已归档包。包保持 `lifecycle_status: in-progress`，不启动其他延期能力。manual_acceptance: N/A（本轮字段和边界由 SYNTHETIC 自动化覆盖，不涉及版式或界面调整）。

- [x] 17A.16 核实独立审查反馈：核心来源指纹遗漏、祖先链接、诊断文件名暴露、导航语法/重复 ID、机主回退与 Canonical 方向、发布位置摘要绑定；为确认的问题复用现有测试并补充区分度。
- [x] 17A.17 按用户“原报告通常不变、保持轻量化”要求，来源复验只扩展核心文件元数据身份；解析复用已读取快照，既有非核心页面排除规则保持不变。适配器版本升级至 1.6.0。
- [x] 17A.18 完成受影响后端回归、独立复审、verify:quick、限定 strict docs 和 diff 检查，记录最终证据。

初步证据：修复前 13 项合成回归失败；平航输入及发布身份聚焦 42 项通过。额外 Windows junction 回归确认读取报告内容前拒绝祖先链接；读取次数回归确认双检材报告解析及复验各只读取 6 个核心文件、每个一次。材料策略函数复用重命名遗漏的两处调用已经修复，材料策略 18 项通过。

最终代码证据（2026-09-13）：受影响后端 330 项通过，覆盖平航、美亚输入快照、Parser/执行中任务、Canonical/材料/软件/导出门控、工作台及发布身份/归档复用；`verify:quick` 与 OpenSpec strict validate 通过。独立代理按五维复审通过；复审指出的指数数字溢出已以同一解码步骤中的有限值判断修复，随后平航 43 项与 `lint:arch` 通过，审查代理独立确认普通浮点数仍可用。没有引入全量扫描、媒体哈希、后台防篡改机制或新服务层；每次平航解析复用核心快照，不再为识别与解析各读取一次。规格已同步到 `openspec/specs/electronic-inspection-record/spec.md` 的“轻量来源复验和解析依赖复用”场景。限定 strict docs 15 项检查通过（0 drift），`git diff --check` 通过。本次只收敛分支审查反馈，未把便携版真实目标机验收或其他延期项记为完成。

- [x] 17A.19 修复平航导航占位节点误拒绝（2026-09-13，本次增量 Level 1）：仅允许 `viewType: 'undefined'` 且 `rangeCount: -1` 的已确认无数据页节点，保留节点 ID、父子关系和原始页数；其他非正页数、重复 ID、非法语法和被选核心页校验保持不变。复用 17A 的非核心页面排除合同，不新增正式 Requirement/Scenario。
  - 证据：扩展既有 SYNTHETIC 大目录和非法导航用例，修复前 1 failed / 13 passed，修复后聚焦 14 passed；平航适配器、输入快照和报告解析受影响回归 112 passed，`lint:arch` 与 `git diff --check` 通过。用户指定仓库外样本只读复测成功：1 个检材、6 个核心依赖；未修改或复制原报告，未记录真实字段值或路径。manual_acceptance: N/A（无 UI/Word 改动；外部结构已只读复核）。本次导航逻辑及测试修改使先前对应审查结论失效，保持 `lifecycle_status: in-progress`，最终候选收敛后统一复审。

## 2026-09-08 来源目录校验移除反馈

本次增量 workflow_level: 2；关联原 8.4 来源授权模式任务，以本节和修订后的需求6为准。demo-readiness-and-source-guidance 仅承载就绪提示，工作台样式包仅承载视觉反馈，不承载该来源请求合同。manual_acceptance: N/A（界面入口上一轮已移除，本轮由请求和后端自动化覆盖）。

- [x] 移除来源请求模式/令牌、浏览器偏好、后端白名单加载和来源授权分支，保留基础安全和导出授权。
- [x] 合并既有测试，覆盖旧设置失效、外部目录导入/替换、非法目录拒绝及导出令牌边界。
- [x] 核对增量与实现并同步现行规格，完成定向测试、verify:quick 和限定严格文档检查。

验证证据（2026-09-08）：受影响后端 154 passed、前端 26 passed；verify:quick 通过（架构、类型、治理、文档及资产检查）。独立审查发现的规格残留与废弃 JSON 字段覆盖缺口已修复，复审通过。增量与现行规格已同步；限定 strict docs 14 项检查通过，git diff --check 通过。后端首次执行因默认工作台数据库只读失败，使用独立 SYNTHETIC 临时数据根完整重跑后通过。

## 2026-09-13 三种内置报告格式统一适配器边界（17B）

本次增量复用阶段一既定的 `ReportAdapter → CanonicalInspectionCase → InspectionReport` 设计，属于不新增公开输入格式的核心链路重构；保持美亚 legacy、美亚 new、平航 v1 的识别、字段和正式输出语义不变，不切换全局 `pipeline_mode`，不启用任意未知格式发现。

- [x] 17B.1 在 Layer 20 建立可注册的来源适配器契约，将美亚 legacy/new 家族与平航 v1 的探测、版本身份和输入快照构建收口到唯一匹配注册表；解析服务不再直接探测厂商结构，输入依赖保持单次读取和版本化指纹。
- [x] 17B.1T 复用现有 SYNTHETIC legacy/new/平航测试，增加注册身份、唯一匹配、输入快照与读取次数断言，证明三种格式均经相同注册表入口且未知/并列结构安全失败。
- [x] 17B.2 在 Layer 21 建立按 `adapter_id` 注册的 Canonical 投影器，美亚 legacy/new 与平航 v1 均先形成 `CanonicalInspectionCase` 再生成兼容投影；主解析编排只消费适配器能力和投影结果，不再判断厂商枚举，现有硬件、软件、时间和材料顺序保持不变。
- [x] 17B.2T 扩展现有解析/Canonical 回归，覆盖三种 adapter id、字段来源、材料顺序、软件确认和硬件初值，并证明现有公开 DTO 与正式导出合同不回归。
- [x] 17B.3 运行架构检查和受影响后端测试，核对 diff 与既定设计；记录证据并保持 `lifecycle_status: in-progress`，不触发延期 canonical 正式切换、最终 Review 或 scoped full gate。

实现证据（2026-09-13）：三种内置 adapter id 与 Canonical projector 注册一致；解析编排已移除平航/美亚厂商探测分支，美亚 legacy/new 均以完整 DTO 前后等价断言证明兼容，平航继续保留导航材料顺序、专属字段覆盖和中性硬件初值；并发回归证明共享任务沿用开始时选中的适配器且只构建一次快照。最终受影响后端回归 253 passed，架构检查、TypeScript 类型检查、治理测试、OpenSpec 规格检查、OpenSpec strict validate、仓库资产检查和 `git diff --check` 通过；适配器歧义拒绝的突变验证按预期失败，恢复后聚焦用例通过。`verify:quick` 和限定 strict docs 仅因仓库既有 `harness/iteration-guide.md` 指向不存在的 `harness/archive/iterations/` 产生 4 项 broken-link 而停止，本次未修改或补造该无关目录。额外全量后端回归为 1369 passed、3 failed、3 skipped；3 项失败来自本次未修改的既有合同/来源恢复基线：Python/TypeScript `Material` 字段及 `ODD_PHOTO_COUNT` 合同漂移，以及两个旧 `_fingerprint` monkeypatch 未接受现有 `report_fingerprint` 参数。manual_acceptance: N/A（内部解析边界重构，无 UI、Word 版式或真实外部格式变化）。变更包继续保持 `lifecycle_status: in-progress`。

## 2026-09-13 奇安信网页版报告 v1 内置适配（17C）

本增量 `workflow_level: 2`，复用 17B 建立的来源适配器与 Canonical projector 注册边界，正式新增第四种输入格式 `qianxin-web-report-v1`。用户指定目录只作为仓库外只读结构确认和最终脱敏验收输入；测试必须使用重新构造并标记为 SYNTHETIC 的最小报告，不得复制案件、人员、设备标识、媒体、绝对路径或生成输出。变更包保持 `lifecycle_status: in-progress`。

- [x] 17C.1 固化奇安信 v1 的入口/profile/JSONP 签名、核心依赖预算和统一字段映射；明确缺失检材编号不伪造、Android 平台不自动确认手机、媒体和编号明细目录不读取。
- [x] 17C.1T 用最小 SYNTHETIC 单/多检材目录验证固定赋值、安全失败、数字索引顺序、核心文件读取范围和适配器冲突；断言聚焦可区分的业务与安全合同，不按字段机械堆叠。
- [x] 17C.2 在 Layer 20 实现奇安信来源适配器，在 Layer 21 映射 `CanonicalInspectionCase` 并注册第四个 adapter id；主解析编排、现有三格式和正式导出链路不增加厂商分支。
- [x] 17C.2T 验证奇安信案件/送检/材料/设备/标识符/时间/主软件投影及缺失值语义，并以现有三格式回归证明输出不变。
- [x] 17C.3 对用户指定仓库外报告执行只读脱敏验收，输出四格式统一字段能力矩阵；同步 living spec，运行受影响测试、`verify:quick`、OpenSpec strict validate、限定 strict docs、资产与 diff 检查，记录无关基线失败并保持 `lifecycle_status: in-progress`。
- [x] 17C.4 修复合法的大型奇安信导航元数据被旧 2 MiB 读取预算误拒绝且首轮 4 MiB 修复余量不足的问题；以 64 MiB 硬上限覆盖约 17 万个当前密度导航节点，继续保持单文件有界读取、固定 JSONP 赋值和只读取根级核心元数据的安全边界，报告明细和媒体总容量不参与该预算。
- [x] 17C.4T 增加超过 4 MiB 但仍在最终预算内的 SYNTHETIC 导航回归，并对用户指定的仓库外多检材报告执行只读脱敏复验；不得复制或记录案件原值、设备标识和绝对路径。

实现与验收证据（2026-09-13）：新增 `qianxin-web-report-v1@1.0.0`，只读取唯一根入口 HTML、`data_navigation`、`data_report_profile` 和按数字索引排序的 package profiles，统一映射 Canonical 后投影现有 DTO；SYNTHETIC 合同覆盖多检材顺序、空检材编号不伪造、Android 类型待确认、字段来源、主软件确认、时间聚合、核心依赖范围、适配器冲突和 JSONP 安全失败。重复 JSON 属性拒绝逻辑临时突变后聚焦用例按预期 1 failed / 2 passed，恢复后 3 passed。四格式及工作台受影响回归 260 passed；全量后端 1377 passed、3 failed、3 skipped，3 项仍是本次未修改的 Python/TypeScript `Material`/`ODD_PHOTO_COUNT` 合同漂移和两个来源恢复既有基线。用户指定约 780 MB、8212 文件的仓库外报告只读解析成功：单次约 60 ms 构建 Canonical 快照、159–194 ms 完成 `parse_report`，仅记录 4 个核心依赖，识别 1 个材料、案件名称、检查时间、主软件名称/版本、设备型号和有效设备标识；原报告为空的案件编号、送检信息、检材编号及硬件保持为空，Android 类型保持待确认。架构、TypeScript 类型、治理、OpenSpec 规格与 strict validate、仓库资产和 `git diff --check` 通过；`verify:quick` 与限定 strict docs 仅因既有 `harness/iteration-guide.md` 的 4 个 broken-link 停止。未复制、修改或执行真实报告内容，未记录真实案件、人员、设备值或绝对路径；`lifecycle_status` 保持 `in-progress`。

归档前兼容反馈证据（2026-09-15）：用户指定的仓库外多检材报告命中奇安信适配器后，因 3.19 MiB 合法导航元数据超过文件读取层和 JSONP 解码层各自的旧 2 MiB 上限而被误拒绝；首轮 4 MiB 修复余量不足，最终将两层预算同步提高到 64 MiB。按当前样本 8693 个节点的密度估算，新预算约可覆盖 17 万个导航节点；报告明细、图片和媒体总容量不参与该预算，因此 1 TB 级报告不会被总容量误拒绝。实现仍保留流式文件读取上限、固定赋值、重复属性、深度、文件身份和读取期间变化等拒绝边界；超过 4 MiB 的 SYNTHETIC 回归在修改前按预期失败，修改后奇安信聚焦 9 passed、报告输入与解析受影响回归 76 passed，现有超过最终上限的增长拒绝测试继续通过。真实目录只读脱敏复验在约 0.74 秒内完成，适配器仅记录入口、报告 profile、导航和两个 package profile 共 5 个核心依赖，稳定投影 2 项材料且未扫描 8400 个明细目录；源报告未提供的案件名称继续留空待审核。相邻边界审计未发现其他已失配的重复阈值：平航单页文件/JSONP 的 2 MiB 上限当前一致且有明确拒绝合同，陌生报告发现和模板、图片、压缩包上限分别属于独立安全或产品合同，本次不作无样本依据的放宽。`verify:quick` 与限定 strict docs 全部通过；未复制、修改或执行外部报告内容，未记录案件原值、人员信息、设备标识或绝对路径。`manual_acceptance: N/A`（后端解析预算兼容修复，无 UI、Word/PDF 版式或桌面工具变化）；变更包继续保持 `lifecycle_status: in-progress`。

## 2026-09-13 陌生报告发现与 ReportProfile MVP（17D）

本轮启动阶段二的受限 MVP，`workflow_level: 3`。只实现确定性的 JSON/JSONP 结构发现、用户确认后的版本化 Profile 和精确结构复用；不实现 AI 推断、模糊兼容、任意脚本/JSONPath、媒体发现或未确认自动导出。内置四格式必须保持快速路径和现有输出语义。

- [x] 17D.1 定义共享 `ReportProfile`、发现候选、确认请求和来源 DTO；补充 SQLite 版本化存储，确保 Profile 不保存案件字段原值、绝对路径或可执行表达式。
- [x] 17D.1T 复用数据库升级测试并增加一个组合持久化合同，证明 confirmed 版本不可覆盖、draft 不可复用、敏感原值不落库。
- [x] 17D.2 实现有界 JSON/JSONP 结构发现、确定性字段候选和结构指纹；只在内置适配器未命中时调用，适配器冲突安全失败。
- [x] 17D.2T 用少量 SYNTHETIC 组合场景证明发现预算、安全解析、候选证据及“已知四格式零发现调用”；对预算/路径校验核心逻辑做断言区分度验证。
- [x] 17D.3 实现候选确认、confirmed Profile 精确复用、通用 `ReportParseInputSnapshot` 与 Canonical 投影；结构或类型漂移回到待确认，不生成错误正式结果。
- [x] 17D.3T 以首次发现→确认→同结构复用→变体拒绝的端到端合同证明统一字段投影和确认门控，不按字段机械堆叠断言。
- [x] 17D.4 接入工作台本机目录选择与候选确认界面；公共响应不暴露绝对路径，确认成功后才创建案件并进入现有审核链路。
- [x] 17D.4T 验证取消/确认/过期/冲突和已知格式直通交互；人工验收确认候选来源可读、正式导出在确认前不可达。
- [x] 17D.5 运行阶段二受影响架构、类型、后端和前端定向验证，核对四格式输出与性能保护；记录证据并保持 `lifecycle_status: in-progress`，不提前冻结候选或运行最终 Review/full gate。

实现与验收证据（2026-09-13）：陌生报告仅在四个内置适配器返回 `REPORT_ADAPTER_NOT_FOUND` 后进入有界 JSON/JSONP 发现；结构预算限制为 4 层、128 个候选文件、单文件 1 MiB、总计 4 MiB、2048 个目录项、JSON 深度 32 和 8192 个节点，不执行脚本、HTML、附件或媒体。用户显式选择后才写入 SQLite v12 的 confirmed Profile，持久内容只含相对文件、受限数据路径、类型、规则和证据；组合合同证明案件原值/预览不落库、同结构二次保存不覆盖首个版本、draft 不可复用。确认后统一构造 `ReportParseInputSnapshot → CanonicalInspectionCase → InspectionReport`；结构指纹或值类型漂移安全拒绝。

有效断言集中在会改变安全或业务结论的组合场景：已知适配器零 Profile 仓储调用、确认前零案件、确认后多检材统一投影、同结构复用、键漂移拒绝、深度预算拒绝、会话过期、同一 canonical 字段冲突、公共响应无绝对路径，以及确认后工作台建案。深度校验被临时移除时预算用例按预期失败，恢复后通过。Profile 聚焦 5 passed；数据库、控制器与 Profile 受影响回归 84 passed；四个内置格式/解析/Canonical/并发受影响回归 124 passed；前端弹窗、hook 与工作台页面 22 passed。全量后端为 1382 passed、3 failed、3 skipped，3 项与此前基线相同，来自本次未修改的合同检查器和来源恢复测试；全量前端的 6 个失败均位于本次未修改的 `CaseRecordGeneratePage` 引导操作基线，新增及受影响前端用例全部通过。

候选弹窗经 Impeccable 静态检查无发现，并用实际本地浏览器在默认窄屏和 1200×900 桌面宽度完成视觉/交互验收：未选择时确认按钮禁用，选择后显示相对来源与数据路径，按钮可用，滚动区、底部操作和响应式单列/双列布局可见；临时预览文件已删除。架构、TypeScript、治理、OpenSpec 规格与 strict validate、仓库资产和 `git diff --check` 通过；`verify:quick` 与限定 strict docs 仅因既有 `harness/iteration-guide.md` 的 4 个 broken-link 停止。`lifecycle_status` 保持 `in-progress`，不冻结整个候选，也不提前运行最终 Review/scoped full gate。

用户确认该工作属于 Level 3 后冻结候选并启动独立 Review Sub-Agent。第一轮审查结论为驳回：发现器可能读取敏感子树、候选读取存在枚举后替换窗口、确认未校验标量/检材集合基数、竞争确认可能静默复用，并建议绑定 Profile 精确版本及拒绝非有限 JSON 数值。修复后，发现器硬排除附件/媒体/明细/工具/资源/编号数据子树，候选使用枚举身份、祖先链复验、绑定句柄和流式上限读取；映射持久化集合锚点并在确认前验证唯一标量、同源同集合、相同索引和同质类型；同结构仅允许名称与规范化映射完全一致的幂等确认；来源记录 Profile ID + version，解析精确取版本；JSON 拒绝 `NaN`/`Infinity`/`-Infinity`。新增证据只覆盖这些可区分风险：文件替换/增长、祖先替换且外部内容零读取、敏感子树零读取且不影响指纹、标量歧义、跨集合检材、混合类型、竞争确认和版本漂移。修复后 Profile/解析/工作台受影响后端 155 passed，Profile 聚焦 13 passed，弹窗 1 passed，TypeScript 类型检查通过。

最终冻结证据（2026-09-14）：同一独立审查者完成复审，结论通过，MUST FIX 与 SHOULD FIX 均为 0；审查者独立相关后端范围 213 passed。最终来源兼容修复后，Profile/解析/工作台定向范围 164 passed，复审确认精确 Profile、奇安信和平航的来源指纹保护未被绕过，非报告来源恢复既有取消和临时失败语义。随后对齐 TypeScript/Python Canonical `Material` 的持有人、持有人来源和取证起止时间字段；独立聚焦复审再次通过，MUST FIX 与 SHOULD FIX 仍为 0，合同检查及 Profile/奇安信/平航聚焦回归 76 passed。最终门控发现的 6 个引导复核用例已按真实行为修复：仅将文书编号和介质编号纳入可回访的系统预填字段白名单，并以完整操作轨迹断言覆盖文书编号、检材完整性、照片、介质编号、刻录时间和完成态；普通系统识别字段仍不暴露，未以弱化断言绕过。补充归档迭代目录说明后，既有 4 个文档链接漂移清零；受影响前端回归 77 passed，同一审查者最终复审再次通过且无 MUST FIX/SHOULD FIX。`npm run verify:full -- --change extensible-report-template-platform` 使用 D 盘隔离短临时根执行，预检、架构、TypeScript、治理、仓库资产、全仓测试、生产构建和限定 strict docs 全部通过；其中全仓测试 296.6 秒、构建 30.0 秒、限定 strict docs 3.8 秒。C 盘短临时根首次预检因可用空间仅 690 MB 而拒绝执行，属于环境预检且未进入测试。OpenSpec strict validate、仓库资产检查与 `git diff --check` 同步通过。本次冻结候选已达到 scoped full gate 要求；变更包因阶段二/三延期任务继续保持 `lifecycle_status: in-progress`，不误记为全部路线或归档完成。

## 2026-09-15 超大报告元数据预算复核（17E）

本次反馈与 17A、17C、17D 的报告识别核心调用链强关联，作为 `workflow_level: 2` 继续原包。此前“相邻阈值没有失配”的结论在用户明确存在 1 TB 级报告并要求继续审计后被新的规模证据推翻：安全预算仍须存在，但只能约束实际扫描和解析的核心元数据，不能把已排除目录、无关超大候选或报告总容量当成格式不支持。该反馈修改了冻结后的核心输入边界，先解冻并保持 `lifecycle_status: in-progress`；最终候选收敛前不复用旧 Review 结论。

- [x] 17E.1 更新报告规模合同：陌生报告发现将“全部已扫描目录项安全上限”与“相关候选目录项上限”分离，被排除的编号/媒体/明细子树不消耗候选预算；单个超大候选文件跳过而不否定同目录其他安全候选。平航导航与普通核心页使用独立字节预算，奇安信入口 HTML 与导航均保留足以覆盖已观察大报告结构的独立有界预算；报告总容量继续不参与初始化判定。
- [x] 17E.1T 先扩展现有 SYNTHETIC 回归，证明超过 2048 个被排除编号目录、一个超大无关 JSON、超过旧 1 MiB 的合法陌生元数据、超过旧 2 MiB 的平航导航和超过旧 4 MiB 的奇安信入口 HTML 在旧实现上产生可区分失败，同时保留真正无界枚举、超出最终核心预算、路径/链接和可执行载荷的拒绝测试。
- [x] 17E.2 在 Layer 20 实施最小预算修复；由于成功解析后的字段语义、依赖集合和投影结果不变，保持内置适配器版本以避免现有来源仅因放宽读取预算被误判变化。固定赋值、重复属性、有限数值、深度、文件身份、读取期间变化和唯一匹配安全边界保持不变。
- [x] 17E.3 核对 delta 与最终实现并同步 living spec，运行报告 Profile、平航、奇安信、来源和解析受影响测试，以及 `lint:arch`、`typecheck`、`verify:quick`、限定 strict docs 和 `git diff --check`；不启动与本反馈无关的延期能力。manual_acceptance: N/A（后端输入预算修复，无 UI、Word/PDF 版式或桌面工具变化）。

实现与验证证据（2026-09-15）：五个聚焦回归在修改前稳定 `5 failed`，分别区分被排除编号目录误耗预算、合法 2 MiB 陌生元数据、超大无关候选连带拒绝、平航导航复用普通页面 2 MiB 上限和奇安信入口 HTML 4 MiB 上限。实现后，陌生发现使用 65,536 个全部扫描项与 2,048 个相关候选项两级边界，单文件/总读取预算调整为 16/64 MiB，超大单候选跳过；平航仅将导航字节/字符预算独立为 64 MiB，普通核心页仍为 2 MiB；奇安信入口和导航均为 64 MiB。新增总扫描上限回归继续证明无界无关目录项会停止。报告 Profile、平航、奇安信聚焦 82 passed，加入报告输入和解析后的受影响范围 149 passed；`lint:arch`、`typecheck`、`verify:quick`、change/living OpenSpec strict 与 `git diff --check` 通过。适配器版本保持不变，避免已经成功登记的来源因纯接受范围放宽失效。用户先前指定的仓库外目录在本轮复测时已不存在，因此只记录“未复测”，不复用旧实样结果作为本次证据；未搜索、复制或记录其他案件数据。

## 2026-09-16 平航设备品牌型号显示回归（17A 续）

本次反馈恢复现行“设备品牌 + 具体型号”合同，属于 Level 1 回归修复；继续关联 17A，不新增 Requirement/Scenario，不改变美亚及其他格式。用户指定报告仅作仓库外只读脱敏复核，测试使用重新构造并标记为 SYNTHETIC 的字段组合。

- [x] 17A.20 平航 v1 设备名称继续取“手机品牌”作为品牌，并在“手机内部型号”与营销“手机型号”同时存在时优先内部型号；升级适配器语义版本以失效旧缓存，增加可区分的合成回归并运行受影响验证。manual_acceptance: N/A（后端字段映射修复，无 UI 或文书版式变化）。
  - 证据：新增 SYNTHETIC 字段组合先稳定失败，明确旧实现会把营销“手机型号”误作具体型号；修复后聚焦用例通过，平航、通用解析、输入快照和兼容投影受影响回归共 120 passed，`lint:arch`、`typecheck` 与 `git diff --check` 通过。平航适配器升级至 1.7.0，确保旧来源缓存失效。用户指定仓库外报告只读脱敏复核命中 1 个检材，品牌和内部型号可用，最终设备名称为用户确认的 `OPPO PKV110`；未复制、修改或执行报告内容，也未生成正式文书。

## 2026-09-16 平航外层多报告包聚合（17A 续）

本次增量 workflow_level: 2；继续复用 17A 的平航 v1 安全读取、Canonical 投影、来源指纹和归档根合同。稳定先例为奇安信同一来源内多个 package profile 的一次快照聚合，但平航保持自身 JSONP、核心页和子报告边界，不引入通用多来源案件模型。manual_acceptance: 仅对用户指定仓库外样本执行只读脱敏解析复核；不复制报告、不记录案件/人员/设备值、不生成正式文书。

- [x] 17A.21 更新 delta 与设计，定义同一平航来源家族的外层多包布局、256 个直接候选包上限、案件/软件一致性、检材编号唯一性、自然顺序、外层依赖与整体失败合同。
- [x] 17A.21T 扩展既有 SYNTHETIC 平航回归，先证明外层双包当前无法识别，再覆盖聚合快照、工作台来源登记、案件冲突、重复检材、损坏候选、直接子目录边界、来源复验和现有单包身份不回归。
  - 证据：新增 bundle 聚焦用例在实现前稳定 `3 failed / 1 passed`，失败均为外层目录 `REPORT_ADAPTER_NOT_FOUND`；实现后平航聚焦 57 passed，加入报告输入注册表、通用解析、Canonical/Legacy 投影、材料/软件/导出门控和工作台服务后的受影响范围 197 passed。读取计数证明双包解析和复验各只打开 12 个已选核心依赖且每个一次，现有单包仍为 6 个且每个一次。
- [x] 17A.22 在现有 `PinghangReportSourceAdapter` 来源家族内增加版本化 bundle 布局，逐包复用现有 `parse_pinghang_report`，合并为单一 `ReportParseInputSnapshot` 并接入现有平航 Canonical projector；完成受影响验证、living spec 同步、`verify:quick`、限定 strict docs 与 diff 检查。
  - 实现：新增 `pinghang-mobile-multipath-bundle-v1@1.0.0`，仅枚举外层目录的直接子目录，最多接受 256 个可识别报告包；每包只调用一次既有解析器，并在案件与软件信息一致、检材编号全局唯一后按自然序合并。依赖路径、结构指纹和归档根均相对外层来源保留，既有单包身份和投影路径不变。
  - 验证：仓库外真实样本只读复核识别为 2 个检材，案件、软件、检查时间和全部检材必填信息完整；检测约 0.34 秒、解析约 0.42 秒，未复制或修改样本，未生成正式文书。受影响自动化 197 passed，`verify:quick`、OpenSpec strict、限定 strict docs 与 `git diff --check` 均通过。

## 2026-09-16 正文固定行距调整（12.9）

本次反馈只将当前内置模板 27 个有文字的正文段落从固定 26 磅调整为固定 28 磅，并同步无 Manifest 兼容导出；3 个正文与附件之间的空白占位段落、附件 1.5 倍行距、字体、字号、缩进、页边距、表格和分页锚点保持不变。属于 Level 1 版式调整，继续关联 current-template-v1，不新增 Requirement/Scenario，不开放前端行距配置。

- [x] 12.9 发布新的内置模板版本，将可见正文固定行距从 520 twips 调整为 560 twips，同步兼容导出的 `26pt` 为 `28pt`，并迁移旧内置版本引用；保持附件摘要留白常量和其他版式结构不变。
- [x] 12.9T 增加模板 XML 范围、兼容导出行距和内置版本迁移回归，运行模板/生成定向测试、架构与类型检查、`officecli validate` 和 `git diff --check`。
  - 证据：两个新增断言在旧实现上稳定 `2 failed`，分别区分正式模板 520 twips 与兼容导出 `26pt`；修复后模板、包指纹、Profile、注册迁移、兼容生成和正式填充链路 `110 passed, 1 skipped`。当前模板发布为 `electronic-inspection-record@1.0.9`，指纹为 `E10220DAAD8F0447519924F42B10757EF21098E54E6E422F0F14838050A955C0`；与旧资产逐部件对比仅 `word/document.xml` 变化，XML 回归确认 27 个有文字正文段落为固定 560 twips、3 个空白留距段落仍为固定 520 twips、40 个附件相关 1.5 倍行距节点仍为 `360 + auto`。普通和长文本 SYNTHETIC DOCX 均生成成功并通过 `officecli validate`；`lint:arch`、`typecheck`、`npm run pre-commit`、仓库资产检查与 `git diff --check` 通过。
- [ ] 12.9M 使用 Microsoft Word/PDF 复核普通与长文本 SYNTHETIC 输出的分页、裁切和附件起页。Computer Use 可启动本机 Word，但连续两次窗口状态读取均返回 `0x80004002（不支持此接口）`，未取得可靠视觉证据，不伪报通过。 [DEFERRED]

## 2026-09-17 双 IMEI 设备类型兜底（17F）

本次增量 `workflow_level: 2`；继续复用当前包的 `MaterialDisplayPolicy`、四种内置报告适配器、ReportProfile Canonical 投影和统一 ExportGate。稳定先例为既有报告明确类型的 `confirmed_by_report` 流程；双 IMEI 仅作为缺少可靠类型时的受控兜底，不覆盖用户确认、明确平板或报告类型冲突。`manual_acceptance: N/A`（业务分类、门控和来源提示均由自动化覆盖，无 Word/PDF 版式或桌面工具变化）。

- [x] 17F.1 同步 delta、批准规格与设计：IMEI1/IMEI2 均为有效、不同的 15 位数字时默认推断 `phone`，保留 `MATERIAL_TYPE_INFERRED_FROM_DUAL_IMEI` 诊断并以 `confirmed_by_report` 直接通过类型导出门控；单个、非法、重复 IMEI、明确平板及类型冲突不得触发或覆盖。
- [x] 17F.1T 复用材料策略、报告解析、Canonical、审核摘要和结构化编辑器现有测试，增加“双 IMEI 推断无需人工确认即可通过 ExportGate”的可区分回归；测试数据必须明确标记为 SYNTHETIC。
- [x] 17F.2 在统一材料策略层应用兜底，并让美亚 legacy/new、平航、奇安信和 confirmed ReportProfile 保留明确类型优先级与冲突；审核界面区分“根据双 IMEI 推断”和“报告明确字段候选”，旧缓存通过版本身份失效。
- [x] 17F.3 核对实现并同步 living spec，运行受影响后端/前端测试、`lint:arch`、`typecheck`、`verify:quick`、限定 strict docs、OpenSpec strict validate 和 `git diff --check`；保持 `lifecycle_status: in-progress`，不触发延期任务、最终 Review 或 scoped full gate。

实现与验证证据（2026-09-17）：统一材料策略以两个有效、不同的 15 位 IMEI 生成 `phone`、`confirmed_by_report` 和 `MATERIAL_TYPE_INFERRED_FROM_DUAL_IMEI`；用户确认、明确平板和类型冲突优先。审核编辑器区分推断来源，ExportGate 聚焦回归证明该状态无需人工二次确认即可通过检材类型门控。关闭推断的进程内突变使新增用例按预期失败，恢复后材料策略 27 passed；四格式解析、Canonical、缓存版本和归档关联的受影响后端 259 passed，前端审核摘要、结构化编辑器和文书内容投影 38 passed。`lint:arch`、`typecheck`、`verify:quick`、OpenSpec strict validate、living spec 校验与 `git diff --check` 通过；限定 strict docs 首次仅因本任务尚未勾选而按预期报告 1 项 `task-incomplete`，勾选后复跑为 15 项检查、0 drift。变更包保持 `lifecycle_status: in-progress`，不启动延期任务、最终 Review 或 scoped full gate。

## 2026-09-17 奇安信 iOS/Android 标识字段归一（17G）

本次增量 `workflow_level: 2`；继续复用 17C 的奇安信 package profile 映射和 17F 的双 IMEI 类型兜底。用户指定仓库外报告仅用于只读、脱敏确认 iOS 与 Android 字段形态；自动化只使用 SYNTHETIC 数据。范围限定为已观察到的 iOS/Android `info.IMEI1/IMEI2`、`deviceInfo.IMEI`、`序列号`和`Mtp序列号`，不增加鸿蒙字段别名或类型推断。`manual_acceptance: N/A`（来源字段归一与分类结果由自动化和脱敏解析覆盖，无 UI、Word/PDF 版式或桌面工具变化）。

- [x] 17G.1 补充 delta，明确 info 分槽 IMEI 优先、deviceInfo 单/双 IMEI 有界回退、iOS/Android 序列号别名及 Android 单 IMEI 继续待确认；不扩展鸿蒙范围。
- [x] 17G.1T 先增加可区分的 SYNTHETIC iOS/Android 回归，证明旧实现会丢失 deviceInfo 中以逗号分隔或带尾部分隔符的有效 IMEI。
- [x] 17G.2 在奇安信 Layer 20 适配器内完成稳定去重和缺失槽位回填，提升适配器版本以使旧来源缓存失效；不得改变显式 info 值优先级或全局材料分类规则。
- [x] 17G.3 对用户指定目录执行只读脱敏复验，核对实现并同步 living spec；运行奇安信及受影响报告测试、`verify:quick`、限定 strict docs、OpenSpec strict validate 和 `git diff --check`，保持 `lifecycle_status: in-progress`。

实现与验证证据（2026-09-17）：新增 SYNTHETIC iOS/Android 组合回归在旧实现上按预期 `1 failed`，可区分 iOS 设备层第二个 IMEI 与 Android 尾部分隔符单 IMEI 的丢失；适配器现按 `info.IMEI1/IMEI2` 槽位优先，从 `deviceInfo.IMEI` 最多提取两个稳定去重的 15 位候选补齐缺失槽位，并继续统一 `序列号`/`Mtp序列号`。适配器版本提升为 `qianxin-web-report-v1@1.2.0`，未修改全局材料分类；修复后奇安信聚焦 `12 passed`。用户指定仓库外报告只读脱敏复验仍只读取 5 个核心依赖并投影 2 项材料：iOS 保持双 IMEI 推断手机，Android 保持单 IMEI 待确认；未记录案件、人员、设备标识或绝对路径。最终行为已同步 living spec；`npm run verify:quick`、OpenSpec strict validate 与 `git diff --check` 通过，限定 strict docs 首次仅因 17G.3 尚未勾选而按预期报告 1 项 `task-incomplete`。本增量不包含鸿蒙字段或规则，变更包保持 `lifecycle_status: in-progress`，不触发延期任务、最终 Review 或 scoped full gate。

## 2026-09-18 奇安信 iOS 产品类型显示名（17H）

本次增量 `workflow_level: 2`；继续复用 17C/17G 的奇安信 package profile 映射和现有 Word 检材显示策略。用户确认 Android 的品牌加型号展示正确，因此 Android 映射必须保持不变；仅修复 iOS 将 Apple 销售料号误作 Word 设备字段的问题。测试使用 SYNTHETIC 字段组合，仓库外报告只作只读脱敏复验。`manual_acceptance: N/A`（来源字段归一和 Word 展示输入由自动化及脱敏投影覆盖，无模板版式变化）。

- [x] 17H.1 补充 delta，规定 iOS 优先使用清理后的`产品类型`、仅移除末尾 Apple 硬件标识括号，并在缺失时回退设备名称和型号；Android 品牌与型号映射保持不变。
- [x] 17H.1T 扩展现有奇安信 iOS/Android 合成回归，先证明旧实现仍把 iOS `型号`销售料号投影为 Word 设备型号，同时断言 Android 品牌和型号不回归。
- [x] 17H.2 在奇安信 Layer 20 适配器内实现受控 iOS 产品类型规范化并提升适配器版本；不修改 Canonical、通用 Word 渲染器或 Android 分支。
- [x] 17H.3 对用户指定目录执行只读脱敏复验，同步 living spec，运行奇安信及受影响报告测试、`verify:quick`、限定 strict docs、OpenSpec strict validate 和`git diff --check`；保持`lifecycle_status: in-progress`。

实现与验证证据（2026-09-18）：扩展现有 SYNTHETIC iOS/Android 回归后，旧实现按预期 `1 failed`，且唯一差异是 iOS 仍将销售料号投影为设备型号，Android 品牌与型号断言保持通过。适配器现仅在 `检材平台=iOS` 时优先读取 `deviceInfo.产品类型`，受控移除末尾 iPhone/iPad/iPod 硬件标识括号，并按产品类型、设备名称、型号顺序回退；普通产品名括号不被删除，Android 分支未变，适配器版本提升为 `qianxin-web-report-v1@1.3.0`。修复后奇安信聚焦 `15 passed`。用户指定仓库外报告只读脱敏复验读取 5 个核心依赖并投影 2 项材料：1 项 iOS 型号等于清理后的预期产品名且不含硬件标识，1 项 Android 品牌与型号均保持非空；未记录案件、人员、设备标识或绝对路径。最终行为已同步 living spec；`npm run verify:quick`、OpenSpec strict validate 与 `git diff --check` 通过，限定 strict docs 首次仅因 17H.3 尚未勾选而按预期报告 1 项 `task-incomplete`。本增量不包含鸿蒙字段或规则，变更包保持 `lifecycle_status: in-progress`，不触发延期任务、最终 Review 或 scoped full gate。

## 2026-09-18 奇安信 iOS 设备类别分类（17I）

本次反馈增量 `workflow_level: 2`；真实报告仅作只读脱敏字段位置确认，自动化使用 SYNTHETIC 数据。范围限定为 iOS `deviceInfo.设备类别`对手机/平板分类的优先输入，不修改产品类型显示名、Android 字段映射或全局材料分类词表。`manual_acceptance: N/A`（来源分类输入与结果由自动化和脱敏投影覆盖，无 UI、Word/PDF 版式或桌面工具变化）。

- [x] 17I.1 补充 delta，规定 iOS `设备类别=iPhone/iPad`分别优先确认为手机/平板；缺失时沿用既有规则，Android 不受影响。
- [x] 17I.1T 新增可区分的 SYNTHETIC iPhone/iPad/Android 回归，先证明旧适配器未读取 iOS `deviceInfo.设备类别`。
- [x] 17I.2 在奇安信 Layer 20 适配器内实现 iOS 设备类别优先映射并提升适配器版本；不修改统一材料分类器。
- [x] 17I.3 对用户指定目录执行只读脱敏复验，同步 living spec，运行奇安信测试、`verify:quick`、限定 strict docs、OpenSpec strict validate 和`git diff --check`；保持`lifecycle_status: in-progress`。

实现与验证证据（2026-09-18）：新增 SYNTHETIC iPhone/iPad/Android 分类回归在旧实现上按预期 `2 failed, 1 passed`，证明 iOS 仍被较低优先级字段错误覆盖，而 Android 对照行为未变化。适配器现仅对 `检材平台=iOS` 优先投影 `deviceInfo.设备类别`，缺失时继续使用既有明确类型与平台回退；统一材料分类器未修改，适配器版本提升为 `qianxin-web-report-v1@1.4.0`。修复后聚焦回归 `3 passed`、奇安信全量 `18 passed`。用户指定仓库外报告只读脱敏复验读取 5 个核心依赖并投影 2 项材料：iOS 来源类型为 iPhone 且确认为手机，Android 来源类型保持 Android 且继续待确认；未记录案件、人员、设备标识或绝对路径。最终行为已同步 living spec；`npm run verify:quick`、OpenSpec strict validate 与 `git diff --check` 通过，限定 strict docs 首次仅因 17I.3 尚未勾选而按预期报告 1 项 `task-incomplete`。本增量不包含鸿蒙字段或规则，变更包保持 `lifecycle_status: in-progress`，不触发延期任务、最终 Review 或 scoped full gate。

## 2026-09-18 平航 iOS 手机型号显示（17J）

本次反馈增量 `workflow_level: 2`；继续复用 17A 的平航 v1 字段映射和 17A.21 的外层多报告包聚合。用户指定仓库外报告仅作只读脱敏字段确认，自动化使用 SYNTHETIC iOS/Android 组合。范围限定为平航 iOS 设备显示名与型号来源，不修改 Android、其他报告格式或通用显示规则。`manual_acceptance: N/A`（来源字段映射和最终展示输入由自动化及脱敏投影覆盖，无模板版式变化）。

- [x] 17J.1 补充 delta，规定平航 iOS 直接使用“手机型号”，缺失时回退既有品牌与内部型号规则；Android 保持“手机品牌 + 手机内部型号”。
- [x] 17J.1T 扩展现有平航 SYNTHETIC 回归，先证明旧适配器对 iOS 仍优先内部型号且拼接品牌，同时断言 Android 对照行为不回归。
- [x] 17J.2 在平航 Layer 20 适配器内实现 iOS 专用字段优先级，并提升单报告与 bundle 适配器版本以失效旧来源缓存；不修改通用显示层。
- [x] 17J.3 对用户指定目录执行只读脱敏复验，同步 living spec，运行平航及受影响报告测试、`verify:quick`、限定 strict docs、OpenSpec strict validate 和 `git diff --check`；保持 `lifecycle_status: in-progress`。

实现与验证证据（2026-09-18）：新增 SYNTHETIC iOS 回归在旧实现上按预期 `1 failed, 1 passed`，唯一失败证明 iOS 仍错误优先内部型号，Android 对照行为保持通过。平航适配器现仅在材料页明确为 iOS 且“手机型号”非空时，将该字段直接投影为设备显示名与型号并移除展示用品牌前缀；缺失“手机型号”时回退既有品牌与内部型号，Android 分支不变。单报告适配器提升为 `pinghang-mobile-multipath-v1@1.9.0`，bundle 提升为 `pinghang-mobile-multipath-bundle-v1@1.2.0`。修复后聚焦 `3 passed`、平航全量 `59 passed`、报告输入与解析受影响范围 `68 passed`。用户指定仓库外 bundle 只读脱敏复验识别 2 项材料：Android 仍保留品牌并组合内部型号，iOS 最终设备显示等于面向用户的手机型号且无品牌前缀；未记录案件、人员或设备标识值，未复制或修改来源报告。当前工作区 `verify:quick` 的架构阶段通过，但两个正在运行的项目开发服务器占用既有 `shared/dist`、`frontend/dist` 增量产物，使标准 TypeScript 阶段以 `EPERM` 停止；未擅自终止用户进程。标准 `npm run typecheck` 在同步当前跟踪文件并隔离构建输出的临时 detached worktree 中通过；当前工作区的治理测试、OpenSpec living specs 校验、文档 quick、仓库资产检查分别通过，限定 strict docs 为 15 项检查、0 drift，OpenSpec strict validate 与 `git diff --check` 通过。变更包保持 `lifecycle_status: in-progress`，不触发延期任务、最终 Review 或 scoped full gate。

## 2026-09-18 美亚 Apple 品牌检材类型优先级（17K）

本次反馈增量 `workflow_level: 2`；继续复用 17F 的统一材料分类与导出门控。美亚报告的“设备类型=手机”不能可靠区分 iPhone 与 iPad，因此只将规范化后精确为 `iPhone`/`iPad` 的“手机品牌”作为 Apple 类型优先事实；明确平板和类型冲突继续保持原保护，双 IMEI 继续作为手机推断，报告“设备类型=手机”降为最后一个自动候选。测试仅使用 SYNTHETIC 字段组合。`manual_acceptance: N/A`（后端分类优先级和诊断由自动化覆盖，无 UI、Word/PDF 版式或桌面工具变化）。

- [x] 17K.1 更新 delta、批准规格与设计，明确人工确认 → Apple 手机品牌 → 明确平板/类型冲突 → 双 IMEI → 设备类型手机 → 待确认的优先级。
- [x] 17K.1T 扩展现有材料策略回归，先证明 `手机品牌=iPad + 设备类型=手机` 会被旧实现误判，并覆盖 iPhone、双 IMEI 优先诊断、设备类型手机最终兜底及非 Apple 品牌不误命中。
- [x] 17K.2 在统一材料策略层实现优先级，不修改美亚字段解析、前端或渲染器；核对美亚 legacy/new 兼容投影。
- [x] 17K.3 同步 living spec，运行材料策略与美亚受影响测试、`verify:quick`、限定 strict docs、OpenSpec strict validate 和 `git diff --check`；保持 `lifecycle_status: in-progress`。

实现与验证证据（2026-09-18）：新增 SYNTHETIC Apple 品牌与优先级回归在旧实现上按预期 `3 failed`，分别证明 iPad 被“设备类型=手机”误判、Apple 品牌缺少独立诊断，以及双 IMEI 未先于手机类型候选。统一材料策略现按人工确认、精确 Apple 手机品牌、明确平板/类型冲突、双 IMEI、设备类型手机、待确认的顺序分类，规则身份提升为 `device_type_evidence_v3`；非精确 Apple 品牌不触发，缺少来源标记的 legacy 报告字段继续兼容，显式 `legacy_display` 仍不作为类型事实。修复后材料策略聚焦 `31 passed`，加入美亚 legacy/new 输入、Parser、Canonical 与工作台后的受影响后端 `170 passed`。`lint:arch`、前端 TypeScript、共享 TypeScript 的等价无输出检查、治理测试、living spec、快速文档和仓库资产检查通过；标准 `verify:quick` 在架构阶段通过后，因现有 Node 进程占用 `packages/shared/dist` 的声明映射而以 `EPERM` 停止，沙箱外重试结果相同，未擅自终止用户进程。OpenSpec strict validate 通过；限定 strict docs 首次仅因 17K.3 尚未勾选而按预期报告 1 项 `task-incomplete`，勾选后复跑。变更包保持 `lifecycle_status: in-progress`，不触发延期任务、最终 Review 或 scoped full gate。
