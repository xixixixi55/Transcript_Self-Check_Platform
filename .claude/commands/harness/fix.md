---
name: "Harness: Fix"
description: "快速修 Bug（简化版迭代流程：propose → apply → verify → archive）"
argument-hint: "<Bug 描述>"
---

快速修 Bug 的简化流程，跳过 specs 和 design，直接从问题描述到修复完成。
内部使用 OpenSpec 快速推进模式（`/opsx:ff`）创建简化变更包。

**Input**：Bug 描述（如 `/harness:fix "仪表盘日期筛选不生效"`）。

---

**步骤**

1. **创建简化变更包**

   优先使用 `/opsx:ff` 命令创建快速变更包（跳过 specs 和 design）。
   如果不可用，降级为手动创建：
   - 从描述推导名称（如 `fix-date-filter`）
   - 创建 `openspec/changes/<名称>/`
   - 生成 proposal.md（简化版：问题描述 + 修复范围）
   - 生成 tasks.md（通常 1-2 个 Task）
   - MUST 遵循 `openspec/config.yaml` 中 `rules.tasks` 的质量标准

2. **定位问题**
   - 读取 `AGENTS.md` 了解架构
   - 定位到具体文件和层级

3. **执行修复**
   - 遵循 `/harness:apply` 的开发节奏（写码→验证→测试→有效性）

4. **运行验证**
   - 执行 npm run verify
   - 确认 Bug 已修复

5. **快速归档**（详见 `harness/entropy-rules.md` — 快速修复豁免）
   - 运行 npx tsx scripts/check-docs.ts — 自动化门控（E-A1 ~ E-A6）MUST 通过
   - 执行 Agent 自治检查（E-M1, E-M3, E-M4）— MUST 执行
   - Agent 辅助检查（E-M2, E-M5）— 快速修复可省略
   - 执行 `/opsx:archive` 或手动移入 archive

**Guardrails**
- 适用于小改动（1-3 个文件）
- 复杂 Bug 应使用完整的 `/harness:propose` 流程
- 修复仍 MUST 有配套测试
