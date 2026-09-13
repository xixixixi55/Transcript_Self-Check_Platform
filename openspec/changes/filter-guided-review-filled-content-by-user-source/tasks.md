# “已填内容”仅展示用户填写

workflow_level: 2
lifecycle_status: ready-to-archive
spec_sync_status: reconciled
spec_sync_evidence: 已同步到 openspec/specs/electronic-inspection-record/spec.md REQ-GUIDED-REVIEW-SHELL 的已填内容与待办规则
manual_acceptance: N/A — 局部来源过滤由组件测试可靠覆盖，不改变布局、样式或真实文档输出

## 范围

- 目标：对话式审核页“已填内容”只列出用户填写、修改、确认或上传形成的内容。
- 保持左侧 Word 内容预览继续展示报告草稿的全部最终生效值。
- 不改变字段来源记录、待处理项、步骤导航、草稿保存、归档或导出合同。
- 关联判断：原始能力来自已归档 `conversational-review-shell`，不可改写；现有活动变更均不覆盖该面板的来源过滤。

## 任务列表

- [x] 调整“已填内容”的候选过滤，仅保留带用户来源标记且可回访的字段。
- [x] 更新组件测试，区分用户填写内容与报告识别/系统生成内容。
- [x] 核对增量规格与实现，运行受影响前端测试及 Level 2 收尾门控。
- [x] 将增量规格同步到现行规格并记录证据。
