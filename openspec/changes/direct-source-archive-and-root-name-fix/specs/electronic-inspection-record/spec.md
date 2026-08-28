# 规格增量：直接源报告归档与根目录修复

> 基准 Spec：`openspec/specs/electronic-inspection-record/spec.md`

## MODIFIED Requirements

### Requirement: REQ-012: 直接压缩的用户确认与运行提示

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

### Requirement: REQ-ARCHIVE-IMMUTABLE-INPUT: 直接源目录执行与变化检测

新归档尝试 MUST 直接读取已授权的源报告目录，不得为 WinRAR 复制全量输入快照。该模式仅提供前后元数据变化检测，不声明执行全程强不可变。

#### Scenario: 直接读取已授权源目录

- WHEN 一个新归档 attempt 开始执行
- THEN 服务在 WinRAR 前复核 SourceRecord 授权、目录结构、链接/reparse 安全和已记录 inventory
- AND WinRAR 直接读取该已授权源目录，服务不创建 `.inputs`、`.i` 或 `.t` 全量输入快照
- AND RAR 完整性、MD5、Manifest 和发布代次门控保持不变

#### Scenario: WinRAR 期间源目录变化

- WHEN WinRAR 成功返回后，当前源 inventory 与压缩前记录的相对路径、类型、大小或 mtime 不一致
- THEN 归档以 `ARCHIVE_INPUT_CHANGED` 安全失败，清理本次 staging RAR
- AND 不执行完整性发布、MD5、Manifest 或完成状态提交，用户可在报告稳定后重新开始

#### Scenario: 元数据校验能力边界

- WHEN 源文件内容被原地改写但相对路径、类型、大小和 mtime 全部保持不变
- THEN 系统不得声称前后元数据门能检测该变化
- AND RAR 完整性与 MD5 仅证明已生成归档自身可读与固定，不等同于源目录的强不可变证明

## ADDED Requirements

### Requirement: REQ-ARCHIVE-ROOT-NAME: RAR 内部保留原始报告根目录名

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

#### Scenario: 多个开发进程共享持久队列

- WHEN 多个后端进程短暂连接同一 deployment 数据库，且 queued task 的授权 context 只登记在其中一个 coordinator
- THEN 只有持有该 task context 的 coordinator 可以领取并执行该 task
- AND 其他进程不得把任务推进到 running 后以 `ARCHIVE_RUNTIME_CONTEXT_UNAVAILABLE` 失败
- AND 持有进程正常停止或其 context owner lease 过期后，queued task 最终进入可重试的 `interrupted`，不得永久等待

### Requirement: REQ-UNIFIED-EXPORT-TIMEOUT: 大体积统一导出不得使用普通请求超时

#### Scenario: 统一导出超过三十秒

- WHEN Word、RAR 复制和 HashMyFiles 校验合计耗时超过普通工作台请求超时
- THEN 前端继续等待统一导出的专用长超时结果
- AND 若后端拒绝目录授权、归档结果不可用或导出路径无效，界面显示对应安全提示而非通用“请求未完成”
