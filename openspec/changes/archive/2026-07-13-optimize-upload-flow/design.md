# Design: 上传流程优化

> 变更包：`openspec/changes/optimize-upload-flow`

---

## 架构决策

### AD-001: 复用现有 `/reports/parse` 端点 vs 新增独立端点

**决策**：修改 `/reports/parse` 端点增加 `compress` 参数和 `archive_file` 可选参数。

**理由**：
- 解析逻辑 90% 相同（读 JSON → 构建 InspectionReport → 缓存）
- 减少 API 端点数量，降低前端调用复杂度
- FastAPI 支持同一端点接受 Form + UploadFile 组合

**备选方案**：新增 `/reports/upload-archive` 端点
- 拒绝理由：会增加前端分支逻辑，解析结果格式完全一致，不值得拆分

### AD-002: 压缩包解压策略

**决策**：`.zip` 用 Python 标准库 `zipfile`，`.rar` 调用 WinRAR CLI。

**理由**：
- Python 标准库不支持 .rar 解压（需第三方库 rarfile，且依赖 unrar 二进制）
- 项目中已有 WinRAR 路径常量（`file_storage.py`），复用现有检测逻辑
- .zip 是主流压缩格式，zipfile 零依赖

**备选方案**：引入 `rarfile` Python 库
- 拒绝理由：仍需系统安装 unrar，无优势；且增加依赖

### AD-003: 前端上传模式切换

**决策**：使用 `Radio.Group` 切换"选择文件夹"与"上传压缩包"两种模式，默认文件夹模式。

**理由**：
- 两种上传方式的 UI 差异大（文件夹选择器 vs 文件拖拽）
- 避免单个 UI 区域承载过多交互
- "压缩为 .rar"复选框仅在文件夹模式下显示

### AD-004: 类型变更 — `rar_info` 改为可选

**决策**：`ParseReportResponse.rar_info` 从 `RarInfo` 改为 `RarInfo | null`。

**理由**：
- 取消压缩时后端返回 null
- 前端根据 null 判断是否展示文件信息卡片
- 不影响现有的已缓存解析结果（向后兼容）

---

## 数据流

```
用户操作                   前端                     后端                      存储
─────────   ─────────────────────────   ─────────────────────   ──────────────────

[选择文件夹] → compress=true (默认)
                → POST /reports/parse     → 解析 JSON
                  {report_dir, compress}    → 压缩 RAR → 计算 MD5
                                           → 返回 {rar_info}       → output/compressed/

[取消压缩]   → compress=false
                → POST /reports/parse     → 解析 JSON
                  {report_dir, compress}    → 跳过压缩
                                           → 返回 {rar_info: null}

[上传 .rar]  → 选择文件 (.rar/.zip)
                → POST /reports/parse     → 保存文件 → 解压
                  {archive_file}            → 解析 JSON
                                           → 计算 MD5 + 大小
                                           → 返回 {rar_info}       → 清理临时目录
```

---

## API 设计

### 修改：POST /api/v1/reports/parse

**请求** (multipart/form-data)：

| 参数 | 类型 | 必填 | 说明 |
|------|------|:--:|------|
| `report_dir` | string | 否 | 报告目录路径（文件夹模式） |
| `archive_file` | file | 否 | 上传的 .rar/.zip 文件（压缩包模式） |
| `compress` | bool | 否 | 是否压缩（默认 true），仅文件夹模式生效 |

**响应** (JSON)：

```json
{
  "success": true,
  "data": {
    "report": { /* InspectionReport */ },
    "parsed_files": ["data_case_info.json", "..."],
    "rar_info": {
      "filename": "xxx.rar",
      "md5": "a1b2c3...",
      "size_bytes": 12345678,
      "size_display": "11.77 MB"
    } | null
  }
}
```

### 错误响应

| 状态码 | 场景 |
|:------:|------|
| 400 | `report_dir` 和 `archive_file` 都未提供 |
| 400 | 同时提供 `report_dir` 和 `archive_file` |
| 422 | 压缩包解压后缺少必需 JSON 文件 |
| 422 | .rar 解压失败（WinRAR 未安装） |
| 422 | 压缩包损坏或格式不识别 |

---

## UI 设计

### RecordGeneratePage 变更

上传步骤（Step 0）增加：

```
┌─────────────────────────────────────┐
│  ○ 选择文件夹    ○ 上传压缩包        │  ← Radio 切换模式
├─────────────────────────────────────┤
│ [文件夹模式]                          │
│  ☑ 压缩为 .rar                       │  ← Checkbox，默认勾选
│  [选择报告目录并解析]                 │  ← 点击弹出路径输入
├─────────────────────────────────────┤
│ [压缩包模式]                          │
│  支持 .rar 和 .zip 格式               │
│  [拖拽或点击上传]                     │  ← Upload.Dragger
├─────────────────────────────────────┤
│ 解析成功后展示：                       │
│ ┌─────────────────────────────┐     │
│ │ 文件 MD5：a1b2c3...         │     │  ← FileInfoCard 组件
│ │ 文件大小：11.77 MB           │     │     (rar_info 不为 null 时)
│ └─────────────────────────────┘     │
│ 或 "未生成压缩文件"                   │  ← (rar_info 为 null 时)
└─────────────────────────────────────┘
```

---

## 文件变更清单

| 文件 | 层级 | 操作 | 说明 |
|------|:----:|:----:|------|
| `packages/shared/types/index.ts` | L0 | 修改 | `rar_info` 改为 `RarInfo \| null` |
| `packages/shared/constants/index.ts` | L1 | 修改 | 新增 `SUPPORTED_ARCHIVE_FORMATS` |
| `packages/frontend/src/hooks/useReportParser.ts` | L10 | 修改 | 支持压缩包文件和 compress 参数 |
| `packages/frontend/src/components/FileInfoCard.tsx` | L11 | **新增** | 展示 MD5 + 文件大小的卡片组件 |
| `packages/frontend/src/pages/RecordGeneratePage.tsx` | L12 | 修改 | 上传模式切换 + 压缩复选框 + FileInfoCard |
| `packages/backend/app/repository/file_storage.py` | L20 | 修改 | 新增 `extract_archive()` 函数 |
| `packages/backend/app/services/report_parser_service.py` | L21 | 修改 | 接受 `compress` 参数，动态生成 software_tools |
| `packages/backend/app/services/document_builder_service.py` | L21 | 修改 | 移除硬编码 Hash/WinRAR 渲染逻辑，改为遍历 software_tools |
| `packages/backend/app/controllers/record_controller.py` | L22 | 修改 | 新增 `archive_file` + `compress` 参数 |

### AD-005: software_tools 动态生成

**决策**：`software_tools` 列表由 `report_parser_service.py` 根据实际调用的工具动态构建。

**当前问题**：
- `report_parser_service.py` 硬编码 `{"name": "Hash", "version": "1.04"}` — 实际 MD5 由 Python `hashlib.md5()` 计算，不存在外部 Hash 工具
- `document_builder_service.py` 第 75 行硬编码 `WinRAR压缩管理软件（版本号为6.24）` 拼接到第一个软件条目 — 版本号不准确，且 WinRAR 不是每次都调用

**修复方案**：

1. **移除 Hash**：从 `software_tools` 生成逻辑中删除虚构的 Hash 条目
2. **条件追加 WinRAR**：仅当 WinRAR CLI 被实际调用时（压缩 .rar 或解压 .rar），才追加 WinRAR 条目
3. **动态检测版本**：通过 `WinRAR.exe` 获取实际版本号（`subprocess.run([winrar_path])` 解析输出）
4. **简化 builder**：`document_builder_service.py` 中移除所有硬编码逻辑，直接遍历 `software_tools` 逐行渲染，不做特殊分支

**software_tools 生成矩阵**：

| 流程路径 | WinRAR 调用？ | software_tools |
|------|:---:|------|
| 文件夹 + compress=true | ✅ (压缩) | 美亚手机大师、WinRAR |
| 文件夹 + compress=false | ❌ | 美亚手机大师 |
| 上传 .rar | ✅ (解压) | 美亚手机大师、WinRAR |
| 上传 .zip | ❌ (zipfile) | 美亚手机大师 |

**理由**：
- 笔录是法律文书，"检查设备"章节必须如实反映使用的工具
- 写上没有用过的工具 = 虚假记录
- 漏掉实际用过的工具 = 记录不完整

**备选方案**：保留 Hash，将其描述为"Python hashlib 模块"
- 拒绝理由：Python 标准库不是独立取证软件，写进笔录不符合规范

---

### 不涉及变更的文件

- `packages/backend/app/routes/__init__.py` — 路由已在 controller 定义
- `packages/backend/app/services/record_generator_service.py` — 导出逻辑不变（已在上次 fix 中修改）
