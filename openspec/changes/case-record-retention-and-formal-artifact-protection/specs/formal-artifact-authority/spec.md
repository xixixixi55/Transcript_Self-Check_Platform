# OpenSpec Delta: formal-artifact-authority

## ADDED Requirements

### Requirement: REQ-AUTH-001: 现有 publication durable facts 是唯一 RAR/Manifest authority

RAR、分卷、Manifest、MD5 和 publication generation 的正式权威 MUST 继续来自现有 `archive_publish_intents` 及其 publication durable facts；同一 intent/generation 的 nullable `publication_verified_at` 是验证时间事实，不是第二 authority，且只能在 publication identity、durable succeeded/verified state、fence、Manifest digest、file inventory 和 ownership 均匹配时通过 NULL-only CAS 从 NULL 写入；普通读取、下载和重复验证不得更新时间。v10 历史 publication MUST 经过受控 revalidation，失败保持 NULL；真正重新发布 MUST 创建新的 `publication_id`。`archive_publish_fences` MUST 继续承担正式发布 CAS/fence 证明；正式 `archive_assets` MUST 继续记录发布文件集合。SQLite 是 durable authority。`.archive-manifest-index.json` 只能是可重建、fail-closed 的派生投影。本 change MUST NOT 创建与 publish intent 竞争的 RAR/Manifest authority 表；`formal-artifact-authority` 只表示由既有 publication facts、formal Word artifact 和 case tombstone 共同提供的能力边界。

#### Scenario: 清理后 publication authority 仍唯一有效

- **WHEN** 案件草稿、普通任务、来源工作投影和 owned 临时数据完成清理
- **THEN** 系统仍从 SQLite `archive_publish_intents`、publication facts、`publication_verified_at`、fence 和正式 asset facts 识别正式 RAR/Manifest/MD5/generation
- **AND** 不因创建 catalog/read model 或清理 tombstone 而形成第二套 publication authority
- **AND** `publication_verified_at` 只有在 NULL-only CAS 和受控 revalidation 成功后存在，重复校验不覆盖已有值

#### Scenario: 派生 index 缺失不改变 authority

- **WHEN** `.archive-manifest-index.json` 缺失、损坏或与 SQLite durable facts 不一致
- **THEN** 系统从可信 SQLite facts 重建或 fail closed
- **AND** 不从孤立磁盘文件、目录名或 index 缺失推断可信正式产物

### Requirement: REQ-AUTH-002: 清理后使用稳定 case/publication/Word artifact identity

清理后的公共正式产物访问 MUST 支持：按保留的 `case_id` 列出安全正式产物投影；按 `publication_id` 验证并访问 Manifest、MD5 和正式 RAR/分卷；按稳定 `word_artifact_id` 验证并访问正式 Word。清理后不得依赖 `archive_context_id`、进程内 runtime store、TTL context、已删除 `case_draft.report_json`、普通任务 payload、客户端路径或派生 JSON index。正式 publication/attempt/fence 的历史 `source_id` 只能指向不含路径和敏感 payload 的最小 source tombstone，不能成为 authority 查询入口。artifact catalog/read model 只能从 durable facts 重建，不能成为删除或下载资格的唯一依据。

#### Scenario: cleaned tombstone 重建正式安全投影

- **WHEN** case shell 已成为 cleaned tombstone，普通 draft/task/source work data 已被删除或 compact
- **THEN** 系统仍可按 `case_id` 列出 publication/Word artifact 安全投影
- **AND** 可按 `publication_id` 找到并校验 Manifest/MD5/RAR，按 `word_artifact_id` 找到并校验 Word
- **AND** 响应不返回内部路径、attempt、context、lease、fence、token 或完整工作 payload

#### Scenario: 清理后重启仍可访问正式产物

- **WHEN** 应用重启或 runtime context TTL 到期后访问 cleaned case 的正式产物
- **THEN** 查询使用 SQLite durable facts 和物理文件完整性校验
- **AND** 不要求恢复进程内 context 或已删除的可编辑报告

### Requirement: REQ-AUTH-003: durable formal Word artifact 和正式门控 fail-closed

成功 Word 导出 MUST 保存最终正式 Word 文件并持久化唯一 `word_artifact_id`、deployment/case/publication identity、文件摘要、大小、受控内部相对路径、生成/验证时间、来源 Manifest digest、模板 identity/version 和状态。正式 Word 记录和物理文件不受案件工作清理影响，且不得保存完整 `report_json` 作为访问依赖。清理后的 Manifest 校验、RAR/MD5 下载/复用和 Word 下载 MUST 检查 SQLite authority、publication/generation、来源 digest、物理文件和摘要；所有 durable 比较时间 MUST 是 timezone-aware UTC，公共时间 MUST 返回带时区 ISO 8601；任一缺失、替换、不一致或 authority 不可用 MUST fail closed。

#### Scenario: cleaned case 的完整正式产物通过门控

- **WHEN** publication intent/fence/assets、Manifest/MD5/RAR 和 formal Word artifact 均存在且摘要/来源 publication 验证通过
- **THEN** 系统允许按 publication/Word artifact identity 继续执行既有 Legacy 验证、下载、复用和 Word gate
- **AND** 不读取已清理的完整 draft/report JSON 或 runtime context

#### Scenario: Word 或 publication 被篡改则拒绝消费

- **WHEN** 正式 RAR、Manifest、Word 文件、来源 digest、publication generation 或 Word artifact 摘要在清理后缺失/替换
- **THEN** 下载、复用和 Word gate 返回稳定完整性错误并 fail closed
- **AND** 不通过文件 mtime、目录扫描或派生 index 重新认定可信

### Requirement: REQ-AUTH-004: 正式产物删除不是公共能力

本 change MUST NOT 增加正式 RAR/分卷、Manifest、MD5、Word、publication generation、正式 `archive_assets` 或其 durable authority 的删除 API。案件记录清理 MUST 由服务端白名单和受控 `enforce` Coordinator 计算，客户端不得提交文件路径、文件列表、output root、表名或“删除正式产物”选项。任何正式产物删除需求 MUST 作为独立 Level 3 范围重新评审。

#### Scenario: 客户端尝试扩大删除范围

- **WHEN** 客户端提交路径、正式文件名、output root、表名、文件列表或正式产物删除标记
- **THEN** API 拒绝整个请求
- **AND** 不部分执行工作数据删除，也不暴露后端文件路径或数据库细节

#### Scenario: 普通案件或 Legacy 入口不绕过保护

- **WHEN** 客户端调用普通案件删除、兼容 Legacy 或未清理 task/context 入口
- **THEN** 系统不将其解释为正式产物删除授权
- **AND** 正式 authority、稳定 identity 和 fail-closed 门控保持不变
