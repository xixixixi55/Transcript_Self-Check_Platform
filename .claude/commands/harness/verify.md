---
name: "Harness: Verify"
description: "运行工程验证门控（架构检查 + 类型检查 + 构建 + 测试 + 文档一致性）"
argument-hint: ""
---

运行 Harness 工程验证门控（Level 3 使用完整自动化工程门控；Level 1/2 按 AGENTS.md 验证分级执行）。
纯自动化检查，验证代码的结构正确性。**不覆盖根目录 AGENTS.md 的级别规则。**

与 `/harness:review`（语义验证）互补：verify 检查结构，review 检查需求覆盖。

---

**步骤**

1. **快速验证（Level 1/2）**
   ```
   npm run verify:quick
   ```

2. **Level 2 模块验证**
   ```
   npm run test:frontend      # 前端变更时
   npm run test:backend       # 后端变更时
   ```
   只运行受影响模块；不再与 `verify:frontend`、`verify:backend` 或完整门控叠加。
   Level 2 收尾另行执行：
   ```
   npm run verify:docs:strict -- --change <变更包名称>
   npm run verify:docs:strict:all                  # 全局严格文档检查
   ```

3. **完整自动化工程门控（Level 3）**
   ```
   npm run verify:full -- --change <变更包名称>  # 全仓库工程检查；严格任务状态仅限当前变更包
   npm run verify:full:all                         # 全局发布/集中归档完整门控
   ```
   这是一次最终门控，不代表 E2E、mypy、真实桌面环境或 Word/PDF 人工验收均已完成。

4. **报告结果**
   - 先展示汇总状态和计数；全部通过后再提示后续 Review/归档
   - 有失败：默认展示按类型汇总；追加 `--details` 后展开错误详情，分析是代码问题还是约束问题

**如果验证失败**
- 代码问题 → 建议修复方向
- 约束问题 → 建议调整 Harness 规则（如 lint-arch 白名单、file_max_lines 等）
