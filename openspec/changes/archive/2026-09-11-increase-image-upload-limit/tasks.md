# Tasks: 单张图片上传上限提升至 100MB

workflow_level: 2
spec_sync_status: reconciled
spec_sync_evidence: openspec/specs/electronic-inspection-record/spec.md REQ-008 单张图片大小限制

> 规格：`openspec/changes/increase-image-upload-limit/specs/electronic-inspection-record/spec.md`
> 范围：将附件图片单文件上传上限由 10MB 提升至 100MB；前后端保持一致，不改变图片格式、数量、案件总容量或导出规则。

## 共享常量（Layer 1）

- [x] T001 将前端共享图片大小常量调整为 100MB。
  - 文件：`packages/shared/constants/index.ts`
  - 内容：更新 `MAX_IMAGE_SIZE`，继续作为前端上传前校验的唯一大小事实源。
  - 验证：TypeScript typecheck 与前端组件边界测试。

## 前端组件（Layer 11）

- [x] T002 更新图片上传提示并覆盖 100MB 边界。
  - 文件：`packages/frontend/src/components/ImageUploader.tsx`、`packages/frontend/src/components/ImageUploader.test.tsx`
  - 内容：允许不超过 100MB 的 JPG/JPEG/PNG，超过上限时提示“图片不能超过 100MB”。
  - 验证：定向 Vitest 覆盖恰好 100MB 与超过 100MB。

## 后端 Repository/Service/Controller（Layer 20–22）

- [x] T003 将后端单张图片硬限制和错误提示同步为 100MB。
  - 文件：`packages/backend/app/repository/workbench/workbench_constants.py`、`packages/backend/app/controllers/case_asset_controller.py`、`tests/test_workbench_case_assets.py`
  - 内容：后端继续执行不可绕过的单文件大小校验，100MB 为允许的边界，超过后返回 `ASSET_IMAGE_TOO_LARGE`。
  - 验证：定向 pytest 覆盖常量值、允许边界与拒绝边界。

## 验证与收尾

- [x] T004 核对 delta 与实现并完成 Level 2 门控。
  - 文件：`openspec/changes/increase-image-upload-limit/specs/electronic-inspection-record/spec.md`、`openspec/specs/electronic-inspection-record/spec.md`
  - 内容：按 delta spec → 实现核对 → sync → living spec 检查完成同步。
  - 验证：前后端定向测试、`npm run verify:quick`、`npm run verify:docs:strict -- --change increase-image-upload-limit`、`git diff --check`。

## 非目标

- 不改变 JPG/JPEG/PNG 格式与真实图片校验。
- 不改变每案图片数量上限或每案图片总容量上限。
- 不改变图片绑定、草稿保存、租约/revision、Word 预览与导出行为。
