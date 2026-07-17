# Template 2026 — 当前实现摘要

> 本变更包记录业务方参考 DOCX 到项目 Word 模板的转换结果。参考 DOCX 仅用于一次性模板重建和人工格式核对，不是运行时输出、自动化 fixture 或正式生成产物。
> 当前运行时模板：`word_templates/template.docx`

---

## 1. 架构决策

### 模板创建方式
- `scripts/create_template.py`：历史 v1 一次性脚本，按段落索引替换，已不作为当前重建入口。
- `scripts/create_template_v2.py`：当前一次性重建脚本，按 run 级别替换并保留段落结构。
- 两个脚本都不会在每次导出时自动执行；正常导出直接读取 `word_templates/template.docx`。

### 模板填充方式
- 文件：`packages/backend/app/services/template_filler_service.py`
- 策略：python-docx 读取模板 → 列表展开 → 表格填充 → 占位符替换 → VML替换 → 照片处理 → 导出
- 回退：模板不存在时使用 `document_builder_service.py` + officecli batch

### 分页设计

- `create_template_v2.py` 在签名摘要和附件标题段落前使用普通 `w:br w:type="page"` 分页符，并移除这些段落上的 `w:pageBreakBefore`。
- `template_filler_service.py` 在填充后清理附件之间的无意义空段落，同时保留图片和分页符。
- 具体页数和分页效果取决于 Word 渲染，自动化检查不等同于最终 DOCX 的人工版式验收。

### 当前已实现内容

- 模板优先的 DOCX 生成、列表展开、附件1表格填充、照片处理和 VML 占位符替换。
- 模板缺失或填充失败时，回退到 `document_builder_service.py` + officecli batch。
- 旧 v1 模板脚本保留作历史参考，不代表当前运行时流程。

---

## 2. 关键字段映射

| 模板占位符 | 数据来源 | 说明 |
|-----------|---------|------|
| `{{title}}` | `report.title` | "电子数据检查笔录" |
| `{{document_number}}` | `report.document_number` | 使用解析/编辑后的文号；后端提供默认值，前端可按案件编号生成 |
| `{{entrust_unit}}` | `introduction.entrust_unit` | 源数据 `submit_unit`（送检单位） |
| `{{entrust_persons_text}}` | `introduction.entrust_persons` | 用 `、` 连接，源数据 `submit_person` |
| `{{entrust_time}}` | `introduction.entrust_time` | `format_time_chinese()` |
| `{{case_summary}}` | `introduction.case_summary` | 避免双"案" → `_format_case_summary()` |
| `{{inspection_time_range}}` | `introduction.inspection_time_range` | `format_time_range_chinese()` |
| `{{data_summary}}` | `inspection.result.data_summary` | 默认 "即时通讯、手机信息" |
| `{{first_evidence_number}}` | `introduction.evidence_list[0].evidence_number` | 附件2照片标题 |
| `{{photo_count}}` | `len(photo_paths)` | 检材图X张 |
| `{{disc_number}}` | `attachments.disc_number` | 光盘编号 |
| `{{burning_date}}` | `attachments.burning_date` | 刻录时间（民警填写） |
| `{{md5_hash}}` | `inspection.result.md5_hash` | 文件MD5哈希值 |
| `{{file_size}}` | `inspection.result.file_size` | 目录压缩时为字节数文本；压缩包直传时为带“字节”后缀的文本 |

### 列表占位符

| 标记 | 数据 | 行为 |
|------|------|------|
| `{{#evidence_list}}...{{/evidence_list}}` | `introduction.evidence_list` | 每个检材一个段落 |
| `{{#inspectors}}...{{/inspectors}}` | `introduction.inspectors` | 每个人员一个段落 |
| `{{#process_steps}}...{{/process_steps}}` | `inspection.process_steps` | 每个步骤一个段落 |

### 列表展开关键规则
- 每个列表只展开**第一个**匹配段落，后续重复标记的段落直接删除
- 实现：`_expand_all_lists()` 中 `expanded_names` set 去重

---

## 3. 已修复的 Bug 清单

| # | Bug | 级别 | 修复文件 | 修复方式 |
|---|-----|:--:|------|------|
| 1 | `entrust_person` → `entrust_persons` 类型升级 | L1 | shared/types, report_parser, doc_builder, RecordEditorForm, tests | string → string[] |
| 2 | 委托人字段映射错误（collector→submit_person） | L1 | `report_parser_service.py` | `submit_unit`/`submit_person` 替代 `collect_unit`/`collector` |
| 3 | 字体颜色全部改黑色 | L1 | `create_template_v2.py` | `_normalize_colors()` 删除显式颜色属性 |
| 4 | 页眉文号硬编码 | L1 | `create_template_v2.py` + `template_filler_service.py` | 页眉占位符 + `_replace_header_footer()` |
| 5 | VML 文本框硬编码值未替换 | L1 | `template_filler_service.py` | `_replace_vml_textbox_placeholders()` |
| 6 | VML 容器段落泄漏正文 | L1 | `template_filler_service.py` | `_remove_vml_container_paragraphs()` |
| 7 | 附件3新增 `burning_date` | L2 | shared/types, report_parser, template, filler, RecordEditorForm | 新增字段 + 前端输入框 |
| 8 | 列表重复展开（steps×4, evidence×2） | L2 | `template_filler_service.py` | `expanded_names` set 去重 |
| 9 | 附件1空表格显示占位符 | L1 | `template_filler_service.py` | 空数据时画对角线 + 清除占位符 |
| 10 | 附件2模板图片残留 | L1 | `create_template_v2.py` + `template_filler_service.py` | `_remove_sample_images()` + `_handle_photos()` |
| 11 | "案案"双后缀 | L1 | `report_parser_service.py` | `_format_case_summary()` 判断已有"案"不追加 |
| 12 | 日期前导零 "07月" | L2 | `template_filler_service.py` | `.replace("年0","年").replace("月0","月")` |
| 13 | 时间格式转中文 | L1 | `html_parser.py` | `format_time_range_chinese()` |
| 14 | file_size 双"字节" | L1 | `report_parser_service.py` | 去掉数据源中"字节"后缀 |
| 15 | 批注残留 | L1 | `create_template_v2.py` + `template_filler_service.py` | 模板创建 + 填充时双重删除 commentRange |
| 16 | 前端无条件覆盖文号 | L1 | `RecordGeneratePage.tsx` | 后端有默认值时保留 |
| 17 | 照片1张时不显示 | L1 | `template_filler_service.py` | `Inches` 导入 + `_cleanup` 跳过 drawing 段落 |
| 18 | 照片布局自适应 | L2 | `template_filler_service.py` | 1张居中段落，≥2张2列表格 |
| 19 | 缓存失效（字段映射变更后旧缓存仍使用） | L1 | `report_parser_service.py` | `_CACHE_VERSION = 4` + 版本校验 |
| 20 | 附件页空白页 | L1 | `create_template_v2.py` + `template_filler_service.py` | 普通分页符 + 填充后清理无意义空段落 |

---

## 4. 缓存管理

- 缓存文件：`packages/output/parsed/[报告目录名].compress.json` 或 `.nocompress.json`
- 缓存版本：`_CACHE_VERSION = 4`（`report_parser_service.py`）
- 缓存有效性同时检查源 JSON 修改时间和缓存载荷版本；版本不匹配时重新解析。
- 缓存目录属于生成产物，本阶段不清理、不纳入正式文档资产。

---

## 5. 解析、软件工具与附件规则

- 设备详情扫描 `data/[检材编号]/` 下各直接子目录中的 JSON，包括 `Base/`、`Phone/` 和其他同级目录；结构化解析支持既有 `name/value` 等格式，以及 `设备型号`、`信息/内容`、`c1/c2` 格式，失败后再进行正则回退。
- `software_tools` 在产品版本非空时包含美亚手机大师、WinRAR 和 Python hashlib 三项；产品版本为空时省略美亚手机大师，但 WinRAR 和 Python hashlib 仍保留。WinRAR 版本优先检测，检测不到时使用默认值；Python 版本取当前解释器版本。
- 附件1使用五列：序号、电子数据、来源、提取方式、文件MD5哈希值。目录解析启用压缩并成功生成归档文件时自动填充一行；未压缩或直接上传 `.rar/.zip` 时当前实现不自动补附件1数据行。
- 目录压缩优先调用 WinRAR 生成 RAR，未检测到 WinRAR 时降级为 ZIP；直接上传 `.rar/.zip` 时记录原始上传文件的文件名、MD5 和大小，并跳过再次压缩。

## 6. 关键文件索引

| 文件 | 用途 |
|------|------|
| `word_templates/template.docx` | Word 模板（由 create_template_v2.py 生成） |
| `scripts/create_template.py` | 历史 v1 一次性模板脚本，不是当前重建入口 |
| `scripts/create_template_v2.py` | 模板生成脚本（run 级纯文本替换） |
| `packages/backend/app/services/template_filler_service.py` | 模板填充核心服务 |
| `packages/backend/app/services/report_parser_service.py` | 报告解析 + 默认值 |
| `packages/backend/app/services/record_generator_service.py` | 文档生成入口（模板优先） |
| `packages/backend/app/services/document_builder_service.py` | 旧方案（officecli batch，回退用） |
| `packages/backend/app/repository/html_parser.py` | HTML 解析 + 时间格式化 |
| `packages/shared/types/index.ts` | InspectionReport 类型定义 |
| `packages/frontend/src/components/RecordEditorForm.tsx` | 前端编辑表单 |
| `packages/frontend/src/pages/RecordGeneratePage.tsx` | 前端报告生成页（文号逻辑） |
| `scripts/lint-arch.ts` | 架构约束检查（template_filler 在例外列表） |

---

## 7. 验证命令

```bash
# 文档一致性
npm.cmd run verify:docs

# 快速工程验证
npm.cmd run verify:quick

# 后端自动化测试
npm.cmd run test:backend
```

本阶段验证结果：`verify:docs` 和 `verify:quick` 均通过；代码测试沿用前一阶段 parser 提交时的 `58 passed` 结果，本阶段未修改代码。以上自动化验证不替代参考 DOCX 的人工视觉核对。

---

## 8. 已知限制

1. 图片嵌入使用 python-docx drawing + `get_or_add_image_part`，非完美复刻参考文档的 VML 左右排版
2. 附件1表格多行时可能跨页断开
3. 检查人员列表需用户在前端手动填写
4. 光盘编号、刻录时间需用户在预览中手动输入
5. 参考 DOCX 仅用于人工格式核对，不是自动化保证或运行时输出文件
