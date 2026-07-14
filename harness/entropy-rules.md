# 熵治理规则（Harness）

> 本文件定义项目随时间演进时的**熵对抗机制**（Harness 骨架）。
> 防止文档过时、规则冲突、教训遗失等系统性退化。

---

## 核心原则

1. **可脚本化的检查 → 纳入 `check_docs` 脚本，作为 pre-commit 门控的一部分**
2. **确定性检查（有标准答案）→ Agent 自治执行 + 自动修复，无需人工介入**
3. **判断性检查（需语义推理）→ Agent 输出分析报告 + 人工快速审阅确认**

---

## 自动化检查（MUST 纳入 npx tsx scripts/check-docs.ts）

以下检查 **MUST** 由 `check_docs` 脚本自动执行，pre-commit 不通过则阻断提交：

### E-A1: directory.md 与文件系统一致性（目录维度）
- 扫描 `harness/directory.md` 中声明的源码目录
- 检查每个声明的目录在实际文件系统中是否存在
- 检查实际新增的顶层源码目录是否已在 directory.md 中声明
- 注意：检查粒度为**目录级别**，不要求每个文件逐一列出

### E-A2: 数据模型 Spec 与类型定义一致性
- 对比 `openspec/specs/data-model.md` 中的实体/字段与类型定义文件中的 `interface`/`type`
- 检查两处的字段名、字段类型是否匹配
- **MUST**: 扫描类型定义**目录**下所有文件，而非仅扫描入口文件。类型拆分为多文件后，仅扫描聚合入口会漏掉子文件中的导出

### E-A3: 文档链接有效性
- 扫描 `AGENTS.md` 和 `harness/*.md` 中的相对路径引用（如 `详见 harness/xxx.md`）
- 检查每个引用路径在文件系统中是否存在

### E-A4: OpenSpec 版本一致性
- 读取 `openspec/config.yaml` 中声明的 `openspec_version`
- 读取 `harness/iteration-guide.md` 中标注的版本
- 两者不匹配时报 warning

### E-A5: TEMPLATE_CANDIDATE 积压统计
- 扫描 `harness/archive/iterations/*.md` 中包含 `TEMPLATE_CANDIDATE` 且状态为 `pending` 的条目
- 积压超过 5 条时报 warning（默认阈值，项目可按需调整）

### E-A6: 迭代记录教训反哺完整性
- 扫描最近一份 `harness/archive/iterations/*.md`
- 如果「沉淀的经验」章节非空，但「已反哺到 Harness」章节为空 → 报 error

---

## Agent 自治检查（归档前自动执行 + 自动修复）

以下检查是**确定性检查**（有标准答案），由 Agent 在归档前**自主执行并修复**，无需人工介入。

### E-M1: AGENTS.md 规则摘要一致性（Agent 自治）
- Agent 对比 `AGENTS.md` 中的规则条目与 `harness/` 各详情文件中的规则
- 发现遗漏或不一致 → Agent **自动更新** AGENTS.md
- 输出：`[E-M1] ✅ 一致` 或 `[E-M1] 🔧 已自动修复：<修复内容摘要>`

### E-M3: 硬编码扫描（Agent 自治）
- Agent 扫描本次迭代修改过的 `harness/*.md` 文件
- 识别具体数字、数量等硬编码值，判断是否会随项目演进变化
- 会变的 → Agent **自动替换**为"详见 xxx"引用或删除
- 输出：`[E-M3] ✅ 无硬编码` 或 `[E-M3] 🔧 已自动修复：<替换内容摘要>`

### E-M4: 教训反哺确认（Agent 自治）
- Agent 读取迭代记录的「沉淀的经验」章节
- 逐条检查是否能在 `harness/` 文件中找到对应规则
- 未写入的 → Agent **自动补充**到对应的 Harness 文件
- 输出：`[E-M4] ✅ 全部已反哺` 或 `[E-M4] 🔧 已自动补充：<规则写入位置>`

---

## Agent 辅助检查（Agent 分析 + 人工快速确认）

以下检查涉及**语义判断**，Agent 输出分析报告后由人工快速审阅确认。

### E-M2: 规则冲突排查（Agent 辅助）
- Agent 扫描本次迭代新增的 Harness 规则
- 与已有规则做语义对比，输出疑似冲突列表及建议处理方式
- **人工**：审阅 Agent 报告，确认无冲突或指示修复
- 无新增规则时自动通过
- 输出格式：
  ```
  [E-M2] 本次新增规则：N 条
  疑似冲突：（无 / 列出）
  建议处理：...
  → 请确认：无冲突 / 需修复
  ```

### E-M5: 模板反哺判定（Agent 辅助）
- Agent 评估每条教训的跨项目通用性，给出建议
- **人工**：审阅 Agent 建议，确认是否标记 `TEMPLATE_CANDIDATE`
- 无新教训时自动通过
- 输出格式：
  ```
  [E-M5] 本次教训：N 条
  Agent 建议标记为 TEMPLATE_CANDIDATE：（无 / 列出及理由）
  → 请确认：同意 / 调整
  ```

---

## 检查节奏

| 时机 | 脚本自动化检查 | Agent 自治检查 | Agent 辅助 + 人工确认 |
|------|---------------|---------------|---------------------|
| 每次提交 | E-A1 ~ E-A6（pre-commit 门控） | — | — |
| 每次迭代归档 | E-A1 ~ E-A6（再次确认） | E-M1, E-M3, E-M4（**自动执行修复**） | E-M2, E-M5（**快速审阅**） |
| 每个里程碑 | — | — | TEMPLATE_CANDIDATE 积压审阅（E-A5 warning 触发） |

---

## Agent 归档协议

Agent 在执行归档（⑥）时 **MUST** 按以下流程操作：

1. 运行 npx tsx scripts/check-docs.ts — 脚本自动化检查全部通过
2. 执行 Agent 自治检查（E-M1, E-M3, E-M4）— 自动检查并修复，输出结果摘要
3. 执行 Agent 辅助检查（E-M2, E-M5）— 输出分析报告，请求人类快速确认
4. 人类确认后，执行 `/opsx:archive`
5. 如有问题，Agent **MUST** 停止归档，协助修复后重新确认

> **设计理由**：E-M1/M3/M4 是确定性检查（有标准答案），Agent 不存在乐观偏见，全自动接管可提升归档效率。
> E-M2/M5 涉及语义判断和跨项目视角，保留人工快速审阅作为安全网。

### 快速修复豁免

通过 `/harness:fix` 执行的快速修复归档，适用以下简化流程：

- **MUST** 执行自动化门控（E-A1 ~ E-A6）— 不可省略
- **MUST** 执行 Agent 自治检查（E-M1, E-M3, E-M4）— 不可省略
- **MAY** 省略 Agent 辅助检查（E-M2, E-M5）— 快速修复通常不新增 Harness 规则或产生跨项目教训

> **适用条件**：仅限小改动（1-3 个文件）的 Bug 修复。复杂 Bug 应使用完整的 `/harness:propose` 流程，走完整归档协议。
