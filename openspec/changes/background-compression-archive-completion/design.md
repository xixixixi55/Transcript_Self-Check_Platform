# Design: 后台压缩与归档完成统一导出

> 变更包：`background-compression-archive-completion`
> 分层约束遵循 `harness/architecture.md`：依赖单向（SharedTypes(0)→Constants(1)→Utils(2)；FE Hooks(10)→Components(11)→Pages(12)；BE Repo(20)→Services(21)→Controllers(22)→Routes(23)），前后端仅经 SharedTypes API 契约通信。

## D1. 案件打开「立即/稍后」后台压缩触发

**决策**：复用现有 workbench 后台归档任务机制（REQ-025 固定里程碑 + 资源准入 + 可恢复），把「案件打开选择立即/稍后」作为主触发；预览/审核页的手动 `EXECUTE_ARCHIVE` 同步路径降级为兼容入口，不再作为新交互主路径。

**理由**：REQ-012 已定义 `archive_deferred` 状态与「稍后压缩可恢复」场景，REQ-025 已有后台任务里程碑、资源准入、Worker 心跳与重启恢复——直接复用可避免重复建设，且满足「压缩不阻塞审核」。

**备选与拒绝**：
- 新建独立后台任务机制 → 与 REQ-025 重复，维护双套任务状态机，拒绝。
- 保持审核页同步 `EXECUTE_ARCHIVE` 为主 → 阻塞审核编辑且不满足「案件打开选择」，拒绝。

**实现要点**：
- 案件卡片/案件打开页在 `archive_deferred`/未压缩态提供「立即压缩」；点击后经现有 workbench 任务创建路径进入后台任务（attempt + 固定里程碑）。
- 任务推进中案件仍可编辑；任务与草稿编辑互不依赖（压缩只消费密封快照）。
- 归档发布证据继续绑定开始发布时的 attempt/binding/fence；发布短临界区内发生的审核保存不改写该证据。完成事务另以最新 shell/draft revision 与最新草稿指纹做 CAS，把 Manifest 派生字段合并到最新草稿，从而既保留证据边界，也不覆盖图片引用等审核编辑。
- 发布前允许 attempt/binding 随正式发布临界区之前的合法草稿保存推进，并使用校验时刻的最新草稿元数据；不得再把开始执行时的报告内容与当前审核草稿做稳定指纹相等校验。RAR 物理内容只由密封输入快照决定，审核字段和图片引用变化不构成归档中断条件。
- 若归档完成事务先于同一时刻的审核保存提交，草稿保存只对“当前 revision 恰为预期值 + 1、当前 lifecycle 为 `archive_verified`、且归档 verified intent 的更新时间与草稿更新时间一致”的完成回填做一次受限重试；重试时可信 RAR/MD5/附件1投影覆盖客户端旧副本，其余审核编辑（含图片引用）按客户端本次变更保存。其他 revision 冲突保持 409。
- 前端 hook 改为案件打开时查询案件状态并呈现选择，替换审核页手动 prepare 主路径。

## D2. 盘号后填：plan 阶段不再要求 first_disc_number

**决策**：`plan_archive` 允许 `first_disc_number=None` 执行（`expected_disc_numbers` 为空）；压缩完成后，由「盘号映射服务」按实际 part 数生成全序列并持久化映射。先填路径保持现行为（计划阶段生成预计序列）。

**理由**：需求明确「压缩前或压缩后输入首个盘号」；REQ-018 已允许盘号每槽独立、可修改、允许不连续，说明盘号本就是延迟决策的槽位属性，把强制前置条件放宽是自然演进。

**备选与拒绝**：
- 压缩后仍需重跑计划 → 浪费压缩结果，且可能触发重复压缩，拒绝。
- 维持压缩前必填 → 与需求相悖，拒绝。

**实现要点**：
- `archive_planner_service.plan_archive`：当 `first_disc_number is None` 时仅按体积计算 part（现有逻辑已按 volume 计算 `expected_part_count`），跳过 `parse_disc_sequence`/`generate_disc_numbers`。
- 新增 `disc_mapping_service`：输入首个盘号 + 实际 part 数 → `parse_disc_sequence` + `generate_disc_numbers` 生成全序列 → 按 part 顺序映射并持久化。
- 归档完成与已导出状态继续显示首盘号输入；输入初值优先取持久化 plan 的首个 active slot 映射。归档结果同时返回 plan 行 revision，提交时作为 CAS 令牌；再次提交复用同一映射服务，按当前实际 part 顺序整体替换映射，不修改或重跑 RAR，过期页面必须返回 revision conflict 而不是静默覆盖。
- 案件内单独 Word 导出携带 `case_id` 时，在盘号校验前读取当前案件最新 plan；全部 active slot 均具有 `confirmation=confirmed` 的非空映射时，以首个 slot 的盘号覆盖客户端草稿兼容字段。plan 映射是此场景的事实源：无 plan 时保留旧兼容行为；plan 存在但 pending、部分映射或空值时显式清空客户端盘号并由门控拒绝，不能用客户端兼容字段旁路。
- **复用指纹解耦**：REQ-012 的归档复用指纹含 `first_disc_number`（`archive_report_fingerprint`）。盘号后填/修改会导致指纹变化。需把盘号从复用指纹输入中剔除（或复用校验排除盘号），使后填不触发重复压缩。此为关键实现点，需在 apply 阶段用回归测试锁定「后填盘号复用已验证 RAR」。

## D3. 每 RAR 完成实时覆盖回填

**决策**：归档 attempt 完成时经 `complete_verified` → `update_verified_draft` 覆盖填写检查结果 `result`（rar_filename/md5_hash/file_size）并投影附件1。

**理由**：需求明确「每个最终 RAR 完成后同步填写检查结果与附件1」且已确认「实时填且覆盖手工值」。
**apply 阶段细化**：WinRAR 执行器批量产出分卷、不暴露逐卷完成事件，真实的「每 part 完成」点不可得；回填点取归档 attempt 完成（`complete_verified` 更新草稿，早于导出），在现有架构下是最早可执行时刻。独立 `attachment_backfill_service` 实现为重复死代码，Review 后删除。

**备选与拒绝**：
- 全部完成后一次性填（现状 usePreviewArchive）→ 回填在 attempt 完成时执行，早于导出且覆盖语义明确，拒绝「推迟到导出」。
- 仅填空白格、保留手工值 → 与用户确认的「覆盖手工值」相悖，拒绝。

**实现要点**：
- `complete_verified` 用 `verified_archive_result_fields` 从 manifest parts 派生 `rar_filename/md5_hash/file_size`（「、」分隔），经 `apply_verified_archive_result` 写入草稿 `inspection.result`，`attachment_projection` 投影附件1 `extract_list`。
- 审核字段尚未齐全而进入附件投影兜底路径时，“提取方式”仍按 Word 的硬件语义生成：`inspection.hardware_device` 为空时使用「取证设备」。前端对历史空值使用同一展示兜底，使既有草稿无需数据迁移即可看到该字段；显式已有值保持不变。
- 草稿更新受 revision CAS 保护，lifecycle 迁移到 `archive_verified`；回填只影响草稿投影，不影响已密封快照与 RAR 物理文件。

## D4. HashMyFiles 三列校验截图集成

**决策**：`hashmyfiles_repository`（Layer 20）用独立临时 `/cfg` 启动真实 HashMyFiles.exe 窗口，对导出 RAR 仅计算 MD5；等待原生 ListView 出现全部结果后，通过 Windows 消息把可见列收敛为 Filename、MD5、File Size，再以 `PrintWindow` 捕获真实窗口为 PNG。统一导出只发布 `hash-verification.png`，临时配置、JSON、脚本全部清理。工具路径由 `BIJI_HASHMYFILES_PATH` 配置，未配置时回退到随包默认位置，缺失、结果数量不完整或窗口截图失败则导出明确失败。

**理由**：用户进一步确认必须使用真实 HashMyFiles.exe 界面，而非仿制窗口。HashMyFiles 2.51 官方命令行提供 `/cfg` 与 `/files`，但不提供窗口截图或列筛选命令；因此使用隔离配置启动真实窗口，再在截图前临时调整其原生列表列宽，既保留真实彩色工具栏和 Windows 样式，也不污染用户日常配置。

**备选与拒绝**：
- 仿制 HashMyFiles 风格窗口 → 图标、标题栏和控件样式与真实 exe 不一致，用户验收不通过，拒绝。
- 继续发布 HTML → 与用户明确要求的截图产物不符，拒绝。

**实现要点**：
- 以 Live Hashes 模式等待原生结果行数与输入 RAR 数量一致，超时、进程提前退出或数量不完整均明确失败。
- PNG 捕获真实窗口，列顺序固定为 Filename、MD5、File Size（HashMyFiles 原生标签，值为字节），多分卷逐行展示；截图前清除默认选中高亮。
- 命令执行安全：仅允许配置的可执行路径，禁止用户注入参数；输出写入受控导出临时目录。
- 大体积超时：按待校验 RAR 总字节数以保守 10 MiB/s 加固定启动余量动态估算，限制在 120 秒至 6 小时，并允许 `BIJI_HASHMYFILES_TIMEOUT_SECONDS` 在同一边界内覆盖。
- 部署：`BIJI_HASHMYFILES_PATH` 支持绝对路径或随包相对路径；hashmyfiles/ 目录按部署说明纳入（不纳入 Git 跟踪）。

## D5. 统一导出到用户路径

**决策**：新增统一导出流程：前端 native picker 选择导出路径 → 后端在导出路径写入「最新编辑 Word + 全部 RAR + HashMyFiles 校验截图」→ 记录导出日志并标记已导出。可重复导出：每次重新生成 Word 与 HashMyFiles PNG，RAR 复用已验证分卷。

**发布一致性**：Word、待导出 RAR 副本和真实 HashMyFiles 截图先在导出目录同卷临时区完整生成，HashMyFiles 校验该待发布副本；全部成功后才以可回滚替换发布。任一步失败保留上一版完整导出，不留下新旧文件混合包。

**理由**：需求要求多文件统一导出到用户指定路径且可重复；RAR 复用避免重复压缩，Word 用最新编辑保证审计内容为最终版本。

**备选与拒绝**：
- 保持单 Word 下载 → 不含 RAR 与校验截图，不满足需求，拒绝。
- 一次性导出并锁死 → 与「可重复导出」决策相悖，拒绝。

**实现要点**：
- 新增/改造导出端点：`POST /workbench/cases/{id}/export-bundle`，请求含导出路径 + 一次性 `directory_token`（由 native picker 后端返回，不接收任意服务器路径）。
- 路径安全：`select-export-directory` 经 `issue_exact_directory_grant` 签发一次性 grant token，`export_bundle` 消费校验，未授权拒绝 `EXPORT_PATH_NOT_AUTHORIZED`，防止任意路径写入。
- 导出前重跑导出门控（REQ-009 全门控）；任一门控失败不标记已导出。
- 正式 Word 的图片事实源是最新草稿的 `asset_refs`，按该顺序解析并校验物理图片；禁止扫描案件资产目录兜底。历史草稿若仅缺 `photo_groups`，按检材顺序和每组两张图片生成确定性兼容映射；存在未绑定上传记录时明确返回图片尚未保存错误。
- 导出记录落库（路径、时间、part 集合、校验截图文件名），供「已导出」标记与审计；历史 HTML 字段作为旧记录兼容字段保留。

**apply 阶段细化（用户实测反馈）**：
- 统一导出交互入口为**案件工作台卡片主按钮**（归档完成/已导出时，替换原「查看结果」）；工作台经 `useArchiveCompletionStatuses` 自动加载归档结果，卡片恒定派生完成态，无需先点查看。案件打开页保留「立即/稍后」与补盘号入口，不再承载导出触发。
- 归档 inventory 性能优化：`verify_input_inventory` 改 `check_readability=False`（可读性由 seal 复制兜底）并移除第二轮重复 stat；`build_input_inventory` 文件 stat/open 用 `ThreadPoolExecutor` 并行（新增 `archive_input_inventory_worker.py`，复用 `BIJI_ARCHIVE_COPY_WORKERS`）。基准 3000 文件：verify 5.3s→0.87s、build 4.5s→1.7s。
- 原生目录选择器由嵌入 C# 后台线程按当前 PowerShell 进程枚举真实可见窗口，优先匹配隐藏 owner 直接拥有的窗口、再回退到标准 `#32770` 对话框；对话框整个存续期间以 `SWP_NOACTIVATE` 持续重申 TopMost Z 序，首次显式前台激活失败持续重试，窗口句柄重建时重新激活，既避免浏览器点击/重绘在首次提升后再次覆盖选择器，也不在用户主动切换应用后循环抢焦点。关闭对话框时等待提升线程退出后再释放窗口。该线程不依赖 `ShowDialog` 模态调用期间无法执行的 WinForms Timer，也不把已成功选择的合法目录事后降级为业务 422。上传报告与统一导出分别以本地版本化偏好持久化上次成功目录，下一次作为 `FolderBrowserDialog.SelectedPath`；取消、目录失效或偏好损坏时安全回退。

## D6. 状态机与已导出/彻底删除

**决策**：在现有案件状态（`archive_deferred`、`archiving`、`archive_verified`、`exporting_word`、`exported`）基础上新增「待补盘号」中间态；「归档完成」= 全部 RAR+MD5+盘号映射完成的稳定态（对应 `archive_verified` 的门控完成语义）；「已导出」= 导出成功（复用/映射 `exported`）；「彻底删除」复用 `case-workbench-delete`。

**理由**：复用现有状态避免双状态机；需求的状态变化可用现有状态 + 一个中间态表达。

**备选与拒绝**：
- 引入全新独立状态枚举 → 与 REQ-025/REQ-012 现有状态冲突，需全面迁移，拒绝。

**实现要点**：
- 「待补盘号」作为卡片展示态，可由 `archive_verified`（RAR/MD5 完成）+ 盘号未映射派生，或新增持久化标志。
- 映射成功后审核页显式重读归档任务结果，用最新分卷映射重新派生「归档完成」并刷新分卷展示；不能只刷新不含结果明细的案件 shell。
- 导出路径提示只在盘号补齐后出现。
- 彻底删除按钮仅「已导出」态可见；复用既有删除能力与确认流程。

## D7. 大型分卷压缩的活动感知超时

**决策**：WinRAR 执行采用“带收尾余量的硬上限 + 输出无增长超时”。硬上限仍按输入体积计算，在没有操作员环境变量覆盖且未触及最大上限时，为体积预算增加固定收尾余量；监控器持续统计 staging 中 RAR 文件总字节数，只有总大小严格增长才刷新空闲计时。连续超过空闲阈值没有任何输出增长时终止进程。

**理由**：机械盘上第一卷写满后，WinRAR 可能在处理下一批数据或执行卷收尾，RAR 文件会暂时不增长；前端此时已能显示已生成多个分卷，但压缩进程尚未完成。仅提高固定 timeout 会掩盖真正卡死，活动感知可以兼顾收尾时间和失控进程回收。

**实现要点**：
- `compute_timeout` 使用向上取整的体积时间并增加固定收尾余量，保留既有环境变量覆盖和最大上限；4.5 GB 与 8.5 GB 输入分别得到 1500 秒与 2300 秒硬上限。
- `monitor_owned_process` 以 RAR 输出总大小作为活动信号，支持可注入 probe 以锁定增长、缩小与停滞边界；首个非零 RAR 输出出现前不启用 idle timeout，仍受硬上限约束。hard 与 idle 均使用绝对 deadline，最早到期者优先，相等时 hard 优先；操作员环境变量覆盖逐字作为 hard deadline 使用。
- idle timeout 由 executor 映射为稳定的 `ARCHIVE_EXECUTION_TIMEOUT`，并先终止自有 WinRAR 进程、再清理 staging；若进程无法安全终止则返回 `ARCHIVE_EXECUTION_FAILED` 并保留 staging，禁止删除仍可能被进程使用的文件。分卷出现仅作为活动指标，不改变成功条件（正常退出、分卷校验、MD5、Manifest）。

## 依赖与风险

| 风险 | 缓解 |
|------|------|
| HashMyFiles.exe 命令行/输出格式未知 | apply 阶段先一次性实测脚本固化，再实现 repository |
| 盘号后填破坏 Manifest 复用指纹 | D2 将盘号从复用指纹解耦，配回归测试 |
| 每 RAR 回填与「、」分隔字段的写入并发 | 回填按 part_id 幂等定位行，受案件 revision CAS 保护 |
| 统一导出路径安全 | 仅接受 native picker 返回的受控路径 |
