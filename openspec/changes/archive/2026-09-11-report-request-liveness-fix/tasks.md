# Level 2 任务：报告解析与缓存清理请求可用性

workflow_level: 2
legacy_migration: true
spec_sync_status: reconciled
spec_sync_evidence: 已同步到 openspec/specs/electronic-inspection-record/spec.md REQ-011

## 目标

保证报告解析和解析缓存清理在同步文件系统工作、网络失败或请求超时后都能结束请求并反馈可重试状态；解析缓存清理不触碰归档生命周期。

## 验收标准

- [x] 解析和清缓存的同步后端工作不阻塞 FastAPI 事件循环。
- [x] 两类前端请求均有统一超时/Abort 收尾；成功、业务错误、服务异常、网络失败和超时都会恢复按钮状态并显示反馈。
- [x] 解析与清缓存均防止重复提交；缓存清理返回实际数量，空缓存返回 0。
- [x] 现有 LRU、RAR/Manifest、Shadow、Word 和模板逻辑保持不变。

## 实施任务

- [x] 将解析、归档上下文快照和清缓存文件操作移入线程池，并补充非阻塞回归测试。
- [x] 为解析/清缓存 Hook 增加统一请求超时、Abort、互斥和错误映射，并补充 loading 收尾测试。
- [x] 运行定向测试、架构检查、类型检查并复核 Git 状态。

## 协作门控说明

本变更包的定向或模块验证可直接执行；若进入完整 Harness 门控，遵循根目录 `AGENTS.md` 的执行者确认规则。
