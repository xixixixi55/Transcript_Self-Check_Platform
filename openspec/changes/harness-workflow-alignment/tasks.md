# Harness 工作流入口对齐

## 目标

修正需求、Bug 和验证入口之间的流程分歧，保持轻量级别默认路径，同时避免活跃变更包重复、Level 2 门控遗漏和测试日志下钻过早。

## 任务

- [x] T001 在需求入口增加活跃变更包扫描、重叠范围处理和 Level 1/2/3 路由规则；验证：入口文档一致性检查。
- [x] T002 在 Bug 入口明确先关联已有活跃变更包，再按级别选择直接修复、tasks.md 或完整变更包；验证：入口文档一致性检查。
- [x] T003 对齐 Level 2 的 `verify:quick`、受影响模块测试和 scoped strict docs 门控，并保留纯样式/文案等低价值测试豁免；验证：治理测试和文档检查。
- [x] T004 将“先看汇总、失败再下钻”扩展到 pytest、Vitest、模块测试和完整门控子命令；验证：治理测试和文档检查。
- [x] T005 运行本变更的定向治理/文档验证，确认未修改业务代码且 Git 差异仅包含预期流程文件；验证：`npm run test:governance`、`npm run verify:docs:strict -- --change harness-workflow-alignment`、`git diff --check`。
