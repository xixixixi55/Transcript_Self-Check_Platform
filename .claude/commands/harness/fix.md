---
name: "Harness: Fix"
description: "快速修 Bug（Level 1 局部修复直接修改；Level 2/3 使用简化变更包流程）"
argument-hint: "<Bug 描述>"
---

快速修 Bug。**不覆盖根目录 AGENTS.md 的级别规则。**

**Input**：Bug 描述（如 `/harness:fix "仪表盘日期筛选不生效"`）。

---

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

1. **创建简化变更包**

   优先使用 `/opsx:ff` 命令创建快速变更包（跳过 specs 和 design）。
   如果不可用，降级为手动创建：
   - Level 2：仅创建 `openspec/changes/<名称>/tasks.md`
   - Level 3：创建完整变更包（proposal + specs + design + tasks）

2. **定位问题**
   - 读取 `AGENTS.md` 了解架构
   - 定位到具体文件和层级

3. **执行修复**
   - Level 2：写码 → 验证 → 测试
   - Level 3：遵循 `/harness:apply` 的完整开发节奏

4. **运行验证**
   - 执行针对性验证
   - 确认 Bug 已修复

5. **归档**（按级别）
   - Level 2：仅自动化门控（check-docs 必要项）
   - Level 3：完整归档协议（详见 `harness/entropy-rules.md`）

**Guardrails**
- 判断依据为行为影响和回滚风险，不按文件数量判断
- Level 1 不创建 OpenSpec change
- 复杂 Bug 或不确定时，可升级为 Level 2 或 3
- 修复仍 MUST 有配套测试
