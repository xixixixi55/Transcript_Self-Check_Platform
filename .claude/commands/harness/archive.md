---
name: "Harness: Archive"
description: "归档已完成的变更包，包含 Harness 熵治理门控和迭代记录"
argument-hint: "[变更包名称]"
---

按 Harness Engineering 迭代闭环的 ⑥ 步骤执行归档同步。
内部调用 OpenSpec archive 完成 specs 合并和文件迁移，并在其上注入 Harness 熵治理阻断机制。

**前置读取**（MUST 在开始前阅读）：
- `harness/iteration-guide.md` — ⑥ 归档同步流程
- `harness/entropy-rules.md` — 自动化检查 + 人工阻断清单

**Input**：可选指定变更包名称。省略时询问用户选择。

---

**步骤**

1. **选择变更包**
   - 有名称则使用，否则列出活跃变更包让用户选择

2. **Harness 自动化门控（MUST 全部通过，在归档前执行）**
   ```
   npx tsx scripts/check-docs.ts
   ```
   检查项（详见 `harness/entropy-rules.md` E-A1 ~ E-A6）：
   - E-A1: directory.md 与文件系统一致（目录维度）
   - E-A2: 数据模型 Spec 与类型定义一致
   - E-A3: 文档链接有效
   - E-A4: OpenSpec 版本一致
   - E-A5: TEMPLATE_CANDIDATE 积压
   - E-A6: 迭代记录教训反哺完整性

   **不通过则停止，修复后重试。**

3. **Agent 自治检查（自动执行 + 自动修复）**

   Agent 自主执行以下确定性检查，发现问题直接修复：
   - [auto] **E-M1** — 对比 AGENTS.md 与 harness/ 详情，不一致则自动更新
   - [auto] **E-M3** — 扫描运营文档中会变的数字，自动替换为引用
   - [auto] **E-M4** — 检查教训是否已写入 Harness 文件，未写入则自动补充

   每项输出结果：`✅ 通过` 或 `🔧 已自动修复：<摘要>`

4. **Agent 辅助 + 人工快速确认**

   Agent 输出分析报告，请求用户快速审阅：
   - [ ] **E-M2** — 本次新增规则 + 疑似冲突列表 + 建议处理方式
   - [ ] **E-M5** — 教训通用性评估 + 是否标记 TEMPLATE_CANDIDATE 的建议

   无新增规则或无新教训时，对应项自动通过。
   **用户确认后方可继续。**

5. **调用 OpenSpec 执行归档**

   执行 `/opsx:archive` 命令完成归档操作：
   - 合并 delta specs 到 `openspec/specs/`
   - 移动变更包到 `openspec/changes/archive/YYYY-MM-DD-<name>/`

   如果 `/opsx:archive` 命令不可用，降级为手动归档：
   - 手动合并 specs 到 `openspec/specs/`，移动变更包到 `openspec/changes/archive/YYYY-MM-DD-<name>/`
   - MUST 遵循 `harness/iteration-guide.md`（⑥归档同步）和 `harness/entropy-rules.md` 中的归档流程

6. **Harness 迭代记录（OpenSpec 不管的，Harness 补上）**
   - 在 `harness/archive/iterations/` 创建迭代记录
   - 使用 `iteration-guide.md` 中的迭代记录模板
   - 包含：迭代概览、遇到的问题、沉淀的经验、反哺确认

7. **展示归档摘要**

**Guardrails**
- Agent 自治检查（E-M1/M3/M4）自动执行修复，无需人工介入
- Agent 辅助检查（E-M2/M5）的人工确认未完成前 MUST NOT 执行归档
- 自动化门控失败时 MUST 停止并协助修复
- 归档后 MUST 创建迭代记录
