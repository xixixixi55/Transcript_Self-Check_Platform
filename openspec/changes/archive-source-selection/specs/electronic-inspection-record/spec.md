# Spec: 审核编辑归档来源选择

> 基准 Spec：`openspec/specs/electronic-inspection-record/spec.md`
> Change：`archive-source-selection`
> 状态：PROPOSED；本文件描述待实施的增量行为，不代表当前生产实现。

## CAP-ARCHIVE-MODE：显式归档方式和触发

### REQ-ARCHIVE-MODE-001：归档方式必须先选择

审核编辑页面必须把归档方式作为显式状态，而不是由报告字段推断。

**Scenario: 报告进入审核编辑时保持待选择**

- WHEN 报告载入审核编辑且光盘编号有效
- THEN 页面将归档方式初始化为未选择，归档准备状态为 `idle`
- AND 不派发归档准备请求、不启动 WinRAR、不创建新的正式归档 Manifest

**Scenario: 仅修改光盘编号不触发归档**

- WHEN 用户填写或修改光盘编号，但没有点击“开始压缩”或“校验并使用”
- THEN 页面只更新报告编辑状态
- AND 不调用归档执行接口、不启动或重启 WinRAR

### REQ-ARCHIVE-MODE-002：自动压缩必须显式执行

**Scenario: 用户明确开始系统自动压缩**

- WHEN 用户选择“系统自动压缩”并点击“开始压缩”
- THEN 系统向现有归档执行链路发送一次 `archive_mode=generated` 的准备请求
- AND 现有计划、WinRAR 压缩、校验、Manifest 组装和正式导出门控保持有效
- AND 直到用户明确重新准备归档，已完成且仍有效的正式 Manifest 不被覆盖

**Scenario: 切换自动压缩和已有压缩包模式**

- WHEN 用户在一次准备尝试未完成时切换归档方式
- THEN 当前未完成尝试被标记为 `abandoned`，其迟到响应不再更新当前页面
- AND 系统不会因为切换动作自动发起另一种归档请求
- AND 仍有效的已完成 Manifest 保持可用，除非用户确认重新准备归档

### REQ-ARCHIVE-MODE-003：已有压缩包必须显式校验并使用

**Scenario: 用户提供归档的正常流程**

- WHEN 用户选择“使用已有压缩包”、完成本机文件选择并点击“校验并使用”
- THEN 后端使用 selection token 解析和校验用户原文件
- AND 成功后生成正式 `ArchiveManifest` 和会话级运行时归档记录
- AND 不调用 WinRAR 压缩执行器、不创建新的系统压缩任务

**Scenario: 用户提供归档校验失败**

- WHEN token 无效、文件不可读、分卷不完整或任一文件校验失败
- THEN 系统不发布新的正式 Manifest
- AND 页面展示稳定错误码和重新选择提示，不回退到系统自动压缩

## CAP-ARCHIVE-SELECTION：本机文件选择和 token

### REQ-ARCHIVE-SELECTION-001：后端原生选择器和最小响应

**Scenario: 交互式本机环境可以调用 Windows 选择器**

- WHEN 前端请求选择已有压缩包且后端运行在与浏览器同一台、具备交互式桌面的受信任 Windows 会话中
- THEN 后端调用 Windows 原生文件选择器并创建一次性、短 TTL、绑定会话和归档上下文的 opaque selection token
- AND 前端只收到 token、脱敏后的文件名/卷摘要和过期信息
- AND 前端响应、日志、Manifest 和持久化索引均不包含真实绝对路径

**Scenario: 后端原生选择器不可用**

- WHEN 后端运行在远程、无桌面会话、服务账户或其他不支持原生选择器的部署方式
- THEN 选择接口返回明确的 `native_picker_unavailable` 能力错误
- AND 首版不自动改用浏览器上传或复制大文件
- AND 仅在开发/降级配置明确开启时提供手工路径入口，手工路径必须经过现有授权和安全校验且不得回显或记录原文

### REQ-ARCHIVE-SELECTION-002：token 生命周期和消费

**Scenario: token 在有效期内单次消费**

- WHEN 用户在 token 的短 TTL 内，用同一会话、同一归档上下文提交“校验并使用”
- THEN 后端原子消费 token 后读取其后端运行时记录并完成一次校验尝试
- AND token 只允许使用一次，校验失败、请求取消或服务异常后均要求重新选择

**Scenario: token 过期或跨上下文使用**

- WHEN token 已过期、服务已重启、token 不存在，或 token 与当前会话/归档上下文不匹配
- THEN 请求被拒绝并返回 `selection_token_invalid` 或 `selection_token_expired`
- AND 不读取 token 关联的文件，不创建 Manifest，不暴露内部路径

## CAP-RAR-VOLUME：单卷和新式分卷解析

### REQ-RAR-VOLUME-001：支持的命名和目录范围

系统只接受下列命名：单卷 `name.rar`，或新式分卷 `name.part1.rar`、`name.part2.rar` 等，其中 `part` 序号为从 1 开始的十进制正整数且不使用前导零。

**Scenario: 用户只选择集合中的任一分卷**

- WHEN 用户选择 `name.partN.rar` 中任一存在的卷
- THEN 后端以该文件的父目录和解析出的 base 为锚点
- AND 只在同一目录进行非递归发现，组装完整的 `name.part1.rar` 到 `name.partM.rar` 集合
- AND 输出顺序按 `part_number` 数字顺序，而不是文件系统枚举顺序

**Scenario: 用户选择单卷**

- WHEN 用户选择 `name.rar` 且同目录不存在该 base 的新式分卷
- THEN 系统将其识别为单卷集合，`part_number=1`
- AND 不要求、不扫描其他目录中的同名文件

### REQ-RAR-VOLUME-002：拒绝不完整或含糊的集合

**Scenario: 缺卷**

- WHEN 同 base 的新式分卷集合缺少任一 1 到 M 之间的序号
- THEN 校验失败并返回包含缺失序号的 `part_missing` 错误
- AND 不生成正式 Manifest

**Scenario: 重复卷、混合单卷/分卷或额外同 base RAR**

- WHEN 同目录出现重复的逻辑卷号、`name.rar` 与 `name.partN.rar` 混合，或存在不能归入唯一合法集合的额外同 base `.rar`
- THEN 校验失败并返回可区分的 `duplicate_part`、`mixed_archive_parts` 或 `extra_archive_part` 错误
- AND 不凭枚举顺序猜测应使用的集合

**Scenario: 旧式分卷**

- WHEN 用户选择或同目录发现 `name.r00`、`name.r01` 等旧式分卷
- THEN 校验失败并返回 `unsupported_legacy_volume_format`，提示首版仅支持 `.rar` 和 `.partN.rar`
- AND 不尝试通过重命名、解压或 WinRAR 测试将其转换为新式分卷

## CAP-ARCHIVE-INVENTORY：文件安全、大小和 MD5

### REQ-ARCHIVE-INVENTORY-001：路径和文件安全检查

**Scenario: 所有分卷均在授权范围内且可读**

- WHEN 已解析的每一卷都存在、是普通文件、可读且位于当前有效路径授权范围
- THEN 系统为每卷建立内部来源引用并继续进行流式清单计算
- AND 任何来源引用都不写入公共 Manifest 或前端响应

**Scenario: 文件删除、目录替代或授权失效**

- WHEN 选定文件或发现的分卷不存在、变为目录、不可读、超出授权根，或其自身/父目录违反符号链接或 reparse point 安全规则
- THEN 校验失败并返回明确的文件或路径授权错误
- AND 不读取越界路径、不启动 WinRAR、不发布 Manifest

### REQ-ARCHIVE-INVENTORY-002：流式大小和 MD5

**Scenario: 生成用户提供归档清单**

- WHEN 每卷通过路径安全检查
- THEN 系统以有界内存流式读取每个文件，计算实际字节数和 MD5
- AND 每卷记录 `filename`、`size_bytes`、`md5`、`part_number` 以及现有 Word 所需的光盘字段
- AND 不解压、不遍历压缩包内部文件、不复制全部输入文件

**Scenario: 读取期间文件发生变化**

- WHEN 文件读取前后 stat 的身份、大小或修改状态不一致，或流式计数与最终 stat 不一致
- THEN 校验失败并返回包含卷名的 `part_changed`
- AND 不使用不确定的大小或 MD5 生成 Manifest

### REQ-ARCHIVE-INVENTORY-003：生成前二次 stat 和可选完整性测试

**Scenario: Manifest 发布前复核**

- WHEN 所有卷已完成流式 MD5
- THEN 系统在组装并发布 Manifest 前再次 stat 每卷，并确认文件仍与刚计算的身份和大小一致
- AND 任一卷不一致时返回 `part_changed`，不发布新的正式 Manifest

**Scenario: 可选 WinRAR 完整性测试**

- WHEN 部署配置启用并且 WinRAR `t` 能力可用
- THEN 系统可以把完整性测试作为独立诊断结果记录
- AND 完整性测试不是首版生成大小、MD5、卷顺序或 Manifest 的必要前置条件
- AND 测试不得解压或复制全部文件，也不得使用户提供模式进入系统压缩执行器

## CAP-MANIFEST-COMPATIBILITY：公共 Manifest 和运行时来源

### REQ-MANIFEST-COMPATIBILITY-001：保持公共 ArchiveManifest 结构

**Scenario: 用户提供归档成功后生成 Word 输入合同**

- WHEN 用户提供归档全部校验通过
- THEN 生成与自动压缩相同结构的公共 `ArchiveManifest`
- AND `parts[]` 至少提供 `filename`、`size_bytes`、`md5`、`part_number`、`disc_number`、`disc_date`、`disc_capacity_bytes`
- AND Word、附件计划和 Legacy 正式导出继续只读取该公共 Manifest，不读取内部源路径

**Scenario: 内部区分 generated 和 user_provided**

- WHEN 系统需要在运行时记录归档来源
- THEN 在会话级 `ArchiveManifestRecord` 或等价内部记录中保存 `source_mode` 为 `generated` 或 `user_provided`
- AND 首版不在公共 `ArchiveManifest` 增加 `source` 字段，不把来源写入现有持久化自动归档索引

### REQ-MANIFEST-COMPATIBILITY-002：正式 Manifest 不被隐式覆盖

**Scenario: 已有有效 Manifest 时再次选择归档方式**

- WHEN 当前存在已完成且导出前复核仍有效的正式 Manifest
- THEN 模式选择和普通编辑不改变该 Manifest
- AND 只有用户明确确认“重新准备归档”后，系统才创建新的准备尝试和新的 Manifest ID
- AND 新尝试失败时保留旧 Manifest 的可追溯状态，不以半成品覆盖它

## CAP-EXPORT-REVALIDATION：正式导出门控

### REQ-EXPORT-REVALIDATION-001：用户提供文件导出前复核

**Scenario: 导出前用户文件仍未变化**

- WHEN 用户提交 Legacy 正式导出且归档来源为 `user_provided`
- THEN 系统重新确认所有分卷存在、可读、仍为授权的普通文件，并重新计算或等价验证其大小和 MD5
- AND 仅在复核结果与正式 Manifest 完全一致时允许导出

**Scenario: 导出前文件删除或修改**

- WHEN 任一分卷在正式导出前被删除或大小/MD5 改变
- THEN 导出被阻止并返回包含卷名的 `part_missing` 或 `part_changed`
- AND 页面提示用户重新选择并重新校验，不启动系统压缩替代

## CAP-ARCHIVE-LIFECYCLE：会话、清理和来源隔离

### REQ-ARCHIVE-LIFECYCLE-001：用户原文件由用户管理

**Scenario: 解析缓存或运行时归档清理**

- WHEN 用户清空解析缓存、归档准备失败、token 过期或运行时会话到期
- THEN 系统只清理自身创建的临时目录、token 和内部元数据
- AND 不删除、不移动、不覆盖、不重命名用户选择的原压缩包或分卷

**Scenario: 服务重启或文件移动**

- WHEN 服务重启导致会话记录丢失，或用户将原文件移动到其他位置
- THEN 旧 token/来源记录不可恢复使用
- AND 页面提示重新选择，不从自动归档索引或 Manifest 推断并复用真实路径

### REQ-ARCHIVE-LIFECYCLE-002：并发和迟到响应隔离

**Scenario: 切换模式或重复点击期间存在迟到响应**

- WHEN 旧的自动压缩请求、用户提供校验请求或轮询响应在模式切换后返回
- THEN 前端按 attempt ID/取消信号丢弃迟到结果
- AND 后端按上下文和运行时来源隔离状态，不让旧结果覆盖新模式或有效正式 Manifest

## CAP-WORD-LEGACY-ISOLATION：Word 和正式输出边界

### REQ-WORD-LEGACY-ISOLATION-001：保持现有 Word 字段映射

**Scenario: 两种来源进入 Word 附件计划**

- WHEN 自动压缩或用户提供归档分别生成有效 `ArchiveManifest`
- THEN `attachment_plan_service` 按相同的 `parts[]` 字段和 `part_number` 顺序生成附件计划
- AND Word 继续读取文件名、大小、MD5、分卷、光盘编号、光盘日期和光盘容量
- AND 不修改正式 Word 模板、VML、分页、Legacy 报告解析或主渲染逻辑

**Scenario: Shadow 和 Canonical 隔离**

- WHEN 本变更的归档来源选择和复核功能被实现或验证
- THEN 只有 Legacy 正式输出可以消费该公共 Manifest
- AND 不新增 Shadow 差异治理逻辑、不切换 Canonical、不把 `source_mode` 暴露为 Canonical 输入

## CAP-TESTING：测试边界

### REQ-TESTING-001：合成小文件和可测边界

**Scenario: 自动化测试执行归档来源校验**

- WHEN 测试覆盖单卷、新式连续分卷、缺卷、重复卷、混合命名、旧式分卷、权限/可读性、删除、大小变化、MD5 变化和 token 生命周期
- THEN 测试只创建带有 `SYNTHETIC`/`TEST`/`FIXTURE` 标记的合成小文件，并通过注入的 fake picker、hash/WinRAR 能力和临时目录运行
- AND 不创建或提交真实 RAR、GB 级文件、本机路径、Manifest、DOCX 或运行输出

**Scenario: 自动模式回归**

- WHEN 测试系统自动压缩模式和用户提供模式
- THEN 断言用户提供模式从未调用 WinRAR 压缩执行器，自动模式仍通过既有执行器和导出门控
- AND 断言模式切换不会产生竞争请求，服务重启不会错误复用失效路径
