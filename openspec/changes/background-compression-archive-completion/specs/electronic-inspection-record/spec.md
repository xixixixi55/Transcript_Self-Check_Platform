# Spec Delta: 后台压缩与归档完成统一导出

> 基准 Spec：`openspec/specs/electronic-inspection-record/spec.md`
> 变更类型：MODIFIED + ADDED（案件打开后台压缩触发、每 RAR 实时回填、盘号后填映射、归档完成态、统一导出、已导出与彻底删除）

## MODIFIED: REQ-012 — 解析与最终归档分离

### REQ-012: 解析与最终归档分离（案件打开后台压缩触发）

系统 MUST 满足以下现有合同：
#### Scenario: 工作台解析阶段不执行真实压缩
- WHEN 工作台报告目录登记成功并进入解析
- THEN 系统先持久化案件壳、来源绑定和解析任务，解析成功后保存 CaseDraft
- AND 解析、审核、草稿保存和预览均不自动调用 WinRAR，也不生成占位 Manifest

#### Scenario: 案件打开提供立即/稍后后台压缩选择
- WHEN 案件报告解析完成后用户打开案件
- THEN 系统提供「立即开始压缩」与「稍后压缩」两个选择，作为启动后台压缩的主触发入口
- AND 「立即开始压缩」创建受控后台归档任务，任务按 REQ-025 的固定里程碑与资源准入推进，不阻塞审核编辑
- AND 「稍后压缩」持久化 `archive_deferred`，页面显示「暂未压缩」，并从案件卡片操作区可再次启动压缩
- AND 解析失败时案件卡片保留失败与重试入口，不询问压缩时机

#### Scenario: 后台压缩不阻塞审核编辑
- WHEN 案件处于压缩执行中
- THEN 民警仍可查看、编辑并保存案件草稿，压缩在后台独立推进
- AND 审核编辑不改变已密封快照；压缩产物只由快照与归档计划决定，不因编辑中途变化
- AND 压缩、完整性、MD5 与 Manifest 各阶段完成状态实时反映在案件卡片上

#### Scenario: Legacy 兼容解析建立归档上下文但不压缩
- WHEN `/records/*` Legacy 兼容入口解析报告目录，无论 deprecated `compress` 参数为何值
- THEN 解析阶段可以建立不透明 `archive_context_id`，但不调用 WinRAR、不生成占位 Manifest
- AND 真实归档仅由案件打开/卡片显式选择触发，不能由工作台预览动作隐式触发

#### Scenario: 稍后压缩可恢复
- WHEN 用户选择「稍后压缩」
- THEN 案件和草稿生命周期持久化为 `archive_deferred`，页面显示「暂未压缩」
- AND 刷新或后端重启后仍显示该状态，并可从案件操作区再次选择立即压缩

#### Scenario: 已验证 Manifest 的安全复用
- WHEN 同一归档上下文、输入目录快照与案件归档基础名均未变化，且已有已验证 Manifest
- THEN 文书失败后的同次安全重试可以复用该归档结果而不重复执行 WinRAR
- AND 盘号后填或盘号修改不破坏 Manifest 复用（盘号从复用指纹中解耦）；新的导出请求仍重新验证实际 part 的存在性、大小和完整 MD5
- AND 重新解析案件、输入目录变化或案件归档基础名变化时旧 Manifest 必须失效
- AND 若 RAR 缺失、大小变化或 MD5 不一致，禁止复用并重新生成归档

## MODIFIED: REQ-017 — 从最终 ArchiveManifest 生成提取清单

### REQ-017: 每 RAR 完成实时覆盖填写附件1与检查结果

系统 MUST 满足以下现有合同：
#### Scenario: 每个 RAR 完成即回填并覆盖
- WHEN 后台压缩的某个 part 完成并通过完整性/MD5 校验
- THEN 后端立即将该 part 的文件名、文件大小和 MD5 写入案件记录的检查结果（`rar_filename`、`file_size`、`md5_hash` 对应位置）与附件1（`extract_list`）对应行，实时增量更新
- AND 自动值覆盖该字段的既有值（含手工编辑值）；来源列仍按审核后的 `evidence_number` 生成，提取方式使用 `inspection.hardware_device`，缺失时使用「取证设备」
- AND 未完成 part 对应位置保持未填写，不提前生成空行占位

#### Scenario: 归档完成后附件1 列结构不变
- WHEN 独立归档执行完成且最终 `ArchiveManifest` 验证通过
- THEN `AttachmentPlan` 按 Manifest 中每个实际 part 生成一行数据，列结构固定为：序号、电子数据、来源、提取方式、文件MD5哈希值
- AND Word 和附件3使用同一 Manifest，不从 `rar_info`、ArchivePlan 或目录扫描重新生成卷列表

#### Scenario: 解析响应兼容字段不驱动附件1
- WHEN 文件夹解析仅返回空值/零值 `rar_info`，或压缩包直传返回上传文件的兼容 `rar_info`
- THEN 这些解析响应字段均不作为正式附件1或最终导出的归档事实源
- AND 正式附件1只按已验证 `ArchiveManifest` 派生的 `AttachmentPlan` 生成

## MODIFIED: REQ-009 — 导出标准格式笔录

### REQ-009: 统一导出最新 Word + RAR + HashMyFiles 校验 HTML

系统 MUST 满足以下现有合同：
#### Scenario: 确认无误后统一导出到用户路径
- WHEN 案件进入归档完成态且民警点击「导出」
- THEN 系统提示用户选择导出路径，并把「最新编辑数据生成的 Word + 全部 RAR 文件 + HashMyFiles 校验 HTML」统一写入该路径
- AND 生产 Controller 使用审核后的 `InspectionReport` legacy DTO 和已验证的最终 `ArchiveManifest` 构造 `AttachmentPlan`
- AND Word 使用案件明确引用且当前重新校验通过的 approved 模板版本生成 .docx；带 Manifest 的正式渲染失败时必须明确失败，不得静默回退到无 Manifest 的 officecli batch 输出
- AND RAR 文件复用已验证的最终分卷；HashMyFiles 校验 HTML 由后端调用 HashMyFiles.exe 对导出 RAR 生成，与 RAR 一并写入导出路径

#### Scenario: 可重复导出且 Word 用最新编辑
- WHEN 案件已导出成功后民警再次导出
- THEN 系统重新打开导出路径选择，Word 用导出时刻的最新编辑数据重新生成，RAR 复用已验证分卷，HashMyFiles HTML 重新生成
- AND 导出成功不关闭审核编辑，民警可继续修改并再次导出

#### Scenario: 导出前的完整门控
- WHEN 案件满足导出条件并开始正式输出
- THEN 继续执行完整 inventory、路径/链接/文件变化、WinRAR、完整性、MD5、Manifest 和 Word 门控
- AND 任一门控失败都不得发布正式导出成功状态
- AND 导出路径写入失败、磁盘不可写或文件被占用时明确报错，不标记已导出

## ADDED: REQ-030 — 盘号后填与顺序映射

### REQ-030: 首个光盘编号可在压缩前或压缩后输入并按 part 顺序映射

#### Scenario: 压缩前未填盘号仍可压缩
- WHEN 用户未填写首个光盘编号即启动压缩
- THEN 系统仍按固定体积分卷执行压缩，压缩阶段不因缺少盘号失败
- AND 案件进入「待补盘号」中间态，卡片显示未填盘号提示并提供补填入口

#### Scenario: 压缩后输入首个盘号自动映射
- WHEN 压缩完成后用户输入首个光盘编号
- THEN 系统校验盘号格式与日期（`GPyyyyMMdd-序号`），按 part 顺序自动生成全序列并一一映射到各 RAR
- AND 映射结果持久化，案件从「待补盘号」转为「归档完成」候选
- AND 盘号仍可按 REQ-018 约定在案件内唯一前提下由用户修改，允许不连续，刻录日期独立保存

#### Scenario: 压缩前已填盘号保持现行为
- WHEN 用户压缩前已填写首个光盘编号
- THEN 系统按现行为在计划阶段生成预计盘号序列，压缩完成后按 part 顺序映射
- AND 后填与先填两种路径最终得到一致的 RAR↔盘号 一一对应关系

## ADDED: REQ-031 — 归档完成与已导出状态机

### REQ-031: 归档完成态、导出路径提示、已导出标记与彻底删除

#### Scenario: 全部对应完成后进入归档完成态
- WHEN 全部 RAR 完成、全部 MD5 计算完成且所有盘号映射完成
- THEN 案件进入「归档完成」状态
- AND 系统提示用户输入导出路径；提示只在盘号补齐后出现，未补齐时保持「待补盘号」

#### Scenario: 导出成功后标记已导出
- WHEN 统一导出写入用户路径成功
- THEN 案件卡片标记为「已导出」
- AND 导出成功后仍可再次导出（可重复），卡片提供「彻底删除」按钮

#### Scenario: 彻底删除仅删平台内产物
- WHEN 已导出案件执行「彻底删除」
- THEN 复用 `case-workbench-delete` 能力，确认后删除案件记录及平台内受控产物（解析缓存、归档快照、压缩 RAR、导出记录）
- AND 用户导出路径下的外部副本不被删除；外部原始资料目录不属于平台删除范围
