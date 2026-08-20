---
name: "Harness: Verify"
description: "运行工程验证门控（架构检查 + 类型检查 + 构建 + 测试 + 文档一致性）"
argument-hint: ""
---

<!-- context-loading: progressive -->

运行 Harness 工程验证门控（Level 3 使用完整自动化工程门控；Level 1/2 按 AGENTS.md 验证分级执行）。
纯自动化检查，验证代码的结构正确性。**不覆盖根目录 AGENTS.md 的级别规则。**

渐进式读取：先根据当前 Level、风险和 change 范围选择命令；只有需要人工验收、环境预检或失败下钻时才读取 `harness/verification-strategy.md` 的相关章节，不预读其他阶段文档。

与 `/harness:review`（语义验证）互补：verify 检查结构，review 检查需求覆盖。

---

**步骤**

1. **增量验证（Level 1/2）**
   Level 1 先按实际风险执行最小定向验证；需要轻量综合检查时运行：
   ```
   npm run verify:quick
   ```

2. **Level 2 模块验证**
   ```
   npm run test:frontend      # 前端变更时
   npm run test:backend       # 后端变更时
   ```
   只运行实际改变逻辑或合同边界的受影响模块；不因前后端同时修改机械要求两侧新增测试，也不与完整门控叠加。
   Level 2 收尾另行执行：
   ```
   npm run verify:docs:strict -- --change <变更包名称>
   npm run verify:docs:strict:all                  # 全局严格文档检查
   ```
   Level 2 的 strict docs 必须只检查显式 `--change <变更包名称>` 当前包的 tasks.md、`workflow_level` 和 delta spec；`--all` 才检查全部活跃包。脚本只做基本结构和格式检查，不宣称自动判断代码与规格的完整语义一致性。

3. **冻结候选后的完整自动化工程门控（Level 3）**
   ```
   npm run verify:full -- --change <变更包名称>  # 全仓库工程检查；严格任务状态仅限当前变更包
   npm run verify:full:all                         # 全局发布/集中归档完整门控
   ```
   开发和反馈阶段只运行风险相称的定向验证；全部反馈收敛、候选冻结后才执行上述最终门控。它不代表 E2E、mypy、真实桌面环境或 Word/PDF 人工验收均已完成。

4. **报告结果**
   - 先展示汇总状态和计数；全部通过后再提示后续 Review/归档
   - pytest、Vitest、模块测试和完整门控子命令通过时不逐条读取通过用例
   - 有失败：默认展示按类型汇总，再下钻失败用例和 traceback；只有命令实际支持时才使用详细输出参数，不虚构通用 `--details`

**如果验证失败**
- 代码问题 → 建议修复方向
- 约束问题 → 建议调整 Harness 规则（如 lint-arch 白名单、file_max_lines 等）
