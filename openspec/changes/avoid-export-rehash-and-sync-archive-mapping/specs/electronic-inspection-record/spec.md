## MODIFIED Requirements

### Requirement: REQ-023: 独立 Review 后的归档一致性、恢复与外部变更加固

归档发布、恢复和正式产物门控 MUST 继续使用完整不可变身份、owner/revision/lease/fence 和同一份 durable Manifest 证据，不得新增第二套发布事实源。发布 intent 的身份至少覆盖 case、attempt、source、source/draft revision、report fingerprint、source/input/archive fingerprint、Manifest/public Manifest、正式相对目录、context binding 和 fence；缺失或任一不一致 MUST 安全拒绝，完整相同的合法 intent 重入 MUST 幂等返回原记录。

应用停止达到有界等待上限时，属于本部署实例的 pending/running claim MUST 在 owner、attempt、task revision、lease 和 fence 条件仍成立时收敛为现有 `interrupted`/可恢复状态；不得把未完成工作标为 succeeded、completed 或 100%，不得改写其他部署实例的 claim。已经完成 durable 发布并通过可信完成门控的 attempt MUST 保持成功。重复停止、Worker 超时后的迟到返回和重启恢复 MUST 幂等。

用户确认压缩期间不修改源目录后，归档执行 MUST 以 Worker 唯一完整 inventory 的路径、类型、大小和 mtime 作为容量规划与 Manifest 输入统计，WinRAR 直接读取授权源目录。产物生成后不得为证明源目录持续不变而再次执行全目录枚举；完成权威收敛到 RAR 完整性、连续分卷/容量、每卷首次计算的案件所选算法摘要、durable intent、Manifest 与发布代次的物理文件校验。

正式发布到索引、Manifest/所选算法摘要确认和完成状态提交之间 MUST 继续核对同一 durable intent、fence、public Manifest、文件集合、顺序、字节数和首次计算的摘要。重启恢复若必须对尚未完成提交的密封发布执行内容校验，每个分卷 MUST 只计算一次案件所选算法摘要，并将本次已验证摘要与文件身份继续用于同一次完成提交，不得再次顺序读取完整 RAR。归档任务成功以后，结果查看、介质映射、下载和 Word 导出 MUST 复用已持久化的摘要，只核对发布绑定、文件安全类型、名称、存在性、字节数和 Manifest 结构元数据；这些后续操作 MUST NOT 再次顺序读取完整 RAR 或重新计算内容摘要。正式卷、Manifest 或索引出现可由上述身份或元数据检查观察到的替换、删除、新增、重命名或大小变化时 MUST 拒绝成功、复用、下载和 Word 导出；恢复遇到部分发布目录也不得直接提升为完成，不得删除或覆盖历史正式资产掩盖冲突。marker MUST 在 durable intent/fence 已建立且正式移动完成后才由明确发布所有者删除一次。

归档尝试内部状态为 `accepted | running | succeeded | failed | interrupted`，另有 `cleanup_status` 为 `not_required | pending | succeeded | failed | unknown`。恢复主要处理未完成的 accepted/running；已完成但停在 indexed 的 intent 只允许补写最终 verified，绝不把 succeeded 改回 interrupted。新的用户确认必须创建新的 attempt_id，不得复用旧记录。attempt_id、revision、PID、内部 staging locator 和 marker 摘要只能用于后端归属证明和诊断，API、DTO、错误和普通日志不得返回这些内部字段。

#### Scenario: 完整 intent 身份重入与冲突
- WHEN 同一合法发布 intent 使用完整相同身份重入
- THEN 系统返回原 durable intent 且不创建第二条记录
- WHEN 任一不可变身份字段缺失或不同，或历史 intent 被其他 attempt/fence 复用
- THEN 系统返回安全 conflict，不覆盖原 intent、不发布或标记成功

#### Scenario: 有界停止收敛本实例 claim
- WHEN shutdown 等待上限到达且本实例仍有 pending/running claim
- THEN claim 和 attempt 进入可恢复 interrupted 状态，未完成任务不显示成功或 100%
- AND 已可信完成的 attempt 保持 succeeded，其他实例 claim 不变，重复 shutdown/recovery 幂等

#### Scenario: 执行期来源不变承诺
- WHEN 用户确认后启动直接源压缩
- THEN 系统不在 WinRAR 前后或发布前重复全量扫描源目录
- AND 用户违反承诺导致的混合时点源内容不在额外检测保证内，但 WinRAR 或输出门观察到失败时不得发布成功

#### Scenario: 正式产物在完成后被复用
- WHEN 已成功发布的 RAR 被当前工作台或兼容旧接口用于结果查看、介质映射、下载或完成导出
- THEN 系统验证其发布绑定、普通文件安全类型、文件名、存在性、字节数和 Manifest 结构元数据
- AND 系统直接使用 Manifest 中首次计算并持久化的案件所选算法摘要，不重新读取完整 RAR 计算摘要
- AND 文件缺失、名称变化、大小变化、非普通文件或发布绑定不一致仍须拒绝复用；仅内容变化且所有受检元数据保持不变不在后续重复校验保证内

#### Scenario: 重启恢复复用单次内容校验
- WHEN 重启恢复对尚未完成提交但已有密封发布证据的 RAR 执行完整内容校验
- THEN 系统对每个分卷只计算一次案件所选算法摘要
- AND 完成状态提交复用本次已验证摘要及文件身份；文件在校验后被替换时仍须拒绝，不得以避免重复哈希绕过发布一致性

#### Scenario: 重启后不自动接管归档资源
- WHEN 应用重启时存在未完成的 Legacy 归档尝试、WinRAR 进程或 staging
- THEN 归档尝试标记为 `interrupted`，案件进入 `archive_interrupted`，用户确认前不得重新执行
- AND 系统不得连接、等待、接管或自动终止无法证明属于本系统的 WinRAR 进程
- AND 系统不得仅凭目录名、PID、进程名或命令行片段认定 staging 或进程归属

#### Scenario: 自有 staging 的最低归属证明
- WHEN staging 位于应用控制的 staging 根，具有系统生成且不可猜测的 attempt_id，数据库或受控索引存在对应记录，且 ownership marker 与 attempt_id、部署实例和受控根匹配
- THEN 系统可以将未完成 staging 标记为隔离或执行安全清理
- AND 多次恢复或清理必须幂等，清理失败不得阻止案件、草稿、任务和图片资产恢复
- AND marker 格式和存储结构不得进入公共 DTO

#### Scenario: staging 归属证据缺失或冲突
- WHEN 任一最低归属证据缺失、记录冲突、marker 不匹配或无法确认
- THEN 资源一律视为未知，不删除、不终止相关进程、不覆盖
- AND 系统只记录不含绝对路径的安全诊断结果

#### Scenario: 半成品和正式产物隔离
- WHEN 重启或失败后发现未验证的 RAR 或 Manifest
- THEN 半成品 RAR 不进入正式产物索引，半成品 Manifest 不注册、不返回、不驱动 Word 导出
- AND 已完成并通过校验的 RAR、Manifest 和 Word 不因案件恢复或普通清理被删除

#### Scenario: 归档恢复不泄露路径
- WHEN API、DTO、错误响应、任务状态或普通日志返回归档恢复结果
- THEN 只返回 opaque ID、稳定错误码和安全摘要
- AND 不返回绝对路径、staging 物理路径、完整进程命令行或原始文件列表

### Requirement: REQ-030: 归档介质编号由用户填写并按归档模式映射

系统 MUST 允许用户在压缩前或压缩后于审核编辑界面以完整字符串输入介质编号。光盘、硬盘编号同时支持原有格式与日期后带两位数字用户标识的新格式；标准分卷按 part 顺序生成光盘编号全序列，超大单卷只映射一个硬盘编号。系统不得自动补写或删除用户标识。

#### Scenario: 压缩前未填盘号仍可压缩
- WHEN 用户未填写首个光盘编号即启动压缩
- THEN 系统仍按固定体积分卷执行压缩，压缩阶段不因缺少盘号失败
- AND 案件进入「待补盘号」中间态，卡片显示未填盘号提示并提供补填入口

#### Scenario: 压缩后输入首个盘号自动映射
- WHEN 压缩完成后用户输入首个光盘编号
- THEN 标准分卷系统校验盘号格式与日期，同时接受 `GPyyyyMMdd-序号` 和 `GPyyyyMMddXX-序号`（`XX` 为两位用户标识），按 part 顺序自动生成全序列并一一映射到各 RAR
- AND 映射结果持久化到该成功任务 Manifest 明确绑定的归档计划，案件从「待补盘号」转为「归档完成」候选；不得因同一案件存在较新的其他计划而更新错误计划
- AND 盘号仍可按 REQ-018 约定在案件内唯一前提下由用户修改，允许不连续，刻录日期独立保存

#### Scenario: 超大单卷输入硬盘编号
- WHEN 压缩前归档输入总量超过 `225 × 1024³` 字节并生成 `oversized_single_volume`
- THEN 审核编辑界面必须提示用户输入一个 `YPyyyyMMdd-序号` 或 `YPyyyyMMddXX-序号` 硬盘编号，其中可选的 `XX` 为两位数字用户标识
- AND 系统只把该用户输入编号映射到唯一完整 RAR，不自动生成后续编号
- AND `GP` 光盘编号不得使该案件进入映射完成态，编号为空时仍允许先执行压缩

#### Scenario: 归档完成或已导出后修改介质编号
- WHEN 案件已经归档完成或已导出，用户修改当前介质编号并重新提交
- THEN 审核编辑界面保持可用的编号编辑入口，并以当前持久化映射作为输入初值
- AND 系统按当前归档模式重建并持久化 RAR↔介质编号映射，不重新压缩 RAR
- AND 提交必须携带界面读取映射时的 plan 行 revision；过期 revision 必须拒绝，不能静默覆盖另一页面的新映射
- AND 每次成功后界面必须重读最新映射及 plan 行 revision，并允许继续修改；压缩后的映射以成功任务 Manifest 绑定的归档计划为事实源，不得因额外写回草稿兼容字段制造案件 revision 冲突
- AND Word 内容预览、附件待核对状态和当前介质输入 MUST 使用重读后的归档映射即时投影介质编号及其日期，不要求刷新页面，也不得等待或依赖案件草稿写回
- AND 若同一页面存在尚未收敛的图片绑定或其他审核字段保存，介质编号提交前必须先等待本页写入完成并重读最新案件 revision；不得把本页保存推进的 revision 误报为其他会话修改，真正过期的案件 revision 仍必须由并发保护拒绝
- AND 修改后的映射用于后续工作台完成导出

#### Scenario: 压缩前已填盘号保持现行为
- WHEN 用户在归档模式尚未确定时提前填写介质编号
- THEN 审核编辑界面以单个“介质编号”完整字符串输入提示同时接受 GP/YP 的 `yyyyMMdd-序号` 与 `yyyyMMddXX-序号` 格式，不得把合法 YP 提前标记为光盘格式错误
- AND 模式确定后只保留与模式匹配的编号：标准分卷按 part 顺序生成 GP 序列，超大单卷保留唯一 YP 编号；前缀不匹配时提示用户改填但不使压缩失败
- AND 后填与先填两种路径最终得到一致的 RAR↔介质编号映射

#### Scenario: 固定介质前缀生成一致的 Manifest 日期与序列
- WHEN 用户按归档模式以 `GP` 或 `YP` 介质前缀，并以合法日期、可选两位用户标识和序号启动归档
- THEN 系统必须从同一次结构化编号解析结果取得日期；标准分卷生成全部连续光盘编号，超大单卷只保留一个硬盘编号，不得按固定字符位置截取日期
- AND 每个实际 RAR 的 `disc_number`、`disc_date` 与发布前复核使用同一序列事实源，多分卷归档必须完成发布
- AND 非法日期、非法编号或与归档模式不匹配的介质前缀仍按稳定错误拒绝

### Requirement: REQ-UNIFIED-EXPORT-TIMEOUT: 大体积统一导出不得使用普通请求超时

前端 MUST 为包含 Word 生成和必要 RAR 迁移的统一导出使用专用长超时，并将后端安全拒绝映射为可区分的业务提示。归档成功后的统一导出 MUST 复用 Manifest 已持久化的摘要，不因 RAR 体积增加而再次执行整包哈希校验。

#### Scenario: 统一导出超过三十秒
- WHEN Word 生成和必要 RAR 迁移合计耗时超过普通工作台请求超时
- THEN 前端继续等待统一导出的专用长超时结果
- AND 若后端拒绝目录授权、归档结果不可用或导出路径无效，界面显示对应安全提示而非通用“请求未完成”

#### Scenario: 已发布 RAR 参与完成导出
- WHEN 工作台完成导出读取已成功发布并登记到 Manifest 的一个或多个 RAR
- THEN 后端不得重新读取完整 RAR 计算摘要，导出耗时不应随 RAR 内容体积产生第二次哈希扫描
- AND 历史工作区 RAR 必须迁移时，副本发布前仍检查安全文件类型和预期字节数，但不得对原件或副本执行内容摘要重算

### Requirement: 最终压缩包仅保留一份

系统 SHALL 在用户点击立即压缩时，以案件绑定的 HTML 报告文件夹的上一级目录作为压缩输出工作位置。在该目录的任务独占临时子目录中生成并完成首次 RAR 内容校验后，系统 SHALL 通过同卷排他重命名将分卷发布到该上级目录，持久登记其唯一最终位置；不得先在应用输出工作区生成 RAR 再复制。工作台以 SQLite 保存发布权威，应用工作区只为无数据库旧流程保留文件索引兼容。完成导出 SHALL 直接复用已校验 RAR 及其 Manifest 摘要，仅生成 Word，不再次执行完整 RAR 内容校验。历史工作区产物保留兼容迁移能力。

#### Scenario: 立即压缩直接落盘
- **WHEN** 用户选择 `D:\案件A\报告\index.html` 所在报告目录并点击立即压缩
- **THEN** 临时 RAR 与最终 RAR 均位于 `D:\案件A` 所在卷，完成后 RAR 直接位于 `D:\案件A`，后续完成导出不复制该 RAR，也不重新读取完整 RAR 计算摘要

#### Scenario: 成功压缩并重启
- **WHEN** 压缩成功并重启服务后导出
- **THEN** 读取并核对报告上级目录中同一份 RAR 的发布绑定、安全文件类型、名称、存在性、字节数和 Manifest 结构元数据，不再次复制、压缩或计算内容摘要，只生成最新 Word

#### Scenario: 发布失败或冲突
- **WHEN** 目标同名 RAR 已存在且非本次拥有的文件，或写入、登记失败
- **THEN** 不覆盖已有文件，不标记归档成功；本次移动可回滚，进程中断可依据持久发布日志和文件身份继续核验恢复，半成品不得被作为正式成功产物

#### Scenario: 删除已归档案件
- **WHEN** 用户删除已归档案件
- **THEN** 同步删除登记的 RAR、Word 和导出记录；不存在第二份压缩缓存需要清理
