## MODIFIED Requirements

### Requirement: REQ-011：无持久化解析结果缓存

系统 SHALL 在每个顺序报告解析请求中读取当前来源并重新运行 Parser，MUST NOT 在 `output/parsed/` 或其他位置持久化可供后续请求复用的完整解析结果。解析响应 MUST NOT 包含缓存版本，系统 MUST NOT 提供报告解析缓存清理 API。系统 MAY 为同一规范化来源共享仍在执行的任务，但任务完成后 MUST 释放该结果。

#### Scenario: 顺序重复解析

- **WHEN** 某次报告解析任务完成后再次请求解析同一来源
- **THEN** 系统重新读取当前输入并运行 Parser
- **AND** 不读取或写入持久化解析结果
- **AND** 不创建 `output/parsed/`

#### Scenario: 并发请求只共享在途任务

- **WHEN** 同一规范化来源已有 Parser 任务正在执行
- **AND** 第二个请求在该任务完成前到达
- **THEN** 两个请求可以共享该在途任务
- **AND** 任务完成后下一次请求重新解析来源

#### Scenario: 解析缓存公共合同被移除

- **WHEN** 客户端使用报告解析能力
- **THEN** 不存在 `DELETE /api/v1/cache/report-parsing` 清理端点
- **AND** 共享契约不包含清理响应类型或端点常量
- **AND** ArchiveManifest/RAR 的独立登记与复用不受影响
