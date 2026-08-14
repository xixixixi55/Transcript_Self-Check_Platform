# Proposal: 后台压缩与归档完成统一导出

> 变更包：`background-compression-archive-completion`
> 级别：Level 3
> 范围：报告解析完成后，案件打开时可选「立即/稍后」启动后台压缩（替换预览手动归档触发）；压缩不阻塞审核编辑；每个 RAR 完成时实时覆盖填写检查结果与附件1；首个光盘编号可在压缩前或压缩后输入并按 part 顺序自动映射；全部 RAR/MD5/盘号对应完成后案件进入归档完成态，工作台以「待导出」展示并提供统一导出；统一导出最新 Word + RAR + HashMyFiles 三列校验截图（可重复）；导出成功后案件卡片标记已导出并以删除案件作为推荐下一步，打开案件与再次导出保留为次要操作。
> 基线：现有 workbench 后台归档任务（REQ-012/REQ-025）、Legacy 分卷归档合同（REQ-018）、单 Word 导出（REQ-009）、从最终 Manifest 生成附件1（REQ-017）、案件删除能力（`case-workbench-delete`，已完成）。

## Why

现状与目标差距：

- **触发依赖手动同步归档**：压缩目前经审核页手动 `EXECUTE_ARCHIVE`（同步等待完成）；虽有 REQ-012/REQ-025 的「立即/稍后」状态与后台任务，但需求要求把「案件打开时的立即/稍后选择」变成主触发，且压缩全程不得阻塞审核编辑。
- **盘号必须先填**：`plan_archive` 在压缩阶段就要求 `first_disc_number`，未填直接 `FIRST_DISC_NUMBER_MISSING` 失败。需求要求压缩前或压缩后均可输入首个盘号，输入后自动按 part 顺序生成全序列并一一映射。
- **附件1/检查结果一次性填充**：`usePreviewArchive` 在 Manifest 全部完成后一次性写入 `rar_filename/md5_hash/file_size` 与附件1。需求要求每个 RAR 完成即实时覆盖填写。
- **归档后审核展示与 Word 不一致**：审核字段尚未齐全时，附件1回填兜底路径可能留下空的“提取方式”，而 Word 会按检查硬件生成提取方式；审核编辑界面必须显示同一语义。
- **盘号映射完成后不可修订**：归档完成态隐藏了首个光盘编号输入，且单独 Word 导出只校验草稿字段、未读取持久化分卷映射，导致已映射案件仍可能被 `FIRST_DISC_NUMBER_MISSING` 阻断。
- **两处 Word 导出交互不一致**：案件工作台「统一导出」会打开 Windows 原生目录选择器并写入用户选择路径，但审核编辑界面「导出 Word」仍由浏览器直接下载，用户无法在同一交互中明确选择落盘目录。两处入口需要复用同一目录选择器、目录记忆和一次性路径授权机制；统一导出仍额外包含 RAR 与校验截图。
- **压缩期间上传图片可能丢失草稿绑定**：图片二进制已经登记，但压缩中的草稿冻结与前端延迟保存使 `asset_refs/photo_groups` 未可靠落库；统一导出随后扫描到未绑定文件并以泛化 422 失败。图片绑定必须作为可并发审核编辑持久化，统一导出只能消费草稿明确绑定的图片并给出可操作错误。

## Non-Goals

- **不改变 WinRAR 分卷规则**：沿用固定体积自动分卷（REQ-018 的 4GB/22GB/45GB 档位）与 part 顺序。
- **不实现 Canonical 双轨**：继续 Legacy 唯一正式输出；Shadow 只做旁路比较，不参与状态、进度、门控或正式产物。
- **不改变归档快照密封/元数据校验/崩溃重试契约**：`REQ-ARCHIVE-IMMUTABLE-INPUT`、`REQ-ARCHIVE-PUBLICATION-GENERATION` 等保持不变。
- **不重写案件删除**：删除案件复用 `case-workbench-delete`（已实现：确认后删除任意状态案件与平台受控产物，已导出到目标目录的文件与外部原始资料目录不删）。
- **不迁移 openspec delta 格式**：沿用仓库自定义轻量格式，权威门控为 `check-docs.ts`。
- **不处理导出路径下的副本生命周期**：导出路径由用户管理，删除案件不触碰已导出副本。

## Capabilities

- `electronic-inspection-record`：
  - **MODIFIED REQ-012**：案件打开提供「立即/稍后」启动后台压缩选择，作为主触发（替换预览手动归档触发）；压缩不阻塞审核编辑；「稍后」持久化 `archive_deferred` 并从案件卡片再次启动。
  - **MODIFIED REQ-017**：附件1与检查结果由「归档完成后一次性填充」改为「每个 RAR 完成时实时覆盖填写」（文件名/大小/MD5）。
  - **MODIFIED REQ-009**：案件工作台统一导出与审核编辑单独 Word 导出均通过 Windows 原生目录选择器写入用户选择路径；统一导出包含最新 Word + 全部 RAR + HashMyFiles 三列校验截图，单独 Word 导出仅写入最新 `.docx`。两处均可重复导出并使用导出时刻最新编辑。
  - **ADDED REQ-030**：首个光盘编号可在压缩前或压缩后输入；压缩后可输入首个盘号，系统按 part 顺序自动生成全序列并一一映射；未填时卡片显示「待补盘号」中间态并保留补填入口。
    - 归档完成或已导出后仍保留首盘号编辑入口；再次提交按当前实际 part 顺序整体重建映射。
    - 案件内单独 Word 导出优先使用已持久化的首个分卷映射，不因草稿兼容字段为空误报缺少盘号。
  - **ADDED REQ-031**：全部 RAR+MD5+盘号对应完成后底层进入 `archive_complete`，工作台展示为「待导出」并以「统一导出」为推荐操作；导出成功后卡片标记「已导出」，以「删除案件」为推荐操作并在更多菜单保留「打开案件」「再次导出」（删除仅清理平台内产物，复用 `case-workbench-delete`）。

## Impact

按 `harness/architecture.md` 分层矩阵（预计受影响文件，实际以 apply 阶段为准）：

| 层 | 预计文件 | 影响 |
|----|---------|------|
| SharedTypes/Constants (0–1) | `packages/shared/types/*`、`workbenchConstants.ts`、`constants/index.ts` | 统一导出、单独 Word 路径导出、盘号映射、案件状态与 HashMyFiles PNG 产物契约 |
| BE Repository (20) | `workbench_schema.py`、归档/案件 repository | 持久化每 part 元数据与盘号映射、导出记录、已导出标记 |
| BE Services (21) | `archive_execution_service.py`、`archive_planner_service.py`、`archive_manifest_service.py`、新增盘号映射/HashMyFiles/统一导出服务 | 盘号后填（plan 不要求盘号）、每 RAR 回填回调、HashMyFiles.exe 调用、统一导出编排 |
| BE Controllers/Routes (22–23) | `archive_controller.py`、`record_controller.py`、导出相关路由 | 后台压缩触发与状态、盘号映射、统一/单独 Word 路径导出、导出记录 |
| FE Hooks (10) | `useArchivePreparation.ts`、`usePreviewArchive.ts`、案件完成/统一导出 hooks、`useRecordExport.ts` | 案件打开立即/稍后选择、盘号后填与映射、复用原生导出目录选择、已导出状态 |
| FE Components/Pages (11–12) | `CaseCard.tsx`、`ArchiveStatusCard.tsx`、`CaseWorkbenchPage.tsx`、`CaseRecordGeneratePage.tsx` | 卡片立即/稍后入口、待补盘号中间态、阶段主状态与推荐操作、已导出后的删除主操作 |

### 风险与依赖

- **HashMyFiles.exe 部署**：选择「系统自动调用 exe」意味着需把工具纳入部署并配置路径（`BIJI_HASHMYFILES_PATH` 或随包放置）；其命令行参数与 HTML 输出格式需实测确认。
- **Manifest 复用指纹含盘号**：REQ-012 复用指纹包含首盘号；盘号后填会使指纹变化，需把盘号从复用指纹中解耦或复用校验排除盘号，避免后填导致重复压缩。
- **状态机一致性**：待补盘号与待导出均由现有事实派生；工作台不新增持久化 lifecycle，统一导出期间只使用当前页面请求 loading，刷新后继续以服务端 lifecycle 为准。
- **删除能力引用**：删除案件依赖 `case-workbench-delete` 已完成；本次只调整不同阶段的入口权重，不重写删除逻辑。

## 关键决策摘要

详见 `design.md`。要点：复用 REQ-025 后台任务机制；`plan_archive` 允许无盘号执行并把序列生成延迟到映射阶段；每 RAR 完成在 md5/integrity 阶段回调回填；HashMyFiles 由后端导出时调用 exe；统一导出走 native picker 选择路径；新增「待补盘号」中间态与「归档完成」终态。
