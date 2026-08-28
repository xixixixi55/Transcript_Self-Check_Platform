# 规格：大型报告预览活性

> 基准规格：`openspec/specs/electronic-inspection-record/spec.md`
> 变更：`large-report-preview-liveness`
> 状态：`PROPOSED`；本文描述预期行为，不代表当前生产行为。

## CAP-PREVIEW-SNAPSHOT：预览使用单一受控解析任务

### REQ-PREVIEW-SNAPSHOT-001：文件夹预览在解析后结束

文件夹模式预览请求 MUST 授权所选目录、解析受支持的报告、持久化解析结果并返回可编辑预览，不得创建完整 ArchiveContext 或扫描完整报告清单。

**Scenario: 多检材文件夹预览成功**

- WHEN 用户选择已授权且受支持的 Legacy 或 New 报告目录
- THEN 后端在持久化解析器缓存后返回兼容 Legacy 的 `InspectionReport`
- AND 响应不等待完整输入清单、WinRAR 执行、Manifest 创建或 RAR 验证
- AND 响应将归档就绪状态报告为 `not_prepared` 或等价的显式状态
- AND 不使用名为 `idle` 的字段暗示完整 ArchiveContext 已就绪

**Scenario: 授权或格式验证失败**

- WHEN 所选目录位于授权范围外、与输出根目录重叠、包含禁止的链接/重解析点或核心结构不受支持
- THEN 请求在解析器工作或发布上下文外壳前失败
- AND 响应包含稳定安全的错误，不含本地路径、案件数据或堆栈跟踪

### REQ-PREVIEW-SNAPSHOT-002：请求范围内复用核心输入

在单个解析任务中，系统 MUST 只加载并解析每个核心公共 JSON 一次，在依赖发现、DTO 构造和缓存持久化之间复用检测到的格式、设备行和证据目录索引。

**Scenario: 复用核心 JSON**

- WHEN 解析受支持的报告
- THEN 格式检测、依赖发现和 DTO 组装不会分别重新加载 `data_case_info.json`、`data_device_lists.json` 和 `data_report_info.json`
- AND 所有消费者使用同一组请求范围值

**Scenario: 解析多条检材记录**

- WHEN 报告包含多条设备/检材记录
- THEN 按证据编号复用目录解析和解析器元数据
- AND 一个检材解析器不会为其他每项检材重新扫描报告根目录

### REQ-PREVIEW-SNAPSHOT-003：受控依赖发现

Parser MUST 动态登记它为业务字段实际读取的文件。MUST NOT 仅为计算解析缓存指纹而预读媒体、附件 HTML、导航载荷或无关 JSON。

**Scenario: Parser 读取相关依赖**

- WHEN 从 JSON 文件提取设备字段
- THEN 在同一次读取中记录该文件的规范化相对路径、大小、修改时间和内容摘要
- AND 依赖记录仅供内部使用，公共输出或持久缓存键中不含绝对路径

**Scenario: 无关源内容变化**

- WHEN 业务 Parser 未使用的媒体文件、附件 HTML 或 JSON 发生变化
- THEN 业务解析缓存仍可复用
- AND 除非实际 Parser 依赖发生变化，否则预览 DTO 保持不变

### REQ-PREVIEW-SNAPSHOT-004：DTO 兼容性

对于相同源输入，优化后的解析器 MUST 保留现有 Legacy DTO 值和受支持的 New DTO 值，包括证据顺序、设备标识符、软件字段、`rar_info` 兼容语义及可编辑报告默认值。

**Scenario: Legacy 流程和结果包含每项检材**

- WHEN Legacy 报告包含多条有序证据/检材记录
- THEN 现有标量字段 `inspection.result.evidence_number` 包含用 `、` 连接的有序检材编号
- AND 现有 `inspection.process_steps` 字符串以相同顺序提及每个检材编号
- AND DTO 结构和单检材措辞保持兼容

**Scenario: 设备显示名称使用有效型号**

- WHEN Legacy 或 New 报告提供通用设备名称和具体型号
- THEN `evidence_list[].device_name` 使用规范化品牌/型号显示值
- AND `evidence_list[].model` 保留具体型号值
- AND `evidence_list[].device_type` 保留明确的报告类型，而不是通用显示名称

**Scenario: Legacy 固件等价**

- WHEN 优化后的解析器和变更前解析器处理同一合成 Legacy 固件
- THEN 除明确记录的缓存/就绪元数据外，两者规范化后的 `InspectionReport` 值相等
- AND 报告 DTO 中不出现路径、摘要或内部快照字段

**Scenario: New 固件等价**

- WHEN 优化后的解析器处理受支持的合成 New 固件
- THEN 保留现有 New 格式字段映射，不通过会改变 DTO 的 Legacy 专用回退处理报告

## CAP-PARSE-CACHE：感知依赖的缓存身份

### REQ-PARSE-CACHE-001：首次解析单遍完成

缓存未命中时，解析与依赖摘要登记 MUST 在单次受控读取中完成。实现 MUST NOT 先对依赖集完整计算内容指纹，再为 Parser 重新打开相同文件。

**Scenario: 缓存未命中**

- WHEN 规范化报告目录不存在有效解析缓存
- THEN 解析器读取每项实际依赖、提取所需字段，并在同一遍处理中记录路径元数据和摘要
- AND 缓存写入包含以后验证所需的依赖清单

### REQ-PARSE-CACHE-002：缓存命中时优先检查元数据

查询缓存时，系统 MUST 在打开文件内容前验证依赖路径、大小、修改时间和稳定文件身份元数据。未变化的依赖复用已存摘要；只重新计算已变化或新发现依赖的哈希。

**Scenario: 依赖未变化时缓存命中**

- WHEN 所有已记录依赖路径都存在、身份元数据未变化且缓存版本为当前版本
- THEN 系统不重新打开依赖内容，直接返回缓存报告
- AND 更新最后访问元数据，不创建重复缓存条目

**Scenario: 一项依赖变化**

- WHEN 已记录依赖被新增、移除、调整大小，或其修改/身份元数据发生变化
- THEN 只重新计算受影响依赖集的哈希，再判断缓存有效性
- AND 实际内容变化会触发重新解析和缓存替换

**Scenario: 缓存损坏或过期**

- WHEN 缓存文件格式错误、版本过期、依赖清单不完整或其构建在发布前失败
- THEN 按现有缓存生命周期规则忽略并清理该记录
- AND 不返回部分报告或永久执行中条目

### REQ-PARSE-CACHE-003：缓存范围隔离

解析缓存 MUST 与原始报告目录、ArchiveContext 清单、RAR 文件、ArchiveManifest 记录、Word 导出、Shadow 状态和 Canonical 状态相互独立。

**Scenario: 清除解析缓存**

- WHEN 用户清除报告解析缓存
- THEN 只移除解析缓存记录
- AND 不通过路径遍历删除或作废源句柄、正式归档、Manifest、Word 导出或用户提供的源文件

## CAP-PARSE-INFLIGHT：复用同目录请求

### REQ-PARSE-INFLIGHT-001：在昂贵工作前加入

执行中注册表 MUST 以规范化的不透明报告目录身份为键，并 MUST 在依赖发现、内容指纹计算、Parser 执行或解析缓存持久化前获取。

**Scenario: 同目录并发请求**

- WHEN 两个或更多请求指向同一规范化报告目录
- THEN 由一个有界任务执行昂贵的解析管线
- AND 后续请求加入该任务并收到相同成功结果或相同安全失败
- AND 共享任务只执行一次 Parser 和缓存写入器

**Scenario: 不同目录**

- WHEN 请求指向不同规范化报告目录
- THEN 它们不共享结果或依赖清单
- AND 注册表强制执行配置的容量，避免无关报告耗尽内存或工作进程容量

### REQ-PARSE-INFLIGHT-002：中止和失败生命周期

客户端取消 MUST 只使被取消的等待方脱离共享任务。第一个任务仍在运行时，MUST NOT 为重试启动重复任务。

**Scenario: 前端中止后重试**

- WHEN 首个请求达到前端超时或网络取消，且用户重试同一目录
- THEN 重试加入现有执行中任务或使用其已完成的缓存结果
- AND 不会为该目录启动第二次依赖发现、Parser 运行或缓存写入

**Scenario: 共享任务失败**

- WHEN 共享 Parser 任务失败或被服务端生命周期策略取消
- THEN 所有当前等待方收到安全且可重试的错误
- AND 注册表发布结果后移除失败条目
- AND 后续重试可以启动新任务

### REQ-PARSE-INFLIGHT-003：有界生命周期和安全可观测性

执行中条目 MUST 具有容量、创建/最后观察时间戳、明确完成状态和异常清理。日志和指标 MUST 使用不透明键或计数器，且 MUST NOT 包含绝对路径、案件数据或缓存内容。

## CAP-ARCHIVE-LIFECYCLE：完整清单显式且延后生成

### REQ-ARCHIVE-LIFECYCLE-001：预览返回未准备状态

预览 MAY 发布短期有效的授权上下文外壳，但 MUST NOT 将其作为包含完整清单的 ArchiveContext 发布。响应 MUST 区分 `not_prepared`、`preparing`、`ready` 和 `failed` 状态。

**Scenario: 预览返回上下文外壳**

- WHEN 文件夹解析成功，且后续归档操作需要稳定源引用
- THEN 后端可以返回绑定授权和短 TTL 的不透明外壳标识符
- AND 外壳不含完整文件数、输入总大小或正式清单声明
- AND 外壳在实体化并验证前，不能用于正式归档执行或 Manifest 绑定的正式导出

**Scenario: 旧版仅报告客户端消费预览响应**

- WHEN 客户端只读取 `report`、`parsed_files` 或兼容字段 `rar_info`
- THEN 无需就绪的 ArchiveContext 也能继续工作
- AND 需要归档执行的客户端收到稳定的未准备错误，而不是误导性的 `idle` 成功

### REQ-ARCHIVE-LIFECYCLE-002：显式准备实体化完整上下文

归档准备操作 MUST 与预览分离。它 MUST 解析已授权外壳/源、构建完整清单，并仅在清单完整后发布就绪的 ArchiveContext。

**Scenario: 用户显式开始归档准备**

- WHEN 用户在预览后显式开始归档准备
- THEN 系统创建或刷新完整 ArchiveContext，并报告独立的准备加载/状态
- AND 仅完成预览绝不会启动 WinRAR 或完整清单处理

**Scenario: 重复准备**

- WHEN 为同一授权源再次准备现有外壳或上下文
- THEN 运行时在安全时应用有界快照复用，但绝不跳过必要的时效性检查
- AND 结果上下文状态准确报告完整清单是否就绪

### REQ-ARCHIVE-LIFECYCLE-003：正式归档门控保持完整

将清单移出预览 MUST NOT 削弱正式归档安全。在 WinRAR 执行或正式归档验证前，系统 MUST 保留当前归档契约要求的完整清单、可读性、路径边界、链接/重解析点、新增/移除/变更、完整输入内容指纹、Manifest、RAR 及下载/导出检查。

**Scenario: 预览后源发生变化**

- WHEN 预览后、归档准备/执行前，文件被新增、移除、修改、变得不可读或被链接/重解析点替换
- THEN 准备或正式执行以安全的输入已变更/路径错误失败
- AND 不将预览缓存或外壳元数据视为正式归档证据

**Scenario: 归档准备失败**

- WHEN 完整清单或正式归档门控失败
- THEN 上下文状态变为 `failed`，并附带安全可重试错误
- AND 不发布部分 Manifest，也不删除用户拥有的源

### REQ-ARCHIVE-LIFECYCLE-004：已认领准备可见且取消安全

归档任务被持久认领后，完整清单准备 MUST 以 `inventory` 里程碑表示，并 MUST 遵循协作取消。所有权 MUST 由绑定的所有者令牌和归档尝试身份决定，而不是任务修订版的不可变副本。

**Scenario: 枚举大型输入树需要时间**

- WHEN 已认领归档任务开始遍历完整清单
- THEN 任务在遍历开始前从 `queued` 推进到 `inventory`
- AND 界面不再将有效扫描描述为等待准入

**Scenario: 取消在准备期间改变任务修订版**

- WHEN 用户取消，而所有者令牌和尝试绑定保持不变
- THEN 遍历以协作方式停止，任务收敛到 `cancelled`
- AND 尝试记录 `ARCHIVE_CANCELLED`，而不是 `ARCHIVE_TASK_OWNERSHIP_LOST`
- AND 未处理的准备错误不能用 `failed_retryable` 覆盖 `cancelling`

**Scenario: 过期工作进程确实已失去所有权**

- WHEN 持久所有者令牌或尝试绑定不再与认领匹配
- THEN 以 `ARCHIVE_TASK_OWNERSHIP_LOST` 拒绝过期工作进程
- AND 它不能推进进度或开始归档执行

## CAP-FRONTEND-LIVENESS：预览和归档准备相互独立

### REQ-FRONTEND-LIVENESS-001：预览不自动归档

预览界面 MUST NOT 因加载报告、光盘编号有效或普通报告编辑的副作用调用归档执行。

**Scenario: 报告进入审核**

- WHEN 解析成功并打开审核页面
- THEN 页面显示报告预览和明确的归档未准备状态
- AND 不启动 WinRAR 请求、归档轮询循环或完整清单请求

**Scenario: 用户编辑普通字段**

- WHEN 用户在选择归档操作前编辑报告字段、光盘元数据或照片
- THEN 只改变本地审核状态
- AND 不自动启动归档准备请求

### REQ-FRONTEND-LIVENESS-002：加载和重试清理

预览和归档准备 MUST 具有相互独立的加载、错误、取消和重试状态。每次成功、业务错误、服务错误、网络失败、超时和取消都 MUST 结束对应的加载状态。

**Scenario: 预览超时或网络失败**

- WHEN 预览失败、超时或被取消
- THEN 预览加载结束并显示可重试消息
- AND 重试不能为同一规范化目录创建第二个后端解析任务

**Scenario: 归档准备失败**

- WHEN 预览成功后归档准备失败
- THEN 预览数据仍可编辑
- AND 只有归档准备状态变为失败；在存在已验证 Manifest 前，Manifest 绑定的正式导出保持阻塞

### REQ-FRONTEND-LIVENESS-003：独立 Word 导出和正式归档门控

未提供归档上下文或 Manifest 时，界面和 Controller MUST 允许在可编辑预览成功后显式执行仅报告 Word 导出。该路径 MUST 保留现有报告字段和文档渲染验证，MUST NOT 启动 WinRAR，也 MUST NOT 声称具有归档或 Manifest 证据。提供归档上下文或 Manifest 时，操作属于正式操作，MUST 拒绝未就绪上下文或未验证 Manifest。

**Scenario: 归档准备前仅导出报告 Word**

- WHEN 用户在归档状态为 `not_prepared` 时显式导出可编辑报告
- THEN 系统生成并下载 Word 报告，不创建完整 ArchiveContext 或执行 WinRAR
- AND 结果不声称具有已验证 Manifest 或正式归档证据

**Scenario: 正式导出仍要求已验证 Manifest**

- WHEN 导出请求提供归档上下文或 Manifest 标识符
- THEN Controller 要求当前就绪上下文和已验证 Manifest，才可正式导出
- AND 缺失、不完整、过期或无效的归档契约以稳定安全错误失败

## CAP-CHANGE-BOUNDARIES：归档源和输出边界

### REQ-CHANGE-BOUNDARIES-001：已授权报告目录源

归档准备边界 MUST 使用预览创建的已授权报告目录源记录。

**Scenario: 显式准备目录支持的归档**

- WHEN 用户在预览后显式开始归档准备
- THEN Controller 解析已授权源记录并重新验证报告目录
- AND 在任何归档或 Manifest 绑定导出前运行完整清单和正式归档安全门控
- AND 不将预览状态、解析缓存数据和源句柄视为正式归档证据

### REQ-CHANGE-BOUNDARIES-002：Shadow 与 Canonical 隔离

- WHEN 实施或验证本变更
- THEN 不增加 Shadow 或 Canonical 解析、比较、路由或输出行为
- AND 正式 Legacy DTO 和 Word/Manifest 消费者契约仍是兼容边界

## CAP-ACCEPTANCE：性能和回归目标

### REQ-ACCEPTANCE-001：代表性性能

**Scenario: 真实本地人工验证**

- WHEN 在之前测量的外部多检材报告上人工运行发布候选
- THEN 首次预览以合理余量低于 90 秒
- AND 有效缓存命中预览低于 15 秒
- AND 预览不创建完整清单或枚举完整输入树
- AND 报告路径、案件名称、业务内容和生成输出保持在仓库资产、日志、测试和 Git 之外

**Scenario: 合成自动化基准**

- WHEN 运行自动化性能测试
- THEN 仅使用标记为 `SYNTHETIC`、`TEST` 或 `FIXTURE` 的小型合成固件
- AND 断言读取次数、依赖范围、执行中共享及预览期间没有完整清单，不要求 GB 级文件

### REQ-ACCEPTANCE-002：正式归档回归

- WHEN 用户在预览后显式准备归档
- THEN 当前生成归档规划、WinRAR 执行、完整性验证、Manifest 组装、下载验证和 Word 导出门控保持通过
