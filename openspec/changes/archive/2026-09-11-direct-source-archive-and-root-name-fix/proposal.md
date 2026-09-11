# Proposal: 直接压缩源报告并保留原始根目录名

> 变更包：`direct-source-archive-and-root-name-fix`
> 级别：Level 3

## 原因

当前归档会在 WinRAR 前把完整报告复制为密封快照。该设计适合严格不可变归档，但项目的主要用途是日常生成笔录，大型报告会因额外的全量复制产生明显等待和磁盘 I/O。产品决策改为直接压缩用户选定的源报告目录，并通过明确提示控制日常误操作风险。

> 后续演进：已归档的 `metadata-fingerprint-archive-path` 进一步将正式合同收敛为“Worker 仅构建一次完整 inventory，不在 WinRAR 前后重复递归扫描”。本包收尾以现行规格为准；下文原先的双 inventory 门控不再作为验收要求。

已发现的回归也需同时修复：现有 WinRAR 执行器在源目录名与快照名不同时传入绝对快照路径，导致压缩包内根目录变成 `.i/s...` 等内部路径，而不是原始报告目录名。

## 非目标

- 不保证源目录在 WinRAR 执行期间的强不可变性；用户已接受“日常效率优先”的产品取舍。
- 不删除历史快照数据表、恢复逻辑或清理能力；已有尝试和旧数据仍需可安全清理。
- 不改变 WinRAR 分卷大小、RAR/MD5/Manifest 完整性验证、发布代次或统一导出规则。
- 不接受用户自定义压缩包内根目录；根名始终来自已授权源报告目录。

## 能力

- `electronic-inspection-record`：
  - **MODIFIED REQ-012**：“立即开始压缩”前必须告知用户压缩期间不得修改、移动、删除源目录，也不得继续向其写入；用户确认后才创建归档任务，执行中持续显示同类提示。
  - **MODIFIED REQ-ARCHIVE-IMMUTABLE-INPUT**：新归档尝试直接读取已授权源目录，不再创建全量输入快照；同一 Worker 只构建一次完整 inventory，WinRAR 或输出校验观察到变化/错误时安全失败。
  - **ADDED 归档根目录合同**：RAR 内部顶层目录必须精确等于原始报告目录名，不得出现 `.i`、`.inputs`、快照 token 或本机绝对路径片段。

## 影响

| 层级 | 预计文件 | 影响 |
|------|----------|------|
| FE Components (11) | `packages/frontend/src/components/ArchiveDecisionPanel.tsx` | 增加开始前确认与执行期风险提示 |
| FE Pages (12) | `packages/frontend/src/pages/CaseRecordGeneratePage.tsx` | 将立即压缩动作接入确认交互 |
| BE Repository (20) | `packages/backend/app/repository/archive/winrar_executor_repository.py` | 始终以相对原始目录名调用 WinRAR，保留正确内部根目录 |
| BE Services (21) | `packages/backend/app/services/archive/archive_execution_service.py` 及 attempt 验证/完成服务 | 改为单次直接源 inventory，移除新尝试对 sealed snapshot 证据的依赖 |
| Tests | `tests/test_archive_execution_service.py`、`tests/test_archive_executor_validator.py`、`tests/test_winrar_directory_structure_integration.py`、前端组件/页面测试 | 锁定直接源路径、单次枚举、原始根名和用户提示 |

## 风险

- 单次 inventory 不证明执行全程强不可变；用户确认后仍在压缩期间修改来源属于明确告知的风险边界。
- WinRAR 或输出完整性校验实际观察到来源/输出错误时必须安全失败，不得伪造成功。
- 历史 attempt 可能仍绑定 snapshot；兼容清理不得把外部源目录当成平台资产删除。
