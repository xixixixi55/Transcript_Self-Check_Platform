# Tasks: 检材持有人字段

workflow_level: 2
spec_sync_status: reconciled
spec_sync_evidence: 2026-09-11 legacy 结构化持有人反馈已同步到 openspec/specs/electronic-inspection-record/spec.md“检材持有人作为可选审核字段”。

## 关联结论与边界

- `support-legacy-and-new-report-formats` 已完成，且原范围明确把“持有人”列为非目标；本需求新增共享检材字段、审核编辑和草稿保存行为，不属于该包归档前回归。
- `conversational-review-shell` 已完成，原范围只把既有检材字段接入 Word 内容预览的原位编辑；本需求是在验收范围外增加新的检材事实字段，不重开原包。
- `extensible-report-template-platform` 尚在进行，但其当前任务围绕 Canonical/模板/归档迁移；本需求继续使用现有 `InspectionReport`/CaseDraft 链路，且明确不进入 Word，因此不并入该架构变更。

## 实施任务

- [x] T001 在共享 `EvidenceItem` 和报告设备行解析中增加可选 `holder_name`；new 报告只从结构化“检材持有人姓名”读取并绑定到对应检材，legacy 或缺失字段保持空值，不从通讯、联系人、案件名等内容猜测。更新既有 SYNTHETIC 解析测试。
- [x] T002 在 Word 内容预览的每项检材原位字段中展示并编辑“持有人”，沿用现有字段来源标记、只读限制、检材数组更新与草稿自动保存；兼容人工新增和存量无字段检材。更新现有投影、组件和自动保存回归。
- [x] T003 保持 `holder_name` 非必填：不进入待核对/导出门控，不改变“检材信息完整”判定；同时不把持有人投影到检查过程、检查结果或正式 Word。用最小可区分回归覆盖空值可继续审核以及 Word 不含持有人。
- [x] T004 核对 delta 与实现，更新 `openspec/specs/electronic-inspection-record/spec.md`，运行受影响前后端测试、Impeccable 单次检测、`npm run verify:quick`、`npm run verify:docs:strict -- --change evidence-holder-field` 和 `git diff --check`。

## 2026-09-11 legacy 结构化持有人反馈

> 原 T001 的“legacy 保持空值”仅代表首轮交付边界；以下任务以用户提供的外部 legacy 报告结构为新事实，取代该项旧行为，其他可选字段、审核编辑和 Word 排除合同保持不变。

- [x] T005 从对应检材 `Base`/`Phone` 设备元数据中精确读取 legacy `c1="检材持有人"`、`c2=<姓名>` 结构并写入该检材 `holder_name`；不得把“持有人编号/民族/性别”等相邻字段、通讯记录或模糊文本当作姓名。只使用 SYNTHETIC 自动化固件，外部真实报告仅做脱敏结构核对。
- [x] T006 核对 delta 与实现、同步现行规格，运行 legacy/new 报告解析定向回归、`npm run verify:quick`、`npm run verify:docs:strict -- --change evidence-holder-field` 和 `git diff --check`，记录本轮证据。

## 验证证据

- `holder_parser_contract_initial: PASS`：首轮 SYNTHETIC legacy/new/多检材解析回归证明 new 行内“检材持有人姓名”进入对应 `holder_name`；首轮 legacy 保持空值行为已由 T005 取代。
- `holder_ui_and_persistence: PASS`：投影、组件与页面集成回归覆盖“持有人”标签、空值“未填写”、原位编辑、字段来源和草稿 PATCH；持有人编辑显式声明不重置检材完整性。
- `holder_optional_and_word_exclusion: PASS`：无持有人仍保持既有完整性判定；fallback 文档构建与正式模板填充回归均证明持有人字符串不进入 Word。
- `holder_affected_tests: PASS`：后端受影响测试 127 passed；前端投影/组件/页面持有人回归通过；TypeScript 类型检查通过。
- `holder_ui_check: PASS`：Impeccable 单次机械检测返回 0 findings；新增字段复用现有 `EditableField`、字段网格、只读和来源标记，不新增样式分叉。
- `holder_manual_acceptance: N/A`：字段存在、标签、编辑、保存、完整性不重置和 Word 排除均由可区分自动化覆盖；未使用或展示真实姓名。
- `holder_level2_gate: PASS`：`npm run verify:quick` 全部阶段通过；scoped strict docs 14 checks、0 drift；OpenSpec strict validation 与 `git diff --check` 通过。
- `legacy_holder_feedback_parser: PASS`：精确标签单测和 `Phone/data_*.json` 合成 legacy 端到端回归先失败后通过；`tests/test_html_parser.py`、`tests/test_report_parser_service.py`、`tests/test_report_parse_input_repository.py` 共 95 passed，new 设备行优先级保持不变。
- `legacy_holder_feedback_external: PASS`：外部只读报告脱敏核对为 legacy、1 项检材、1 项持有人识别成功；仅记录数量和非空长度，不记录姓名、案件号或设备标识。
- `legacy_holder_feedback_level2_gate: PASS`：`npm run verify:quick` 通过；scoped strict docs 14 checks、0 drift；`git diff --check` 通过。

## 验收口径

- 每个检材拥有独立的可选“持有人”字段。
- new 报告的“检材持有人姓名”按行进入对应检材；legacy 报告从对应检材设备元数据的明确“检材持有人”键值行读取，缺失时为空。
- 用户可在截图所示 Word 内容预览中直接修改，修改随案件草稿保存。
- 持有人为空不产生待办或导出阻断；最终 Word 不出现持有人内容。
- 测试数据只使用明确标记的 SYNTHETIC/TEST/FIXTURE 内容。
