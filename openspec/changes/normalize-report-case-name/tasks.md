workflow_level: 2

# 任务

- [x] T001 更新报告案件名称解析行为。
  - 文件：`packages/backend/app/services/report/report_parser_service.py`
  - 内容：清理报告识别案件名称末尾 `案（...）` / `案(...)` 标记，并移除案件简要情况自动补“案”的逻辑；递增解析缓存版本。
  - 验证：`pytest tests/test_report_parser_service.py -q --tb=short`
- [x] T002 补充案件名称归一化回归测试。
  - 文件：`tests/test_report_parser_service.py`
  - 内容：覆盖括号后缀清理、不以“案”结尾时不自动补“案”、已以“案”结尾时保持原样，以及集成解析元数据同步。
  - 验证：`pytest tests/test_report_parser_service.py -q --tb=short`
- [x] T003 同步规格并执行 Level 2 门控。
  - 文件：`openspec/changes/normalize-report-case-name/specs/electronic-inspection-record/spec.md`、`openspec/specs/electronic-inspection-record/spec.md`
  - 内容：记录并同步 REQ-002 的案件名称清洗与不补“案”行为。
  - 验证：`npm run verify:quick`、`npm run verify:docs:strict -- --change normalize-report-case-name`、受影响后端测试

## 2026-09-09 案件简要情况默认空值反馈

- [x] T004 移除案件名称到案件简要情况的解析兜底；新旧报告均将 `introduction.case_summary` 初始化为空，案件名称规范化保持不变。
- [x] T005 更新现有 SYNTHETIC 解析回归，覆盖普通案件名、带末尾括号标记案件名和旧格式报告，确认元数据及报告简要情况均为空。
- [x] T006 同步本包 delta 与 living spec，运行受影响后端测试、`verify:quick`、限定范围严格文档检查和差异检查。

- `blank_case_summary_contract: PASS`：旧实现上的新格式、末尾括号案件名与旧格式三条回归均失败于案件名称被复制；修复后 CaseDraft 案件名称继续规范化，`introduction.case_summary` 与解析元数据摘要均初始化为空。
- `blank_case_summary_tests: PASS`：报告解析、输入快照与工作台组合链路 3 files / 87 tests 通过；`verify:quick` 通过。
- `blank_case_summary_manual_acceptance: N/A`：默认值和落库投影由 SYNTHETIC 解析与工作台回归可靠区分，未读取或操作真实案件数据。
