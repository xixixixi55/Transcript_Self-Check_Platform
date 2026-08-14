# 审核编辑页现代政务工作台样板

workflow_level: 2
legacy_migration: true
spec_sync_status: reconciled
spec_sync_evidence: reconciled to openspec/specs/electronic-inspection-record/spec.md REQ-020 and REQ-029, including unified page scrolling, default workbench entry, compact source authorization control, right-side pending navigation, compact case-summary warning, responsive entrust-unit fields, icon-only review actions, and removal of the redundant topbar, review steps, and page-level source explanation; current OpenSpec CLI exposes no standalone sync command

## 目标

在不改变报告解析、字段数据结构、上传、附件处理和 Word 导出行为的前提下，为平台建立现代政务工作台全局外壳，并在电子数据检查笔录流程中保留已验收的审核编辑页样板。

本任务为 Level 2，仅维护本文件；不创建 proposal、spec 或 design，不实现其他五类未开放文书。

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
