# 规格增量：直接源报告归档与根目录修复

> 基准 Spec：`openspec/specs/electronic-inspection-record/spec.md`

## MODIFIED Requirements

### Requirement: REQ-012: 直接压缩的用户确认与运行提示

系统 MUST 在创建立即压缩任务前取得用户明确确认，并在读取源目录期间持续显示不得修改源文件的提示；压缩期间只允许盘号及其派生字段按发布证据合同安全更新。

#### Scenario: 确认后才立即压缩

- WHEN 用户在待压缩、稍后压缩或中断后可重试的案件上选择“立即开始压缩”
- THEN 前端在提交归档决策前显示确认提示，明确告知压缩期间不得修改、移动或删除源报告目录，也不得继续使用取证软件向其写入
- AND 只有用户明确确认才创建归档任务，取消时不发送立即压缩请求，不改变案件状态

#### Scenario: 压缩期间持续提示

- WHEN 案件处于 `archive_queued` 或 `archiving`
- THEN 页面持续显示“请勿修改源文件”警告及可识别的压缩进行状态
- AND 压缩成功、失败、取消或中断后不再将案件显示为正在读取源文件

#### Scenario: 压缩期间填写首个光盘编号

- WHEN 用户在 `archive_queued` 或 `archiving` 期间填写或修正首个光盘编号
- THEN 后端仅接受盘号及其派生日期/序列字段的草稿变化，并同步当前 attempt 的发布证据 revision 与 fingerprint
- AND WinRAR 完成后 Manifest 和最终草稿使用最新有效盘号
- AND 若盘号在 Manifest 组装与发布围栏建立之间再次保存，系统重新读取最新证据并重建 Manifest，不发布旧盘号映射
- AND 同期其他报告字段变化不得静默并入本次归档

### Requirement: REQ-ARCHIVE-IMMUTABLE-INPUT: 用户确认边界下的单次直接源清单

用户明确确认压缩期间不会修改、移动、删除源目录或继续写入后，新归档尝试 MUST 直接读取已授权源目录。系统 MUST 只构建一次完整输入 inventory 供容量规划、Manifest 输入统计和 WinRAR 执行使用，不得复制全量快照，也不得在来源复核、归档提交、WinRAR 前后或 Manifest 读取阶段重复递归扫描同一目录。

#### Scenario: 直接压缩快速进入后台

- WHEN 来源核心身份可用且用户确认立即压缩
- THEN 归档决策请求快速创建后台任务并结束 loading
- AND 完整输入 inventory 在归档 Worker 中构建，工作台列表、案件详情和其他 HTTP 请求保持可用
- AND 同一 attempt 在 WinRAR 启动前只构建一次完整 inventory

#### Scenario: 输出准确性门保持

- WHEN WinRAR 完成直接源压缩
- THEN 系统仍执行 RAR 完整性测试、连续分卷与容量校验、每卷案件所选文件哈希、Manifest/发布身份和最终产物存在性校验
- AND 任一输出校验失败不得标记归档完成或允许统一导出
- AND 输入 inventory 的文件数、总字节数和路径元数据来自本次 Worker 的唯一完整枚举

#### Scenario: 用户在压缩期间修改源目录

- WHEN 用户违反确认并在 inventory 或 WinRAR 执行期间修改、移动、删除或继续写入源目录
- THEN 系统不承诺通过额外的压缩前后全目录扫描检测该变化
- AND WinRAR 或输出完整性校验观察到的错误仍必须安全失败，不得伪造成功

### Requirement: REQ-ARCHIVE-PUBLICATION-GENERATION: 直出发布完成证据

正式发布 MUST 使用唯一的 SQLite 持久发布代次，并将其与任务、尝试、部署、栅栏、Manifest 及精确的物理文件集绑定；工作台直出完成不得依赖全局 JSON Manifest 索引。

#### Scenario: 直出发布完成

- WHEN 已验证的暂存 RAR 原子发布到用户所选报告目录的上一级
- THEN 仅当已封存的发布标识、意图/栅栏、当前修订、Manifest 和 SQLite 持久发布事实一致时，完成事务才将尝试和任务设为 `succeeded`
- AND 下载、恢复、统一导出和结果查询从 SQLite 发布事实解析实际 RAR 位置并重新执行物理完整性门控

### Requirement: REQ-ARCHIVE-MANIFEST-PROJECTION: 直出权威与旧索引兼容边界

数据库参与的工作台直出归档 MUST 仅以 SQLite 持久发布事实作为 Manifest 权威，不得读取、创建、锁定或重写全局 JSON Manifest 索引；JSON 索引只保留给无数据库旧流程兼容使用。

#### Scenario: 历史 output 索引不阻塞新直出归档

- WHEN 当前案件库没有对应发布记录，但 `output/compressed` 中存在历史、损坏、缺失或与当前部署不一致的 JSON Manifest 索引或旧文件
- THEN 工作台直出流程忽略该索引且不修改现有历史文件
- AND 新 attempt 继续依据当前 SQLite 任务、发布意图、目标目录冲突和实际 RAR 完整性执行，不得返回 `ARCHIVE_INDEX_UNTRUSTED`
- AND SQLite 证据缺失或不一致时仍基于对应的持久证据错误安全失败，不得从旧索引补造成功状态

#### Scenario: 无数据库旧流程继续失败关闭

- WHEN 兼容调用在没有 SQLite 数据库的情况下使用集中式归档目录
- THEN JSON Manifest 索引继续在跨进程锁下原子更新
- AND 索引缺失、损坏或无法可信解释时继续安全失败，不得被当作空列表或成功证据

## ADDED Requirements

### Requirement: REQ-ARCHIVE-ROOT-NAME: RAR 内部保留原始报告根目录名

系统 MUST 由已验证的源目录路径派生 WinRAR 工作目录和相对输入名，使 RAR 内唯一业务根保持原始报告目录名，并禁止客户端注入内部根名或 WinRAR 参数。

#### Scenario: 原始根目录名和完整目录树

- WHEN WinRAR 从已授权报告目录生成单卷或分卷 RAR
- THEN 压缩包内唯一顶层业务根目录名精确等于源报告目录名
- AND 根目录下文件、重名文件、中文/空格目录和空目录的相对结构与源目录一致
- AND listing 不包含 `.i`、`.inputs`、`.t`、snapshot token、staging 名或源目录之上的绝对路径片段

#### Scenario: 非法根目录输入不可注入

- WHEN 执行器接收已授权源目录
- THEN WinRAR 的工作目录与相对输入名由后端从已验证 `Path` 派生
- AND API 和前端不能提供任意归档内部根名或 WinRAR 参数

### Requirement: REQ-ARCHIVE-RUNTIME-OWNERSHIP: 进程本地上下文不得被其他进程领取

系统 MUST 仅允许持有 queued task 授权 context 的 coordinator 领取任务，并在持有进程停止或租约过期后将任务收敛为可重试中断状态。

#### Scenario: 多个开发进程共享持久队列

- WHEN 多个后端进程短暂连接同一 deployment 数据库，且 queued task 的授权 context 只登记在其中一个 coordinator
- THEN 只有持有该 task context 的 coordinator 可以领取并执行该 task
- AND 其他进程不得把任务推进到 running 后以 `ARCHIVE_RUNTIME_CONTEXT_UNAVAILABLE` 失败
- AND 持有进程正常停止或其 context owner lease 过期后，queued task 最终进入可重试的 `interrupted`，不得永久等待

### Requirement: REQ-UNIFIED-EXPORT-TIMEOUT: 大体积统一导出不得使用普通请求超时

前端 MUST 为包含 Word、RAR 复制和哈希校验的统一导出使用专用长超时，并将后端安全拒绝映射为可区分的业务提示。

#### Scenario: 统一导出超过三十秒

- WHEN Word、RAR 复制和 HashMyFiles 校验合计耗时超过普通工作台请求超时
- THEN 前端继续等待统一导出的专用长超时结果
- AND 若后端拒绝目录授权、归档结果不可用或导出路径无效，界面显示对应安全提示而非通用“请求未完成”
