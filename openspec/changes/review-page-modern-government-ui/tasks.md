# 审核编辑页现代政务工作台样板

workflow_level: 2
legacy_migration: true
spec_sync_status: reconciled
spec_sync_evidence: 现有场景及主软件单一显示场景已于 2026-08-25 同步到 openspec/specs/electronic-inspection-record/spec.md

## 目标

在不改变报告解析、字段数据结构、上传、附件处理和 Word 导出行为的前提下，为平台建立现代政务工作台全局外壳，并在电子数据检查笔录流程中保留已验收的审核编辑页样板。

本任务为 Level 2，仅维护本文件；不创建 proposal、spec 或 design，不实现其他五类未开放文书。

## 第十二阶段：审核章节标题反馈补丁

- [x] 将完整审核编辑器及右侧进度导航中的“文书信息与导出设置”统一精简为“文书信息”。
- [x] 保持文号编辑、四部分进度、章节定位、主取证软件、软件工具、保存和导出行为不变，并完成前端定向验证与差异检查。

### 第十二阶段验证记录

- 前端定向 Vitest：`RecordEditorForm`、`ReviewPendingSummary`/`ReviewSection`、`useReviewChecklist` 共 3 个文件、46 项用例通过。
- 架构检查、共享/前端 TypeScript 类型检查与 Impeccable UI 机械检测通过；`git diff --check` 通过。
- 本次仅调整章节展示文案，不改变正式业务行为；无需新增测试或 delta spec，人工验收不适用。

## 第十三阶段：主取证软件展示去重

- [x] 在“软件工具”区域只展示一次主取证软件名称和版本，并移除其下方重复的独立主取证软件区块。
- [x] 将主软件来源/确认状态及名称、版本编辑入口合并到同一主软件行；编辑继续更新 `inspection.primary_software` 并沿用既有派生与导出门控。
- [x] 运行主软件列表聚焦回归、受影响前端测试、Level 2 工程与文档门控，并核对最终差异。

### 第十三阶段验证记录

- 聚焦 Vitest：`SoftwareToolsList`、`RecordEditorForm`、`useReviewChecklist`、`softwareProjectionUtils` 共 4 个文件、47 项用例通过；覆盖主软件名称/版本只显示一次、待确认入口和原有派生行为。
- `npm run verify:quick` 通过，包含架构、共享/前端类型、治理文档、快速文档和仓库资产检查。
- delta 已与实现核对并同步 living spec；Impeccable 检测未发现本次新增区域问题，报告的两项告警均位于未修改的既有样式行。
- 人工验收：N/A；本次不改变视觉体系，单点展示、响应式结构和交互由聚焦 DOM 回归、类型与机械检测覆盖。

## 验收标准

- [x] 当前工作台左侧导航只显示首页和已确认的六类文书功能；未开放功能不可进入并显示明确的“暂未开放”状态，设备管理只作为电子数据检查笔录下的二级入口。
- [x] 首页、电子数据检查笔录模块入口、生成笔录上传/解析/审核/导出流程和电子设备管理共享同一个全局 PlatformShell。
- [x] 一级“电子数据检查笔录”与二级“生成笔录/电子设备管理”在路由和导航模型中真实体现父子关系。
- [x] 侧栏视觉覆盖整个 `100vh`，不依赖 Header/Footer 高度计算；主内容过长时侧栏无断层，1366×768、125% 和 150% 缩放下仍可用。
- [x] 案件工作台和审核编辑页的主内容只使用一个垂直滚动容器，浏览器文档不额外产生第二条页面滚动条。
- [x] 旧 `/generate` 和 `/devices` 地址通过路由层重定向到新地址，并尽量保留查询参数和 hash。
- [x] 首页只展示六类文书功能和真实开放状态，不增加统计、最近任务、使用次数或其他虚假数据。
- [x] 电子数据检查笔录模块入口展示真实的生成笔录和电子设备管理入口。
- [x] 审核编辑页使用独立的报告生成内容布局；全局路由只负责挂载统一的 `PlatformShell`，不在审核页重复创建侧栏。
- [x] 页面展示当前功能、案件摘要、案件编号、当前步骤、基础待核对提示和保存状态。
- [x] 待核对数量只来自当前报告可确定的空缺字段及既有日期/文件名校验结果，不硬编码、不修改共享数据模型和后端接口。
- [x] 章节可以折叠，单列表单、现有字段编辑、日期时间选择、图片和附件编辑行为保持不变。
- [x] Word 预览使用默认关闭的覆盖式右侧 Drawer，不参与主内容宽度计算；内容明确标注为结构摘要，不承诺最终 Word 版式。
- [x] 底部保存、返回、导出操作栏保持可见且不遮挡最后字段；导出和状态按钮在处理中防止重复触发。
- [x] 键盘 Tab 焦点可见；`Esc` 取消当前字段编辑，或在非字段编辑状态下关闭预览 Drawer；`Ctrl+S` 只执行已实现的当前页面状态更新并显示真实含义，不伪造服务器保存。
- [x] 1920×1080、1366×768、浏览器 125% 和 150% 缩放下，页面仍可操作，表格必要时横向滚动。
- [x] 原有字段编辑、上传解析和 Word 导出测试不回归，并新增工作台导航、状态、待核对提示、折叠、Drawer、键盘和防重复操作测试。
- [x] `npm.cmd run verify:frontend`、`npm.cmd run verify:quick` 和 `git diff --check` 通过；变更只包含本任务预期文件及用户原有修改。

## 任务列表

- [x] 建立仅服务报告生成流程的审核内容布局，接入深灰蓝视觉 Token，不承担全局导航职责。
- [x] 调整审核编辑页结构，增加页面标题区、案件摘要、当前步骤、可折叠章节和统一 Token 样式，同时复用现有字段编辑及附件组件。
- [x] 实现基于现有报告字段和既有校验函数的基础待核对清单与摘要，不新增业务必填规则。
- [x] 实现默认关闭、覆盖主编辑区的结构摘要预览 Drawer，保留关闭前滚动位置，不接触 Word/VML/分页逻辑。
- [x] 实现真实状态文案、当前页面状态更新、`Ctrl+S`、`Esc`、返回确认和保存/导出防重复操作。
- [x] 增加或更新组件测试，覆盖导航、步骤、案件摘要、待核对提示、折叠章节、Drawer、底部操作栏、焦点、键盘行为和原有编辑/导出行为。
- [x] 运行前端门控、快速门控和差异检查，记录验证结果并标记任务完成。

## 第二阶段：全局外壳与平台信息架构

- [x] 将报告生成专用外壳提升为全局 `PlatformShell`，让首页、模块入口、上传/解析、审核编辑和设备管理共享同一个侧栏；审核页不再嵌套完整侧栏。
- [x] 重构侧栏为真实一级/二级导航，支持父级展开、当前父子高亮、用户主动收起/展开、收起后的图标与 Tooltip 及未开放状态。
- [x] 建立 `/electronic-inspection` 模块入口和 `/electronic-inspection/generate`、`/electronic-inspection/devices` 子路由，保留旧路由兼容重定向。
- [x] 将旧首页改造成克制的现代政务工作台首页，展示六类功能入口和真实开放状态，不增加虚假业务数据。
- [x] 调整设备管理页面只变更路由和外层布局，保持现有设备 CRUD 行为和 API 不变。
- [x] 移除全局 Header/Footer 对侧栏高度的影响，统一主内容滚动和 Drawer/流程底部操作栏定位。
- [x] 统一 `html`、`body`、`#root` 的高度、默认外边距和文档溢出约束，确保案件工作台与审核编辑页只保留主内容滚动条。
- [x] 增加全局外壳、首页、模块入口、一级/二级导航、重定向和现有流程回归测试。
- [x] 运行前端门控、快速门控、生产构建和差异检查，并完成人工验收。

## 必要实现说明

- PlatformShell 是全局路由外壳；生成流程内部只保留页面标题、步骤、表单、Drawer 和底部操作栏，不再创建第二个完整侧栏。
- 侧栏不得使用依赖 Footer 高度的 `height: calc(100vh - xxxpx)`；优先采用固定全高侧栏与主区域独立滚动的布局。
- 一级导航仅包含首页和六类文书；电子设备管理只作为电子数据检查笔录下的二级功能。
- `/generate` 和 `/devices` 通过路由层兼容重定向，不复制页面实现；生成流程内部 `currentStep` 行为保持不变。
- 首页卡片第一项进入模块入口页，其他五项禁用并显示“暂未开放”；不添加单位名称、公安徽标、警徽、宣传口号或未确认品牌资产。
- 不引入新的大型 UI 依赖；优先复用 Ant Design，并将工作台视觉 Token 集中放入页面级主题和集中样式文件。
- 当前没有真实保存 API。“保存当前修改”与 `Ctrl+S` 只更新当前页面状态，状态文案必须明确为“当前页面修改已更新”，并辅以“仅保留在当前页面，未写入服务器”的说明。
- 导出仍调用现有 `useRecordExport` 和后端接口；如需获得导出成功/失败状态，只增加结果反馈，不改变文件生成、下载、VML、附件分页和空白页修复逻辑。
- 预览 Drawer 只展示报告结构摘要、案件信息、章节目录、附件数量和“非最终 Word 版式预览”提示。
- 待核对数量采用保守的前端派生清单：可识别的空缺字段和现有日期/文件名格式错误可以提示；无法由当前模型可靠判断的业务完整性不计入数量。
- 最终核验结果：`npm.cmd run test:frontend` 通过（13 个测试文件、70 个测试）；`npm.cmd run verify:frontend`、`npm.cmd run verify:quick`、`npm.cmd run build` 和 `git diff --check` 均通过。构建仍报告现有的大体积 chunk 提示，但未导致失败。

## 最终实现说明

- 全局路由外壳由 `PlatformShell` 统一挂载，首页、电子数据检查笔录模块入口、生成笔录流程和设备管理共用同一套平台侧栏；审核编辑页不再嵌套第二个完整侧栏。
- 侧栏采用全高平台布局，主内容独立滚动；一级文书导航与电子数据检查笔录下的“模块首页、生成笔录、电子设备管理”二级导航在路由模型中保持父子关系。未开放功能仅展示状态，不产生可进入路由。
- `/electronic-inspection` 为模块首页，`/electronic-inspection/generate` 和 `/electronic-inspection/devices` 为子路由；旧 `/generate`、`/devices` 通过路由重定向兼容，并保留查询参数与 hash。生成流程的 `currentStep`、设备 CRUD、上传解析和导出行为未改动。
- 审核编辑页继续使用单列审核表单、案件摘要、基础待核对提示、可折叠章节、默认关闭的覆盖式结构摘要 Drawer 和底部操作栏。待核对数量仅来自现有可确定的空缺字段及既有日期/文件名校验结果。
- 当前没有真实保存接口；保存和 `Ctrl+S` 只更新当前页面状态并显示“当前页面修改已更新”等真实文案，不表示已写入服务器。导出继续使用现有导出链路，并保留处理中、成功和失败反馈及防重复触发。
- 人工验收已确认全局外壳、首页信息架构、侧栏层级、审核页接入和一级菜单整行展开/收起交互符合预期。

## 最终人工验收

- [x] 全局平台侧栏从首页开始贯穿首页、模块入口、生成笔录流程和设备管理页面。
- [x] 首页展示六类文书功能，第一项可用，其余五项明确标记“暂未开放”且不可进入。
- [x] 一级/二级导航层级、父子高亮、侧栏收起/展开和未开放状态符合确认的信息架构。
- [x] “电子数据检查笔录”一级菜单整行支持鼠标及键盘展开/收起，二级菜单可正常进入模块首页、生成笔录和设备管理。
- [x] 审核编辑页保留步骤、案件摘要、待核对提示、折叠章节、结构摘要 Drawer、底部操作栏和真实状态反馈。
- [x] 人工视觉验收通过，确认本次 UI、全局外壳和导航改造可进入提交前核验阶段。

## 第七阶段：底部操作栏图标化

### 目标与验收标准

- [x] 审核编辑页底部的返回、保存和导出操作只显示简洁、可辨识的图标，不在按钮表面显示原文字说明。
- [x] 三个图标按钮继续提供原操作名称的悬浮提示与无障碍名称，保存中、导出中、禁用和点击行为保持不变。

### Layer 11：前端组件、样式与测试

- [x] 调整 `packages/frontend/src/components/ReviewActionBar.tsx` 与 `packages/frontend/src/reviewWorkspace.css`，使用返回、保存和 Word 文件图标构成紧凑的圆形操作按钮。
- [x] 更新 `packages/frontend/src/components/reviewWorkspaceComponents.test.tsx`，覆盖纯图标呈现、无障碍名称及既有忙碌状态行为。
- [x] 运行前端定向 Vitest、`npm run verify:quick`、scoped strict docs 与 `git diff --check`。

### 影响范围

- 影响层级：Layer 11 FE_Components；不修改操作回调、共享类型、后端接口、数据模型、持久化或 Word 导出合同。
- 人工验收：确认三个图标在审核编辑页底部操作栏中含义直观，按钮表面无文字，悬浮提示正确。

### 第七阶段验证记录

- 前端定向 Vitest：`reviewWorkspaceComponents.test.tsx` 共 1 个测试文件、10 个用例通过。
- `RecordEditorForm.test.tsx` 的 Tooltip 测试桩适配后 12 个用例通过，前端完整测试套件通过。
- 架构检查、TypeScript 类型检查、`npm run verify:quick` 与 `git diff --check` 通过；living spec 已同步纯图标操作场景。

## 第三阶段：移除模块首页并默认进入案件工作台

### 目标与验收标准

- [x] 保留平台总首页；移除电子数据检查笔录的独立模块首页，不再渲染 `ElectronicInspectionModulePage`。
- [x] 访问 `/electronic-inspection` 时默认重定向到 `/electronic-inspection/workbench`，并保留查询参数和 hash。
- [x] 点击侧栏一级“电子数据检查笔录”或平台总首页的电子数据检查入口时进入案件工作台；二级功能与父级展开、高亮行为保持可用。
- [x] 来源目录校验控制项位于案件工作台标题区右上角，并采用紧凑的小型控件；其开启/关闭、浏览器持久化及案件登记请求语义保持不变。
- [x] 案件工作台刷新、上传目录、分页、案件卡片和其他业务流程不回归。

### Layer 11–12：前端外壳、页面与样式

- [x] 调整 `packages/frontend/src/App.tsx`、`packages/frontend/src/components/PlatformSidebar.tsx` 和 `packages/frontend/src/pages/HomePage.tsx`，让电子数据检查入口统一落到案件工作台，并移除模块首页路由实现引用。
- [x] 调整 `packages/frontend/src/pages/CaseWorkbenchPage.tsx` 与 `packages/frontend/src/platformShell.css`，将既有来源目录校验偏好控件放入标题区右上角，以紧凑样式与刷新操作共同组成页面操作区。
- [x] 移除不再使用的电子数据检查模块首页页面文件，不得复制或改变 `useSourceAuthorizationPreference` 的持久化合同。
- [x] 更新 `packages/frontend/src/pages/platformShell.test.tsx`、`packages/frontend/src/pages/CaseWorkbenchPage.test.tsx`，并移除失去页面目标的模块首页测试；覆盖默认重定向、导航目标、控件位置/持久化和登记请求语义。

### 影响范围与验证

- 影响层级：Layer 11 FE_Components、Layer 12 FE_Pages；不修改共享类型、后端接口、数据模型或持久化格式。
- 自动化验证：相关 Vitest 页面测试、`npm run verify:quick`、当前变更 `npm run verify:docs:strict -- --change review-page-modern-government-ui` 与 `git diff --check`。
- 人工验收：确认案件工作台右上角的小型来源目录校验控件在常用桌面分辨率和侧栏收起状态下不挤压标题及刷新操作。

### 第三阶段验证记录

- `npm run lint:arch`、`npm run typecheck` 和 `npm run verify:quick`：通过。
- 前端定向测试：`platformShell.test.tsx` 与 `CaseWorkbenchPage.test.tsx` 共 2 个测试文件、29 个用例通过。
- 浏览器布局验收：1280×720 下来源目录校验按钮位于标题区右侧操作组，尺寸约 128×24；720×900 下操作组右对齐换行且无横向溢出；按钮开关状态可切换并恢复。
- living spec 已同步 `REQ-029` 的默认案件工作台入口及紧凑来源目录校验控制项场景。

## 第四阶段：右侧待核对栏与案件简要提示紧凑化

### 目标与验收标准

- [x] 审核编辑页存在待核对项且右侧空间充足时，利用主表单右侧空白显示窄版随屏待核对栏，不在页面顶部横向吸顶；主表单现有宽度和字段布局保持不变。
- [x] 右侧待核对栏保持当前真实数量、分组和点击定位能力；点击字段后目标章节不得被侧栏或底部操作栏遮挡。
- [x] 窄屏或浏览器 125%/150% 缩放导致右侧空间不足时，待核对栏收敛为不长期遮挡编辑区的窄版右侧悬浮入口，点击后临时展开并可立即收起；没有待核对项时不显示随屏侧栏或悬浮入口。
- [x] “（四）案件简要情况”标题右侧显示红色“（请注意人工核对）”，不再单独显示“案件简要情况由报告自动解析，可能不准确，请人工核对。”提示行。
- [x] 案件简要内容末尾存在回车、空格或制表符时，继续显示“当前内容末尾存在多余回车、空格或制表符，请检查并删除。”警告；没有尾部空白时不显示该警告。
- [x] 审核界面的字段标题简化为“委托单位前缀”，不再显示“（共享默认值）”；桌面端该字段与“（一）委托单位”在同一行左右分栏展示，空间不足时自动回落为上下布局，不产生横向溢出。
- [x] 不改变待核对清单派生规则、字段编辑、草稿保存、Word 导出或后端接口。

### Layer 11–12：前端组件、页面样式与测试

- [x] 调整 `packages/frontend/src/pages/CaseRecordGeneratePage.tsx`、`packages/frontend/src/components/ReviewPendingSummary.tsx` 与 `packages/frontend/src/reviewWorkspace.css`，将有待核对项的摘要移入审核表单右侧随屏栏；空间不足时提供可展开的右侧悬浮入口，并为章节定位预留不被遮挡的滚动偏移。
- [x] 调整 `packages/frontend/src/components/ReviewField.tsx`、`ReviewIntroductionSection.tsx` 与 `reviewWorkspace.css`，支持字段标题旁的紧凑红色提醒、尾部空白条件警告、精简的“委托单位前缀”标题，以及委托单位前缀/委托单位的响应式双列容器。
- [x] 更新 `packages/frontend/src/components/reviewWorkspaceComponents.test.tsx`、`RecordEditorForm.test.tsx` 及必要的页面测试，覆盖有/无待核对项的右侧栏/悬浮入口、定位回调、标题内红色提醒、尾部空白警告显示条件及委托单位双列结构。
- [x] 运行前端定向 Vitest、前端全量测试、生产构建、`npm run verify:quick` 与 `git diff --check`。
- [x] 人工检查桌面、窄屏和 125%/150% 缩放下的右侧栏、悬浮入口、双列回落与换行布局。

### 第四阶段验证记录

- 架构检查与 TypeScript 类型检查通过；受影响组件和页面集成测试共 3 个文件、36 个用例通过。
- 前端全量测试、生产构建、`verify:quick` 和仓库资产检查通过；构建仅保留既有的大体积 chunk 警告，测试仅输出既有 Ant Design deprecated/jsdom 能力提示。
- OpenSpec CLI 当前没有独立 `sync` 命令，delta 场景已按 reconciliation 路径同步到 living spec；scoped strict docs 与 OpenSpec strict validation 作为最终文档门控。
- 应用内浏览器初始化因本地浏览器工具路径缺失失败；后续已由用户在真实界面完成人工响应式视觉检查并确认通过。

### 影响范围

- 影响层级：Layer 11 FE_Components、Layer 12 FE_Pages/样式；修改既有文件，不新增目录、共享类型、后端接口、数据模型或持久化格式。
- 规格归属：待核对持续可见属于本变更 `REQ-029`；案件简要仍遵守 `audit-edit-enhancement` 的 `REQ-032` 人工核对与尾部空白提示语义，本阶段只调整展示位置和密度。

## 第五阶段：待核对浮层拖拽与字段级精确定位

### 目标与验收标准

- [x] 有待核对项时，用户可直接拖动收起状态的右侧“待核对”入口，无需先展开清单；拖动不误触发展开，位置限制在当前可视区域内且不得覆盖到底部操作栏之外。
- [x] 展开面板使用绝对定位并以竖向入口为固定锚点；展开、点击“收起待核对项”和再次展开时，入口屏幕位置不发生横向跳动。
- [x] 拖拽位置在当前审核页面会话内保持；重新进入页面使用默认位置，不新增浏览器、草稿或服务端持久化字段。
- [x] 点击每个待核对项时定位到对应字段或编辑块，而不是仅跳到所在章节顶部；目标短暂高亮，便于用户确认落点。
- [x] 目标章节已折叠时，系统先展开章节，再执行滚动定位；目标不存在时安全回退到对应章节，不抛出页面错误。
- [x] “光盘编号”待核对项定位到页面上方归档/盘号区域的“首个光盘编号”输入，不再定位到底部附件章节。
- [x] 拖拽与定位支持鼠标和 Pointer 事件；位置重置按钮支持键盘操作，点击待核对项后焦点进入可编辑目标或其最近编辑块。
- [x] 不改变待核对项的派生条件、数量、严重程度、字段保存、归档、Word 导出或后端接口。

### Layer 10：待核对目标模型与派生测试

- [x] 调整 `packages/frontend/src/hooks/useReviewChecklist.ts`，为 `ReviewPendingItem` 增加字段级 `targetId`，给文号、绪论字段、检材/人员、检查字段、结果字段、附件字段和光盘编号建立稳定目标映射；光盘编号映射到顶部盘号输入。
- [x] 更新 `packages/frontend/src/hooks/useReviewChecklist.test.ts`，断言各类清单项使用可区分的字段级目标，特别覆盖光盘编号空值与格式错误均指向顶部盘号锚点。

### Layer 11–12：锚点、折叠展开、拖拽与页面接线

- [x] 调整 `ReviewField.tsx`、`ReviewSection.tsx`、结构化编辑组件及 `ArchiveCompletionPanel.tsx`，为实际字段/编辑块提供稳定 DOM 锚点，并支持定位事件触发展开章节、聚焦和短暂高亮。
- [x] 调整 `ReviewPendingSummary.tsx`、`CaseRecordGeneratePage.tsx` 与 `reviewWorkspace.css`，实现受视口约束的浮层拖拽、会话内位置保持、默认位置重置，以及 `targetId → 精确目标 → 章节回退` 的导航流程。
- [x] 更新 `reviewWorkspaceComponents.test.tsx`、`RecordEditorForm.test.tsx`、`CaseRecordGeneratePage.test.tsx` 及必要的结构化编辑测试，覆盖拖拽边界、重置、折叠章节展开、精确目标、焦点/高亮、缺失目标回退和顶部光盘编号跳转。
- [x] 运行前端定向 Vitest、前端全量测试、生产构建、`npm run verify:quick`、OpenSpec strict、`npm run verify:docs:strict -- --change review-page-modern-government-ui` 与 `git diff --check`；自动化门控通过，人工桌面和缩放复核通过。

### 影响范围

- 影响层级：Layer 10 FE_Hooks、Layer 11 FE_Components、Layer 12 FE_Pages/样式；修改既有前端文件，不新增依赖、共享类型、后端接口、数据模型或持久化格式。
- 交互边界：拖拽只改变待核对浮层在当前页面会话中的显示位置；字段级锚点只服务审核导航，不进入报告、草稿或 Word 数据。

### 第五阶段验证记录

- 架构检查和 TypeScript 类型检查通过；受影响的 6 个测试文件共 53 个用例通过，覆盖字段级目标、顶部盘号锚点、拖拽边界、键盘重置、折叠展开、聚焦高亮与章节回退。
- 前端全量测试、生产构建、`verify:quick` 和仓库资产检查通过；仅保留既有 Ant Design/jsdom 提示和大体积 chunk 警告。
- delta 场景已同步到 living spec；OpenSpec change 严格校验、scoped strict docs 与 `git diff --check` 通过。living spec 全量校验仍报告本阶段之外既有的 REQ-016/REQ-030/REQ-031 结构问题，本阶段未扩大范围修改。
- 用户已在真实界面完成人工验收，确认右侧入口直接拖动、展开/收起位置保持、字段跳转和响应式布局通过。

## 第六阶段：工作台与审核编辑文案层级精简

### 目标与验收标准

- [x] 案件工作台以“案件工作台”作为一级大标题，“电子数据检查笔录”仅作为上方小型模块标识，不再以“电子数据检查案件”作为页面主标题。
- [x] 持久化案件审核编辑页移除标题下方“请核对解析内容；修改会按 revision 自动保存到案件草稿。”说明；非工作台兼容编辑模式的既有保存边界说明保持不变。
- [x] 附件2只显示“一个检材对应两个图片，按照检材顺序对应。”，移除格式、大小、拖拽、正反面和偶数数量的两段旧提示。
- [x] 核实现有图片映射行为：图片引用保存时按审核后的检材顺序每两张生成一个 `photo_groups` 分组，检材变化时会确定性重建映射，导出前继续校验每个检材恰好两张及完整有序归属。
- [x] 定向 Vitest、架构检查、TypeScript 类型检查、`verify:quick`、scoped strict docs 与 `git diff --check` 通过。

### 影响范围与验证

- 展示修改：`packages/frontend/src/components/RecordEditorForm.tsx`、`ImageUploader.tsx`、`packages/frontend/src/pages/CaseWorkbenchPage.tsx`。
- 回归断言：`RecordEditorForm.test.tsx`、`RecordPreview.test.tsx`、`CaseWorkbenchPage.test.tsx`；不修改图片映射、草稿持久化、附件校验、上传格式/大小限制或 Word 导出行为。
- 自动化验证：上述三个前端测试文件、`npm run lint:arch`、`npm run typecheck`、`npm run verify:quick`、`npm run verify:docs:strict -- --change review-page-modern-government-ui` 与 `git diff --check`。
- 人工验收：需在真实界面确认标题视觉层级与精简提示的留白效果；自动化不替代视觉确认。

### 第六阶段验证记录

- 定向 Vitest：3 个测试文件、31 个用例通过；仅输出既有 Ant Design 弃用提示与 jsdom 样式能力提示。
- `verify:quick`：架构、共享/前端类型、治理测试、快速文档检查和仓库资产检查全部通过。
- 当前变更包 scoped strict docs 与 `git diff --check` 通过；人工视觉验收待用户在真实界面确认。

## 第七阶段：附件2按检材分组的双图片卡片

### 目标与验收标准

- [x] 审核编辑页附件2按照审核后的检材顺序渲染检材卡片，每个检材明确展示“图片 1”和“图片 2”两个槽位及检材编号。
- [x] 图片仍以既有扁平有序列表保存，并按每两张对应一个检材；只开放当前下一个空槽，避免中间空槽导致图片归属与实际导出错位。
- [x] 删除图片后，后续图片按既有列表语义前移；超出当前检材容量的图片显示为可删除的待处理图片，没有检材时提示先添加检材且不开放上传。
- [x] 提示语调整为“每个检材对应两张图片，按检材顺序依次对应。”，不新增正反面业务含义。
- [x] 新增组件测试覆盖双槽分组、顺序追加、删除前移、空检材和多余图片；运行定向 Vitest、`verify:quick`、scoped strict docs 与 `git diff --check`。

### 影响范围与验证

- 展示与交互：`packages/frontend/src/components/ImageUploader.tsx`、`ReviewAttachmentsSection.tsx`、`RecordEditorForm.tsx`、`packages/frontend/src/reviewWorkspace.css`。
- 测试：`packages/frontend/src/components/ImageUploader.test.tsx` 及受影响的审核编辑组件测试。
- 不修改共享类型、后端接口、草稿持久化格式、`photo_groups` 生成逻辑、图片格式/大小校验或 Word 导出规则。
- 人工验收：确认桌面与窄屏下检材卡片、双槽图片和待处理图片区域清晰可用。

### 第七阶段验证记录

- 定向 Vitest：3 个测试文件、23 个用例通过；附件组件 7 个用例覆盖双槽、等待槽、顺序追加、删除前移、无检材和待处理图片。
- 前端全量测试通过；附件上传、草稿自动保存、审核编辑和导出相关套件未回归，仅保留既有 Ant Design/jsdom 提示。
- `verify:quick` 通过；delta 场景已按现有 reconciliation 路径同步到 living spec。
- scoped strict docs 与 `git diff --check` 通过。
- 人工视觉验收通过：使用真实 React、Ant Design 与正式 CSS 的合成附件2验收页检查 1280×720、620×900 和 375×812；桌面双检材卡片并排，窄屏卡片上下排列，卡片内双图片槽始终左右对应，均无横向溢出、文字重叠或截断。验收临时页已删除，不进入仓库资产。

## 第八阶段：人工检材确认后的待核对项收敛

- [x] 记录人工验收问题：人工添加检材并确认“手机/平板”后，待核对清单仍按旧空 `device_type` 生成“检材设备类型”提示。
- [x] 根因分类：清单同时检查旧展示字段 `device_type` 和当前用户确认字段 `material_type`，而人工检材只写入后者及其确认来源，形成重复且无法通过当前 UI 消除的提示。
- [x] 修复方式：派生设备类型待核对项时，优先使用已有设备类型/名称/型号；人工确认手机或平板时以该确认值作为有效显示语义，不再保留旧空字段提示；未确认检材和非法来源仍保持导出阻断。
- [x] 脱敏回归 fixture：`useReviewChecklist.test.ts` 使用 SYNTHETIC 人工检材，断言用户确认类型后“设备类型”和“类型”待核对项均消失。
- [x] 最终验证：图片/自动保存协同与待核对相关回归共 7 个测试文件、56 项用例通过；`verify:quick`、当前变更包 scoped strict docs 和 diff 检查通过。独立 Code Review 复审 PASS、无 MUST FIX。2026-08-12 用户人工真实界面复测通过。

## 第九阶段：移除重复顶栏、审核步骤与页面级来源说明

### 目标与验收标准

- [x] 全局 `PlatformShell` 不再显示“笔录自检平台（文枢） / 电子数据检查笔录”等重复顶部横栏；平台侧栏及其导航文案保持不变。
- [x] 审核编辑页不再显示“案件工作台 / 审核编辑 / 导出 Word”三步进度条。
- [x] 审核编辑页不再显示页面级“文号来源”行和“字段来源”说明块；`FieldState` 数据、待人工确认提示及导出门控保持不变。
- [x] 删除失去调用方的来源说明组件及测试，清理对应导入和无效样式，不改变审核表单、自动保存、归档或 Word 导出行为。
- [x] 更新前端回归断言，并运行定向 Vitest、架构检查、TypeScript 类型检查、`verify:quick`、scoped strict docs 与 `git diff --check`。

### 影响范围与验证

- 展示修改：`packages/frontend/src/components/PlatformShell.tsx`、`packages/frontend/src/pages/CaseRecordGeneratePage.tsx`、`packages/frontend/src/platformShell.css`、`packages/frontend/src/reviewWorkspace.css`。
- 测试：`packages/frontend/src/pages/platformShell.test.tsx`、`packages/frontend/src/pages/CaseRecordGeneratePage.test.tsx`；移除不再有组件目标的 `ReviewSourceLegend.test.tsx`。
- 不修改共享类型、后端接口、草稿持久化格式、字段来源模型、待确认规则、归档或 Word 导出合同。

### 第九阶段验证记录

- 架构检查与 TypeScript 类型检查通过；平台外壳 14 项测试通过，审核页套件首轮 17 项中 16 项通过，本次新增的移除断言通过。
- 审核页套件唯一失败为既有并发冲突用例同时发现两条相同 Ant Design 消息；该失败用例独立重跑通过（1 项通过、16 项跳过），未修改业务实现或该既有断言。
- `verify:quick`、scoped strict docs 与 `git diff --check` 通过；delta spec 已同步到 living spec 的 REQ-020、REQ-029。

## 第十阶段：四部分必填进度与待核对导航合并

### 目标与验收标准

- [x] 审核编辑页右侧导航始终展示“文书信息与导出设置 / 一、绪论 / 二、检查 / 附件”四部分，并显示根据当前报告实时派生的必填填写进度；不新增人工确认状态。
- [x] 当前基础空缺字段作为本阶段的必填进度范围；字段为空时对应部分显示“缺少 N 项”，该范围内不存在空值时自动显示绿色“必填已齐”。格式错误和确认阻断继续作为待核对提醒展示，但不冒充空值或单独降低填写进度。
- [x] 点击四部分标题时展开并定位到对应章节；点击具体缺失或格式提醒时继续精确定位、聚焦和短暂高亮字段。内部归档盘号目标在进度上归入“附件”，字段点击仍定位页面上方首个光盘编号。
- [x] 完整侧栏继续只利用宽屏右侧空白且不压缩主表单；空间不足时收敛为可拖动的“进度 N/4”入口，展开后同时展示四部分状态与待核对详情。
- [x] 进度完全由当前 `InspectionReport` 和待核对派生结果计算，不写入案件草稿、浏览器持久化或服务端，不增加 PATCH、revision 或导出门控。

### Layer 10：派生模型与导航

- [x] 为 `ReviewPendingItem` 区分“必填空缺”和“校验提醒”，建立四部分固定顺序及“附件包含归档盘号”的映射；补充空缺、格式提醒和四部分归并测试。
- [x] 扩展审核定位 Hook，使章节级点击与现有字段级点击复用同一展开、滚动、聚焦和高亮流程，并补充章节定位测试。

### Layer 11–12：统一侧栏与页面接线

- [x] 将 `ReviewPendingSummary` 升级为四部分必填进度与待核对项统一导航，接入章节级定位；更新章节标题计数、右侧响应式样式及页面接线。
- [x] 更新组件、Hook 和页面定向测试，覆盖 0～4 部分进度、必填与格式提醒分离、始终可见、章节跳转、字段精确跳转、附件盘号归并和窄屏拖拽回归。

### 验证与边界

- [x] 运行受影响前端定向 Vitest、架构检查、TypeScript 类型检查、`npm run verify:quick`、当前变更包 scoped strict docs 与 `git diff --check`；核对 delta 后同步 living spec。
- 影响层级：Layer 10 FE_Hooks、Layer 11 FE_Components、Layer 12 FE_Pages/样式；不修改共享类型、后端接口、数据库、草稿持久化格式、自动保存或 Word 导出合同。
- 人工验收：检查宽屏固定侧栏、缩放/窄屏悬浮入口、四部分绿色状态和待核对详情的视觉密度；自动化覆盖行为与响应式标记，不能替代真实布局确认。

### 第十阶段验证记录

- 定向 Vitest：4 个文件、44 项用例通过；覆盖 0/4 与 4/4 边界、必填/校验分类、四部分及附件盘号归并、章节/字段导航、拖拽和页面接线。前端全量 Vitest 通过，仅保留既有 Ant Design 弃用和 jsdom 样式能力提示。
- 架构检查、共享/前端 TypeScript 类型检查、生产构建和 `verify:quick` 通过；仓库资产检查通过，未新增测试或生成资产。
- delta 已与实现核对并同步到 living spec 的 REQ-029；scoped strict docs 与 `git diff --check` 通过。
- 人工视觉验收通过：使用完全合成数据和正式 React/Ant Design/CSS 检查 1920×900、1280×800、620×900；宽屏侧栏位于主表单右侧且不压缩表单，普通/窄屏入口和展开面板无横向溢出，四部分状态、绿色完成态与校验提醒清晰。临时验收页已删除，不进入仓库资产。

## 第十一阶段：薄荷晴窗 Sidebar 与首页视觉样板

### 目标与验收标准

- [x] 以暖白和中性色为主体，为 `PlatformSidebar` 与平台首页建立“薄荷晴窗”候选视觉样板；深青绿仅用于 CTA、Active 与 Focus，杏橙仅用于少量首页图标点睛。
- [x] 候选 Token 只维护在集中样式文件中，TSX 只负责样板 scope、组件主题模式与视觉 tone 消费；全局 Ant Design `colorPrimary` 保持现值。
- [x] 侧栏改为浅色菜单，一级与二级导航不再出现深蓝或黑蓝实色背景；现有父子路由、高亮、折叠、鼠标与键盘展开行为保持不变。
- [x] 首页继续展示原六类业务名称，且只有电子数据检查笔录可进入；五类未开放功能只显示一次“即将开放”，不新增未经确认的产品能力文案。
- [x] 候选 Token 不影响案件工作台、上传报告目录、审核编辑页、设备管理、人员管理和模板管理正文；`CaseWorkbenchDirectoryPickerCard` 本阶段不修改，但不构成后续视觉冻结，其既有 Windows 目录选择与解析链路必须继续保留。

### Layer 11–12：前端组件、页面样板与测试

- [x] 调整 `packages/frontend/src/components/PlatformSidebar.tsx`、`packages/frontend/src/pages/HomePage.tsx` 与 `packages/frontend/src/platformShell.css`，实现浅色侧栏、暖白首页画布、柔和图标容器、紧凑功能卡和局部 CTA/Focus 样式。
- [x] 更新 `packages/frontend/src/pages/platformShell.test.tsx`，覆盖浅色菜单、六类功能、单一可进入入口、五个“即将开放”状态及既有导航行为。
- [x] 运行定向 Vitest、架构检查、TypeScript 类型检查与 `git diff --check`；检查全局 `colorPrimary` 未改变，并核对样板 Token 只被 Sidebar 与首页选择器消费。

### 影响范围

- 影响层级：Layer 11 FE_Components、Layer 12 FE_Pages/样式；不修改路由、共享类型、后端接口、数据模型、持久化、上传解析或 Word 导出合同。
- 本阶段只冻结 Sidebar 与首页视觉候选供人工验收，不启动工作台、审核页或管理页的全站迁移。

### 第十一阶段验证记录

- 平台外壳定向 Vitest：1 个文件、14 项用例通过；覆盖浅色菜单、六类功能名称、单一工作台入口、五个“即将开放”状态、侧栏折叠及既有导航行为，仅保留既有 Ant Design/React Router 测试提示。
- 架构检查与共享/前端 TypeScript 类型检查通过；`git diff --check` 通过。
- 真实浏览器计算样式核验：Sidebar 与首页未发现 Ant Design 默认蓝、旧政务主蓝、旧深蓝侧栏或黑蓝子菜单颜色泄漏；展开子菜单保持透明背景。
- 候选 Token 仅在 `platformShell.css` 的 `.platform-shell` 作用域维护并由 Sidebar/首页选择器消费；全局 `colorPrimary` 与既有 `--review-primary` 未修改。案件工作台正文未消费候选 Token，上传报告目录卡片及其选择、解析链路保持原实现。
- 当前仅形成 Sidebar 与首页视觉候选，等待人工视觉验收；不继续进行工作台、审核页或管理页迁移。

## 第十二阶段：首页自适应核心区与紧凑能力区

### 目标与验收标准

- [x] 首页模块以 `available | comingSoon` 状态作为单一分组依据，不按模块名称或固定位置决定视觉层级。
- [x] `available` 模块进入“核心功能”区域：1 个时使用低高度横向工作入口，2 个时两列等宽，3 个时宽容器三列；空间不足时按实际内容容器自动降为两列或单列。
- [x] `comingSoon` 模块进入独立“更多能力”区域，以中性、无操作的紧凑 Tile 展示，不再与核心功能强制等高或重复显示五个大面积状态卡。
- [x] 模块只需改变状态并补齐入口信息即可从“更多能力”自然迁移到核心功能区域，不需要新增模块名称专属布局代码。
- [x] 每个可用核心功能只保留一个整卡 Link，内部进入提示不再使用 Button；未开放能力不渲染 Link 或 Button。
- [x] 保留现有六类业务名称、真实开放状态、候选颜色 Token 与首页文案，不修改 Sidebar、路由、案件工作台及任何业务逻辑。

### Layer 12：首页布局与测试

- [x] 调整 `packages/frontend/src/pages/HomePage.tsx` 与 `packages/frontend/src/platformShell.css`，实现状态分区、1/2/3 核心功能容器响应式布局、紧凑更多能力区及单一链接语义。
- [x] 更新 `packages/frontend/src/pages/platformShell.test.tsx`，覆盖当前 1 个核心功能、合成 2/3 个核心功能、状态迁移、更多能力非交互及链接内不再嵌套按钮。
- [ ] 运行 layout 机械扫描、定向 Vitest、架构检查、TypeScript 类型检查、`verify:quick`、scoped strict docs 与 `git diff --check`，并在真实浏览器中联合检查桌面与窄屏布局。 [DEFERRED]

### 影响范围

- 影响层级：Layer 12 FE_Pages/样式；不修改 Sidebar、共享类型、路由、后端接口、数据模型、持久化、上传解析或 Word 导出合同。
- 当前候选色值保持不变；本阶段只调整信息层级、布局比例、内容密度和 `available / comingSoon` 视觉权重。
- 人工验收：确认 1366×768 首屏层级、1/2/3 核心功能扩展逻辑、更多能力密度，以及单核心状态不产生 Hero 或难看空位。

### 第十二阶段验证记录

- 两份隔离布局评估完成：主观布局评估确认阅读路径、状态分组与容器响应式空间命题；layout 机械扫描实施前后均为 0 项发现。
- 平台外壳定向 Vitest：1 个文件、18 项用例通过；覆盖当前 1 个核心功能、合成 2/3 个核心功能、状态迁移、未来能力非交互和整卡单一 Link。
- 架构检查与共享/前端 TypeScript 类型检查通过；delta 已与实现核对并同步到 living spec 的 REQ-029。
- 真实浏览器联合验收：1280×720 下单核心横向卡约 150px 高、更多能力按三列紧凑 Tile 展示；600×760 下核心区与更多能力区均按内容容器降为单列。两个视口均无横向溢出，可用卡内嵌按钮为 0，未来能力交互元素为 0。
- `git diff --check` 与仓库资产卫生检查通过；`verify:quick` 和 scoped strict docs 仅被任务开始前已存在的 Agent 工具镜像漂移阻断：未跟踪的 `.agents/skills/impeccable`、`.claude/skills/impeccable` 与 `.claude/settings.local.json` 共报告 39 项 `agent-tooling-mirror-drift`。本布局任务不擅自运行 Impeccable doctor 或覆盖用户工具文件，因此门控任务保持 deferred。
- 当前候选颜色 Token 未调整，本阶段未修改 Sidebar、路由、案件工作台或业务逻辑；视觉样板继续等待人工确认。

## 第十三阶段：成果总览首页与鸢尾暖光视觉样板

### 目标与验收标准

- [x] 平台首页从六类功能入口目录调整为成果总览，只展示状态为 `available` 的已开放功能；功能导航继续由 Sidebar 承担，首页成果卡不提供“进入功能”入口。
- [x] 每个已开放功能预留累计成果、近两周变化和更新时间三个统计区域；累计成果为第一视觉焦点，近两周变化为辅助信息。
- [x] 未接入统计数据时显示 `—` 与“数据待接入”，不得显示虚构数字、虚构趋势或把待接入误写为真实 `0`；统计暂不可用时提供独立文字状态。
- [x] 成果模块根据已开放功能数量自然适配 1、2、3 个功能；未开放功能不在首页占用统计卡或“更多能力”区域。
- [x] Sidebar 与首页采用“鸢尾暖光”候选视觉样板：白色 Sidebar、浅灰紫工作底板、白色成果表面、中深鸢尾紫功能锚点与少量杏橙温度强调；不使用满屏渐变、金融图表或科技大屏效果。
- [x] 全局 Ant Design `colorPrimary`、案件工作台、上传报告目录、审核编辑页、管理页和所有业务逻辑保持不变。

### Layer 11–12：导航、首页、样式与测试

- [x] 更新 `packages/frontend/src/components/PlatformSidebar.tsx`，将未开放模块收敛到“更多能力”导航分组，同时保持其禁用和不可进入语义。
- [x] 更新 `packages/frontend/src/pages/HomePage.tsx` 与首页样式，建立可扩展成果数据状态模型、1/2/3 功能布局、诚实占位状态和鸢尾暖光表面层级。
- [x] 更新 `packages/frontend/src/pages/platformShell.test.tsx`，覆盖首页不再重复功能导航、只展示已开放成果、待接入/已接入/暂不可用状态、准确数字格式及 1/2/3 功能适配。
- [x] 运行定向 Vitest、架构检查、TypeScript 类型检查、`verify:quick`、scoped strict docs 与 `git diff --check`；同步 delta 到 living spec，并在 1366×768 与宽屏浏览器中检查视觉层级。

### 影响范围

- 影响层级：Layer 11 FE_Components、Layer 12 FE_Pages/样式；不修改共享类型、后端接口、数据库、持久化、上传解析、案件状态机或 Word 导出合同。
- 本阶段只提供前端成果展示模型和无数据占位，不定义“成功处理”的后端权威口径，不从现有案件列表推测累计成果。
- 人工验收：确认首页与 Sidebar 分工清晰、成果卡具有明确层次、占位不伪造数据，并且候选配色保持现代办公气质而非金融 Dashboard 或营销页面。

### 第十三阶段验证记录

- 平台外壳定向 Vitest：1 个文件、20 项用例通过；覆盖 Sidebar 分组、首页只读成果语义、待接入/已接入/暂不可用状态、数字格式和 1/2/3 功能适配。
- 架构检查、共享/前端 TypeScript 类型检查、前端生产构建与 `git diff --check` 通过；delta 已与实现核对并同步到 living spec 的 REQ-029。生产构建仅保留既有的大 chunk 体积提示。
- 真实浏览器验收：1366×768 下确认白色 Sidebar、浅灰紫画布、鸢尾紫成果摘要与白色统计明细层级；1600×900 下成果卡宽 1120px、高 280px，无页面或主内容横向溢出，首页可交互链接/按钮为 0。
- 工作台隔离核验：进入案件工作台后 `.platform-home` 不存在，正文外壳继续使用既有 `#f5f7fa` 背景；全局 `colorPrimary` 仍为 `#2F6FA3`，上传、解析、案件状态和业务操作未修改。
- `verify:quick` 已运行，架构、类型和治理测试通过，但文档快速检查仍被任务开始前已存在的 39 项 `agent-tooling-mirror-drift` 阻断；漂移来自未跟踪的 Impeccable/本地工具配置，本阶段未覆盖用户工具文件。scoped strict docs 同受该前置漂移影响。
- 本阶段停留在候选视觉样板与前端数据占位，等待人工视觉验收；不继续工作台、审核页或管理页迁移。

## 第十四阶段：折叠 Sidebar 轨道与图标按钮层级

### 目标与验收标准

- [x] 折叠态 Sidebar 使用鸢尾紫外层轨道与白色圆角内板形成明确边界，不再表现为无层级的纯白窄栏。
- [x] 品牌标记、一级导航与展开控制形成独立方形按钮层级；当前导航使用鸢尾紫实色与白色图标，非当前导航使用白色表面、深色图标和轻量阴影。
- [x] `PlatformShell` 首次进入时默认折叠；悬停品牌、一级导航与展开控制显示对应名称，折叠态子菜单点击打开，展开后恢复既有菜单交互。
- [x] 保留首页、电子数据检查笔录与“更多能力”的既有导航、键盘 Focus、当前路由和禁用语义；展开态 Sidebar、首页成果区及业务正文保持不变。

### Layer 11：折叠导航样式与验证

- [x] 调整 `packages/frontend/src/components/PlatformShell.tsx` 的默认状态、`PlatformSidebar.tsx` 的折叠宽度与悬停名称，并在 `platformShell.css` 中仅为 `.ant-layout-sider-collapsed` 建立轨道、控制表面、Active、Hover 与 Focus 样式。
- [x] 运行平台外壳定向 Vitest、架构检查、TypeScript 类型检查与 `git diff --check`，并在真实浏览器中检查折叠态对比度、图标对齐、弹出子菜单和展开恢复行为。

### 影响范围

- 本阶段是既有“鸢尾暖光”候选样板的局部层级修正，不新增业务能力、不改变路由或信息架构，也不修改首页成果数据模型、案件工作台或其他业务页面正文。

### 第十四阶段验证记录

- 平台外壳定向 Vitest：1 个文件、21 项用例通过；新增覆盖默认 80px 折叠宽度、中文图标名称、折叠态点击打开一级功能菜单和主动展开恢复。
- 架构检查与共享/前端 TypeScript 类型检查通过；测试仅保留既有 Ant Design `Menu children`、`findDOMNode` 与 React `act` 提示。
- 真实浏览器验收：1366×768 下 Sidebar 默认折叠，鸢尾紫外轨、白色圆角内板、独立图标表面与当前首页实色 Active 对比清晰；点击“电子数据检查笔录”图标可弹出二级菜单，展开后恢复完整导航文字。
- 浏览器无障碍树中的三个折叠入口均使用中文名称；首页成果内容、案件工作台与其他业务正文未修改。

## 第十五阶段：折叠态首页导航回归修复

### 目标与验收标准

- [x] 用户从案件工作台点击折叠态 Sidebar 的“首页”图标后进入平台首页 `/`。
- [x] 展开态“首页”继续保留真实链接语义，既有父子导航、当前路由高亮和业务页面行为不变。

### Layer 11：导航实现与测试

- [x] 调整 `packages/frontend/src/components/PlatformSidebar.tsx`，让整个首页菜单项在折叠态和展开态均可触发首页导航，并避免展开态文字链接重复冒泡导航。
- [x] 更新 `packages/frontend/src/pages/platformShell.test.tsx`，覆盖从案件工作台点击折叠态首页图标返回 `/` 的回归场景。
- [x] 运行平台外壳定向 Vitest、架构检查、TypeScript 类型检查、`verify:quick`、scoped strict docs 与 `git diff --check`。

### 影响范围

- 影响层级：Layer 11 FE_Components；不修改路由表、共享类型、后端接口、数据模型、持久化或任何案件业务逻辑。
- 人工验收：在真实桌面界面从案件工作台点击折叠态首页图标，确认进入平台首页且侧栏高亮同步更新。

### 第十五阶段验证记录

- 平台外壳定向 Vitest：1 个文件、22 项用例通过；新增覆盖从案件工作台点击折叠态首页图标进入 `/`。
- 架构检查、共享/前端 TypeScript 类型检查与 `git diff --check` 通过；delta 已与实现核对并同步到 living spec 的 REQ-029。
- `verify:quick` 与 scoped strict docs 已运行，本次代码、类型、治理测试和任务状态检查均无新增失败；两项文档门控仍被任务开始前已存在的 39 项 `agent-tooling-mirror-drift` 阻断，来源为用户未跟踪的 Impeccable/本地工具文件，本修复未改动这些文件。
- 人工验收：N/A；该导航行为由 MemoryRouter 交互回归测试可靠覆盖，不涉及只能由真实桌面环境确认的视觉或平台能力。

## 第十六阶段：折叠子菜单提示遮挡修复

### 目标与验收标准

- [x] 折叠态悬停“电子数据检查笔录”仍显示名称提示；打开子菜单后提示立即关闭，不遮挡或拦截“案件工作台”，且二级选项不再重复弹出黑色名称提示。
- [x] “更多能力”采用相同的互斥浮层规则；展开态导航、首页跳转、父子高亮和键盘语义保持不变。

### Layer 11：浮层状态与测试

- [x] 调整 `packages/frontend/src/components/PlatformSidebar.tsx`，统一管理折叠图标 Tooltip 状态，在子菜单打开时清除提示并禁止提示层接管鼠标事件，同时移除已完整显示名称的二级项冗余 `title`。
- [x] 更新 `packages/frontend/src/pages/platformShell.test.tsx`，覆盖悬停名称可见、打开子菜单后提示消失且“案件工作台”可见。
- [x] 运行平台外壳定向 Vitest、架构检查、TypeScript 类型检查、`verify:quick`、scoped strict docs 与 `git diff --check`。

### 影响范围

- 影响层级：Layer 11 FE_Components；不修改路由、业务页面、共享类型、后端接口或数据模型。
- `impeccable harden` 约束：互斥浮层不得同时占据任务选项区域，名称提示不得阻断主操作。

### 第十六阶段验证记录

- 平台外壳定向 Vitest：1 个文件、22 项用例通过；覆盖折叠态名称提示出现、子菜单打开后提示关闭及案件工作台入口保持可见。
- 架构检查、共享/前端 TypeScript 类型检查与 `git diff --check` 通过；delta 已与实现核对并同步到 living spec 的 REQ-029。
- `verify:quick` 与 scoped strict docs 已运行，本次代码、类型、治理测试和任务状态检查无新增失败；两项文档门控仍被任务开始前已存在的 39 项 `agent-tooling-mirror-drift` 阻断，本修复未改动相关用户工具文件。
- 人工验收：N/A；Tooltip 与子菜单互斥及入口可用性已由真实 Ant Design 组件交互测试覆盖。

## 第十七阶段：超宽屏审核进度导航收缩修复

### 目标与验收标准

- [x] 审核编辑页在 3440×1440 等超宽屏分辨率下默认只显示可拖动的“进度 N/4”入口，不再强制展开完整进度导航。
- [x] 用户点击入口后可以展开导航，并可通过“收起进度导航”立即恢复为入口；普通桌面、窄屏及浏览器缩放下保持同一交互语义。
- [x] 超宽屏仍利用主表单右侧空白定位入口，不压缩主表单、不改变必填进度和待核对项的派生、定位、保存或导出行为。

### Layer 11：响应式样式与回归验证

- [x] 调整 `packages/frontend/src/reviewWorkspace.css`，让超宽屏媒体查询只负责横向定位，不再覆盖组件的展开状态或隐藏展开、收起控件。
- [x] 运行审核工作台定向 Vitest、Impeccable 静态检查、前端类型检查、`verify:quick`、scoped strict docs 与 `git diff --check`。

### 影响范围

- 影响层级：Layer 11 FE_Components 样式；不修改组件状态模型、共享类型、后端接口、持久化、上传解析或 Word 导出合同。
- 人工验收：在 3440×1440 部署电脑上确认首次进入默认收起、展开后可收起，且浮层不遮挡主要编辑区域。

### 第十七阶段验证记录

- 审核工作台定向 Vitest：1 个文件、11 项用例通过；既有交互回归覆盖默认收起、点击展开、点击条目或“收起进度导航”后恢复收起。
- Impeccable 静态检查完成；仅报告本次修改前已存在且不在改动区域的侧边强调线与宽度动画警告。
- 架构检查、共享/前端 TypeScript 类型检查、治理测试、文档快速检查、仓库资产检查和 `verify:quick` 通过；delta 已同步到 living spec。
- 人工验收待部署电脑复测：3440×1440 属于真实桌面布局验证，自动化交互测试不能替代最终视觉确认。

## 第十八阶段：部署环境中文图片文件名预览修复

### 目标与验收标准

- [x] 用户上传文件名含中文的合法 JPG/JPEG/PNG 后，审核编辑页能够读取并显示图片缩略图，不再出现裂图。
- [x] 图片读取响应保持原有二进制内容和媒体类型，并使用符合 HTTP 响应头编码约束的 UTF-8 文件名参数；英文文件名和既有 opaque 资产接口保持兼容。
- [x] 不改变图片持久化、租约、revision、检材映射、容量限制或 Word 导出合同。

### Layer 22：资源响应头与回归测试

- [x] 调整 `packages/backend/app/controllers/case_asset_controller.py`，避免把非 Latin-1 文件名直接写入 `Content-Disposition`。
- [x] 更新 `tests/test_workbench_case_assets.py`，以明确标记的 SYNTHETIC 中文文件名覆盖资源上传后读取、二进制内容和响应头编码。
- [x] 运行图片资产定向 Pytest、`verify:quick`、scoped strict docs 与 `git diff --check`。

### 影响范围

- 影响层级：Layer 22 BE_Controllers；不修改公共 JSON DTO、数据库、资产路径、前端上传组件或 Word 模板。
- 规格归属：本阶段恢复 living spec `REQ-008` 的“预览和管理已上传照片”及“上传成功后持久化并恢复”既有场景，不新增或修改正式 Requirement/Scenario。
- 人工验收：在部署 EXE 中上传中文文件名图片，确认上传完成和重新进入案件后缩略图均可见。

### 第十八阶段验证记录

- 失败用例先复现：含 SYNTHETIC 中文文件名的图片读取接口在修复前返回 422；采用 UTF-8 扩展文件名参数后返回 200、图片二进制保持一致且响应头可按 Latin-1 安全传输。
- 图片资产定向 Pytest：`tests/test_workbench_case_assets.py` 12 项用例通过；覆盖英文/中文文件名、上传读取、重启恢复、签名/大小限制、损坏/缺失、租约、revision、绑定冲突和导出解析。
- 架构检查、共享/前端 TypeScript 类型检查、治理测试、文档快速检查、仓库资产检查、`verify:quick` 与 `git diff --check` 通过。
- 人工验收待部署 EXE 复测；自动化已覆盖导致裂图的 HTTP 失败链路，但不能替代目标电脑中的真实浏览器显示确认。

## 第十九阶段：附件2图片折叠与紧凑图标入口

### 目标与验收标准

- [x] 附件2提供纯图标的展开/收起入口；完整展示收起后隐藏缩略图、上传槽位和批量导入操作，并按检材逐项显示 `0/2`、`1/2` 或 `2/2`。
- [x] 再次展开后恢复既有双图片槽位、上传、删除和待处理图片操作；切换展示状态不修改图片列表、检材映射、草稿 revision 或 Word 导出结果。
- [x] 展开/收起和批量导入按钮均只显示图标；鼠标悬浮或键盘聚焦时显示动作提示，并提供同义 `aria-label`、键盘焦点和展开状态语义。
- [x] 批量导入的文件选择、格式、数量、排序、容量和错误反馈规则保持不变。

### Layer 11：组件、样式与回归验证

- [x] 修改 `packages/frontend/src/components/ImageUploader.tsx`，实现附件2渐进披露、逐检材完成度摘要以及纯图标操作入口；既有 `ReviewAttachmentsSection.tsx` 接线无需改动。
- [x] 修改 `packages/frontend/src/reviewWorkspace.css`，让完成度摘要和图标按钮在桌面及窄屏下保持清晰对齐，并复用现有审核页颜色、间距和焦点体系。
- [x] 更新 `packages/frontend/src/components/ImageUploader.test.tsx` 及必要的审核编辑组件测试，覆盖展开/收起、`0/2`、`1/2`、`2/2`、恢复完整展示、纯图标可访问名称、Tooltip 和批量导入行为不变。
- [x] 先运行附件组件定向 Vitest，再运行 `npm run lint:arch`、`npm run typecheck`、`npm run verify:quick`、`npm run verify:docs:strict -- --change review-page-modern-government-ui` 与 `git diff --check`。

### 影响范围

- 影响层级：Layer 11 FE_Components 与审核页样式；不修改共享类型、后端接口、图片持久化、`photo_groups` 映射、上传校验或 Word 导出合同。
- 复用既有 `review-page-modern-government-ui` 变更包中“附件2按检材分组的双图片卡片”能力，不创建新的变更包。
- 人工验收：在桌面与窄屏真实界面确认收起摘要可扫描、纯图标含义在悬浮时清楚、键盘焦点可见，展开后图片管理能力完整恢复。

### 第十九阶段验证记录

- 失败用例先复现：旧实现新增的纯图标入口与折叠完成度测试精确失败 2 项，既有 17 项通过；实现后附件组件 19/19 通过，审核编辑关联测试合计 3 files / 37 passed。
- 架构检查与共享/前端 TypeScript 类型检查通过；折叠状态只保存在组件会话内，`onChange` 无副作用断言确认展开/收起不修改图片列表。
- Impeccable 机械检测只报告本次改动前已存在的侧边强调线和宽度动画；真实桌面与 640px 窄屏检查确认纯图标入口、双槽卡片和响应式排列清晰，窄屏首轮发现的图标按钮整行拉伸已修正并复核。
- delta 已与实现核对并同步到 living spec 的 REQ-029；未强制接管被其他页面占用的真实案件，折叠后的三种完成度由合成组件测试覆盖。

## 第二十阶段：检材完整性人工确认门控

### 目标与验收标准

- [x] “（五）检材情况”标题旁在未确认时显示红色“请确认检材是否完整？”按钮；用户点击后按钮消失。
- [x] 未确认完整性时，右侧审核进度将该状态计入“一、绪论”的未完成条件，并以红色而非绿色显示进度；确认后才允许该部分及总进度进入绿色完成状态。
- [x] 确认结果使用既有案件草稿 `FieldState` 持久化；重新进入案件仍保持已确认，增删或修改检材后自动恢复为待确认。
- [x] 按钮提供原生键盘操作、明确的可访问名称和禁用语义，不新增弹窗或只依赖颜色表达状态。

### Layer 10–11：状态、组件、样式与回归验证

- [x] 调整 `packages/frontend/src/hooks/useCaseRecordSession.ts`，通过既有 `field_states` 保存检材列表完整性确认，并在并发自动保存响应后保留更新较新的确认状态。
- [x] 调整 `packages/frontend/src/hooks/useReviewChecklist.ts`、`packages/frontend/src/components/ReviewIntroductionSection.tsx`、`RecordEditorForm.tsx`、`ReviewPendingSummary.tsx` 及页面接线，让确认按钮、待核对项和右侧进度使用同一状态事实源。
- [x] 调整 `packages/frontend/src/reviewWorkspace.css`，复用审核页现有错误色、间距和焦点体系，覆盖桌面及窄屏文本换行。
- [x] 更新既有 Hook、表单和审核进度测试；先运行定向 Vitest，再运行 `npm run lint:arch`、`npm run typecheck`、`npm run verify:quick`、`npm run verify:docs:strict -- --change review-page-modern-government-ui` 与 `git diff --check`。

### 影响范围

- 影响层级：Layer 10 FE_Hooks、Layer 11 FE_Components；复用现有 `FieldState` 和草稿 PATCH 合同，不新增共享类型、后端端点、数据库字段或 Word 导出字段。
- 关联结论：复用未归档 `review-page-modern-government-ui` 的右侧审核进度与待确认状态能力；不归入目标更宽且处于历史收敛阶段的 `audit-edit-enhancement`。
- `impeccable harden` 约束：检材内容变化必须使旧确认失效；提示不只依赖红色，键盘与只读状态保持可用。
- 人工验收：在真实审核编辑页确认红色按钮、右侧进度颜色、点击后的消失与重新进入后的持久化状态。

### 第二十阶段验证记录

- 定向 Vitest：4 个文件、43 项用例通过；覆盖按钮确认/消失、检材修改后确认失效、右侧红色 `3/4` 状态及确认状态在自动保存与图片绑定并发中的重放。
- 前端完整测试：61 个文件、394 项用例通过；输出中的 React `act(...)`、Ant Design 测试桩属性及 JSDOM `getComputedStyle` 提示均为既有告警，不影响退出码。
- 架构检查、共享/前端 TypeScript 类型检查、治理测试、文档快速检查、仓库资产检查与 `verify:quick` 通过；delta 已同步到 living spec 的 REQ-029。
- Impeccable 机械检测仅报告本次修改前已存在的 3px 侧边强调线与宽度过渡；本次新增按钮、红色进度状态、文本换行和焦点样式无新增告警。
- 人工验收待真实案件页面复测；自动化已覆盖状态与样式类切换，但不能替代部署环境中的最终视觉确认。

## 第二十一阶段：修复检材完整性确认在自动保存后回弹

### 回归原因与修复

- [x] 复现并确认：前端点击后已将检材完整性标记为 `confirmed`，但草稿自动保存的后端字段状态整理只保留报告派生字段，删除了该人工控制状态，保存响应覆盖页面状态后按钮重新出现。
- [x] 调整 `FieldProvenanceService`，仅将 `introduction.evidence_list.completeness` 登记为允许持久化的人工控制状态；继续过滤其他未知字段状态，不修改报告、Word、端点或数据库合同。
- [x] 补充字段状态单元测试和案件草稿保存集成断言，覆盖 `confirmed` 经保存整理后仍出现在返回草稿中。
- [x] 运行受影响后端测试、原有检材完整性前端回归、`npm run verify:quick`、scoped strict docs 与 `git diff --check`。

### 第二十一阶段验证记录

- 失败用例先复现保存整理后的 `KeyError`；修复后字段状态与工作台服务测试共 25 项通过，案件草稿保存响应保留 `confirmed`。
- 原有检材完整性、审核进度、表单和图片绑定并发回归共 4 个文件、43 项用例通过。
- `verify:quick` 与当前变更包 scoped strict docs 通过；本次 4 个文件的 scoped `git diff --check` 通过。全仓 diff 检查仅报告本次范围外既有 `AGENTS.md` 文件末尾空行。

## 第二十二阶段：委托日期空态与图片缺失进度提示

### 目标与验收标准

- [x] 新案件委托时间为空时，日期控件附近明确提示“请选择委托日期”，选择日期后提示消失。
- [x] 存在检材且任一双图片槽位未填充时，右侧进度导航的“附件”显示检材照片缺失项和剩余张数；图片补齐后该项消失。
- [x] 图片缺失项点击后定位到附件2图片编辑区域，且继续使用现有扁平图片顺序、持久化和 Word 导出合同。

### 实现与验证

- [x] 调整 `DateTimeField.tsx`、`ReviewIntroductionSection.tsx`、`ReviewAttachmentsSection.tsx` 与样式，提供可访问的日期空态提示和图片区域导航锚点。
- [x] 调整 `useReviewChecklist.ts`，按 `检材数 × 2` 与 `attachments.photo_ids` 的实际数量派生一个聚合图片缺失项，不新增后端字段或导出门控。
- [x] 更新既有日期字段和审核清单测试，运行前端定向测试、`lint:arch`、`typecheck`、`verify:quick`、scoped strict docs 与 Impeccable 检测。

### 影响范围

- 影响 Layer 10–11 前端派生与组件展示；委托时间的新案初始化另由 `manual-entrust-time-default-today` 变更包承载。
- 复用既有进度导航、日期控件、图片顺序和保存事实源；不修改共享类型、后端 API、数据库、图片上传约束或 Word 合同。
- 人工验收：在真实审核页确认日期空态提示以及附件图片 `0/2`、`1/2`、`2/2` 时的进度变化与点击定位。

### 第二十二阶段验证记录

- 前端日期、审核清单、表单与进度组件定向测试 4 files / 48 passed；覆盖空态提示、可访问关联、缺少 3 张的聚合文案、图片补齐清除提示和图片区域锚点。
- 前端全量 408 项中 407 passed；唯一失败为本次范围外 `ArchiveCompletionPanel` 既有介质说明文案断言，相关文件不在本阶段差异内。
- `lint:arch`、`typecheck` 与 `verify:quick` 通过；delta 已同步 living spec，scoped strict docs 14 checks / 0 drift。
- Impeccable 检测仅报告本次修改前已存在的侧边强调线与宽度过渡；日期提示和图片缺失进度无新增机械告警。
