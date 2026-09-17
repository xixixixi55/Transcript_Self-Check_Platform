# 取消导出重复哈希并同步归档映射预览

workflow_level: 2
lifecycle_status: in-progress
spec_sync_status: reconciled
spec_sync_evidence: `openspec/specs/electronic-inspection-record/spec.md` 已同步 REQ-023、REQ-030、REQ-UNIFIED-EXPORT-TIMEOUT 与“最终压缩包仅保留一份”的完成后免重哈希、恢复单次校验、兼容旧接口及映射预览合同
manual_acceptance: pending — 需要确认硬盘映射成功后 Word 内容预览立即出现硬盘编号和刻录时间，完成导出可正常生成 Word

## 关联判断

- 候选：活动变更 `extensible-report-template-platform` 命中 Manifest、正式 Word 和归档校验等词汇。
- 结论：新建本变更。该候选处理可扩展模板平台、Canonical 渲染和模板治理，不包含已成功归档 RAR 的重复内容哈希性能合同，也不包含压缩后介质映射与当前 Word 预览的同步缺陷；本次反馈不改变其模板平台目标和核心调用链。

## 1. Implementation

- [x] 1.1 调整 `packages/backend/app/services/archive/archive_task_result_service.py` 与 `packages/backend/app/services/export/unified_export_service.py`，让归档成功后的结果复用和完成导出只执行发布绑定、安全文件类型、存在性、名称、字节数与 Manifest 元数据检查，不再顺序读取整个 RAR 计算摘要；以定向后端测试验证哈希函数未被调用且缺失/大小异常仍被拒绝。
- [x] 1.2 调整 `packages/backend/app/services/archive/archive_task_api_service.py` 与 `packages/backend/app/services/disc/disc_mapping_service.py`，让压缩后介质编号只更新当前成功任务 Manifest 绑定的归档计划；以多计划回归测试验证不会误写同案件的较新其他计划。
- [x] 1.3 调整 `packages/frontend/src/pages/CaseRecordGeneratePage.tsx`，在归档结果重读后将首个介质编号及其日期投影到 Word 内容预览和待核对状态，不额外写回案件草稿；以页面测试验证硬盘映射成功后无需刷新即可显示硬盘编号和刻录时间。
- [x] 1.4 调整重启恢复链路，将首次完整校验得到的持久 Manifest 摘要与文件身份继续传给完成提交，避免同一次恢复再次读取完整 RAR，同时保留校验后文件替换检测。
- [x] 1.5 调整兼容旧导出与分卷下载入口，在已认证 Manifest 边界复用持久摘要，只执行安全文件类型、名称、存在性、字节数与结构元数据检查；按用户要求不新增单元测试或低价值断言。

## 2. Verification and reconciliation

- [x] 2.1 先运行新增/更新的前后端定向回归并确认能够区分旧行为，再完成实现并复跑通过。
- [x] 2.2 核对 delta 与实现，将最终行为同步到 `openspec/specs/electronic-inspection-record/spec.md`，并记录 `spec_sync_evidence`。
- [x] 2.3 运行受影响模块测试、`npm run verify:quick` 和 `npm run verify:docs:strict -- --change avoid-export-rehash-and-sync-archive-mapping`。
- [x] 2.4 检查 `git diff` 只包含本变更预期内容，不覆盖工作区中既有的无关修改。
- [x] 2.5 复用现有归档恢复、篡改拒绝、Manifest、下载与复用测试完成本次增量验证；相关 127 项通过，`verify:quick` 与限定范围 strict docs 通过，未新增单元测试或低价值断言。
