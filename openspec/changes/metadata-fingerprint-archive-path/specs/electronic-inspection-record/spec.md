# Spec Delta: 归档路径元数据级指纹

> 基准 Spec：`openspec/specs/electronic-inspection-record/spec.md`
> 变更类型：MODIFIED（来源复核与归档输入使用元数据级指纹，归档输出侧完整性校验保留）

## MODIFIED Requirements

### Requirement: REQ-021: 来源复核不得递归扫描完整报告目录

案件为导出后可删除的短生命周期工作数据。用户确认压缩期间不修改源目录时，来源复核 MUST 只检查授权路径、允许根、链接/reparse、报告结构以及核心报告文件的路径、类型、大小和 mtime，不得为展示审核页或提交归档决策而递归枚举全部媒体文件。来源目录缺失、越界、结构无效或核心报告文件身份变化时必须要求重新选择目录。

#### Scenario: 解析完成后快速开放直接压缩

- WHEN Parser 已成功生成可审核草稿
- THEN 后端只对授权 locator、报告根目录、`data` 目录和核心报告文件执行有界身份检查并将来源置为可用
- AND 审核页无需等待完整报告目录递归扫描即可显示“直接压缩”入口
- AND 深层媒体文件的数量不得线性增加来源复核或归档决策请求耗时

#### Scenario: 核心来源身份失效

- WHEN 授权路径、允许根、链接/reparse 安全、报告结构或核心报告文件的路径、类型、大小、mtime 与已登记身份不一致
- THEN 来源变为 `requires_reselection` 并阻止归档
- AND 暂时 I/O/权限失败保持 `pending` 并允许有界重试
- AND 检查不得读取媒体文件内容或递归遍历深层媒体树

### Requirement: REQ-ARCHIVE-IMMUTABLE-INPUT: 用户确认边界下的单次直接源 inventory

用户明确确认压缩期间不会修改、移动、删除源目录或继续写入后，新归档尝试 MUST 直接读取已授权源目录。系统 MUST 只构建一次完整输入 inventory 供容量规划、Manifest 输入统计和 WinRAR 执行使用，不得复制全量快照，也不得在来源复核、归档提交、WinRAR 前后或 Manifest 读取阶段重复递归扫描同一目录。

#### Scenario: 直接压缩快速进入后台

- WHEN 来源核心身份可用且用户确认立即压缩
- THEN 归档决策请求快速创建后台任务并结束 loading
- AND 完整输入 inventory 在归档 Worker 中构建，工作台列表、案件详情和其他 HTTP 请求保持可用
- AND 同一 attempt 在 WinRAR 启动前只构建一次完整 inventory

#### Scenario: 输出准确性门保持

- WHEN WinRAR 完成直接源压缩
- THEN 系统仍执行 RAR 完整性测试、连续分卷与容量校验、每卷 MD5、Manifest/发布身份和最终产物存在性校验
- AND 任一输出校验失败不得标记归档完成或允许统一导出
- AND 输入 inventory 的文件数、总字节数和路径元数据来自本次 Worker 的唯一完整枚举

#### Scenario: 同一次新归档只读取一次 RAR 内容计算 MD5

- WHEN RAR 完整性测试通过且 Worker 为本次新生成的每个 part 组装 Manifest
- THEN 每个 part 只执行一次完整内容 MD5，并将该摘要绑定到 durable publish intent、Manifest 和精确文件集合
- AND 同一 attempt 后续密封、原子发布、索引与完成提交复用该可信摘要，同时继续核对目录边界、文件类型、文件名集合、顺序、精确字节数和已哈希文件的稳定身份元数据
- AND 发布切点观察到文件缺失、替换、增删、字节数变化或同大小文件身份/时间变化时仍必须安全失败

#### Scenario: 结果展示不重复读取大文件内容

- WHEN 已完成案件读取归档结果以展示 part、MD5 和盘号映射
- THEN 后端验证 task/attempt/deployment、durable publication digest、Manifest 身份以及物理文件的存在性、类型、名称集合和精确字节数
- AND 普通结果展示不得再次对全部 RAR 执行内容 MD5，也不得阻塞工作台事件循环
- AND 结果展示不是正式文件授权；下载、统一导出、恢复与跨 attempt 复用仍执行现有完整内容校验，发现同大小内容篡改时必须拒绝

#### Scenario: 用户在压缩期间修改源目录

- WHEN 用户违反确认并在 inventory 或 WinRAR 执行期间修改、移动、删除或继续写入源目录
- THEN 系统不承诺通过额外的压缩前后全目录扫描检测该变化
- AND WinRAR 或输出完整性校验观察到的错误仍必须安全失败，不得伪造成功

### Requirement: REQ-022: Phase 1D 最小归档中断和产物保护

SourceRecord 的生产可用性身份 MUST 使用 REQ-021 的授权路径、报告结构与核心报告文件有界元数据指纹。完整媒体目录不再生成逐文件内容摘要，也不作为审核入口、归档提交或发布前的重复信任门。发布 intent、attempt/case/source/draft revision、Manifest 身份和物理 RAR 校验仍是完成权威。

#### Scenario: 有界来源身份与输出权威分离

- WHEN 工作台复核来源或归档发布核对当前来源记录
- THEN 来源可用性只使用授权 locator、报告结构和核心报告文件有界指纹
- AND 正式完成仍须通过 durable intent、Manifest、RAR 存在性/字节数/MD5 与发布代次门控

### Requirement: REQ-023: 独立 Review 后的归档一致性、恢复与外部变更加固

用户确认压缩期间不修改源目录后，归档执行 MUST 以 Worker 唯一完整 inventory 的路径、类型、大小和 mtime 作为容量规划与 Manifest 输入统计，WinRAR 直接读取授权源目录。产物生成后不得为证明源目录持续不变而再次执行全目录枚举；完成权威收敛到 RAR 完整性、连续分卷/容量、每卷 MD5、durable intent、Manifest 与发布代次的物理文件校验。

#### Scenario: 执行期来源不变承诺

- WHEN 用户确认后启动直接源压缩
- THEN 系统不在 WinRAR 前后或发布前重复全量扫描源目录
- AND 用户违反承诺导致的混合时点源内容不在额外检测保证内，但 WinRAR 或输出门观察到失败时不得发布成功
