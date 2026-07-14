# Design: 电子数据检查笔录自动生成

## 核心流程

```
上传 HTML 报告 → 后端解析 JSON → 返回结构化数据
       ↓
前端渲染完整笔录预览（Web 表单，每个字段可编辑）
       ↓
民警在线审核修改任意内容 → 前端实时更新
       ↓
确认无误 → 点击导出 → 后端 officecli merge → 下载 .docx
```

## 数据模型

### 笔录全文数据结构

```typescript
interface InspectionReport {
  // 标题
  title: string                    // "电子数据检查笔录"
  document_number: string          // "xx电检〔2026〕xx号"

  // 一、绪论
  introduction: {
    entrust_unit: string           // (一) 委托单位
    entrust_person: string         // (二) 委托人
    entrust_time: string           // (三) 委托时间
    case_summary: string           // (四) 案件简要情况
    evidence_list: EvidenceItem[]  // (五) 检材情况
    inspection_requirement: string // (六) 检查要求
    inspection_time_range: string  // (七) 检查起止时间
    inspectors: Inspector[]        // (八) 检查人员
    inspection_place: string       // (九) 检查地点
  }

  // 二、检查
  inspection: {
    method: string                 // (一) 检查方法（固定文本）
    equipment: {
      hardware: string             // 硬件设备（下拉选）
      software: SoftwareItem[]     // 软件工具列表（版本号可编辑）
    }
    process_steps: ProcessStep[]   // (三) 检查过程
    result: {                      // (四) 检查结果
      summary: string
      export_file_name: string
      md5_hash: string
      file_size: string
      disc_number: string
    }
  }

  // 附件
  attachments: {
    extract_list: TableData        // 附件1: 电子数据提取固定清单(表格)
    photo_count: number            // 附件2: 照片数量
    disc_label: string             // 附件3: 光盘信息
  }
}
```

## 技术决策

### 决策 1: 预览使用结构化表单渲染

**方案**: 笔录预览渲染为一个大的 Ant Design Form，每个章节为 Card，每个字段为 Form.Item。点击字段即进入编辑模式（Input / TextArea）
**理由**:
- Ant Design Form 天然支持大量字段的管理和校验
- 用户可以直观看到整份笔录的结构
- 编辑状态和预览状态合二为一，无需切换
- **备选方案**: contentEditable 富文本。拒绝理由：结构化数据需要精确控制每个字段，富文本不利于后续 officecli merge 的数据提取

### 决策 2: 导出使用 officecli create + batch set

**方案**: 不依赖预置 Word 模板文件，而是：
1. 用 `officecli create` 创建空白 .docx
2. 用 `officecli batch` 写入全部段落、表格、样式
3. 用 `officecli refresh` 更新页码

**理由**:
- 笔录格式标准化，结构固定，代码生成比模板填充更可控
- 不依赖额外模板文件部署
- 支持未来 6 类文书各自不同的格式结构
- **备选方案**: 准备 .docx 模板 + officecli merge。保留为降级方案，如果 create+batch 实现复杂度过高则切换

### 决策 3: 硬件设备存 JSON 配置文件

**方案**: `packages/backend/app/data/hardware_devices.json` 存储设备列表
**理由**:
- 配置简单，无需数据库
- 符合本地文件系统存储策略
- 方便直接编辑和备份

### 决策 4: 检查过程为模板化生成 + 可编辑

**方案**: 检查过程 4 个步骤预定义模板字符串，解析时自动替换变量（设备型号/IMEI/编号/版本号），渲染为 4 个独立文本域，民警可修改每步的文本
**理由**:
- 固定步骤结构保证格式规范
- 自动替换减少手工输入
- 每步独立编辑保证灵活性

### 决策 5: RAR 压缩 + MD5 哈希自动计算

**方案**: 上传 HTML 报告目录后，后端自动：
1. 用 Python `zipfile`（或调用 WinRAR CLI）将整个报告目录压缩为 .rar
2. 用 Python `hashlib.md5()` 计算文件哈希值
3. 用 `os.path.getsize()` 获取文件大小
**理由**:
- Python hashlib MD5 结果已验证与标准工具一致（与 certutil 对比：05c1020b2e5d6fc52346cb4669d2cd08）
- RAR 文件名用案件名称，自动生成
- 检查结果段落全自动填充，零人工输入
- **备选方案**: 人工输入 MD5。拒绝理由：MD5 算法标准化，Python 计算结果与所有标准工具一致，可全自动

### 决策 6: 附件图片上传

**方案**: 预览页附件区提供图片上传组件（Ant Design Upload），支持多选本地 .jpg/.png 文件，上传后展示缩略图列表，可删除和拖拽排序。导出时通过 officecli add 将图片嵌入 .docx
**理由**:
- 检材照片不在 HTML 报告中，必须由民警手动添加
- 拖拽排序方便控制照片在文档中的展示顺序
- officecli 支持通过 batch 命令插入图片到指定位置

## 文件结构（新增）

```
packages/shared/types/
  └── index.ts                     # 修改：添加 InspectionReport 等类型

packages/backend/app/
├── repository/
│   ├── html_parser.py             # 美亚报告 JSON 解析器
│   └── device_config.py           # 硬件设备配置存取
├── services/
│   ├── report_parser_service.py   # 报告解析编排
│   ├── record_generator_service.py # 笔录文档生成（officecli 调用）
│   ├── document_builder_service.py  # docx 文档构建器（段落/表格/样式）
│   └── file_storage.py           # 文件存取（RAR压缩/MD5计算）
└── controllers/
    ├── record_controller.py       # 修改：解析/导出 API
    └── device_controller.py       # 硬件设备 CRUD API
    └── device_controller.py       # 硬件设备 CRUD API

packages/frontend/src/
├── hooks/
│   ├── useReportParser.ts         # 上传解析状态管理
│   └── useRecordExport.ts         # 导出状态管理
├── components/
│   ├── ReportUploader.tsx         # 报告上传组件
│   ├── RecordPreview.tsx          # 笔录预览+编辑（核心组件）
│   ├── RecordSection.tsx          # 单个章节卡片（绪论/检查/附件）
│   ├── EvidenceEditor.tsx         # 检材情况编辑器
│   ├── InspectorEditor.tsx        # 检查人员编辑器
│   └── DeviceManager.tsx          # 硬件设备管理
└── pages/
    ├── RecordGeneratePage.tsx     # 笔录生成主页面
    └── DeviceManagePage.tsx       # 设备管理页面
```

### API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/reports/parse` | 上传并解析 HTML 报告目录 |
| POST | `/api/v1/records/export` | 导出 .docx 笔录 |
| GET | `/api/v1/devices` | 获取硬件设备列表 |
| POST | `/api/v1/devices` | 添加硬件设备 |
| PUT | `/api/v1/devices/{id}` | 更新硬件设备 |
| DELETE | `/api/v1/devices/{id}` | 删除硬件设备 |

### 决策 7: 解析缓存

**方案**: 解析结果 JSON 缓存 + RAR 防重复压缩
1. 首次解析后保存 `output/parsed/[report_dir_name].json`
2. 再次请求同目录时，缓存存在且源文件未变 → 直接返回缓存
3. RAR 已存在 → 跳过压缩，直接用现有文件
**理由**: 避免每次操作重复解析和压缩，提升响应速度

### 存储路径

| 用途 | 路径 |
|------|------|
| 解析缓存 | `output/parsed/[报告目录名].json` |
| RAR 压缩包 | `output/compressed/[案件名称].rar` |
| 导出 .docx | `output/exports/[文号].docx` |
| 硬件设备配置 | `packages/backend/app/data/hardware_devices.json` |

## 架构合规性

- ✅ 前端层不直接引用后端层（HTTP API 通信）
- ✅ officecli 调用仅存在于 BE_Services
- ✅ Controller 不直接访问文件系统（通过 Service → Repository）
- ✅ 文件 ≤ 250 行
