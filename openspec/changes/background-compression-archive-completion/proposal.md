# Proposal: 后台压缩与归档完成统一导出

> 变更包：`background-compression-archive-completion`
> 级别：Level 3
> 范围：报告解析完成后，案件打开时可选「立即/稍后」启动后台压缩（替换预览手动归档触发）；压缩不阻塞审核编辑；每个 RAR 完成时实时覆盖填写检查结果与附件1；首个光盘编号可在压缩前或压缩后输入并按 part 顺序自动映射；全部 RAR/MD5/盘号对应完成后案件进入归档完成态并提示输入导出路径；统一导出最新 Word + RAR + HashMyFiles 三列校验截图（可重复）；导出成功后案件卡片标记已导出并提供彻底删除按钮。
> 基线：现有 workbench 后台归档任务（REQ-012/REQ-025）、Legacy 分卷归档合同（REQ-018）、单 Word 导出（REQ-009）、从最终 Manifest 生成附件1（REQ-017）、案件删除能力（`case-workbench-delete`，已完成）。

## Why

现状与目标差距：

- **触发依赖手动同步归档**：压缩目前经审核页手动 `EXECUTE_ARCHIVE`（同步等待完成）；虽有 REQ-012/REQ-025 的「立即/稍后」状态与后台任务，但需求要求把「案件打开时的立即/稍后选择」变成主触发，且压缩全程不得阻塞审核编辑。
- **盘号必须先填**：`plan_archive` 在压缩阶段就要求 `first_disc_number`，未填直接 `FIRST_DISC_NUMBER_MISSING` 失败。需求要求压缩前或压缩后均可输入首个盘号，输入后自动按 part 顺序生成全序列并一一映射。
- **附件1/检查结果一次性填充**：`usePreviewArchive` 在 Manifest 全部完成后一次性写入 `rar_filename/md5_hash/file_size` 与附件1。需求要求每个 RAR 完成即实时覆盖填写。
- **导出只有单 Word**：`/records/export` 仅下载一个 `.docx`，不含 RAR 与校验截图，也不写入用户指定路径。需求要求把「最新编辑 Word + 全部 RAR + HashMyFiles 校验截图」统一导出到用户选择的路径，导出成功标记已导出并提供彻底删除。

## Non-Goals

- **不改变 WinRAR 分卷规则**：沿用固定体积自动分卷（REQ-018 的 4GB/22GB/45GB 档位）与 part 顺序。
- **不实现 Canonical 双轨**：继续 Legacy 唯一正式输出；Shadow 只做旁路比较，不参与状态、进度、门控或正式产物。
- **不改变归档快照密封/元数据校验/崩溃重试契约**：`REQ-ARCHIVE-IMMUTABLE-INPUT`、`REQ-ARCHIVE-PUBLICATION-GENERATION` 等保持不变。
- **不重写案件删除**：彻底删除复用 `case-workbench-delete`（已实现：确认后删除任意状态案件与平台受控产物，外部原始资料目录不删）。
- **不迁移 openspec delta 格式**：沿用仓库自定义轻量格式，权威门控为 `check-docs.ts`。
- **不处理导出路径下的副本生命周期**：导出路径由用户管理，彻底删除不触碰已导出副本。

## Capabilities

- `electronic-inspection-record`：
  - **MODIFIED REQ-012**：案件打开提供「立即/稍后」启动后台压缩选择，作为主触发（替换预览手动归档触发）；压缩不阻塞审核编辑；「稍后」持久化 `archive_deferred` 并从案件卡片再次启动。
  - **MODIFIED REQ-017**：附件1与检查结果由「归档完成后一次性填充」改为「每个 RAR 完成时实时覆盖填写」（文件名/大小/MD5）。
  - **MODIFIED REQ-009**：导出由「单个 Word 浏览器下载」改为「写入用户选择路径的统一导出包：最新 Word + 全部 RAR + HashMyFiles 三列校验截图」，可重复导出，Word 使用导出时刻最新编辑。
  - **ADDED REQ-030**：首个光盘编号可在压缩前或压缩后输入；压缩后可输入首个盘号，系统按 part 顺序自动生成全序列并一一映射；未填时卡片显示「待补盘号」中间态并保留补填入口。
  - **ADDED REQ-031**：全部 RAR+MD5+盘号对应完成后案件进入「归档完成」态并提示输入导出路径；导出成功后卡片标记「已导出」，提供「彻底删除」按钮（仅删平台内产物，复用 `case-workbench-delete`）。

## Impact

按 `harness/architecture.md` 分层矩阵（预计受影响文件，实际以 apply 阶段为准）：

| 层 | 预计文件 | 影响 |
|----|---------|------|
| SharedTypes/Constants (0–1) | `packages/shared/types/*`、`workbenchConstants.ts`、`constants/index.ts` | 新增统一导出请求/结果、盘号映射请求、案件状态（`待补盘号`/`归档完成`/`已导出`）、HashMyFiles PNG 产物契约 |
| BE Repository (20) | `workbench_schema.py`、归档/案件 repository | 持久化每 part 元数据与盘号映射、导出记录、已导出标记 |
| BE Services (21) | `archive_execution_service.py`、`archive_planner_service.py`、`archive_manifest_service.py`、新增盘号映射/HashMyFiles/统一导出服务 | 盘号后填（plan 不要求盘号）、每 RAR 回填回调、HashMyFiles.exe 调用、统一导出编排 |
| BE Controllers/Routes (22–23) | `archive_controller.py`、`record_controller.py`、新增导出 bundle 路由 | 后台压缩触发与状态、盘号映射、导出到路径、导出记录 |
| FE Hooks (10) | `useArchivePreparation.ts`、`usePreviewArchive.ts`、新增案件完成/统一导出 hooks | 案件打开立即/稍后选择、盘号后填与映射、导出路径选择、已导出状态 |
| FE Components/Pages (11–12) | `CaseCard.tsx`、`ArchiveStatusCard.tsx`、`CaseWorkbenchPage.tsx`、`CaseRecordGeneratePage.tsx` | 卡片立即/稍后入口、待补盘号中间态、归档完成提示导出路径、已导出标记与彻底删除按钮 |

### 风险与依赖

- **HashMyFiles.exe 部署**：选择「系统自动调用 exe」意味着需把工具纳入部署并配置路径（`BIJI_HASHMYFILES_PATH` 或随包放置）；其命令行参数与 HTML 输出格式需实测确认。
- **Manifest 复用指纹含盘号**：REQ-012 复用指纹包含首盘号；盘号后填会使指纹变化，需把盘号从复用指纹中解耦或复用校验排除盘号，避免后填导致重复压缩。
- **状态机一致性**：需把新状态（待补盘号/归档完成）映射进 REQ-025 的固定里程碑与案件状态，避免与现有 `archive_deferred/archiving/archive_verified/exporting_word/exported` 冲突。
- **删除能力引用**：彻底删除依赖 `case-workbench-delete` 已完成；仅新增「已导出」状态的删除入口，不重写删除逻辑。

## 关键决策摘要

详见 `design.md`。要点：复用 REQ-025 后台任务机制；`plan_archive` 允许无盘号执行并把序列生成延迟到映射阶段；每 RAR 完成在 md5/integrity 阶段回调回填；HashMyFiles 由后端导出时调用 exe；统一导出走 native picker 选择路径；新增「待补盘号」中间态与「归档完成」终态。
