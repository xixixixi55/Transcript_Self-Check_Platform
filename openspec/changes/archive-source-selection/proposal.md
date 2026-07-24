# Proposal: 归档来源选择与已有压缩包复用

> Change ID: `archive-source-selection`
> Status: `PROPOSED`
> Level: 3
> Date: 2026-07-24
> 基线：`master` / `221572727d8f19031d44c913f2332dad005530ac`

## Why

审核编辑页面当前在报告载入、光盘编号有效后由 `useArchivePreparation` 自动派发 WinRAR 归档请求。用户如果已经准备好单卷或完整分卷压缩包，仍需等待系统再次压缩；同时，修改光盘编号会和归档准备产生隐式竞争。

浏览器文件选择器不能把用户本机的真实绝对路径安全地交给后端。首版需要在受信任的本机部署环境中由后端调用 Windows 原生文件选择器，前端只接收一次性 opaque selection token 和脱敏后的文件名，后端直接读取已授权的原文件，不复制、移动或删除原文件。

## Capabilities

### CAP-ARCHIVE-MODE-001：显式选择和显式执行

审核编辑页面提供“系统自动压缩”和“使用已有压缩包”两种模式。未选择模式时不派发归档请求；选择自动压缩后必须点击“开始压缩”，选择已有压缩包后必须完成“选择文件”并点击“校验并使用”。光盘编号的填写或修改本身不触发 WinRAR。

### CAP-ARCHIVE-SELECTION-002：本机已有文件选择

后端在可用的交互式 Windows 会话中调用原生文件选择器，签发绑定当前会话和归档上下文、短 TTL、单次使用的 opaque token。前端仅持有 token、脱敏文件名、卷数和过期信息；原始绝对路径只存在于受保护的后端运行时记录中。

### CAP-RAR-VOLUME-003：单卷和新式分卷识别

支持 `name.rar` 以及 `name.part1.rar`、`name.part2.rar` 等新式分卷。用户可以选择任一分卷，后端只在该文件所在目录按同 base 名称发现完整集合，要求序号从 1 连续递增，拒绝缺卷、重复卷、混合单卷/分卷、额外同 base RAR 以及旧式 `.r00/.r01`。

### CAP-ARCHIVE-INVENTORY-004：外部文件清单校验

对每卷执行路径授权、存在性、可读性、非目录、reparse point 安全检查，并流式计算文件大小和 MD5。生成 Manifest 前再次 stat；正式导出前再次确认文件存在、大小和 MD5 未变化。首版不解压，也不逐文件核对压缩包内部内容与报告目录。

### CAP-MANIFEST-COMPATIBILITY-005：Legacy Manifest 与 Word 兼容

已有压缩包校验成功后产出与系统自动压缩相同的公共 `ArchiveManifest` 输入，保持 Word 读取的 `parts[].filename`、`size_bytes`、`md5`、`part_number`、`disc_number`、`disc_date` 和 `disc_capacity_bytes` 不变。`generated/user_provided` 优先留在内部运行时归档记录中。

### CAP-ARCHIVE-LIFECYCLE-006：来源隔离和安全清理

用户提供归档首版为会话级状态，不写入自动归档持久化复用索引，不覆盖仍有效的正式 Manifest，不把真实路径写入 Manifest、前端响应或日志。解析缓存清空、运行时过期清理和失败回滚均不得删除或修改用户原文件；服务重启、token 过期或文件移动后要求重新选择。

## Non-Goals

- 不要求证明压缩包内部内容与当前报告目录逐文件完全一致。
- 不解压、不复制全部压缩包内容，不以 WinRAR `t` 完整性测试作为首版生成大小、MD5 和分卷信息的前置条件；完整性测试仅作为可选能力评估。
- 不支持 ZIP、旧式 `.r00/.r01`、其他 RAR 命名变体或跨目录分卷集合。
- 不修改正式 Word 模板、VML、分页、Word 主渲染逻辑、Legacy 报告解析。
- 不进入 Shadow 差异治理，不切换 Canonical，不扩大正式输出链路。
- 不建设完整桌面应用壳；仅在确认后端原生选择器在当前部署方式不可用时，再单独提出桌面桥接方案。
- 不使用真实案件数据、本机真实路径、真实压缩包、GB 级文件、RAR 或 DOCX 运行输出进行自动化测试。

## Impact

### 用户体验与触发边界

归档区从“自动准备”改为显式状态机。报告进入审核编辑只初始化状态；模式选择不执行归档；“开始压缩”或“校验并使用”才创建一次准备尝试。切换模式会显式废弃当前未完成尝试并取消其前端消费资格，但不会静默覆盖已完成且仍有效的正式 Manifest。重新准备已完成归档必须由用户明确确认。

### API 与公共合同

需要增加选择 token 和归档模式的请求/响应合同，以及选择器不可用、token 无效/过期、`part missing`、`part changed` 等稳定错误码。公共 `ArchiveManifest` 首版不增加 `source` 字段：前端可从本地模式状态展示来源，Word 和现有外部消费者不需要识别来源；内部运行时记录保存 `source_mode`。只有未来证明外部 API、持久化审计或跨页面展示必须读取来源时，才另开公共合同变更。

### 预计影响模块

- Frontend：`useArchivePreparation`、`RecordGeneratePage`、`RecordEditorForm`、归档状态/选择组件和对应测试。
- Backend：文件选择与授权存储、RAR 卷集合解析、已有归档校验、运行时 Manifest 来源记录、导出前复核、archive controller 和测试。
- SharedTypes：新增模式、选择摘要和错误码的 API 类型；不修改 `ArchiveManifest` 字段。
- Word：不改实现；增加现有 Manifest 到附件计划/Word 字段的回归测试即可。

### 风险、回滚与发布边界

自动压缩仍调用现有 WinRAR 执行链路，但触发改为显式按钮；可通过关闭已有归档模式入口或回滚本变更恢复旧页面。已有归档是外部文件来源，必须将读取、授权、token 和导出复核放在同一安全边界内。后端没有交互式 Windows 桌面时，选择器能力应明确返回不可用，不应退化为浏览器上传或泄露路径。

## Level 3 rationale

本变更同时改变审核页面归档触发状态、引入本机文件选择和路径授权安全边界、增加新的 API 请求/响应、扩展核心归档运行时记录并影响导出前 Manifest 权威校验。它不是局部 UI 改动，属于跨层公共行为和安全边界变化，按 Level 3 执行 proposal、spec、design、tasks、implementation、verify、review、archive 的完整流程。本轮只完成文档，暂不实施后四个阶段。

## Acceptance summary

实现完成后，合成小文件测试应证明：未选择模式或仅修改光盘编号不调用归档；自动模式仍调用原压缩链路；已有模式可从任一新式分卷发现并校验完整集合，不调用 WinRAR 压缩；缺卷、重复卷、混合命名、旧式分卷、不可读、删除、大小变化、MD5 变化和 token 失效均返回明确错误；Word 继续使用同一组 Manifest 字段；服务重启和缓存清理不会错误复用或删除用户原文件。
