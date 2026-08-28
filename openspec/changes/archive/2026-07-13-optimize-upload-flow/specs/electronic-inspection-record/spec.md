# 规格增量：电子数据检查笔录自动生成——上传流程优化

> 基准 Spec: `openspec/specs/electronic-inspection-record/spec.md`
> 变更类型：MODIFIED (CAP-001, CAP-004) + ADDED (CAP-006 ~ CAP-008)

---

## MODIFIED: CAP-001 — HTML 报告上传与解析

### REQ-001: 上传报告目录（修改）

在原有基础上新增压缩选项：

**Scenario: 选择文件夹上传（压缩默认勾选）**
- WHEN 用户通过文件夹选择器选择报告文件夹
- AND "压缩为 .rar"复选框保持默认勾选
- THEN 前端以 `webkitdirectory` 模式上传 data/ 目录下的所有 JSON 文件
- AND 后端解析各 JSON 提取案件信息、设备信息、工具版本、数据分类统计
- AND 后端将整个报告目录压缩为 `[案件名称].rar` 并计算 MD5
- AND 返回结构化解析结果（含 rar_info）

**Scenario: 选择文件夹上传（取消压缩）**
- WHEN 用户取消勾选"压缩为 .rar"复选框
- AND 选择报告文件夹上传
- THEN 后端跳过 RAR 压缩步骤
- AND 不计算 MD5
- AND 返回的 `rar_info` 为 null

### REQ-012: 避免重复压缩（修改）

**Scenario: 压缩开关关闭时跳过**
- WHEN `compress=false`
- THEN 无论 RAR 是否存在，均跳过压缩步骤
- AND `rar_info` 返回 null

**Scenario: RAR 已存在且 compress=true 时跳过**
- WHEN `compress=true`
- AND `output/compressed/[案件名称].rar` 已存在且大小 > 0
- THEN 跳过压缩步骤，直接使用现有 RAR 文件

---

## ADDED: CAP-006 — 压缩选项控制

### REQ-013: 压缩复选框

**Scenario: 默认勾选压缩**
- WHEN 用户进入上传页面
- THEN "压缩为 .rar"复选框默认勾选

**Scenario: 压缩复选框仅在文件夹模式下可用**
- WHEN 用户选择"上传压缩包"模式
- THEN "压缩为 .rar"复选框禁用或隐藏

**Scenario: 取消压缩后检查结果留空**
- WHEN 用户取消压缩并完成解析
- THEN 检查结果中的 RAR 文件名、MD5 哈希、文件大小字段留空
- AND 导出的 Word 笔录中对应字段显示为空

---

## ADDED: CAP-007 — 压缩包直接上传

### REQ-014: 上传 .rar/.zip 压缩包

**Scenario: 上传 .rar 文件并解析**
- WHEN 用户通过文件选择器选择 .rar 文件上传
- THEN 后端接收文件，保存到临时目录
- AND 调用解压工具（WinRAR/7-Zip/Python zipfile）解压到临时目录
- AND 验证解压后的目录包含必需的 JSON 文件（data_case_info.json 等）
- AND 解析 JSON 数据，构建 InspectionReport
- AND 直接计算上传的 .rar 文件的 MD5 和文件大小
- AND 跳过压缩步骤（已经是压缩包）

**Scenario: 上传 .zip 文件并解析**
- WHEN 用户选择 .zip 文件上传
- THEN 流程同上（使用 Python zipfile 解压）

**Scenario: 压缩包内缺少必需文件**
- WHEN 解压后的 data/ 目录下缺少必需 JSON 文件
- THEN 返回 422 错误，明确提示缺少哪个文件

**Scenario: 文件类型不支持**
- WHEN 用户选择非 .rar/.zip 格式的文件
- THEN 前端阻止上传，提示"仅支持 .rar 和 .zip 格式"

---

## ADDED: CAP-008 — 文件信息展示

### REQ-015: 展示 MD5 和文件大小

**Scenario: 上传后展示文件信息**
- WHEN 报告解析成功
- AND rar_info 不为 null（压缩包上传或有压缩的文件夹上传）
- THEN 前端在页面上展示：
  - "文件 MD5：[32 位十六进制哈希值]"
  - "文件大小：[X.XX MB]"
- AND 信息位于上传区域下方，解析结果卡片中

**Scenario: 未压缩时不展示文件信息**
- WHEN 报告解析成功
- AND rar_info 为 null（取消压缩的文件夹上传）
- THEN 文件信息区域显示"未生成压缩文件"

**Scenario: 文件大小按 MB 显示**
- WHEN 文件大小 >= 1 MB
- THEN 显示为 "X.XX MB"（保留两位小数）
- WHEN 文件大小 < 1 MB
- THEN 显示为 "X.XX KB"

---

---

## ADDED: CAP-009 — 软件工具列表动态生成

### REQ-016: 按实际操作生成 software_tools

系统 MUST 根据实际调用的工具动态生成 software_tools 列表，而非硬编码。

**Scenario: WinRAR 参与流程时追加**
- WHEN 流程中调用了 WinRAR CLI（压缩 .rar 或解压 .rar）
- THEN `software_tools` 列表包含"WinRAR压缩管理软件（版本号 X.XX）"
- AND 版本号通过 `WinRAR.exe --version` 或注册表动态检测，而非硬编码

**Scenario: Python zipfile 解压时不追加 WinRAR**
- WHEN 用户上传 .zip 压缩包
- AND 系统使用 Python zipfile 标准库解压
- THEN `software_tools` 列表不包含 WinRAR（zipfile 是 Python 标准库，不是独立取证工具）

**Scenario: 不压缩时不追加 WinRAR**
- WHEN 用户取消"压缩为 .rar"
- AND 流程中没有任何 WinRAR CLI 调用
- THEN `software_tools` 列表不包含 WinRAR

**Scenario: 移除虚构的 Hash 工具**
- WHEN 系统计算 MD5 哈希值
- THEN MD5 通过 Python `hashlib.md5()` 标准库计算，不添加虚构的"Hash"软件工具条目

### software_tools 生成规则

| 流程路径 | software_tools 内容 |
|------|------|
| 文件夹 + 压缩 (.rar) | 美亚手机大师-并行版V5、WinRAR压缩管理软件 |
| 文件夹 + 不压缩 | 美亚手机大师-并行版V5 |
| 上传 .rar | 美亚手机大师-并行版V5、WinRAR压缩管理软件 |
| 上传 .zip | 美亚手机大师-并行版V5 |

---

## 跨功能约束（追加）

- **MUST**: `rar_info` 在 ParseReportResponse 中改为可选字段（`RarInfo | null`）
- **MUST**: 压缩包上传端点与文件夹上传端点复用同一个 Controller
- **MUST**: 解压操作仅存在于 BE_Repository 层（`file_storage.py`）
- **MUST**: `software_tools` 列表由后端根据实际调用的工具动态生成，禁止硬编码
- **MUST**: `document_builder_service.py` 中的软件工具渲染逻辑移除所有硬编码版本号和特殊分支，直接遍历 `software_tools` 列表逐行输出
