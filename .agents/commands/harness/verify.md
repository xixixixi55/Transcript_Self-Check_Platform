---
name: "Harness: Verify"
description: "运行工程验证门控（架构检查 + 类型检查 + 构建 + 测试 + 文档一致性）"
argument-hint: ""
---

运行 Harness 工程验证门控。纯自动化检查，验证代码的结构正确性。

与 `/harness:review`（语义验证）互补：verify 检查结构，review 检查需求覆盖。

---

**步骤**

1. **架构约束 + 类型检查 + 构建**
   ```
   npm run verify
   ```

2. **自动化测试**
   ```
   pnpm test
   ```

3. **文档一致性检查**
   ```
   npx tsx scripts/check-docs.ts
   ```

4. **报告结果**
   - 全部通过：展示通过状态，提示可运行 `/harness:review` 做需求验证
   - 有失败：展示错误详情，分析是代码问题还是约束问题

**如果验证失败**
- 代码问题 → 建议修复方向
- 约束问题 → 建议调整 Harness 规则（如 lint-arch 白名单、file_max_lines 等）
