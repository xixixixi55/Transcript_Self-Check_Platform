# Tasks: 二进制分卷档位与超大单卷归档

workflow_level: 2

> Delta spec：`openspec/changes/binary-archive-tiers-and-oversized-single-volume/specs/electronic-inspection-record/spec.md`
> 关联说明：现有归档基线来自活跃的 `extensible-report-template-platform`，本轮经用户明确判定为独立 Level 2 行为调整，不继承该历史包的 Level 3 门控。

## 目标

- 4GB、22GB、45GB 三档统一按 `1GB = 1024³` 字节计算，最大卷数分别为 2、2、5。
- 输入不超过 225GB 时使用标准分卷；超过 225GB 时生成单个 `案件名.rar`，不把 225GB 当作系统压缩上限。
- Manifest、校验、下载/导出复用和附件投影按显式归档模式处理，超大单卷不套用 45GB 每卷限制。

## 验收标准

- 8GB、44GB、225GB 及各自 `+1 byte` 的规划结果符合 delta spec。
- 标准模式仍严格校验单卷基础名或多卷 `.partN.rar`、连续卷号、每卷档位上限和最大卷数。
- 超大单卷只接受一个安全、非空的 `案件名.rar`，即使实际文件大于 45GB也可通过模式对应的结构校验。
- 超过 225GB 不返回 `ARCHIVE_TOO_LARGE` 或 `ARCHIVE_INPUT_LIMIT`；磁盘空间、CPU/IO、WinRAR 并发和输入安全门控保持有效。
- 旧 Manifest 的读取和既有 4/22/45GB 标准分卷展示不回归。

## 任务

### SharedTypes / SharedConstants（Layer 0–1）

- [x] T001 增加显式归档模式并统一二进制容量常量。
  - 文件：`packages/shared/types/archive.ts`、`packages/shared/constants/archiveConstants.ts` 及现有聚合导出。
  - 内容：定义 `standard_volume | oversized_single`；4/22/45GB 改为 `1024³` 字节；45GB 最大卷数改为 5；仅标准分卷适用的档位和光盘容量字段可明确表示“不适用”，不得使用 0 或伪造容量作为模式哨兵。
  - 验证：`pnpm --filter @biji/shared typecheck`；由后端边界测试锁定常量对应的精确字节值。

### FE Components（Layer 11）

- [x] T002 兼容超大单卷 Manifest 展示。
  - 文件：`packages/frontend/src/components/ArchiveStatusCard.tsx`、`packages/frontend/src/components/ArchiveStatusCard.test.tsx`。
  - 内容：超大单卷展示实际文件名、大小和 MD5，不把不适用的标准光盘容量显示为 0 或 45GB；标准分卷展示保持不变。
  - 验证：Vitest + RTL 覆盖 delta spec 的标准分卷与超大单卷展示场景。

### BE Repository（Layer 20）

- [x] T003 按归档模式构造 WinRAR 参数并验证实际产物。
  - 文件：`packages/backend/app/repository/winrar_execution_models_repository.py`、`packages/backend/app/repository/winrar_executor_repository.py`、`packages/backend/app/repository/archive_validator_repository.py`。
  - 内容：标准分卷继续传二进制 `-v...b`，单卷接受基础名、多卷校验 `.partN.rar`；超大单卷省略 `-v`，只接受一个 `案件名.rar`，不套用 45GB 每卷上限；两种模式都保留文件安全、非空和 WinRAR 完整性校验。
  - 验证：`tests/test_archive_executor_validator.py`、`tests/test_winrar_timeout.py`，覆盖参数、命名、大于45GB、混合产物和多 RAR 拒绝路径。

### BE Services（Layer 21）

- [x] T004 实现二进制档位、225GB 模式切换和模式化 Manifest。
  - 文件：`packages/backend/app/services/archive_planner_service.py`、`packages/backend/app/services/archive_execution_service.py`、`packages/backend/app/services/archive_manifest_service.py`、`packages/backend/app/services/archive_manifest_output_security_service.py`、`packages/backend/app/services/archive_manifest_access_service.py`。
  - 内容：不超过225GB选择标准档位，超过225GB规划为超大单卷；Manifest 显式保存模式，超大单卷保留实际大小、MD5、part 1、盘号、日期和完整性证据；发布、读取、复用与重新校验均按模式执行。
  - 验证：`tests/test_archive_planner_service.py`、`tests/test_archive_execution_service.py`、`tests/test_winrar_discovery_and_manifest.py`，边界覆盖8GB、8GB+1、44GB、44GB+1、225GB、225GB+1（均按 `1024³`）。

- [x] T005 移除容量策略造成的总输入上限并适配 Manifest 消费者。
  - 文件：`packages/backend/app/services/archive_runtime_resource_service.py`、`packages/backend/app/services/archive_resource_admission_service.py`、`packages/backend/app/services/attachment_plan_models_service.py`、`packages/backend/app/services/attachment_plan_service.py` 及搜索确认的其他 Manifest 消费者。
  - 内容：不再以135GB或225GB作为系统禁止压缩上限；保留实际磁盘空间、CPU/IO、WinRAR并发和输入安全准入；附件、下载、导出与复用链路接受超大单卷的不适用容量字段。
  - 验证：资源准入、附件计划、下载/导出/Manifest复用相关 pytest，确认超大输入不因容量策略阻止且其他资源门控不回归。

### 综合验证与规格同步

- [x] T006 完成 Level 2 验证并同步 living spec。
  - 文件：本变更代码、测试、delta spec 与 `openspec/specs/electronic-inspection-record/spec.md`。
  - 内容：逐条核对 delta 场景与实现；完成 `delta spec → 实现核对 → sync → living spec 检查`，再标记本任务完成。
  - 验证：受影响前端 Vitest、受影响后端 pytest（`-q --tb=short`）、`npm run verify:quick`、`npm run verify:docs:strict -- --change binary-archive-tiers-and-oversized-single-volume`、`git diff --check`。

## 影响范围

- Layer 0–1：归档模式、Manifest 可空容量字段和二进制档位常量。
- Layer 11：归档结果卡片对超大单卷的兼容展示。
- Layer 20：WinRAR 参数构造与实际产物结构校验。
- Layer 21：规划、执行编排、资源准入、Manifest 组装/复用和附件投影。
- 不新增路由、数据库迁移、第三方依赖或新压缩档位。

## 人工验收

- N/A：边界规划、命令参数和 Manifest 结构由自动化测试覆盖；本轮不创建真实百 GB 级测试数据。
