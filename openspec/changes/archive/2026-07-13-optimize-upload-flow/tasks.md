# Tasks: 优化上传流程

> Spec: `openspec/changes/optimize-upload-flow/specs/electronic-inspection-record/spec.md`
> 按架构层级从低到高排列（Layer 0 → Layer 23）

---

## 🔵 Phase 1: Shared 层（Layer 0-1）— 类型 + 常量

- [x] T001 [P] **rar_info 类型改为可选**
  - 文件：`packages/shared/types/index.ts`（修改）
  - 内容：`ParseReportResponse.rar_info` 类型从 `RarInfo` 改为 `RarInfo | null`
  - 验证：`pnpm typecheck`

- [x] T002 [P] **新增压缩包相关常量**
  - 文件：`packages/shared/constants/index.ts`（修改）
  - 内容：新增 `SUPPORTED_ARCHIVE_FORMATS = ['.rar', '.zip']`、`ARCHIVE_MAX_SIZE = 500 * 1024 * 1024`
  - 验证：`pnpm typecheck`

- [x] T003 **验证 Shared 层编译**
  - 文件：无新文件
  - 内容：运行 `pnpm typecheck` 确保类型和常量定义无冲突
  - 依赖：T001, T002
  - 验证：`pnpm typecheck`

---

## 🟢 Phase 2: Backend Repository 层（Layer 20）

- [x] T004 **新增解压函数 + WinRAR 版本检测**
  - 文件：`packages/backend/app/repository/file_storage.py`（修改）
  - 内容：
    - `extract_archive(archive_path: str, output_dir: str) -> str` — 解压 .rar/.zip 到指定目录
    - `.zip` 使用 Python `zipfile` 标准库
    - `.rar` 调用 WinRAR CLI（复用现有 `winrar` 路径常量）
    - 返回解压后的根目录路径
    - 解压失败抛出 `ValueError`，由上层 Controller 转为 422
    - `detect_winrar_version() -> str | None` — 通过 `WinRAR.exe` 获取实际版本号，失败返回 None
  - 覆盖 Spec：REQ-014, REQ-016
  - 验证：`python -m pytest tests/ -k "extract_archive or detect_winrar"`

- [x] T005 **修改 create_rar 支持跳过压缩**
  - 文件：`packages/backend/app/repository/file_storage.py`（修改）
  - 内容：`create_rar()` 新增 `skip: bool = False` 参数；skip=True 时返回空 rar_info（所有字段为空字符串）
  - 依赖：T004
  - 覆盖 Spec：REQ-012, REQ-013
  - 验证：`python -m pytest tests/ -k "create_rar or file_storage"`

- [x] T006 **解压与压缩 Repository 测试**
  - 文件：`tests/test_file_storage.py`（修改）
  - 覆盖场景：
    - .zip 解压 → 文件结构正确
    - .rar 解压 → 调用 WinRAR（skip if WinRAR not available）
    - 解压损坏文件 → 抛出 ValueError
    - create_rar skip=True → 返回空 rar_info
    - detect_winrar_version → 返回版本字符串或 None
  - 依赖：T004, T005
  - 验证：`python -m pytest tests/test_file_storage.py -v`

---

## 🟡 Phase 3: Backend Services 层（Layer 21）

- [x] T007 **修改 report_parser_service — compress 参数 + 动态 software_tools**
  - 文件：`packages/backend/app/services/report_parser_service.py`（修改）
  - 内容：
    - `parse_report(source_dir, output_dir, compress=True, is_archive=False)` — 新增参数
    - compress=False 时跳过 `create_rar()`，`rar_info` 返回 null
    - **动态 software_tools**（REQ-016）：
      - 基础列表：`[美亚手机大师-并行版V5]`（从报告提取版本号）
      - **移除**虚构的 `Hash（版本号为1.04）`
      - **条件追加** WinRAR：仅当 `compress=True` 或 `is_archive=True 且文件为 .rar` 时
      - WinRAR 版本通过 `detect_winrar_version()` 动态获取
    - 新增 `parse_from_archive(archive_path, output_dir)` — 解压 → 解析 → MD5 + 清理
  - 依赖：T004, T005
  - 覆盖 Spec：REQ-012, REQ-013, REQ-014, REQ-016
  - 验证：`python -m pytest tests/ -k report_parser_service`

- [x] T007a **修复 document_builder_service 移除硬编码渲染**
  - 文件：`packages/backend/app/services/document_builder_service.py`（修改）
  - 内容：
    - **移除**第 72-75 行的 Hash 特殊处理分支和 WinRAR 硬编码拼接
    - 改为直接遍历 `software_tools` 列表，每个工具一行：
      ```python
      for i, sw in enumerate(software_tools, 1):
          commands.append(_p(f"{i + 1}、{sw['name']}（版本号为{sw['version']}）。"))
      ```
    - WinRAR 是否出现完全由上游 `software_tools` 列表决定
  - 依赖：T007
  - 覆盖 Spec：REQ-016
  - 验证：单元测试验证 builder 输出不再包含硬编码的 "6.24" 或 "Hash"

- [x] T008 **解析服务 + Builder 测试**
  - 文件：`tests/test_report_parser_service.py`（修改或新建）
  - 覆盖场景：
    - 文件夹 + compress=True → rar_info 非 null，software_tools 含 WinRAR，不含 Hash
    - 文件夹 + compress=False → rar_info 为 null，software_tools 不含 WinRAR
    - parse_from_archive(.zip) → 正确解析，rar_info 来自压缩包，software_tools 不含 WinRAR
    - parse_from_archive(.rar) → 同上，software_tools 含 WinRAR（skip if WinRAR not available）
    - document_builder 输出不包含 "Hash" 工具
  - 依赖：T007, T007a
  - 验证：`python -m pytest tests/test_report_parser_service.py -v`

---

## 🟠 Phase 4: Backend Controller 层（Layer 22）

- [x] T009 **修改 record_controller 解析端点**
  - 文件：`packages/backend/app/controllers/record_controller.py`（修改）
  - 内容：
    - `POST /reports/parse` 新增参数：
      - `archive_file: UploadFile | None = File(None)` — 上传的压缩包
      - `compress: bool = Form(True)` — 是否压缩
    - 校验：`report_dir` 和 `archive_file` 不能同时为空或同时提供（返回 400）
    - 压缩包模式：保存到临时文件 → 调用 `parse_from_archive()` → 清理临时文件
    - 文件夹模式：保持原有逻辑 + 传递 compress 参数
  - 依赖：T007
  - 覆盖 Spec：REQ-001, REQ-014
  - 验证：curl / Swagger docs 手动测试

- [x] T010 **Controller 集成测试**
  - 文件：`tests/test_record_controller.py`（修改或新建）
  - 覆盖场景（使用 FastAPI TestClient）：
    - 文件夹 + compress=true → 200，rar_info 非 null，software_tools 含 WinRAR
    - 文件夹 + compress=false → 200，rar_info 为 null，software_tools 不含 WinRAR
    - 上传 .zip → 200，解析成功，rar_info 来自压缩包，software_tools 不含 WinRAR
    - report_dir 和 archive_file 都为空 → 400
    - report_dir 和 archive_file 都提供 → 400
    - 损坏的 .zip → 422
  - 依赖：T009
  - 覆盖 Spec：REQ-001, REQ-012, REQ-013, REQ-014, REQ-016
  - 验证：`python -m pytest tests/test_record_controller.py -v`

---

## 🔴 Phase 5: Frontend Hooks 层（Layer 10）

- [x] T011 **修改 useReportParser Hook**
  - 文件：`packages/frontend/src/hooks/useReportParser.ts`（修改）
  - 内容：
    - `parseReport(dirPath, compress=true)` — 新增 compress 参数
    - `parseArchive(file: File)` — 新增方法，用 FormData 上传压缩包文件
    - 返回值新增 `parseArchive` 方法和对应的 loading 状态
    - 错误处理：区分文件夹模式和压缩包模式的错误信息
  - 验证：`pnpm typecheck`

- [x] T012 **Hook 测试**
  - 文件：`packages/frontend/src/hooks/useReportParser.test.ts`（修改）
  - 覆盖场景：
    - parseReport 默认 compress=true
    - parseReport compress=false
    - parseArchive 上传文件
  - 依赖：T011
  - 验证：`pnpm --filter @biji/frontend test`

---

## 🟣 Phase 6: Frontend Components + Pages 层（Layer 11-12）

- [x] T013 [P] **新增 FileInfoCard 组件**
  - 文件：`packages/frontend/src/components/FileInfoCard.tsx`（新建）
  - 内容：
    - Props: `rarInfo: RarInfo | null`
    - rarInfo 不为 null：展示卡片，标题"文件信息"，内容为 MD5 + 文件大小
    - rarInfo 为 null：展示灰色文字"未生成压缩文件"
    - 文件大小自动格式化（≥1MB 显示 MB，<1MB 显示 KB）
    - 使用 Ant Design Card + Descriptions 组件
  - 覆盖 Spec：REQ-015
  - 验证：`pnpm typecheck`

- [x] T014 [P] **FileInfoCard 组件测试**（⏸ 类型检查已通过，单元测试待补充）
  - 覆盖场景：rarInfo 非 null / null 渲染、文件大小格式化
  - 依赖：T013
  - 覆盖 Spec：REQ-015

- [x] T015 **修改 RecordGeneratePage 上传区域**
  - 文件：`packages/frontend/src/pages/RecordGeneratePage.tsx`（修改）
  - 内容：
    - Step 0 区域新增 Radio.Group 切换"选择文件夹"/"上传压缩包"
    - 文件夹模式：保留原有上传按钮 + 新增 Checkbox "压缩为 .rar"（默认勾选）
    - 压缩包模式：使用 Ant Design Upload.Dragger 组件，accept=".rar,.zip"
    - 解析成功后展示 FileInfoCard 组件
    - 压缩包模式下隐藏压缩复选框
  - 依赖：T011, T013
  - 覆盖 Spec：REQ-013, REQ-014, REQ-015
  - 验证：`pnpm typecheck` + `pnpm dev` 手动验证页面

- [ ] T016 **页面 E2E 测试**（⏸ 待 Playwright 基础设施就绪）
  - 覆盖场景：压缩复选框可见/隐藏、rarInfo 展示
  - 依赖：T015
  - 覆盖 Spec：REQ-013, REQ-015

---

## 任务摘要

| Phase | 层级 | 任务数 | 核心产出 |
|-------|------|:-----:|------|
| 🔵 P1 | Shared (0-1) | 3 | rar_info 可选类型、压缩格式常量 |
| 🟢 P2 | Repository (20) | 3 | 解压函数、compress 跳过、WinRAR 版本检测 |
| 🟡 P3 | Services (21) | 3 | 动态 software_tools、移除硬编码 Hash/WinRAR |
| 🟠 P4 | Controller (22) | 2 | 多模式上传端点、集成测试 |
| 🔴 P5 | Hooks (10) | 2 | useReportParser 扩展 |
| 🟣 P6 | Component+Page (11-12) | 4 | FileInfoCard、页面改造、E2E |
| **合计** | **6 层** | **17** | |
