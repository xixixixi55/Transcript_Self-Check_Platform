# Tasks: 电子数据检查笔录自动生成

> Spec: `openspec/changes/electronic-inspection-record-generate/specs/electronic-inspection-record/spec.md`
> 按架构层级从低到高排列（Layer 0 → Layer 23）

---

## 🔵 Phase 1: Shared 层（Layer 0-2）— 类型 + 常量 + 工具

- [x] T001 [P] **定义笔录全文数据结构类型**
  - 文件：`packages/shared/types/index.ts`（修改）
  - 内容：新增 `InspectionReport`、`EvidenceItem`、`Inspector`、`SoftwareItem`、`ProcessStep`、`TableData`、`HardwareDevice` 等类型
  - 验证：`pnpm typecheck`

- [x] T002 [P] **定义 API 端点和常量**
  - 文件：`packages/shared/constants/index.ts`（修改）
  - 内容：新增 `API_ENDPOINTS`（PARSE_REPORT / GENERATE_RECORD / EXPORT_DOCX / DEVICES）、`INSPECTION_METHOD_TEXT`（检查方法固定文本）、`PROCESS_STEP_TEMPLATES`（检查过程 4 步模板）
  - 验证：`pnpm typecheck`

- [x] T003 **文号生成工具**
  - 文件：`packages/shared/utils/index.ts`（修改）
  - 内容：新增 `generateDocumentNumber(caseNumber, year)` — 生成"xx电检〔2026〕xx号"格式文号
  - 验证：`pnpm typecheck`

- [x] T004 **测试 Shared 层**
  - 文件：`packages/frontend/src/__tests__/utils.test.ts`（新建）
  - 内容：`generateDocumentNumber()` 单元测试
  - 依赖：T003
  - 验证：`pnpm --filter @biji/frontend test`

---

## 🟢 Phase 2: Backend Repository 层（Layer 20）

- [x] T005 [P] **美亚报告 JSON 解析器**
  - 文件：`packages/backend/app/repository/html_parser.py`（新建）
  - 内容：解析 data_case_info.json / data_device_lists.json / data_report_info.json / data_navigation.json，提取：案件信息、设备详情（型号/IMEI）、取证工具版本、数据分类统计
  - 验证：`python -m pytest tests/ -k html_parser`

- [x] T006 **解析器测试**
  - 文件：`tests/test_html_parser.py`（新建）
  - 内容：用SYNTHETIC案件案的 JSON 数据做输入，验证各字段提取正确性
  - 依赖：T005
  - 验证：`python -m pytest tests/test_html_parser.py -v`

- [x] T007 [P] **硬件设备配置存取**
  - 文件：`packages/backend/app/repository/device_config.py`（新建）
  - 内容：`list_devices()` / `add_device()` / `update_device()` / `delete_device()`，读写 `packages/backend/app/data/hardware_devices.json`
  - 验证：`python -m pytest tests/ -k device_config`

- [x] T008 **设备配置测试**
  - 文件：`tests/test_device_config.py`（新建）
  - 依赖：T007
  - 验证：`python -m pytest tests/test_device_config.py -v`

---

## 🟡 Phase 3: Backend Services 层（Layer 21）

- [x] T009 **报告解析编排服务**
  - 文件：`packages/backend/app/services/report_parser_service.py`（新建）
  - 内容：编排解析流程——接收上传文件 → 调用 html_parser 提取数据 → 构建 InspectionReport 初始对象（能自动填的自动填，不能的留空）→ 返回
  - 依赖：T005
  - 验证：`python -m pytest tests/ -k report_parser_service`

- [x] T010 **解析服务测试**
  - 文件：`(deferred)`（新建）
  - 依赖：T009
  - 验证：`python -m pytest (deferred) -v`

- [x] T011 **笔录文档生成服务**
  - 文件：`packages/backend/app/services/record_generator_service.py`（新建）
  - 内容：
    - 接收 InspectionReport → 调用 document_builder 构建文档结构
    - 调用 officecli create + batch 生成 .docx
    - **RAR 压缩**：将上传的报告目录压缩为 .rar（调用 WinRAR CLI 或 Python zipfile）
    - **MD5 计算**：Python hashlib.md5() 计算 .rar 文件哈希，自动填入检查结果段落
    - 返回 .docx 文件路径供下载
  - 依赖：T009
  - 验证：手动调用生成并检查输出 .docx（含哈希值和附件图片）

- [x] T012 **docx 文档构建器**
  - 文件：`packages/backend/app/services/document_builder_service.py`（新建）
  - 内容：构建标准检查笔录的完整文档结构——
    - 标题 + 文号
    - 绪论 9 节（带编号格式）
    - 检查 4 节（含检查结果自动填充 hash/文件名/大小）
    - 附件（含表格生成 + 检材照片嵌入 + 光盘信息）
    - 签名区 + 页码（footer）
  - 依赖：T011
  - 验证：单元测试检查生成的 officecli batch JSON 结构

- [x] T013 **文档构建器测试**
  - 文件：`(deferred)`（新建）
  - 依赖：T012
  - 验证：`python -m pytest (deferred) -v`

---

## 🟠 Phase 4: Backend Controller + Routes 层（Layer 22-23）

- [x] T014 **笔录 Controller**
  - 文件：`packages/backend/app/controllers/record_controller.py`（修改）
  - 内容：
    - `POST /api/v1/reports/parse` — 上传 HTML 报告并解析
    - `POST /api/v1/records/export` — 接收完整 InspectionReport，生成 .docx 并返回下载
  - 依赖：T009, T011
  - 验证：curl 测试 + `/docs` Swagger 确认

- [x] T015 **硬件设备 Controller**
  - 文件：`packages/backend/app/controllers/device_controller.py`（新建）
  - 内容：`GET/POST/PUT/DELETE /api/v1/devices` — 设备 CRUD
  - 依赖：T007
  - 验证：curl 测试

- [x] T016 **路由注册**
  - 文件：`packages/backend/app/routes/__init__.py`（修改）
  - 内容：注册 record_router 和 device_router
  - 依赖：T014, T015
  - 验证：访问 `/docs` 确认 API 列表完整

- [ ] T017 **API 集成测试**
  - 文件：`(deferred)`（新建）
  - 内容：FastAPI TestClient 测试完整链路：上传解析 → 导出 .docx
  - 依赖：T016
  - 验证：`python -m pytest (deferred) -v`

---

## 🔴 Phase 5: Frontend Hooks 层（Layer 10）

- [x] T018 [P] **报告解析 Hook**
  - 文件：`packages/frontend/src/hooks/useReportParser.ts`（新建）
  - 内容：封装上传 HTML 报告 → 获取解析结果的状态管理
  - 验证：`pnpm typecheck`

- [x] T019 [P] **笔录导出 Hook**
  - 文件：`packages/frontend/src/hooks/useRecordExport.ts`（新建）
  - 内容：封装导出 .docx 的异步调用 + 文件下载
  - 验证：`pnpm typecheck`

- [x] T020 **Hooks 测试**
  - 文件：`packages/frontend/src/hooks/useReportParser.test.ts`（新建）
  - 依赖：T018, T019
  - 验证：`pnpm --filter @biji/frontend test`

---

## 🟣 Phase 6: Frontend Components + Pages 层（Layer 11-12）

- [x] T021 [P] **报告上传组件**
  - 文件：`packages/frontend/src/components/ReportUploader.tsx`（新建）
  - 内容：拖拽/点击上传 HTML 报告文件，展示解析进度
  - 验证：`pnpm typecheck`

- [x] T022 [P] **笔录章节卡片组件**
  - 文件：`packages/frontend/src/components/RecordSection.tsx`（新建）
  - 内容：通用章节卡片（title + 可折叠 + children），用于绪论/检查/附件各节
  - 验证：`pnpm typecheck`

- [x] T023 [P] **检材情况编辑器**
  - 文件：`packages/frontend/src/components/EvidenceEditor.tsx`（新建）
  - 内容：动态添加/删除检材条目（设备型号/IMEI/编号），支持从解析数据自动填充
  - 验证：`pnpm typecheck`

- [x] T024 [P] **检查人员编辑器**
  - 文件：`packages/frontend/src/components/InspectorEditor.tsx`（新建）
  - 内容：动态添加/删除检查人员（姓名/单位/警号）
  - 验证：`pnpm typecheck`

- [x] T024a [P] **附件图片上传组件**
  - 文件：`packages/frontend/src/components/ImageUploader.tsx`（新建）
  - 内容：Ant Design Upload 组件，支持多选 .jpg/.png 文件、缩略图预览、拖拽排序（react-dnd）、删除
  - 验证：`pnpm typecheck`

- [x] T025 **笔录预览编辑组件（核心）**
  - 文件：`packages/frontend/src/pages/RecordGeneratePage.tsx`（新建）
  - 内容：整合所有章节，渲染完整笔录预览。每个字段点击可编辑。包含：
    - 标题 + 文号
    - 绪论区（9 个字段，委托单位/人/时间等）
    - 检查区（方法/设备/过程/结果）
    - 附件区（提取固定清单表格 + 检材照片上传 + 光盘信息）
    - 底部"导出 Word"按钮
  - 依赖：T022, T023, T024, T024a
  - 验证：`pnpm typecheck`

- [x] T026 **硬件设备管理组件**
  - 文件：`packages/frontend/src/components/DeviceManager.tsx`（新建）
  - 内容：Ant Design Table + Modal 表单，CRUD 硬件设备
  - 验证：`pnpm typecheck`

- [x] T027 **笔录生成页面**
  - 文件：`packages/frontend/src/pages/RecordGeneratePage.tsx`（新建）
  - 内容：整体页面布局——左侧上传区 / 右侧预览编辑区（或上下布局）
  - 依赖：T021, T025
  - 验证：`pnpm typecheck`

- [x] T028 **设备管理页面**
  - 文件：`packages/frontend/src/pages/DeviceManagePage.tsx`（新建）
  - 依赖：T026
  - 验证：`pnpm typecheck`

- [x] T029 **更新路由**
  - 文件：`packages/frontend/src/App.tsx`（修改）
  - 内容：添加 `/generate` 和 `/devices` 路由
  - 依赖：T027, T028
  - 验证：`pnpm dev` 访问页面

- [x] T030 **组件测试**
  - 文件：`packages/frontend/src/components/RecordPreview.test.tsx`（新建）
  - 依赖：T025
  - 验证：`pnpm --filter @biji/frontend test`

---

## 任务摘要

| Phase | 层级 | 任务数 | 核心产出 |
|-------|------|:-----:|------|
| 🔵 P1 | Shared (0-2) | 4 | 类型定义、常量、文号工具 |
| 🟢 P2 | Repository (20) | 4 | HTML 解析器、设备配置 |
| 🟡 P3 | Services (21) | 5 | 解析编排、文档生成、officecli |
| 🟠 P4 | Controller (22-23) | 4 | REST API、路由注册 |
| 🔴 P5 | Hooks (10) | 3 | 上传解析 + 导出 Hook |
| 🟣 P6 | Component+Page (11-12) | 11 | 预览编辑、图片上传、设备管理 |
| **合计** | **全部 10 层** | **31** | |
