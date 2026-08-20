# 测试资产盘点快照

> 快照日期：2026-08-20。第 1–8 节保留第二批测试治理后的盘点基线，第 9 节记录随后完成的 P0 修复；这是变更包内的时点证据，不是需要长期手工同步的 living 文档。

## 1. 结论

- 仓库共有 168 个自动化测试源文件、约 35,944 行测试代码。
- 正常 `npm test` 收集 1,600 条测试：前端 381 条，后端 1,219 条。
- `packages/shared` 另有 4 个测试文件、12 条测试，显式运行全部通过，但未被根 `npm test`、`verify:full` 或 `verify:quick` 纳入。
- 没有快照文件、独立 fixture 目录或测试专用二进制目录；大量后端资产由 `tmp_path` 动态合成。
- 4 个 DOCX 共 1,576,687 字节，既是产品运行模板，也是 13 个后端测试文件的共同基准，不能按“测试 fixture”直接删除。
- 当前主要资产风险不是 warning，而是 shared 测试门控缺口、测试模块互相导入、超大测试文件和覆盖层级失衡。

## 2. 测试源文件与收集范围

| 资产组 | 文件 | 收集项 | 测试代码行 | 当前门控 |
|---|---:|---:|---:|---|
| Frontend Vitest | 60 | 381 | 7,532 | `test:frontend`、`npm test`、`verify:full` |
| Shared Vitest | 4 | 12 | 185 | 未纳入；显式运行 4 文件/12 条通过 |
| Backend pytest | 103 | 1,219 | 28,010 | `test:backend`、`npm test`、`verify:full` |
| Governance assertions | 1 | 40 个顶层 assert 调用 | 217 | `test:governance`、`verify:quick`、`verify:full` |
| 合计 | 168 | 1,600 已门控 + 12 未门控 | 35,944 | 见上 |

前端 60 个文件按职责分布：Components 22、Hooks 24、Pages 4、Utils/Contracts 10。Shared 的 4 个文件分别验证：

- `downloadFileName.test.ts`：2 条
- `fieldProvenance.test.ts`：2 条
- `materialPhotoGroups.test.ts`：6 条
- `naturalEvidenceOrder.test.ts`：2 条

`@biji/shared` 只有 `build` 和 `typecheck` 脚本，没有 test 脚本。Frontend Vitest 的 root 是 `packages/frontend`，直接过滤 `../shared/utils` 会报告无测试文件；以仓库根显式调用相同 Vitest 配置时，4 文件/12 条全部通过。

## 3. 测试代码负担

| 区域 | 生产源码行 | 测试代码行 | 测试/源码比 |
|---|---:|---:|---:|
| Frontend | 7,665 | 7,532 | 0.98 |
| Shared | 3,146 | 185 | 0.06 |
| Backend | 35,411 | 28,010 | 0.79 |
| 全仓上述源码 | 46,222 | 35,944（含治理测试） | 0.78 |

按物理行统计，168 个测试文件的中位数为 146 行；19 个超过 400 行，7 个超过 800 行，2 个超过 1,200 行。最大的维护热点为：

| 文件 | 行数 |
|---|---:|
| `tests/test_workbench_controller.py` | 1,631 |
| `tests/test_phase1d_review_remediation.py` | 1,235 |
| `tests/test_record_controller.py` | 1,072 |
| `tests/test_winrar_timeout.py` | 915 |
| `tests/test_archive_runtime_lifecycle.py` | 898 |
| `tests/test_template_controller.py` | 871 |
| `tests/test_attachment_docx_renderer.py` | 826 |
| `tests/test_template_filler_service.py` | 755 |

超长不等于低价值。WinRAR、安全恢复和归档生命周期属于高风险矩阵，应先按职责拆分或复用 fixture，不能仅因行数或用例数删除。

## 4. Backend 测试资产分布

以下分类按文件名做互斥归组，用于识别资产重心，不代表正式 capability 边界：

| 资产域 | 文件 | 收集项 |
|---|---:|---:|
| Archive / compression | 29 | 374 |
| Workbench / record / parsing | 20 | 271 |
| Reference / policy / API | 19 | 216 |
| Word / template / attachment | 11 | 199 |
| Runtime / portable / filesystem | 10 | 63 |
| Contracts / shadow / governance | 8 | 62 |
| Retention / cleanup | 6 | 34 |

基础设施特征：

- 24 个 pytest fixture 定义，均分散在测试模块内；没有公共 `tests/conftest.py`。
- 56 个 `parametrize` 装饰器；参数化数量是 1,219 条收集项高于函数数量的主要原因之一。
- 83/103 个后端测试文件使用 `tmp_path`，测试输入和输出主要动态生成。
- 27 个文件直接处理 DOCX、ZIP 或 OOXML；9 个文件启动 subprocess/runpy。
- 最新隔离环境全量结果为 1,216 passed、3 skipped；代码中共有 9 个条件/运行时 skip 位置，实际跳过数取决于平台和外部工具。

## 5. Fixture、模板与二进制资产

仓库没有以下测试资产：

- `fixtures/`、`testdata/`、`golden/` 或 `__snapshots__/` 目录
- Vitest/Jest `.snap` 文件
- `tests/` 下跟踪的图片、压缩包、PDF 或 DOCX

跟踪的二进制基准只有 `word_templates/` 下 4 个互不相同的 DOCX：

| 文件 | 字节 |
|---|---:|
| `template-v1.0.0.docx` | 656,582 |
| `template-v1.0.1.docx` | 306,711 |
| `template-v1.0.2.docx` | 306,726 |
| `template.docx` | 306,668 |

这些文件同时承担内置产品模板、版本迁移基准、OOXML 合同基准、正式生成输入和 portable 打包资源，不是可随测试删除的独立 fixture。

## 6. 资产耦合与门控缺口

### P0：Shared 测试未进入任何标准门控

4 个文件/12 条测试处于“仓库存在且可通过，但常规验证永远不运行”的状态。后续应先建立职责映射，再决定：

1. 将它们纳入标准测试命令；或
2. 若其风险已被 Frontend/Backend 等价覆盖，迁移唯一断言后删除。

在完成映射前，不能把这 12 条计入当前 1,600 条质量证据，也不能直接认定为冗余。

### P1：测试模块互相充当 fixture 库

10 个后端测试文件直接从另外 7 个 `test_*.py` 模块导入 helper/常量。主要依赖链包括：

- Phase1D safety/recovery/remediation 测试链
- Case cleanup → tombstone 测试 helper
- Template controller/profile/customization/record generator → legacy report helper
- Record generator → template filler manifest helper
- Parse cache lifecycle → cache metadata helper

删除或拆分 provider 测试文件会隐式影响其他测试资产。后续治理前应先把真正共享的数据 builder 与断言 helper 识别出来，避免以测试模块作为公共 API。

### P1：覆盖层级失衡

- 有 60 个 Frontend Vitest 文件，但没有 Playwright/E2E 测试资产。
- Pages 行为主要由 jsdom 组件集成测试承担；数量增长不能替代真实浏览器/桌面流程证据。
- `verify:full` 当前也不包含 E2E，这与已有治理文档声明一致。

### P2：大文件和高成本资产

优先盘点 19 个超过 400 行的测试文件，并区分：安全矩阵、参数合同、重复 setup、重复生成过程、跨层重复断言。只有后两类是优先合并候选。

## 7. 后续治理顺序

1. 对 4 个 Shared 测试逐条建立“唯一风险断言 → 当前门控覆盖”矩阵，先解决 12 条孤儿资产。
2. 绘制 10 个 cross-test import consumer 与 7 个 provider 的依赖表，禁止在未迁移 helper 前删除 provider。
3. 对 19 个超长文件按 setup 成本、外部进程、DOCX 生成次数和风险等级排序。
4. 分别治理“重复职责”和“慢 setup”，不以合并安全参数矩阵换取测试数量下降。
5. Warning/mock/jsdom 日志治理暂停，不纳入本轮后续动作。

## 8. 统计说明

- 测试文件和行数来自 `rg --files` 与物理行统计。
- Backend 收集项来自 `pytest --collect-only -q`，共 1,219 条。
- Frontend 收集项来自已通过的 Vitest 全量运行，共 381 条。
- Vitest `list --json` 在 60 秒内未完成，本盘点未使用其输出，也未推断具体原因。
- 测试/源码比用于衡量维护体量，不用于判断测试价值或设定机械删除目标。

## 9. P0 修复结果

Shared 的 4 个孤儿测试已按职责映射完成处置：

- 下载文件名和检材分组的主要合同已由现有 gated Frontend 单元、Hook 和组件测试直接覆盖，不保留重复 Shared 测试。
- 来源标签、confirmed 状态不显示待确认提示、多数字段文件名排序、扩展名排序和带前导零的位置解析，已并入现有 `InspectorEditor` 与 `ImageUploader` 测试，不新增测试条目。
- `naturalEvidenceOrder` 与 `markFieldStateUserEdited` 在生产代码中均无调用；删除实现及导出，不为无消费者代码保留测试。
- 同名文件稳定排序属于运行时稳定排序保证，且位置命名模式会拒绝重复槽位，不再作为独立产品风险断言。

修复后的资产状态：

| 指标 | 盘点基线 | P0 修复后 |
|---|---:|---:|
| 测试源文件 | 168 | 164 |
| 测试代码行 | 35,944 | 35,765 |
| 标准门控收集项 | 1,600 | 1,600 |
| 门控外孤儿测试 | 4 文件 / 12 条 | 0 |

Frontend 全量仍为 60 文件/381 条通过；Backend 未受本次 TypeScript 清理影响，沿用同一工作区刚完成的 1,216 passed/3 skipped 结果。P0 修复减少了无效资产和死代码，没有通过增加测试数量弥补门控缺口，也没有继续处理 warning。

## 10. P1 Controller 测试合并记录

### Cross-test import 依赖

静态核对确认共有 10 个 consumer 测试文件、7 个 provider 测试文件，形成 13 条导入边：

| Provider | Consumer | 被当作公共资产的内容 |
|---|---|---|
| `test_phase1d_recovery.py` | `test_archive_second_round_safety.py`、`test_phase1d_fourth_review.py`、`test_phase1d_review_remediation.py` | case/source 常量、database fixture、ready/available helper |
| `test_phase1d_review_remediation.py` | `test_archive_second_round_safety.py`、`test_phase1d_fourth_review.py` | trusted completion、valid manifest builder |
| `test_case_tombstone_repository.py` | `test_case_record_cleanup_repository.py` | case/task/source 常量与 `_prepare` |
| `test_workbench_persistence.py` | `test_phase1d_recovery.py` | `IDENTITY`、`REPORT` |
| `test_legacy_report_projection_service.py` | `test_record_generator_service.py`、`test_template_customization_service.py`、`test_template_controller.py`、`test_template_profile_service.py` | report builder |
| `test_template_filler_service.py` | `test_record_generator_service.py` | manifest builder |
| `test_report_parse_cache_metadata.py` | `test_report_parse_cache_lifecycle.py` | report/cache-file builder |

本批没有删除或重命名这些 provider，也没有为了整理目录新增测试。后续若治理对应 provider，必须先迁移共享资产，不能把测试模块继续当作隐式公共 API。

### 删除与替代覆盖说明

本批从标准 Backend 门控合并 7 个收集项；以下逐项记录原因：

| 被删除的独立测试 | 删除原因 | 保留或替代的质量证据 |
|---|---|---|
| `test_parse_folder_compress_false` | 与 `compress=true` 使用同一端点、setup 和预览上下文合同；该参数已明确标记 deprecated，原测试也未断言独立的 false 行为。 | 合并后的 `test_parse_folder_accepts_deprecated_compress_values` 仍分别发出 true/false 请求，并对两者执行相同的成功、上下文和待准备状态断言。 |
| `test_parse_rejects_configured_root_itself` | 与“不允许的外部根目录”共享同一个 HTTP 错误码和路径脱敏映射，独立函数重复 Controller 映射。 | `test_parse_rejects_disallowed_roots_and_does_not_echo_paths` 同时验证两类路径；Repository 的 `test_configured_root_itself_and_prefix_sibling_are_rejected` 保留精确边界断言。 |
| `test_clear_empty_report_parsing_cache_is_idempotent` | 0 条缓存的幂等性属于 Service 行为，Controller 对 `cleared_count` 的透明封装已由非零返回验证。 | `test_clear_is_idempotent_and_never_deletes_archive_or_defaults` 直接验证连续清理得到 1/0 且不误删其他资产；Controller 保留成功映射和失败脱敏测试。 |
| `test_clear_cache_controller_offloads_file_work` | 与成功返回测试重复构造同一 Controller 请求，仅多断言一次 threadpool 调度。 | threadpool mock、await 和目标函数断言已并入 `test_clear_report_parsing_cache_returns_count_and_ignores_client_path`。 |
| `test_parse_invalid_format_returns_400` | 与“缺少输入”同属同一端点的输入拒绝合同，setup 很小且无需独立 fixture 生命周期。 | 合并后的 `test_parse_rejects_missing_or_invalid_archive_input` 分别发送两种请求并断言各自的 400 和可区分消息。 |
| `test_select_export_directory_endpoint_cancel_returns_cancelled` | 与选择成功共享完全相同的 picker、服务和端点 setup，仅返回分支不同。 | 合并后的 tri-state 测试仍实际调用取消分支并断言 `{cancelled: true}`。 |
| `test_select_export_directory_endpoint_fails_when_picker_unavailable` | 与选择/取消属于同一无持久化副作用端点的第三个返回分支，独立 TestClient setup 重复。 | 同一 tri-state 测试仍将 picker 设为不可用并断言 422 与 `DIRECTORY_PICKER_UNAVAILABLE`。 |

合并后测试文件数保持 164，测试代码约 35,765→35,723 行；Backend 收集项 1,219→1,212，标准总收集项 1,600→1,593。没有删除安全、权限、持久化、并发、恢复、归档生命周期或关键数据转换矩阵，也没有继续治理 warning。

## 11. P2 Word/DOCX 重复生成合并记录

5 个相关套件基线为 84 条/48.82 秒。以下删除的是重复的真实 DOCX 生成，不是将参数化改写成循环：

| 删除的独立参数/测试 | 删除原因 | 保留或替代的质量证据 |
|---|---|---|
| 附件一最终签名分页 `count=1` | 同一个 `manifest(1)` 已由空白斜线专项测试生成；原参数只补充表格行数与签名位置。 | 空白斜线测试新增 5 行表格、检查人员与盖章断言。 |
| 附件一最终签名分页 `count=3` | 字体基线专项测试已用 `manifest(3)` 生成同一布局。 | 字体基线测试保留 5 行结构，并新增完整检查人员/盖章签名断言。 |
| 附件一最终签名分页 `count=4` | 四条目签名换页专项测试已验证 `[5,1]` 分页和前页无签名。 | 专项测试新增盖章断言，完整承接最终页合同。 |
| 附件一最终签名分页 `count=5` | 附件一起始分页测试已用 `manifest(5)` 验证 `[5,2]`、标题、页数和最终签名。 | 该测试新增首表无签名断言；最终签名仍验证检查人员与盖章。 |
| 附件一最终签名分页 `count=6` | 六条目空白行专项测试已验证 `[5,3]`、两条数据与最终签名行。 | 专项测试新增首表无签名和最终盖章断言。 |
| `test_attachment2_continuation_titles_are_empty_break_paragraphs` | 与三检材续页居中测试使用相同 6 图、2 页布局并各自生成一次 DOCX。 | 空续页标题、唯一“附件2：”和分页符断言已并入三检材续页测试。 |
| Filler 图片回归：单张横图 | 横向几何已由纯 `calculate_fixed_geometry` 和实际 Renderer 横/竖图测试覆盖。 | 保留单张超大图验证单图集成边界，四张混合图验证多图顺序与几何写入。 |
| Filler 图片回归：单张竖图 | 纵向几何已有纯函数和实际 Renderer 覆盖，原测试与单横图仅输入尺寸不同。 | 同上；实际 DOCX Renderer 仍同时验证横图与竖图 extent。 |
| Filler 图片回归：两张横/竖图 | 两图布局、横竖 extent、嵌入顺序在 Attachment2 Renderer 中已有更强断言。 | 保留四张混合图的 Filler 集成以及两图 Renderer 网格/顺序测试。 |
| Filler 图片回归：两张超尺寸图 | 超尺寸缩放对每张图片独立计算，两张相同超大图不引入新分支。 | 保留单张超大图集成、纯几何超界缩放和多图 Renderer 测试。 |

定向套件修复后为 74 passed/34.32 秒，减少 10 个收集项和 10 次真实 DOCX 生成，墙钟减少 14.50 秒（约 29.7%）。测试代码约 35,723→35,714 行；Backend 全量为 1,199 passed/3 skipped，收集项 1,212→1,202，标准总收集项 1,593→1,583。全量墙钟由上一批同入口的 183.10 秒降至 162.52 秒（单次运行会受环境波动影响）。奇数图片拒绝、无效图片清理、模板 profile 漂移、模板不可变性、脱敏和正式导出门控均未删除。

## 12. P3 子进程启动合并记录

静态扫描发现 15 个测试文件引用 `subprocess`/`CompletedProcess`/`TimeoutExpired`，其中多数只构造返回值或 patch 进程 API；实际启动外部进程的是 7 个文件。以下边界保留：

- 合同检查：一次有漂移失败、一次无漂移通过，两个进程结果不可互相替代。
- 模板清理与平衡脚本：每个脚本运行两次并与跟踪模板逐字节比较，用于证明确定性。
- Portable 入口、Windows Job Object、Phase1D 进程所有权恢复和真实 WinRAR 目录结构：验证的就是进程生命周期或外部程序边界。

唯一重复启动集中在 `test_python_arch_check.py`：9 条测试每条都启动一次 `_python_imports.py`，而核心风险是 AST 提取与 JSON payload，只有参数/标准输出接线必须经过真实 CLI。`scripts/_python_imports.py` 因此导出与 CLI 共用的 `extract_files`，保留一次批量 CLI smoke，其余直接调用。

| 被合并的独立测试 | 删除原因 | 保留或替代的质量证据 |
|---|---|---|
| `test_level1_same_package` | 与 level-2 相对导入走同一 `ast.ImportFrom` 分支，仅 level 值不同。 | 并入批量 CLI smoke，仍断言 level=1 和模块名。 |
| `test_multi_line_parenthesized` | 多行写法由 Python AST 归一化，不需要独立进程。 | 并入同一次 CLI，仍断言 `repository.foo`。 |
| `test_type_checking_block_still_extracted` | 风险是 `ast.walk` 不应忽略条件块，与其他相对导入可在同一批文件验证。 | 并入同一次 CLI，仍断言条件块中的 `config`。 |
| `test_third_party_absolute_skipped` | 与 `app.*` 绝对导入识别构成同一分类合同。 | 合并测试同时断言内部模块被提取、第三方/标准库为空。 |
| `test_valid_file_no_errors` | 单独只验证空错误列表，不能覆盖错误文件与有效文件共存。 | 与语法错误测试合并后，同时断言错误只属于坏文件且有效文件仍被提取。 |

Python 架构测试由 9→4 条、真实进程启动由 9→1；与合同检查、模板脚本组成的定向组合由 18→13 passed、8.74→7.24 秒。测试代码约 35,714→35,688 行；Backend 全量为 1,194 passed/3 skipped，收集项 1,202→1,197，标准总收集项 1,583→1,578。全量墙钟为 161.09 秒；相较上一批 162.52 秒的变化较小，主要收益以明确减少的 8 次进程启动和定向 1.50 秒为准。

## 13. P4 报告/模板共享 builder 与 Generator 交接合并记录

报告/模板链原有 5 条测试模块间导入边：4 个 consumer 从 `test_legacy_report_projection_service.py` 导入 report builder，Record Generator 另从 `test_template_filler_service.py` 导入 manifest builder。provider 测试一旦改名、拆分或删除就会隐式破坏其他套件。两个 builder 已迁入不参与 pytest 收集的 `tests/synthetic_report_builders.py`，相关 cross-test import 由 5→0；全仓 cross-test import 由 13→8。此次新增的是测试支持模块，不新增测试条目。

### 删除与替代覆盖说明

本批只合并 1 个收集项，没有删除 Projection、真实 DOCX、模板合法性、不可变性、持久化、并发或正式导出边界：

| 被合并的独立测试 | 删除原因 | 保留或替代的质量证据 |
|---|---|---|
| `test_generator_migrates_the_exact_legacy_step_four_before_word_render` | 与保存顺序/脱敏测试调用同一个 `generate_docx → fill_template` 交接点、使用相同 mock 和输出 setup；唯一差异是在输入中加入旧版第 4 步文案。独立执行不会覆盖额外的进程、IO 或错误分支。 | 保留的 `test_generator_passes_normalized_saved_order_projection_to_word_renderer` 在同一次调用中加入旧步骤，并继续断言检材顺序、人员快照顺序、UI 元数据清理以及迁移后的完整精确文案。原测试的全部行为断言均保留。 |

6 个相关套件由 60→59 条，修复后定向结果为 59 passed/16 warnings/33.90 秒。warning 属于既有环境告警，本批按约定不处理。以下风险因职责不同而明确保留：Projection 的重复/不可识别编号稳定性，真实 DOCX XML 顺序与脱敏，Profile 指纹和结构漂移，Customization allowlist，Controller 的审批、回滚、并发和迁移，以及正式导出的多重指纹门控。

Backend 全量收集项由 1,197→1,196，正常权限下结果为 1,193 passed/3 skipped/37 warnings、196.29 秒；加上未变化的 Frontend 381 条，标准总收集项由 1,578→1,577。首次沙箱内全量因默认 LocalAppData SQLite 对沙箱账户只读而失败，同一命令在正常权限下通过，故不计为代码回归。`verify:quick`、scoped strict docs、OpenSpec strict 与 `git diff --check` 均通过。

## 14. P5 Parse-cache 与 case cleanup 支持链合并记录

4 个相关套件基线为 25 passed/5.93 秒，并包含 2 条测试模块间导入边。Parse-cache 的 tree builder 已迁入 `synthetic_report_builders.py`，tombstone 常量和完整 setup 已迁入 `case_cleanup_test_support.py`；两者均不参与 pytest 收集。本批相关 cross-test import 由 2→0，全仓由 8→6，剩余 6 条全部属于 Phase1D safety/recovery/remediation 链，本批不触碰。

Parse-cache 13 条测试全部保留：它们分别覆盖未改变命中、mtime 同内容、内容变化、无关文件、候选成员变化、删除候选、删除核心输入、旧缓存迁移、相同目录并发、clear 代际、验证期 join 和不安全路径拒绝，不能用数量相近替代风险等价证明。

### 删除与替代覆盖说明

| 被合并的独立测试 | 删除原因 | 保留或替代的质量证据 |
|---|---|---|
| `test_cleaned_case_rejects_edit_and_lifecycle_transition` | 与成功 compact/restart 测试构造完全相同的 tombstone 成功状态，只额外验证清理后的三种拒绝；独立函数重复一次完整 retention、publication、artifact 和 cleanup-run setup。 | 三个异常断言已并入 `test_compact_keeps_formal_facts_and_rejects_record_edits_after_restart`，继续验证 `CASE_RECORD_CLEANED`、`DRAFT_NOT_FOUND`、formal Word 保留、清理状态和重启后事实。 |
| `test_tombstone_ignores_lease_from_another_deployment` | 与 deployment scope 测试使用相同 setup 和相同 shell deployment 改写，唯一额外行为是创建旧 deployment lease 并调用 active-work 边界。 | lease 创建和 `_assert_no_active_work` 已并入 `test_case_draft_and_active_work_are_deployment_scoped`，同时保留 case list/get/update、draft get/save 的完整跨 deployment 拒绝断言。 |

相关套件由 25→23 条，定向结果为 23 passed/8.33 秒；单次墙钟较基线受环境波动反而上升，因此不宣称性能收益，只记录确定减少 2 次完整数据库 setup。Formal authority、active lease 阻断、回滚、naive time、snapshot active/recovery、receipt 缺失和 unknown ownership fail-closed 测试均未删除。

Backend 全量收集项由 1,196→1,194，最终复跑结果为 1,191 passed/3 skipped/37 warnings、168.35 秒；加上未变化的 Frontend 381 条，标准总收集项由 1,577→1,575。首次全量仅未改动的 archive runtime revision 时序用例失败，该用例单独复跑通过且第二次全量未复现，未为通过门控而修改断言或业务代码。`verify:quick`、scoped strict docs、OpenSpec strict 与 `git diff --check` 均通过。
