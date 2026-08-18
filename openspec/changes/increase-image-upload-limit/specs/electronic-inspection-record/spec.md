# Spec Delta: 单张图片上传上限提升至 100MB

> 基准 Spec：`openspec/specs/electronic-inspection-record/spec.md`
> 变更类型：MODIFIED（CAP-004 REQ-008 附件图片上传）

## MODIFIED: CAP-004 — 实时预览与附件

### Requirement: REQ-008: 附件图片上传

系统 MUST 在前端和后端统一执行 100MB 的单张图片上传上限；合法 JPG/JPEG/PNG 图片大小不超过 100MB 时 MUST 允许上传，超过 100MB 时 MUST 拒绝并给出明确提示。现有图片数量、案件图片总容量、资产持久化、租约/revision、图片绑定及导出合同保持不变。

#### Scenario: 上传不超过 100MB 的合法图片

- WHEN 用户在有效编辑租约下选择大小小于或等于 100MB 的合法 JPG/JPEG/PNG 图片
- THEN 前端不得因单文件大小拒绝该图片
- AND 后端单文件大小校验允许该图片继续进入真实图片、案件数量与总容量校验流程

#### Scenario: 拒绝超过 100MB 的图片

- WHEN 用户选择大小超过 100MB 的图片
- THEN 前端拒绝该文件并提示“图片不能超过 100MB”
- AND 绕过前端直接请求后端时，后端返回稳定错误码 `ASSET_IMAGE_TOO_LARGE`，错误提示明确单张图片超过 100MB 限制
