# Design: 直接源报告归档与根目录修复

> 变更包：`direct-source-archive-and-root-name-fix`
> 依赖方向遵循 `harness/architecture.md`。

## D1. 新尝试直接使用已授权源 inventory

**决策**：`execute_archive` 在复核 `ArchiveContext` 授权和初始 inventory 后，直接将 `context.inventory.source_root` 与其 files 交给 WinRAR，新 attempt 不再调用 `seal_execution_input`。

**理由**：避免全量输入复制，符合日常笔录生成的效率优先定位。源路径仍必须经现有 SourceRecord 授权、重启复核、链接/reparse 安全和 inventory 检查。

**备选与拒绝**：
- 继续复制快照仅修复根名：不能解决用户确认的性能问题，拒绝。
- 用硬链接代替复制：源内容原地改写会同时改变“快照”，且跨卷不可用，拒绝。
- 用 VSS：可提供更强一致性，但引入管理员权限、部署和恢复复杂度，不符合本轮日常流程，拒绝。

## D2. WinRAR 前后双 inventory 门控

**决策**：WinRAR 前使用现有 `verify_input_inventory` 确认路径、目录、文件大小和 mtime 与建立 context 时一致；WinRAR 成功返回后、RAR 完整性/MD5/Manifest 之前再做一次相同校验。后置校验失败时立即清理 staging RAR 并返回 `ARCHIVE_INPUT_CHANGED`。

**理由**：这是不复制源内容前提下可实现的低成本失败闭合，能覆盖常见的新增、删除、重命名、截断、大小或 mtime 变化。

**局限**：它不是原子快照，无法排除同尺寸同 mtime 改写，规格和 UI 必须如实表达。

## D3. RAR 内部根名只来自授权源目录

**决策**：WinRAR 进程的 `cwd` 固定为源目录的 parent，输入参数固定为 `source_root.name`，不再接受实际未用于改名的 `archive_root_name`分支。

**理由**：WinRAR 对相对目录参数会稳定保留该目录为顶层根；传入绝对快照路径是 `.i/s...` 泄漏的直接原因。直接源模式下 `source_root.name` 就是业务期望根名。

**防回归**：真实 WinRAR 集成测试必须同时检查 listing 和解压结果；单元测试检查 args 不包含绝对源路径和内部快照名。

## D4. 用户确认与执行期提示

**决策**：第一次“立即开始压缩”和从 deferred/interrupted 重新开始时，前端均显示确认对话框；确认文案要求用户停止取证软件写入，且不修改、移动或删除报告目录。`archive_queued`/`archiving` 状态面板持续显示同类警告，成功或失败后停止显示。

**理由**：直接源模式依赖用户避免常见变更，关键提示必须与实际提交操作同步，不能只放在帮助文档。

**备选与拒绝**：只显示非阻断 Alert 不能证明用户在启动前看到提示，拒绝；不提供“不再提示”选项。

## D5. 历史快照兼容

**决策**：保留 snapshot repository/schema/recovery/cleanup 代码，但新 attempt 不创建 snapshot 记录。attempt 完成证据改为接受“已授权源 inventory 前后验证通过”，同时对旧记录继续支持 snapshot 清理。

**理由**：避免数据库破坏性迁移，也避免清理流程遗留旧 `.inputs/.i/.t` 资产。

## D6. 压缩期间盘号编辑与发布证据同步

**决策**：案件处于 `archive_queued`/`archiving` 时，后端只允许报告中的首个光盘编号及其派生日期/序列字段发生变化；保存时原子更新当前 attempt 与 active binding 的草稿 revision/报告 fingerprint。WinRAR 完成后读取带 revision/fingerprint 的发布快照，以该快照刷新 Manifest 映射；publish intent 在同一事务内 CAS 校验该证据并建立写围栏。若组装期间盘号再次保存，CAS 不建立 intent，执行器重新读取并重建 Manifest，直到最新证据被围栏冻结或有界重试失败。其他报告字段变化继续拒绝。

**理由**：页面明确允许后台压缩时填写盘号。若只更新草稿而不更新 attempt 证据，发布前会在阶段 8 误判 stale；若放宽全部草稿字段，则会破坏归档文件名、报告证据和发布围栏的一致性。

## D7. 进程本地 context 的领取约束

**决策**：归档 coordinator 只允许 scheduler 领取已登记在该 coordinator 内存中的 task id。登记时复用 active archive context binding 的 `expires_at` 写入 queued 短租约，调度循环续租且不改变公开 task revision；claim 事务建立 running ownership 时清除短租约。正常停止立即中断仍 queued 的本地任务，其他 coordinator 会将过期租约或超过宽限期仍未首次租约的 bound task 原子收敛为 `interrupted`。因此非持有进程不会执行任务，持有进程异常退出后任务也不会永久 queued。

**理由**：preview/formal context 是有意不持久化的进程内授权对象。多个热重载进程短暂共存时，任意进程领取 durable task 会导致 `ARCHIVE_RUNTIME_CONTEXT_UNAVAILABLE`。

## D8. 统一导出专用超时和错误呈现

**决策**：统一导出使用独立长超时，不复用 30 秒普通工作台请求超时；目录授权、结果不可用、路径无效和导出状态提交失败提供明确安全文案。

**理由**：统一导出包含 Word 生成、大体积 RAR 复制和 HashMyFiles 截图，30 秒不能代表合理失败边界，客户端提前超时会把仍在执行或已返回的具体错误降级成通用网络提示。
