---
name: "Harness: Propose"
description: "创建需求变更包（需求定义 + 影响分析 + 任务拆解），按 Harness 架构约束编排"
argument-hint: "<功能描述>"
---

<!-- context-loading: progressive -->

处理新需求或正式行为修改；根目录 `AGENTS.md` 是级别、关联和验证规则的唯一入口，不在本命令复制完整流程。

## 渐进式上下文

1. 先用请求、Git 状态以及活跃 change 的目录名、`tasks.md` 搜索命中筛选候选；只对候选读取 tasks，仍不足时读相关 delta，再不足才读 proposal/design。
2. Level 1 只读取直接相关源码和现有测试，不读取完整迭代指南或架构文档。
3. Level 2 读取或创建 `tasks.md` + 相关 delta；只有生成/校验 OpenSpec 工件时读取 `openspec/config.yaml`。
4. Level 3 按当前 proposal/spec/design/tasks 阶段读取 `harness/iteration-guide.md` 的对应章节；出现新文件、跨层引用、公共契约或架构风险时才读取 `harness/architecture.md`。

## 执行

1. 依据正式能力、用户结果、验收场景、核心调用链和反馈生命周期关联未归档 change；同目标复用原包。多个候选仍无法排除时请求用户选择。
2. 排除候选后按 `AGENTS.md` 判定 Level；创建新 Level 2/3 包时记录主要候选和排除理由。
3. Level 1 不创建 change。Level 2 只创建 tasks + 至少一个 ADDED/MODIFIED/REMOVED/RENAMED delta，并持久化 `workflow_level: 2`。Level 3 才创建 proposal + specs + design + tasks。
4. tasks 指向具体文件和验证方式；先复用现有验证，只在风险覆盖缺口存在时新增测试。涉及架构时按层级从低到高安排任务。
5. 输出关联结论、Level、已读取资料、计划工件和下一步；需求语义有实质歧义时再请求用户确认。
