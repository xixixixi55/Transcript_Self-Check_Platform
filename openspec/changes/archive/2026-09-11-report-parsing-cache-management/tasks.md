# Level 2 任务：移除报告解析持久化缓存

workflow_level: 2
legacy_migration: true
spec_sync_status: reconciled
spec_sync_evidence: T14 已将无持久化解析结果、仅共享在途任务及移除清理 API 的最终行为同步到 living spec/data model，并更新冲突活跃变更状态

> 2026-08-29 产品决策：项目不再需要报告解析持久化缓存。本包从 complete 状态重开，撤销磁盘缓存、LRU 和清理入口；原实施记录保留为历史证据。
>
> 范围：阶段 1 报告解析结果的磁盘持久化、复用和清理入口。
> 非范围：Canonical、Shadow、阶段 2、阶段 3、LLM，以及独立的归档文件清理 UI。

## 目标

每次顺序解析请求都读取当前报告源并重新构建解析结果，不在 `output/parsed/` 或其他位置保存可供后续请求复用的 `InspectionReport`。移除缓存版本、LRU、缓存仓储/服务以及 `DELETE /api/v1/cache/report-parsing` 公共合同。

同一规范化来源的并发请求可以共享仍在执行的 Parser 任务；任务完成后不保留结果，后续请求重新解析。已验证 ArchiveManifest/RAR 的独立登记与复用不属于报告解析缓存，继续保留原有校验与生命周期。

## 验收标准

- [x] 顺序重复解析同一来源时重新运行 Parser，不读取或写入持久化解析结果。
- [x] 后端不再创建 `output/parsed/`，解析响应不包含 `cache_version`。
- [x] 移除缓存配置、仓储、服务、Controller、路由以及共享 API 类型/端点常量。
- [x] 同一来源的并发请求仍可共享进行中的任务；任务结束后后续请求重新解析。
- [x] ArchiveManifest/RAR 的独立登记、复用和完整性校验保持不变。

## 本次撤销任务

- [x] **T10 移除报告解析缓存持久化实现与清理 API**
  - 删除缓存 Repository、Service、Controller、配置和共享合同；Parser 不再读写 `output/parsed/`。

- [x] **T11 保留并发任务复用，改为顺序请求始终重新解析**
  - `ReportParseInFlightRegistry` 只共享当前执行中的任务，完成结果不跨请求保留。

- [x] **T12 清理缓存专用测试并保留行为回归证据**
  - 删除 LRU、版本、失效、清理接口测试；覆盖顺序请求重建、无磁盘写入和并发共享。

- [x] **T13 处置冲突的未完成变更**
  - `legacy-parser-cache-change-trust` 因产品决策失去实施对象，标记为 superseded，未完成任务记为 `[N/A]`。

- [x] **T14 同步现行规格并运行 Level 2 门控**
  - 更新 living spec 与相关活跃变更文档；运行定向测试、`verify:quick`、后端全量及限定范围严格文档检查。
  - 证据：解析/并发/归档/Controller 定向集合 `120 passed`；默认业务 SQLite 导致的 2 个 Controller 环境失败在隔离 SYNTHETIC 工作台数据根后 `2 passed`；`npm.cmd run verify:quick` 通过；隔离 SYNTHETIC 工作台数据根执行 `npm.cmd run verify:backend` 为 `1252 passed, 3 skipped`；`npm.cmd run verify:docs:strict -- --change report-parsing-cache-management` 为 14 checks、0 drift。
  - manual_acceptance: [N/A] 本变更删除后端持久化与公共合同，无新增 UI、Word/PDF 或桌面工具交互；自动化已覆盖顺序重建、无磁盘写入、并发共享及归档独立性。

## 历史实施记录（已由 T10–T14 撤销）

### Layer 0/1/2：共享配置与文件身份

- [x] **T1 编写缓存与归档共用的规范化目录键/内容指纹辅助**
  - 文件：`packages/backend/app/repository/source/filesystem_identity_repository.py`
  - 验证：pytest 单元测试覆盖尾分隔符、大小写规范化、稳定内容指纹和目录变化。

- [x] **T2 增加解析缓存上限配置和清理 API 类型/端点常量**
  - 文件：`packages/backend/app/config.py`、`packages/shared/types/index.ts`、`packages/shared/constants/index.ts`
  - 验证：Python/TypeScript 类型检查及共享包构建通过。

### Layer 20：解析缓存和独立归档登记持久化

- [x] **T3 实现持久化解析缓存仓储**
  - 文件：`packages/backend/app/repository/report/report_parsing_cache_repository.py`
  - 验证：pytest 覆盖原子写入、损坏/旧版本清理、稳定 LRU、并发写保护、清空只删除 `parsed` 内容。

- [x] **T4 实现独立 ArchiveManifest/RAR 登记仓储**
  - 文件：`packages/backend/app/repository/archive/archive_manifest_repository.py`
  - 验证：pytest 覆盖登记持久化、按目录/输入/归档指纹查找、RAR/Manifest 文件保留及旧登记失效标记，不删除归档文件。

### Layer 21：业务服务与阶段 1 解析/归档接入

- [x] **T5 接入解析缓存服务、指纹校验、LRU 和一键清理**
  - 文件：`packages/backend/app/services/report/report_parsing_cache_service.py`、`packages/backend/app/services/report/report_parser_service.py`
  - 验证：pytest 覆盖 5/6 条、命中更新时间、重复目录、大小写/尾分隔符、指纹变化、清空后重新解析及重启上限。

- [x] **T6 接入跨重解析的已验证归档复用，并保持归档生命周期独立**
  - 文件：`packages/backend/app/services/archive/archive_runtime_service.py`（含同置的生命周期记录模型）、`packages/backend/app/services/archive/archive_execution_service.py`、`packages/backend/app/services/archive/archive_manifest_access_service.py`、`packages/backend/app/services/archive/archive_manifest_reuse_service.py`
  - 验证：pytest 覆盖清空解析缓存后 RAR/Manifest/下载/导出仍可用；同目录未变化复用；目录变化、大小变化、MD5 变化拒绝复用并生成新归档。

### Layer 22/23：HTTP 接口

- [x] **T7 增加安全的一键清空解析缓存接口**
  - 文件：`packages/backend/app/controllers/cache_controller.py`、`packages/backend/app/routes/__init__.py`
  - 验证：pytest + FastAPI TestClient 覆盖返回数量、空缓存幂等、失败响应、拒绝客户端路径且不泄露路径。

### Layer 10/11/12：阶段 1 前端入口

- [x] **T8 接入清空缓存 Hook 和阶段 1 主流程入口**
  - 文件：`packages/frontend/src/hooks/useReportParser.ts`、`packages/frontend/src/components/ReportUploadStep.tsx`、`packages/frontend/src/pages/RecordGeneratePage.tsx`
  - 验证：Vitest/React Testing Library 覆盖确认、成功、空缓存、失败重试和重复点击禁用；当前解析结果和表单状态不被清空动作强制抹除。

### 现行规格

- [x] **T9 同步当前 living spec**
  - 文件：`openspec/specs/electronic-inspection-record/spec.md`、`openspec/specs/data-model.md`
  - 验证：`pnpm verify:docs` 与需求场景逐条核对通过。

## 交付验证

- [x] `pnpm verify:quick`
- [x] `pnpm verify:frontend`
- [x] `pnpm verify:backend`
- [x] `pnpm verify:docs`
- [x] `pnpm check:repository-assets`
- [x] `git diff --check`
- [x] 不提交、不推送；汇报精确 Git 状态。
