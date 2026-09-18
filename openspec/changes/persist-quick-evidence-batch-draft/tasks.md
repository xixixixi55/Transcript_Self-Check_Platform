# 批量检材输入草稿与回车换行

workflow_level: 2
lifecycle_status: ready-to-archive
spec_sync_status: reconciled
spec_sync_evidence: 已同步到 openspec/specs/electronic-inspection-record/spec.md REQ-GUIDED-REVIEW-SHELL 的键盘、未提交草稿恢复与批量添加场景
manual_acceptance: N/A — 键盘默认行为、案件隔离恢复、异常存储降级与成功清理均可由组件测试稳定覆盖，不改变页面布局
verification_evidence: 受影响前端 5 files / 53 tests PASS；`verify:quick`、scoped strict docs、OpenSpec strict validate、Impeccable 检测与 `git diff --check` PASS

## 范围

- 目标：快捷批量添加检材时，普通 Enter 只插入换行，提交继续使用现有显式解析与确认按钮。
- 将尚未确认写入案件的批量输入保存为按 `caseId` 隔离、版本化且有长度上限的浏览器本地草稿；切换步骤、重新进入或刷新后恢复，确认添加成功后清除。
- 未提交草稿不得写入案件报告、字段状态或步骤导航检查点；本地存储不可用或内容无效时不得阻断审核。
- 保持现有逐行解析、整批校验、自然排序、结构化预览、案件自动保存和检材完整性确认链路不变。
- 关联判断：已归档 `conversational-review-shell` 是原始能力事实源，不改写；活动的 `filter-guided-review-filled-content-by-user-source` 已待归档且只处理面板来源过滤；`case-record-retention-and-formal-artifact-protection` 处理服务端案件保留与并发边界；`large-report-preview-liveness` 处理报告预览性能，均与本次未提交输入草稿的用户结果和调用链不同。

## 任务列表

- [x] 新增 Layer 10 案件级批量检材输入草稿持久化，覆盖版本、长度、案件隔离、无效内容和存储不可用降级。
- [x] 调整 Layer 11 快捷批量输入：普通 Enter 插入换行且不推进事项，更新提示文案，切换步骤或刷新后恢复输入，确认添加后清理草稿。
- [x] 更新既有组件测试，覆盖 Enter 不提交、同案件恢复、跨案件隔离、校验失败保留与确认成功清理。
- [x] 核对增量规格与实现，同步现行规格并运行受影响前端测试、`verify:quick`、scoped strict docs、OpenSpec 严格校验、Impeccable 检测和 diff 检查。
