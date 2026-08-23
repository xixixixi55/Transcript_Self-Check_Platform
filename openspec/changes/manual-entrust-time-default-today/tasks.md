workflow_level: 2
spec_sync_status: reconciled
spec_sync_evidence: delta synced to openspec/specs/electronic-inspection-record/spec.md REQ-002 and parser contract

# Tasks

- [x] T001 停止从报告创建时间推导委托时间。
  - 文件：`packages/backend/app/services/report_parser_service.py`、`packages/backend/app/repository/html_parser.py`
  - 内容：报告解析结果中的 `introduction.entrust_time` 保持为空；“创建时间”继续只参与检查起止时间，不再作为委托时间来源；递增解析缓存版本以淘汰旧映射结果。
  - 验证：`pytest tests/test_report_parser_service.py -q --tb=short`
  - 证据：报告解析与工作台组合定向测试共 77 passed；解析结果断言委托时间为空、检查起止时间仍来自创建/报告时间，缓存版本更新为 23。
- [x] T002 新案件草稿按当天日期预填可编辑的委托时间。
  - 文件：`packages/backend/app/services/case_draft_service.py`、`tests/test_workbench_services.py`、`tests/test_report_parser_service.py`
  - 内容：在新案件草稿初始化时，按 `Asia/Shanghai` 当天日期写入中文纯日期；覆盖报告携带的旧委托时间种子，保留现有审核页日期控件的人工修改和保存行为，不改写已保存案件。
  - 验证：`pytest tests/test_workbench_services.py tests/test_report_parser_service.py -q --tb=short`
  - 证据：固定 UTC 时刻跨上海自然日的初始化回归通过；旧报告日期被当天日期覆盖，输入报告未被原地修改，字段来源为 `system_default`。
- [x] T003 同步规格并执行 Level 2 门控。
  - 文件：`openspec/changes/manual-entrust-time-default-today/specs/electronic-inspection-record/spec.md`、`openspec/specs/electronic-inspection-record/spec.md`
  - 内容：核对 delta 与实现，更新 living spec，并记录定向测试、`verify:quick` 与 scoped strict docs 结果。
  - 验证：`npm run verify:quick`、`npm run verify:docs:strict -- --change manual-entrust-time-default-today`
  - 证据：delta 已同步至 living spec；后端 77 passed、前端日期编辑与页面链路 32 passed；`verify:quick` 全部通过；scoped strict docs 14 checks、0 drift。

manual_acceptance: N/A（委托时间来源、时区换日和人工编辑链路均由确定性自动化测试覆盖，不改变页面布局。）
