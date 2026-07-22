# Level 2 任务：阶段 1 报告解析缓存管理

> 范围：阶段 1 主流程的报告解析缓存，以及与 RAR/ArchiveManifest 独立生命周期所需的安全复用登记。
> 非范围：Canonical、Shadow、阶段 2、阶段 3、LLM，以及独立的归档文件清理 UI。

## 目标

为每个规范化后的报告目录维护一条持久化解析缓存，按 LRU 最多保留 5 条；解析命中更新最后访问时间，源内容指纹变化时重新解析；前端提供确认后的一键清空入口。解析缓存的清理和 LRU 淘汰只能删除 `output/parsed/` 中的解析缓存文件，不得触碰 `output/compressed/`、RAR、ArchiveManifest、Word 导出、原始报告目录、默认设置或当前页面内存状态。

再次解析同一目录时，若原始输入内容指纹、归档审核指纹均未变化且已登记的 Manifest/RAR 通过存在性、大小和 MD5 校验，则允许复用已有归档；否则新建归档并保留旧归档文件，由独立归档生命周期策略处理后续清理。

## 验收标准

- [x] 同一规范化目录（含大小写、尾部分隔符差异）只产生一条缓存记录，命中更新 `last_accessed_at`。
- [x] 缓存可持久化重启读取，最多保留 5 条；第 6 条按最早访问时间、再按稳定键顺序淘汰。
- [x] 源内容指纹变化、缓存损坏或缓存版本过期时不会命中，并且无效记录不占用 5 条额度。
- [x] `DELETE /api/v1/cache/report-parsing` 幂等返回 `cleared_count`；失败返回错误而非伪造成功；响应和日志不包含本地绝对路径或报告内容。
- [x] 清空缓存后 RAR、Manifest 登记、归档下载和 Word 导出所需的运行时记录仍可用；原始目录、默认设置和表单内存状态不受影响。
- [x] 同一目录重新解析后，输入和归档校验有效时复用 RAR/Manifest；输入变化、RAR 缺失、大小变化或 MD5 不一致时不复用并重新生成。
- [x] 前端一键清空包含确认提示、明确的重新解析说明、重复提交保护、成功/空缓存提示和失败重试入口。

## 实施任务

### Layer 0/1/2：共享配置与文件身份

- [x] **T1 编写缓存与归档共用的规范化目录键/内容指纹辅助**
  - 文件：`packages/backend/app/repository/filesystem_identity_repository.py`
  - 验证：pytest 单元测试覆盖尾分隔符、大小写规范化、稳定内容指纹和目录变化。

- [x] **T2 增加解析缓存上限配置和清理 API 类型/端点常量**
  - 文件：`packages/backend/app/config.py`、`packages/shared/types/index.ts`、`packages/shared/constants/index.ts`
  - 验证：Python/TypeScript 类型检查及共享包构建通过。

### Layer 20：解析缓存和独立归档登记持久化

- [x] **T3 实现持久化解析缓存仓储**
  - 文件：`packages/backend/app/repository/report_parsing_cache_repository.py`
  - 验证：pytest 覆盖原子写入、损坏/旧版本清理、稳定 LRU、并发写保护、清空只删除 `parsed` 内容。

- [x] **T4 实现独立 ArchiveManifest/RAR 登记仓储**
  - 文件：`packages/backend/app/repository/archive_manifest_repository.py`
  - 验证：pytest 覆盖登记持久化、按目录/输入/归档指纹查找、RAR/Manifest 文件保留及旧登记失效标记，不删除归档文件。

### Layer 21：业务服务与阶段 1 解析/归档接入

- [x] **T5 接入解析缓存服务、指纹校验、LRU 和一键清理**
  - 文件：`packages/backend/app/services/report_parsing_cache_service.py`、`packages/backend/app/services/report_parser_service.py`
  - 验证：pytest 覆盖 5/6 条、命中更新时间、重复目录、大小写/尾分隔符、指纹变化、清空后重新解析及重启上限。

- [x] **T6 接入跨重解析的已验证归档复用，并保持归档生命周期独立**
  - 文件：`packages/backend/app/services/archive_runtime_service.py`、`packages/backend/app/services/archive_runtime_models_service.py`、`packages/backend/app/services/archive_execution_service.py`、`packages/backend/app/services/archive_manifest_access_service.py`、`packages/backend/app/services/archive_manifest_reuse_service.py`
  - 验证：pytest 覆盖清空解析缓存后 RAR/Manifest/下载/导出仍可用；同目录未变化复用；目录变化、大小变化、MD5 变化拒绝复用并生成新归档。

### Layer 22/23：HTTP 接口

- [x] **T7 增加安全的一键清空解析缓存接口**
  - 文件：`packages/backend/app/controllers/cache_controller.py`、`packages/backend/app/routes/__init__.py`
  - 验证：pytest + FastAPI TestClient 覆盖返回数量、空缓存幂等、失败响应、拒绝客户端路径且不泄露路径。

### Layer 10/11/12：阶段 1 前端入口

- [x] **T8 接入清空缓存 Hook 和阶段 1 主流程入口**
  - 文件：`packages/frontend/src/hooks/useReportParser.ts`、`packages/frontend/src/components/ReportUploadStep.tsx`、`packages/frontend/src/pages/RecordGeneratePage.tsx`
  - 验证：Vitest/React Testing Library 覆盖确认、成功、空缓存、失败重试和重复点击禁用；当前解析结果和表单状态不被清空动作强制抹除。

### living spec

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
