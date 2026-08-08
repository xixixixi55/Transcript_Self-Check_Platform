# Spec Delta: 电子数据检查笔录自动生成 — 审核编辑界面增强

> 基准 Spec: `openspec/specs/electronic-inspection-record/spec.md`
> 变更类型：MODIFIED (CAP-003 REQ-007) + ADDED (CAP-010, CAP-011)

---

## MODIFIED: CAP-003 — 全文在线编辑

### REQ-007: 任意字段可编辑（修改交互模式）

将交互模式从"始终可编辑"修正为"点击编辑"，与原 Spec 的 WHEN/THEN 描述对齐。该模式适用于预览页的独立字段，以及检材、人员、软件工具和提取清单中的文本编辑入口。

**Scenario: 点击字段进入编辑（通用）**
- WHEN 民警在预览页面上点击任意文本字段
- THEN 该字段从纯文本展示切换为可编辑状态（Input 或 TextArea）
- AND 其他字段不受影响（每个字段独立控制编辑状态）

**Scenario: 失焦保存**
- WHEN 民警在编辑状态下点击字段外部区域或按下 Enter
- THEN 字段退出编辑状态，恢复为纯文本展示
- AND 修改后的值通过 `updateReport()` 同步到前端状态

**Scenario: 修改委托人**
- WHEN 民警点击委托人字段的文本
- THEN 切换为 Input 输入框，可修改
- WHEN 失焦 → 预览实时更新显示新值

**Scenario: 修改案件简要情况**
- WHEN 民警点击案件简要情况文本
- THEN 切换为 TextArea（多行文本），可修改
- WHEN 失焦 → 预览实时更新

**Scenario: 修改检查设备硬件**（保持不变）
- WHEN 民警从硬件下拉框选择不同设备
- THEN 检查设备章节自动更新

**Scenario: 修改软件版本号**
- WHEN 民警修改软件版本号
- THEN 检查过程和检查设备章节中的版本号同步更新

**Scenario: 编辑结构化条目文本**
- WHEN 民警编辑检材、检查人员、软件工具或提取清单中的文本
- THEN 该文本先以展示态呈现，点击后进入编辑态
- AND 保存、取消、添加和删除操作保持对应编辑器的既有数据回调行为

**Scenario: 光盘编号使用统一入口**
- WHEN 民警进入审核编辑页面，且案件尚未开始压缩或正在压缩
- THEN 附件区域不再展示“附件3：光盘编号”编辑输入
- AND 页面顶部展示唯一的首个光盘编号输入框
- AND 压缩完成前填写或修改时，编号随案件草稿自动保存并供后续压缩使用
- AND 附件区域仍可根据已保存的光盘编号展示只读日期或格式校验反馈

**Scenario: 压缩完成后复用统一入口映射盘号**
- WHEN 压缩已完成但盘号尚未映射
- THEN 页面顶部同一位置展示首个光盘编号输入框和提交映射动作
- AND 修改该输入只用于提交全序列盘号映射，不另行修改案件草稿

**Scenario: 已验证归档不再允许改写盘号**
- WHEN 盘号映射已验证且案件归档完成
- THEN 页面顶部不再展示可编辑的首个光盘编号输入框
- AND 已验证 Manifest 中的盘号保持只读

**Scenario: 只读页面禁止修改盘号**
- WHEN 当前审核编辑页面没有有效编辑租约
- THEN 页面顶部首个光盘编号输入框不可编辑
- AND 待映射状态的提交动作不可用

---

## ADDED: CAP-010 — 所有字段可见

### REQ-017: 补齐缺失字段区域

预览页面 MUST 展示 InspectionReport 中所有业务字段，当前缺失的字段区域全部补齐。

**Scenario: 展示检材情况（五）**
- WHEN 用户进入预览页面
- THEN (五) 检材情况区域展示所有检材条目
- AND 使用 `EvidenceEditor` 组件渲染
- AND 支持添加/删除/修改检材（型号、IMEI1、IMEI2、序列号、编号）

**Scenario: 展示检查人员（八）**
- WHEN 用户进入预览页面
- THEN (八) 检查人员区域展示所有检查人员
- AND 使用 `InspectorEditor` 组件渲染
- AND 支持添加/删除/修改检查人员（姓名、单位、警号）

**Scenario: 展示检查过程（三）**
- WHEN 用户进入预览页面
- THEN (三) 检查过程区域展示 4 个步骤
- AND 每个步骤的步骤号固定，内容可编辑

**Scenario: 展示软件工具列表**
- WHEN 用户进入预览页面
- THEN (二) 检查设备下方展示软件工具列表
- AND 列表从 `software_tools` 动态生成
- AND 每个工具的版本号可编辑

**Scenario: 展示检查结果子字段**
- WHEN 用户进入预览页面
- THEN (四) 检查结果中的各子字段（检材编号、软件名称、版本、数据摘要、RAR 文件名、MD5、文件大小）独立展示和编辑
- AND 不再使用拼接模板字符串展示

**Scenario: 展示提取固定清单（附件1）**
- WHEN 用户进入预览页面
- THEN 附件1 区域展示提取固定清单表格
- AND 表格列可编辑，行可增删

### REQ-018: 检查方法可编辑

**Scenario: 检查方法可修改**
- WHEN 民警需要修改检查方法
- THEN (一) 检查方法字段不再禁用（`disabled`）
- AND 支持点击编辑

---

## ADDED: CAP-011 — 点击编辑交互

### REQ-019: EditableField 通用组件

**Scenario: 文本展示模式（默认）**
- WHEN 字段未处于编辑状态
- THEN 以 `<Typography.Text>` 样式渲染纯文本
- AND 鼠标悬停时显示编辑提示（边框或图标）
- AND 空值字段显示占位文字"点击编辑"

**Scenario: 切换为编辑模式**
- WHEN 用户点击文本区域
- THEN 切换为 `<Input>`（单行）或 `<TextArea>`（多行，如 > 50 字）
- AND 输入框自动聚焦
- AND 其他字段保持文本展示模式不变

**Scenario: 保存并退出编辑**
- WHEN 用户按下 Enter（单行）或失焦（单行/多行）
- THEN 值通过 `onChange` 回调提交
- AND 组件恢复为文本展示模式
- WHEN 用户按下 Escape → 放弃修改，恢复原值

**Scenario: 字段类型自动判断**
- WHEN `type="text"` → 渲染为可编辑 `<Input>`
- WHEN `type="textarea"` → 渲染为可编辑 `<TextArea rows={3}>`
- WHEN `type="select"` → 渲染为可编辑 `<Select>`（用于硬件设备等枚举字段）

---

## ADDED: CAP-012 — 手动测试反馈修复（2026-07-13）

### REQ-020: 文号格式修正

**Scenario: 文号从案件编号生成**
- WHEN 报告解析成功
- THEN 前端使用解析出的 `case_number`（案件编号）生成文号
- AND 格式为 `[区域前缀]电检〔YYYY〕[6位数字]号`
- AND 区域前缀从委托单位自动推断（如含"测试地区"→"测试公"，否则"xx"）

**Scenario: 文号旁显示警告提示**
- WHEN 预览页面渲染
- THEN 文号字段旁展示黄色警告 Alert："注意修改文号！"

### REQ-021: 检材/人员删除按钮始终可见

**Scenario: 单条记录时可删除**
- WHEN 检材情况或检查人员仅剩 1 条记录
- THEN 删除按钮仍然可见和可用
- AND 删除最后一条后列表为空

### REQ-022: 数据字段映射修正

**Scenario: 委托单位 = 采集单位**
- WHEN 系统从 HTML 报告提取数据
- THEN `entrust_unit`（委托单位）映射为报告中的"采集单位"（`collect_unit`）

**Scenario: 委托人 = 采集人**
- WHEN 系统从 HTML 报告提取数据
- THEN `entrust_person`（委托人）映射为报告中的"采集人"（`collector`）

**Scenario: 检查地点默认值**
- WHEN 系统构建 InspectionReport
- AND 报告中未提供检查地点
- THEN `inspection_place` 默认值为"合成检验鉴定中心"

### REQ-023: 软件工具名称可编辑

**Scenario: 新建软件工具**
- WHEN 用户点击"添加软件工具"
- THEN 新增一行空白的软件工具（名称+版本号均可编辑）

**Scenario: 修改工具名称和版本**
- WHEN 用户点击软件工具名称或版本号
- THEN 进入编辑模式，可修改
- WHEN 失焦 → 保存修改

**Scenario: 删除软件工具**
- WHEN 用户点击工具行的删除按钮
- THEN 该工具从列表中移除

### REQ-024: 提取固定清单默认表头

**Scenario: 无数据时展示默认表头**
- WHEN 提取固定清单的 columns/rows 为空
- THEN 默认展示 6 列标准表头：序号、文件名称、文件路径、文件大小、MD5哈希值、备注
- AND 默认展示 1 行空白记录

### REQ-025: 附件2 图片上传集成

**Scenario: 上传检材照片**
- WHEN 用户在附件2区域点击"上传"按钮
- THEN 选择本地 .jpg/.png 图片文件后展示缩略图

**Scenario: 导出时图片随传**
- WHEN 用户点击"导出 Word"
- THEN 已上传的图片文件随 `report_json` 一起通过 FormData 发送到后端
- AND 后端将图片嵌入 .docx 附件2区域

---

### REQ-026: officecli 跨环境调用兼容

`record_generator_service.py` 调用 officecli 时 MUST 兼容不同执行环境（bash 终端 vs uvicorn 子进程）。

**Scenario: uvicorn 环境下 PATH 不完整**
- WHEN 后端通过 `uvicorn` 启动（`npm run dev`）
- AND 子进程环境中 PATH 不包含 npm 全局目录和 System32
- THEN 系统通过 `shutil.which("officecli")` 查找 officecli 的绝对路径（含 `.CMD` 扩展名）
- AND 子进程 `env` 中显式注入 `C:\Windows\System32` 到 PATH，确保 Windows 能通过 cmd.exe 执行 .CMD 批处理文件

**Scenario: officecli 输出 UTF-8 解码**
- WHEN subprocess 捕获 officecli 的 stdout/stderr
- THEN 使用 `encoding="utf-8"` 解码（而非中文 Windows 默认的 GBK）

**Scenario: 封装调用接口**
- WHEN 服务层需要调用 officecli
- THEN 通过 `_run_officecli(*args)` 辅助函数统一调用
- AND 调用方不直接使用 `subprocess.run` 或 `shell=True`

### REQ-027: 后端测试命令可用

**Scenario: 从工作区运行后端测试**
- WHEN 开发者执行 `pnpm --filter @biji/backend test` 或项目的 `npm run test`
- THEN 后端脚本能够定位项目根目录的 `tests/` 目录
- AND pytest 收集并执行后端测试用例，而非因测试目录不存在而退出

### REQ-028: 文档漂移检查忽略运行时测试缓存

**Scenario: pytest 生成缓存后执行文档检查**
- WHEN 后端测试在应用目录生成 `.pytest_cache/`
- AND 开发者执行 `npm run check-docs`
- THEN 文档检查忽略该运行时缓存目录
- AND 仍继续报告实际项目目录与 `harness/directory.md` 的差异

---

## ADDED: CAP-013 — 检查人员卡片布局与添加入口

### REQ-030: 检查人员卡片自适应布局和持续添加入口

审核编辑界面的检查人员区域 MUST 使用可自适应的正方形卡片网格。宽屏每行最多展示 3 个卡片，窄屏允许自动降为 2 个或 1 个；检查人员卡片后 MUST 始终保留一个添加检查人员的虚线加号卡片。

**Scenario: 展示检查人员卡片网格**
- WHEN 审核编辑界面存在检查人员
- THEN 每个检查人员使用正方形卡片展示
- AND 宽屏每行最多 3 个卡片，超出后自动换行
- AND 窄屏根据可用宽度自动降为 2 列或 1 列

**Scenario: 空列表保留添加入口**
- WHEN 当前报告没有检查人员
- THEN 检查人员区域仍展示一个虚线边框的加号卡片
- AND 加号卡片可用于添加启用的检查人员

**Scenario: 添加入口持续存在**
- WHEN 当前报告已有一个或多个检查人员
- THEN 加号卡片始终位于检查人员卡片之后
- AND 点击加号卡片直接展示尚未添加的启用检查人员
- AND 选择人员卡片立即添加，不再要求通过下拉框二次选择
- AND 添加人员后保持现有人员顺序、删除和拖拽排序行为

### REQ-031: 检查人员编辑保存必须收敛

审核编辑界面修改检查人员后，草稿保存 MUST 在成功响应后结束 pending/loading 状态，不得持续重复发送内容完全相同的 PATCH 请求。真正发生后续内容变化时，仍 MUST 按现有 revision 顺序继续保存。

**Scenario: 检查人员修改后保存一次**
- WHEN 用户添加、删除或调整检查人员顺序
- AND 草稿 PATCH 成功返回保存后的草稿
- THEN 保存状态结束并显示已保存结果
- AND 相同草稿内容不会因令牌或组件重渲染变化再次发送 PATCH

**Scenario: 保存期间发生真实后续修改**
- WHEN 首个草稿 PATCH 尚未返回时用户再次修改检查人员或其他字段
- THEN 新内容保留在待保存队列
- AND 首个请求成功后仅继续发送包含新内容且使用最新 revision 的请求
