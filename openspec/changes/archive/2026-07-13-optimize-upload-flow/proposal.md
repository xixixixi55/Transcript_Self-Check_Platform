# Proposal: 优化上传流程

> 状态：PROPOSED
> 日期：2026-07-13

## 原因

当前上传流程存在以下不足：

1. **强制压缩**：每次上传报告目录后必定生成 .rar 压缩包，但用户可能只需要在线编辑和导出 Word，不需要压缩包
2. **不支持压缩包直接上传**：部分用户已将报告目录打包为 .rar/.zip，希望直接上传压缩包而非先解压再选择文件夹
3. **文件信息不透明**：压缩包的 MD5 哈希值和文件大小仅在生成的 Word 笔录中可见，上传后前端页面不展示，用户无法确认文件信息

## 内容

### 压缩选项控制（CAP-006）

前端增加"压缩为 .rar"复选框（默认勾选）。取消勾选时，系统跳过压缩步骤，不生成 .rar 文件，检查结果中的 RAR 信息字段留空。

### 压缩包直接上传（CAP-007）

新增"上传压缩包"入口，支持直接上传 .rar/.zip 文件。系统自动解压到临时目录，解析内部 JSON 数据，跳过压缩步骤，直接计算上传文件的 MD5 和文件大小。

### 文件信息展示（CAP-008）

解析完成后，前端在页面上展示文件的 MD5 哈希值和文件大小（MB 格式）。对于未生成压缩包的场景（取消压缩 + 非压缩包上传），展示"N/A"。

## 非目标

- 不改变美亚报告的标准文件夹格式要求
- 不支持远程文件/URL 上传
- 不支持 .7z / .tar 等其他压缩格式
- 不改变现有的解析缓存机制
- 不改变 officecli 生成 .docx 的流程

## 能力

| 编号 | 能力 | 类型 | 说明 |
|------|------|------|------|
| CAP-006 | 压缩选项控制 | ADDED | 用户可决定是否生成 .rar 压缩包 |
| CAP-007 | 压缩包直接上传 | ADDED | 支持上传 .rar/.zip 压缩包，自动解压解析 |
| CAP-008 | 文件信息展示 | ADDED | 上传后展示 MD5 哈希值和文件大小（MB） |
| CAP-009 | 软件工具列表动态生成 | ADDED | 按实际调用的工具动态生成 software_tools，移除硬编码 |
| CAP-001 | HTML 报告上传与解析 | MODIFIED | 扩展支持压缩包上传和压缩开关 |
| CAP-004 | 导出 .docx | MODIFIED | 检查结果中 RAR 信息可能为空；软件工具列表动态渲染 |

## 影响

按 `harness/architecture.md` 分层矩阵分析影响范围：

| 层级 | 目录 | 变更类型 | 说明 |
|------|------|:------:|------|
| Layer 0: SharedTypes | `packages/shared/types/` | 修改 | `ParseReportResponse.rar_info` 改为可选；新增 `ArchiveUploadResponse` |
| Layer 1: SharedConstants | `packages/shared/constants/` | 修改 | 新增压缩相关的 API 端点和常量（支持的文件格式等） |
| Layer 2: SharedUtils | `packages/shared/utils/` | — | 无变更 |
| Layer 10: FE_Hooks | `packages/frontend/src/hooks/` | 修改 | `useReportParser` 支持压缩选项和文件上传 |
| Layer 11: FE_Components | `packages/frontend/src/components/` | 新增 | `FileInfoCard` 组件（展示 MD5 + 文件大小） |
| Layer 12: FE_Pages | `packages/frontend/src/pages/` | 修改 | `RecordGeneratePage` 增加压缩复选框 + 压缩包上传入口 + 文件信息展示 |
| Layer 20: BE_Repository | `packages/backend/app/repository/` | 修改 | `file_storage.py` 新增解压函数，修改 `create_rar` 支持跳过压缩 |
| Layer 21: BE_Services | `packages/backend/app/services/` | 修改 | `report_parser_service` 接受 compress 参数；`document_builder_service` 移除硬编码渲染 |
| Layer 22: BE_Controllers | `packages/backend/app/controllers/` | 修改 | `record_controller` 新增压缩包上传端点，修改解析端点 |
| Layer 23: BE_Routes | `packages/backend/app/routes/` | — | 无变更（路由已在 controller 定义） |
