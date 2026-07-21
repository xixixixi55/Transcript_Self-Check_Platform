# Implementation Tasks: extensible-report-template-platform

本清单对应根目录 `spec.md` 和 `design.md`。当前 38/48 项已完成。第一批基础实现（0.1、1.1、1.2、2.1、2.2、3-13 及其测试任务）已完成并验证。14（Shadow 回归）、15（人工 Word 验收）、16（canonical 切换）和 17（阶段二/三接口预留）保持未完成。阶段二/三只保留契约和扩展点，不把通用能力纳入阶段一门槛。

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

- [x] 2.1 实现集中 `pipeline_mode = legacy | shadow | canonical` 的运行时配置和 Shadow orchestration。输入：旧管线结果、canonical case、plans、隔离 staging manifest；输出：旧管线唯一正式输出和新管线比较输入；验收：legacy 只跑旧管线，shadow 不产生第二份正式 Word，canonical 当前基础层显式保持未启用。
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

## 7. ArchivePlanner（Layer 2/21）

- [x] 7.1 实现纯函数 `ArchivePlanner`，生成只含预计方案的 `ArchivePlan`。输入：案件名、源目录逻辑大小和策略；输出：4GB/22GB/45GB 档位、预计卷数、十进制容量、`maxReplanAttempts=2`；验收：4GB最多2卷、22GB最多2卷、45GB最多3卷，超过135GB预先阻止。
- [x] 7.1T 增加 8GB、8GB+1、44GB、44GB+1、135GB、135GB+1 边界测试；验收：不调用 WinRAR 即可验证档位和上限。

## 8. WinRAR Executor 及最终 ArchiveManifest（Layer 20/21）

WinRAR 缺失或不可调用是明确阻断项：允许上传、解析、审核和编辑，禁止自动压缩和最终正式导出，不生成 `ArchiveManifest`，不降级 ZIP，并返回可操作的安装/调用错误。

- [x] 8.1 实现 `WinRarExecutor`、`ArchiveValidator` 和 `ArchiveManifestAssembler`。输入：ArchivePlan、WinRAR staging 结果和 DiscSequence；输出：最终不可变 `ArchiveManifest`；验收：manifest 至少含实际文件名、实际大小、MD5、分卷序号、光盘容量、光盘编号、刻录日期和连续性校验结果；附件一/三渲染仍由后续任务负责。
- [x] 8.1T 增加 mock/真实小 fixture 测试，覆盖 `-v...b`、`.partN.rar`、跳号、卷数、大小、MD5、连续性和 staging 清理；验收：预计文件名/大小/卷数不能进入最终 Manifest。
- [x] 8.2 实现实际结果不符合计划时的有限重规划：最多两次重试，重试仍失败返回明确错误且不提交归档/Word。输入：执行结果与 ArchivePlan；输出：最终 manifest 或阻止错误；验收：4→22→45 的升级和耗尽路径可回归。
- [x] 8.2T 增加压缩比导致少卷、超卷、无下一档和重试耗尽测试；验收：不会静默降级 ZIP 或自动回退 legacy。
- [x] 8.3 实现归档输入双轨授权与不透明 `archive_context_id` 生命周期：`UPLOAD_BASE` 加 `BIJI_ALLOWED_INPUT_ROOTS` 只允许具体案件目录；根目录外普通 `report_dir` 拒绝；精确目录令牌仅保留为受控本机桥接预留，不提供普通 API 发令牌；后续规划、执行、Manifest 和 DOCX 只接受上下文标识；上下文过期、输入变化、并发和服务重启行为返回稳定代码。
- [x] 8.3T 增加固定根目录、前缀相邻目录、大小写、相对/穿越、链接/reparse、UNC/设备路径、输入输出重叠、精确授权令牌、上下文摘要/过期/并发/清理、解析接口稳定错误码和前端提示测试；验收：公共响应和错误不包含完整本地路径，原始案件不会被清理。

8.3/8.3T 的完成边界：本轮完成固定根目录生产能力、精确目录授权安全模型/令牌验证/拒绝边界及其自动化测试；未完成且不得宣称完成的是本机目录选择器或可信桌面桥接签发入口，以及精确授权端到端人工验收。两项未接线能力不另增本轮任务计数，保留为后续工作边界。

## 9. 附件一页面计划（Layer 21）

附件一固定手写行是甲方模板的最后结束区域，不属于动态检查人员渲染；正文仍保留有序 `InspectorSnapshot[]`。

- [x] 9.1 实现 `Attachment1Plan`，只接收 final ArchiveManifest。输入：manifest、报告来源/工具和模板 Profile；输出：第一页标题、后续页无标题、每页完整来源/提取方法、最后页保留模板固定手写行所需容量。`inspector_final` 是历史内部名称，当前语义为固定手写行最终页（不填充 InspectorSnapshot，不生成动态检查人员框）；建议后续重命名为 `handwritten_final` 或 `signature_final`。验收：行数严格等于 manifest 卷数，不生成 `INSPECTOR_BLOCK_OVERFLOW`。
- [x] 9.1T 增加 1/2/4/5/8/9 卷边界、固定手写行复制、动态人员仅正文、标题/清单文字可见次数和无附件二章节测试；验收：不读取 ArchivePlan 或原始目录。

## 10. 附件二图片页面计划（Layer 21）

0 张图片不生成附件二页面；现有图片 renderer 的回归范围确认有效图片章节独立起页、附件三仍显示“附件3”和关系完整性；本轮扩展为每页最多4张，2张组成同一居中图片组，4张按上两张/下两张上下对齐，超过4张继续分页。偶数门禁表达每个检材需正反两张图片；审核后的检材顺序与图片顺序一一对应，每两张图片绑定一个检材，并在该图片对下方显示对应文字。计划输入必须是显式 `photo_groups`，Renderer 不得从扁平图片数组位置或文件名猜测归属。

- [x] 10.1 实现 `Attachment2PagePlan` 和 `MaterialPhotoGroup`，支持零张兼容、任意正偶数、每页最多4张、每页最多两个检材组、2张组成同一居中图片组、4张按上两张/下两张上下对齐、每组恰好两张审核后的有序图片、5.64cm×7.52cm contain 槽和稳定图片顺序。输入：审核后的显式 `photo_groups` 映射；输出：页面/检材组/布局/槽位/当前页检材编号/安全显示名计划；验收：奇数、组内图片数非法、缺失归属、重复归属、顺序交叉或图片组与检材数不一致时以稳定错误码直接阻止导出。
- [x] 10.1T 增加 0/1/2/3/4/5/6/8/10 张、1/2/3/4/5 个检材组、组内顺序、跨组交叉、缺失/重复 material_id、空 material_number、横图/竖图/方图/超尺寸图、损坏图片、比例完整显示、固定网格、关系和分页衔接测试；验收：不裁剪、不拉伸、2张在整宽居中单元格中组成图片组并在下方显示对应检材文字、4张为上两张/下两张2×2表格且每行图片下方有对应检材文字、检查结果仅显示当前页检材编号、无半成品 DOCX。

## 11. 附件三页面计划（Layer 21）

- [x] 11.1 实现 `Attachment3Plan`，只接收 final ArchiveManifest。输入：manifest 和 DiscSequence；输出：一卷一页、第一页显示“附件3”、每页五行上下元数据、每页对应实际文件/MD5/光盘号/刻录日期和底部光盘说明；验收：不重新扫描目录或计算卷列表。
- [x] 11.1T 增加一卷、三卷、重规划后 manifest 绑定、分卷日期和附件一/三 partId 一致性测试；验收：只有第一页有标题、每页底部编号与当前 part 一致且页面数量等于 manifest 卷数。

## 12. current-template-v1 受控渲染（Layer 21）

Renderer 当前正式渲染输入为 `InspectionReport` 兼容数据 + `ArchiveManifest` + `AttachmentPlan` + `current-template-v1` TemplateProfile。`DocumentRenderPlan` 是后续统一渲染合同目标，当前尚未完成生产实现。

- [x] 12.1 建立固定 `current-template-v1` TemplateProfile 和资产 hash/anchor 检查；实现当前 DOCX Renderer 对正文结构化检查人员字段、固定手写行、表格、VML、图片、章节独立起页和普通分页的受控扩展。输入：canonical、final manifest、三类 page plan、固定模板；输出：唯一正式 DOCX；验收：阶段一不实现通用设计器、DSL、任意 DOCX 自动绑定、可视化编辑或无标记识别。

已完成：AttachmentPlan 和 TemplateProfile 基础设施。未完成：统一 `DocumentRenderPlan` 类型、生产构造、Renderer 只消费 RenderPlan。
- [x] 12.1T 增加模板 ZIP/XML、资产漂移、VML 宿主段落、关系、PAGE/NUMPAGES、`updateFields=true`、章节分页、固定手写行、摘要 manifest 计数和页面计划渲染测试；验收：固定 Profile 之外的模板被阻止，manifest/renderer 错误不回退 legacy。

## 13. 全黑字体策略（Layer 21）

- [x] 13.1 在受控 renderer 中统一正文、表格、页眉页脚、VML 文本框和动态内容字体为黑色，不改变 VML/边框/图片背景结构。输入：模板 XML 和 render plan；输出：黑色字体 DOCX；验收：黑色策略不由业务模型提前拼接文字实现。
- [x] 13.1T 增加 XML 颜色、VML、表格、页眉页脚和结构保留测试；验收：没有动态彩色文字、空白页或奇偶页分节符回归。

## 14. 新旧报告与双管线回归（Layer 20/21/22）

Shadow 回归只比较新旧结构化结果和非执行性归档投影；测试不得触发真实第二次 WinRAR 压缩或产生第二份正式文书。

- [ ] 14.1 将现有新旧报告 fixture 接入 legacy/shadow/canonical 三模式，保留已验收解析优先级和旧前端 DTO。输入：脱敏合成旧/新报告；输出：解析/投影/plan/比较结果；验收：真实案件、人员、IMEI、序列号不进入自动化 fixture。
- [ ] 14.1T 运行 parser、service、controller、frontend 和 renderer 回归，并验证 Shadow 比较日志脱敏；验收：新旧报告解析能力无回归，canonical 错误不自动 fallback。

## 15. 人工 Word 验收（跨层）

- [ ] 15.1 准备阶段一脱敏人工验收矩阵：手机/平板标识、人员顺序、主软件、正文/光盘日期、4/22/45GB档位、重规划、附件一/二/三、VML、黑字、图片比例、分页和模板 hash。输入：通过自动化门禁的唯一正式 DOCX；输出：甲方可审阅验收记录；验收：人工打开 Word 确认版式和可读性。
- [ ] 15.1T 固化人工验收证据清单和失败复现入口；验收：未通过项不会标记阶段一完成或切换 canonical。

人工验收记录（2026-07-19）：甲方已在 Microsoft Word GUI 检查一组脱敏Word样例并确认通过。记录结果为：无Word修复提示；附件章节独立起页、附件1标题和固定清单、固定手写行、正文动态检查人员、附件3元数据和底部光盘说明、摘要数量、PAGE/NUMPAGES、VML、无空白页和无末尾空白页均通过。稳定材料和清单保存在被Git忽略的验收目录。

人工验收记录（2026-07-20，认可版本 v8）：甲方已在 Microsoft Word GUI 确认通过。该样例包含两个检材，每个检材两张图片；附件2页面按两个检材组上下排列、每组两张图片左右排列，图片文字与检材一一对应且顺序无交叉。检查结果合并显示当前两个检材编号，Word 无修复提示，附件2标题只出现一次，附件3从下一页衔接，图片比例和页脚通过人工检查。v8 的机器校验和 SHA-256 记录保存在被 Git 忽略的验收目录；本记录只确认 v8 的人工视觉验收，不将 `15.1` 或 `15.1T` 勾选为阶段一全部完成。

15.1/15.1T 暂不勾选：任务原文还包含 4/22/45GB 档位、重规划、全局黑字策略、图片比例等本次五份 Word 样例未逐项人工验收的范围；本记录不将这些未验收范围伪装为已完成，也不改变附件二偶数布局、canonical、Shadow E2E、桌面桥接或阶段一全部完成状态。

## 16. canonical 切换和回滚演练（跨层）

演练必须覆盖“允许编辑但禁止最终导出”的统一门控，并确认 canonical 正确性失败只返回明确错误，不自动回退 legacy；回滚仅通过集中 `pipeline_mode` 完成。

- [ ] 16.1 通过集中 `pipeline_mode` 将默认从 `legacy` 经 `shadow` 切换到 `canonical`；设计 canonical 数据错误、模板漂移、manifest 校验失败和缓存污染的人工运维回滚。输入：Shadow 比较通过且阶段一人工验收通过；输出：canonical 唯一正式输出或明确失败；验收：canonical 失败不自动回退，人工改回 legacy 后可重新处理。
- [ ] 16.1T 执行回滚演练和缓存隔离测试；验收：已有输出不被覆盖、Shadow 结果不被当正式缓存、legacy/canonical 模式均可恢复。

## 17. 阶段二/三接口预留（不属于阶段一实现门槛）

- [ ] 17.1 只定义 `ReportProfile`、`FieldProvenance`、结构发现/候选确认接口和版本化存储契约，不在阶段一实现任意报告自动解析。输入：未知结构候选；输出：可序列化的 draft/confirmed Profile 契约；验收：未确认 Profile 不得静默导出。
- [ ] 17.1T 为 Profile 来源文件、JSON 路径、规则、置信度、确认和版本失效增加契约测试；验收：同类复用和低置信人工确认边界明确。
- [ ] 17.2 只定义 `TemplateProfile` 的段落/表格/单元格/内容控件/VML anchor、重复区、图片区、显示条件、分页和推荐草稿扩展点，不在阶段一实现通用模板设计器、无标记识别或自动推荐。输入：固定 current-template-v1 Profile；输出：阶段三可扩展接口；验收：阶段一只接受固定 Profile。
- [ ] 17.2T 为 TemplateProfile round-trip、版本、anchor 和“未确认不可导出”增加契约测试；验收：接口可扩展但阶段一能力边界不扩大。
