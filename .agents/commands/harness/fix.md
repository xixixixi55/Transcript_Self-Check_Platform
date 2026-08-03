---
name: "Harness: Fix"
description: "快速修 Bug（Level 1 局部修复直接修改；Level 2 使用 tasks.md；Level 3 使用完整变更包）"
argument-hint: "<Bug 描述>"
---

快速修 Bug。**不覆盖根目录 AGENTS.md 的级别规则。**

**Input**：Bug 描述（如 `/harness:fix "仪表盘日期筛选不生效"`）。

---

**所有路径的前置步骤（MUST）**：

1. 扫描 `openspec/changes/` 下除 `archive/` 外的活跃变更包。
2. 读取范围相近候选包的 `tasks.md` 及必要的 proposal/spec/design。
3. 完全属于已有需求时，必须在原变更包内修复并更新任务状态和测试证据，不得创建重复包。
4. 仅名称相似但范围不一致时不得强行挂靠；存在多个无法排除的候选时暂停并请求用户选择。
5. 确认没有匹配包后，按行为影响、调用范围和回滚风险判断 Level；不确定时默认较轻级别。

**步骤**

**Level 1 路径（局部 Bug 修复，默认）**：

1. 检查 Git 状态，阅读直接相关代码和测试
2. 搜索调用范围
3. 实施最小修改
4. 运行针对性测试或 `lint:arch` + `typecheck`
5. 检查 `git diff`
6. 汇报结果
7. **不创建 OpenSpec change**

**Level 2/3 路径（复杂 Bug，影响范围较大）**：

1. **创建或选择变更包**

   - 已有匹配包：继续使用原变更包，不创建重复包。
   - 没有匹配包：Level 2 仅创建 `openspec/changes/<名称>/tasks.md`；Level 3 创建完整变更包（proposal + specs + design + tasks）。
   - 不依赖未在仓库入口中定义的快捷命令；不能使用 OpenSpec 快速命令时按上述规则手动创建。

2. **定位问题**
   - 读取 `AGENTS.md` 了解架构
   - 定位到具体文件和层级

3. **执行修复**
   - Level 2：写码 → 验证 → 测试
   - Level 3：遵循 `/harness:apply` 的完整开发节奏

4. **运行验证**
   - Level 2：运行 `npm run verify:quick`、受影响模块原始测试，收尾运行 `npm run verify:docs:strict -- --change <名称>`。
   - Level 3：按完整开发节奏执行定向测试，收尾运行 `npm run verify:full -- --change <名称>`。
   - 先读取测试和门控的退出码、最终汇总和失败数量；失败时再下钻具体日志。
   - 确认 Bug 已修复

5. **归档**（按级别）
   - Level 2：仅执行 Level 2 的自动化门控，不执行 Level 3 完整归档协议
   - Level 3：完整归档协议（详见 `harness/entropy-rules.md`）

**Guardrails**
- 判断依据为行为影响和回滚风险，不按文件数量判断
- Level 1 不创建 OpenSpec change
- 复杂 Bug 或不确定时，可升级为 Level 2 或 3
- 行为、交互、数据处理或安全修复 MUST 有受影响层的有效测试；纯样式、文案、图标和不改变交互的展示修复不强制新增低价值测试
