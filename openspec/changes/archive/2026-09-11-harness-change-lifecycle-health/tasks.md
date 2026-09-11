# Harness 变更生命周期健康治理

workflow_level: 2
lifecycle_status: ready-to-archive
spec_sync_status: reconciled
spec_sync_evidence: openspec/specs/harness-workflow/spec.md 已同步 Level 2 schema、显式 lifecycle_status、living spec 快速校验与选定归档范围合同

## 关联判断

- 主要候选：已归档的 `harness-workflow-alignment`，其建立了 Level 2 与 scoped gate 基线，但不能改写归档历史。
- 排除候选：现有活跃包分别属于 UI、业务数据、归档执行、预览稳定性与部署能力；用户结果和核心调用链均不同。
- 结论：创建独立 Level 2 包，修改 `harness-workflow` 正式合同，不引入业务功能或应用架构变化。

## 1. OpenSpec 工件对齐

- [x] 1.1 新增项目内 `openspec/schemas/level2/`，使 Level 2 状态只跟踪 delta specs 与 tasks。
- [x] 1.2 为现有 Level 2 活跃包补充 `.openspec.yaml` schema 元数据并验证状态解析。

## 2. 生命周期门控

- [x] 2.1 在 `scripts/check-docs-utils.ts` 增加完成态与 living spec 校验工具并补回归测试。
- [x] 2.2 在 `scripts/check-docs.ts` 检测完成未同步、全局范围完成未归档和过大的活跃任务文档。
- [x] 2.3 在 `package.json` 将 living spec 严格校验接入 `verify:quick`。

## 3. 归档范围与文档合同

- [x] 3.1 更新 `AGENTS.md`、`harness/entropy-rules.md` 和 `harness/iteration-guide.md`，区分选定批量归档与全局发布门控。
- [x] 3.2 同步 `.agents` 与 `.claude` 的 propose/archive 命令和 Skill 入口规则。

## 4. 验证与同步

- [x] 4.1 运行治理测试、schema 校验与相关 OpenSpec 状态检查。
- [x] 4.2 将 delta 同步到 `openspec/specs/harness-workflow/spec.md` 并记录 `spec_sync_evidence`。
- [x] 4.3 运行 `npm run verify:quick` 与 `npm run verify:docs:strict -- --change harness-change-lifecycle-health`。

## 5. 归档误判反馈

- [x] 5.1 引入显式 `lifecycle_status`，不再根据“无必选未完成项”推断变更可归档。
- [x] 5.2 为全部活跃 change 迁移生命周期状态，并修正与已记录验证证据冲突的 checklist 状态。
- [x] 5.3 更新 delta、living spec、schema 模板和双端 Harness 入口。
- [x] 5.4 补治理回归并重新运行 Level 2 收尾门控。
