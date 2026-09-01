# Tasks: 默认对话式审核外壳

workflow_level: 2

> 目标：案件审核地址默认只展示对话式引导，以当前对话和操作为主舞台，历史处理轨迹置于上方并通过上滑查看；现有完整审核编辑按用户操作切换显示。两种视图共用现有案件会话和全部业务机制；本包只改变前端展示与导航，不创建第二套业务流程。

## 1. 关联结论与边界

- [x] 复用 `review-page-modern-government-ui` 已实现的待核对派生、字段定位、响应式审核布局和可访问交互，但按用户要求以独立包承载默认对话式外壳，不改写该包的既有任务与 delta。
- [x] 复用 `audit-edit-enhancement` 已实现的字段、检查人员、检材、文号、图片和导出控件；默认检查人员信息完整时不重复询问，不修改默认设置或人员快照机制。
- [x] 复用 `background-compression-archive-completion` 已实现的立即/稍后压缩、后台状态、GP/YP 介质映射和统一导出；不修改归档状态机、容量档位、Manifest、CAS 或导出合同。
- [x] 复用 `case-record-retention-and-formal-artifact-protection` 已实现的草稿保存失败/冲突判定、当前输入保留和导出前保存收敛；本包只让引导视图呈现并触发现有恢复能力，不新增保存状态或冲突解决合同。
- [x] 复用 `background-compression-archive-completion` 已冻结的单独 Word 图片容错合同：图片上传/绑定继续受现有离页保护，图片读取超时或失败时明确提示附件2将被省略并允许按现有规则继续；本包不得把该非阻断合同改成新的导出门控。
- [x] 非目标保持：不新增后端 RequiredAction、数据库、共享业务 DTO、持久化对话历史、业务必填规则、确认规则、Export Gate、模板或 Word 生成逻辑；不使用自由聊天文本替代现有结构化控件。

## 2. Layer 10：对话展示投影

- [x] 新增 `packages/frontend/src/hooks/useGuidedReviewCards.ts` 及同目录测试，从现有 `getReviewPendingItems()`、案件 lifecycle、归档完成投影、来源/租约/图片状态派生前端会话级的历史条目、当前操作、待处理项和生成就绪状态；不引入业务有效性判断或持久化状态。
  - 验证：先以 SYNTHETIC/TEST 报告覆盖默认人员完整、文号缺失、检材待确认、归档中、待补介质号、来源失效、只读和生成就绪；断言系统产出的 RAR/MD5 等空值在处理中进入系统轨迹而不成为人工填写卡片，模式切换后派生结果一致。
- [x] 在同一 Hook 或纯展示工具中维护当前页面会话的展示顺序，并定义刷新后的事实重建规则；不得把 UI 历史写入 CaseDraft、FieldState、localStorage、后端或新的 API。
  - 验证：测试覆盖同一会话按顺序追加、刷新重建只保留当前事实摘要、已经失效的中间状态不冒充历史事实，以及输出不包含路径、令牌、revision、Worker、堆栈或完整错误代码。
- [x] 复用 `packages/frontend/src/hooks/useReviewChecklist.ts` 的既有待核对结果和稳定 targetId；仅增加展示分类/过滤适配，禁止在引导 Hook 内复制必填、日期、图片、介质格式或导出规则。
  - 验证：扩展 `useReviewChecklist.test.ts` 或引导 Hook 测试，证明既有清单变化会自动反映到卡片，已由默认设置带入且不在待核对清单中的检查人员不会被机械生成为确认项。

## 3. Layer 11：引导视图、操作卡片与样式

- [x] 新增 `packages/frontend/src/components/GuidedReviewView.tsx`、`GuidedReviewView.test.tsx`，把审核工作区纵向拆为上方历史处理区和下方当前对话区；上方占用剩余高度并独立滚动，下方保持可见并承载当前推荐操作、全部待处理入口和模式切换入口。
  - 验证：组件测试覆盖历史为空/多条/长文本、当前有操作/等待/完成/恢复、动态新增介质事项、只读、错误、查看摘要和自由选择待处理项；断言 DOM 顺序始终历史在前、当前对话在后，且不得断言虚假连续归档百分比。
- [x] 为历史处理区实现尊重用户阅读位置的追加行为：用户位于末端时可跟随新记录，用户正在查看较早记录时不得强制滚回底部；下方当前对话变化不得清空历史区域。
  - 预计文件：`packages/frontend/src/components/GuidedReviewHistory.tsx` 及测试，实际可在不超过文件上限时并入 `GuidedReviewView.tsx`。
  - 验证：组件测试模拟末端跟随、离开末端后保持 scrollTop、返回末端后恢复跟随，以及历史区和当前对话区的可访问区域名称与键盘焦点。
- [x] 新增或抽取小型引导卡片组件，复用现有 `ArchiveDecisionPanel`、`ArchiveCompletionPanel`、结构化文号、检材、图片、来源恢复和导出回调；如果现有完整区块不适合紧凑卡片，只提取共用控件或增加纯展示 variant，不复制 API 调用和业务校验。
  - 预计文件：`packages/frontend/src/components/GuidedReviewCard.tsx`、现有对应组件及其测试，实际以实现阶段最小拆分为准。
  - 验证：交互测试断言每张卡片触发原有 callback，默认检查人员不出现强制选择卡片，查看/展开/收起不触发 `updateReport` 或归档操作。
- [x] 在 `packages/frontend/src/reviewWorkspace.css` 增加引导布局和响应式样式；审核工作区必须为历史区提供可收缩的剩余高度、为下方当前对话提供稳定但不遮挡的空间。第一版角色使用可替换的静态资源或占位组件，支持加载失败回退和 `prefers-reduced-motion`，不得把核心操作建立在图像或动效上。
  - 验证：运行 Impeccable 机械检测，并在常用桌面、3440×1440、浏览器 125%/150% 和窄屏检查历史滚动、底部当前对话、焦点、长文号、长错误文本及系统状态布局；确认当前对话不覆盖历史最后一条记录或平台全局操作。

## 4. Layer 12：审核页面默认模式与现有会话接线

- [x] 调整 `packages/frontend/src/pages/CaseRecordGeneratePage.tsx`，继续只创建一份 `useCaseRecordSession`，默认条件渲染具有“上方历史、下方当前对话”结构的 `GuidedReviewView`；用户点击“完整审核编辑”后才渲染现有完整审核内容，并提供返回引导模式入口。
  - 验证：页面测试断言首次进入和刷新默认为引导视图、历史区位于当前对话区上方、完整编辑器未同时存在于 DOM、切换不创建第二份 session、不重启归档、不重复上传图片、不改变案件 lifecycle。
- [x] 保持现有编辑租约、autosave、图片离页保护、来源风险确认、压缩决定、介质映射、预览和两种导出入口接线；切换视图时不得丢失当前内存编辑或绕过现有保存失败/只读保护。
  - 验证：更新 `packages/frontend/src/pages/CaseRecordGeneratePage.test.tsx`，复用现有保存、冲突、图片绑定、归档和导出测试，新增引导→完整→引导往返后同一字段值与状态不丢失的区分断言。

## 5. 文档、增量门控与人工验收

- [x] 将本包 delta 与实现逐项核对后同步到 `openspec/specs/electronic-inspection-record/spec.md`；不修改归档、数据模型或其他 living spec。
- [x] 运行引导 Hook/组件/页面定向 Vitest、`npm run lint:arch`、`npm run typecheck`、`npm run verify:quick`、`npm run verify:docs:strict -- --change conversational-review-shell` 与 `git diff --check`。
- [x] 人工验收使用 SYNTHETIC/TEST 案件：确认默认仅显示引导、上方历史可独立滚动、下方当前对话持续可见且不遮挡、默认检查人员不被重复询问、完整编辑按需出现、后台归档期间可继续处理、归档完成后出现正确 GP/YP 介质卡片、往返切换无数据丢失、现有导出门控仍生效；不得使用或提交真实案件数据、人员信息、设备编号或生成输出。

## 6. 2026-08-26 流程评审反馈（已重开）

- [x] 6.1 将用户流程图反馈关联到本包并保持 `workflow_level: 2`：流程图描述的獬豸助手与本包属于同一用户结果、同一审核页面和同一核心调用链；`review-page-modern-government-ui` 只提供原有审核布局，`case-record-retention-and-formal-artifact-protection` 与 `background-compression-archive-completion` 分别拥有保存和图片/归档业务合同，因此不新建 change，也不把这些合同迁入本包。
  - 需求结论：助手使用动态操作集，不采用“介质编号→文号→委托时间→案情→检材→图片”的固定题序；压缩时机、后台归档和人工审核可以并行；安全暂存、后台归档和两种导出具有不同终态。
  - 工件：仅更新本包 `tasks.md` 与 `specs/electronic-inspection-record/spec.md`，不创建 proposal/design，不修改应用代码或 living spec。
- [x] 6.2 Layer 10：扩展 `packages/frontend/src/hooks/useGuidedReviewCards.ts` 及测试，把现有 autosave `failed/conflict`、可恢复租约状态和图片上传/绑定/读取异常投影为可执行恢复事项；当前操作已开始编辑时只加入历史与全部待办，不突然抢占当前卡片。
  - 验证：SYNTHETIC/TEST 用例覆盖保存失败、revision conflict、租约 expired/failed、图片绑定失败、图片读取容错提示和恢复后事项自动消失；断言不复制保存、图片或导出业务规则。
  - [x] 6.2a 已完成 autosave `failed/conflict`、租约 `read_only/expired/failed` 与图片异常的会话级投影、警告事实和恢复事实；恢复事项使用稳定 ID，用户正在填写的现有卡片仍保持选中。
- [x] 6.3 Layer 11：调整 `packages/frontend/src/components/GuidedReviewView.tsx`、`GuidedReviewCard.tsx`、相关测试与 `reviewWorkspace.css`，为恢复事项提供现有“重试保存/加载服务端版本/恢复租约/打开图片控件”操作；为待办与摘要开关建立稳定 `aria-controls` 关系，并保证窄屏和浏览器缩放下操作目标、长错误文案及焦点可见。
  - 验证：组件测试覆盖恢复按钮回调、展开控件关系、错误文案、键盘顺序和只读状态；浏览器人工验收覆盖 125%/150%/200% 缩放与窄屏触控，不以颜色、图标或角色表情单独表达状态。
  - [x] 6.3b 已在页面现有特殊内容插槽接通“重试保存/加载服务端版本/重新获取编辑权限/强制接管/返回图片控件”，窄屏 390×844 下四个全局操作目标均为 44px 且无横向溢出。完整缩放矩阵仍待 6.3 收口。
- [x] 6.3a 按界面反馈收敛引导模式布局：移除旧审核页头；历史区保持事实轨迹并明确展示报告自动识别内容，不使用聊天气泡；仅下方当前对话采用带可替换角色占位的紧凑 Chat 布局，并补齐待办与摘要开关的 `aria-controls`。
  - 验证：页面测试区分引导模式与完整编辑模式的页头可见性；组件测试断言历史在上、獬豸助手身份、稳定展开关系和现有结构化控件；Hook 测试覆盖报告识别摘要；运行定向 Vitest、类型检查、Impeccable 布局检测和 `git diff --check`。
- [x] 6.4 Layer 12：调整 `packages/frontend/src/pages/CaseRecordGeneratePage.tsx` 及页面测试，接通既有 autosave retry/load-server-version 与租约恢复能力；guided→full 切换后聚焦目标字段或完整编辑区标题，full→guided 后聚焦当前对话标题/卡片；卸载原按钮时不得留下不可预测焦点。
  - 验证：页面测试覆盖保存失败/冲突后保留输入和恢复、expired/failed 租约可执行恢复、双向模式切换焦点、刷新重建，以及恢复过程不创建第二份 session、不改变 lifecycle。
- [x] 6.5 保持图片与导出合同：图片上传/绑定失败继续显示可恢复事项并保留现有离页保护；单独 Word 等待图片超时或持久化图片读取失败时，页面明确提示附件2将被省略并提供返回图片控件的入口，但继续遵守既有非阻断导出合同；统一导出、归档和介质映射门控不变。
  - 验证：复用并扩展 `packages/frontend/src/pages/CaseRecordGeneratePage.test.tsx`、`useCasePhotoAssets.test.tsx` 和既有导出测试，区分“图片未安全绑定阻止离页”与“单独 Word 图片读取容错提示”，防止静默声称图片已进入 Word。
- [x] 6.6 明确办理终态与并行状态：助手不得把“选择立即压缩”、`archive_queued`、`archiving` 或图片上传请求返回视为办理完成；分别表达“草稿已保存并稍后处理”“后台归档处理中”“单独 Word 已导出”和“统一导出已完成”，后台状态不得阻断用户继续处理其他待办。
  - 验证：引导 Hook/组件/页面测试覆盖 deferred、queued、archiving、archive verified 待 GP/YP、单独 Word 成功和统一导出成功，断言不出现固定题号或虚假统一完成态。
- [x] 6.7 完成反馈实现后重新核对 delta，修正 living spec 中“獙豸”为“獬豸”并同步本次新增场景；运行引导定向测试、`npm run verify:quick`、`npm run verify:docs:strict -- --change conversational-review-shell`、OpenSpec strict validate 与 `git diff --check`。
  - [x] 6.7a 已将本包 delta 智能合并到 living spec；当前 `REQ-GUIDED-REVIEW-SHELL` 的 127 行需求块与 delta 精确一致，living spec 中“獙豸”残留为 0。
- [x] 6.8 使用 SYNTHETIC/TEST 案件重新人工验收恢复与无损切换：保存失败/冲突、租约失效、图片绑定失败、图片读取容错、归档中断、模式切换焦点和三类终态；不得使用或提交真实案件数据、人员信息、设备编号或生成输出。
- [x] 6.9 采用用户提供的獬豸角色作为助手正式形象：提取透明角色切图并生成轻量项目资产，替换当前对话区的盾牌占位；角色图像加载失败时继续回退到既有图标，不改变助手身份文字、状态或操作可用性。
  - 验证：透明 PNG 为 256×256、四角 alpha 为 0且约 66 KB；组件测试覆盖正式角色资源及加载失败回退，TypeScript 与 `git diff --check` 通过；Impeccable 检测仅命中本次差异外已记录的两处旧样式告警。
- [x] 6.10 按界面反馈把獬豸形象从小头像提升为当前对话区主角色：桌面端完整角色栏使用 96–120px 响应式宽度，窄屏保持 64–72px，不增加角色底框，也不改变右侧对话、控件和 DOM/键盘顺序。
  - 验证：组件测试继续覆盖角色资源与加载失败回退；前端类型检查、生产构建、Impeccable 布局检测和 `git diff --check` 通过。
- [x] 6.11 按界面反馈把当前事项改为獬豸逐步提示：文号、日期、确认、上传、恢复、压缩、等待和生成状态均先展示完整可执行提示句，再展示对应现有控件；同一说明只出现一次，仍由动态待办集决定下一项，不新增固定题序或持久化聊天消息。
  - 验证：Hook 测试覆盖“请输入/请选择/请确认”及恢复、等待、压缩、生成提示；组件测试覆盖具名助手消息区和非待办说明去重；同步 delta/living spec 并运行定向测试、类型检查、Impeccable 检测与 scoped strict docs。
- [x] 6.12 按界面反馈把当前事项从局部展示台收敛为逐轮对话：助手提示与用户控件分别使用左右消息块，事项完成后仅在本次页面会话展示不含逐字输入的用户完成回执及助手承接语，其他审核操作退出主对话流；保留现有自动保存、动态事项排序和上方事实历史。
  - 验证：组件失败用例先证明旧实现缺少“你的回复”和上一轮完成回执，实施后 4/4 通过，并覆盖案件切换清空回执；Hook/组件合计 12/12、页面 19/19、`typecheck`、`verify:quick`、生产构建和 `git diff --check` 通过；Impeccable 仅报告本次范围外第 67、214 行两处既存告警。
- [x] 6.13 按视觉反馈提高历史处理轨迹的信息密度：保留上方主浏览区、时间顺序、独立滚动和窄屏顺序，仅压缩标题栏、轨迹条目、图标及空状态的纵向留白，不改变事实内容或交互行为。
  - 验证：复用历史滚动组件测试；运行前端类型检查、生产构建、布局检测、scoped strict docs 与 `git diff --check`，不为纯样式调整机械新增测试。
- [x] 6.14 按视觉反馈校正当前对话的位置关系：用户上一轮回复保持右侧，獬豸形象移动到当前助手消息行并独立位于提示气泡外侧，助手身份、承接语和当前提示与形象对齐；其他操作继续位于主对话流之外。
  - 验证：先以组件失败用例区分旧版整区左栏与新版外置助手消息行，再运行组件测试、类型检查、生产构建、布局检测、scoped strict docs 与 `git diff --check`。
- [x] 6.15 根据截图明确“外置”边界：宽屏下獬豸形象必须位于主内容左边界之外，当前对话正文、滚动条和操作控件留在边界以内；可用外部留白不足时恢复为对话区内的响应式侧栏，避免形象被视口裁切。
  - 验证：组件用例区分形象与对话正文内容层，实际页面核对形象占据正文边界外的独立留白；运行组件测试、类型检查、生产构建、布局检测、scoped strict docs 与 `git diff --check`。
- [x] 6.16 按交互反馈让外置獬豸与当前对话滚动联动：角色与正文进入同一滚动容器，宽屏仍位于主内容边界外；滚动时同步位移并受对话窗口纵向裁切，不覆盖历史区。
  - 验证：组件失败用例区分角色是否属于对话滚动容器；在实际页面滚动当前对话，核对角色与消息的位移量一致，并运行组件测试、类型检查、生产构建、布局检测、scoped strict docs 与 `git diff --check`。
- [x] 6.17 根据“缺少对话灵动感”的反馈重排引导主舞台：当前对话先于历史摘要展示，历史默认收起且可访问展开；事项完成后使用与真实完成结果和下一项相关的承接语，不伪造处理中状态；窄屏取消角色独占列与对话内部裁切，并保持全部结构化控件和非线性入口可用。
  - 验证：先调整组件失败用例，区分当前对话/历史 DOM 顺序、历史默认收起与展开关系、真实完成回执和情境化承接语；运行组件定向测试、前端类型检查、生产构建、Impeccable 检测、桌面与 390px 实际页面检查、`verify:quick`、scoped strict docs、OpenSpec strict validate 与 `git diff --check`。
- [x] 6.18 根据对话视口反馈把完整历史轨迹移到当前对话上方的同一纵向滚动轨道：首次进入、刷新和切换案件时默认锚定完整当前办理舞台，用户向上滚动后才看到历史；新增历史时，停留当前事项的用户继续锚定当前对话，正在阅读历史的用户保持原位置；窄屏与键盘操作沿用同一可访问滚动模型。
  - 验证：先以组件失败用例区分历史/当前对话 DOM 顺序、默认锚点和两种新增历史位置策略；运行组件定向测试、前端页面测试、类型检查、生产构建、Impeccable 检测、桌面与 390px 实际页面检查、`verify:quick`、scoped strict docs、OpenSpec strict validate 与 `git diff --check`。
- [x] 6.19 修复文本事项输入首个字符后自动切换的问题：字段继续实时写入现有报告草稿和自动保存，但当前文本事项仅在用户按下非输入法组合态的 Enter 后推进；多行文本保留 Shift+Enter 换行，日期、确认按钮和其他显式操作沿用既有完成语义。
  - 验证：先以 Hook/组件失败用例区分“输入单字符仍停留”“Enter 后推进”“输入法组合态 Enter 不推进”和“Shift+Enter 不推进”；再运行引导定向测试、类型检查、生产构建、Impeccable 检测、`verify:quick`、scoped strict docs、OpenSpec strict validate 与 `git diff --check`。
- [x] 6.20 根据检材完整性反馈提供图标化双向选择：引导卡片同时显示“完整”和“不完整”两个具名图标操作；选择完整继续复用现有确认回调，选择不完整则留在当前对话窗口内展开既有检材编辑器，使用户通过原有“添加检材”能力手工补充，不复制检材状态、保存或编辑逻辑。
  - 验证：先以组件与页面失败用例区分两个图标、可访问名称、完整确认回调，以及不完整后仍保留当前对话并出现“添加检材”入口；实现后运行引导组件/页面定向测试、类型检查、Impeccable 检测、`verify:quick`、scoped strict docs、OpenSpec strict validate 与 `git diff --check`。
- [x] 6.21 根据步骤导航反馈为獬豸助手补充“返回上一步”：当前结构化事项完成并推进后，在本次页面会话保留上一轮动作快照；用户可返回原控件核对或修改，并可返回最新当前步骤。该导航不得回滚已保存草稿、把已完成项重新计入待处理数、持久化会话轨迹或复制字段校验。
  - 验证：先以 Hook/组件失败用例区分完成后无入口、返回上一轮动作和恢复当前步骤；再运行引导 Hook/组件/页面定向测试、类型检查、`verify:quick`、scoped strict docs、OpenSpec strict validate 与 `git diff --check`。
- [x] 6.21a 修复“全部当前事项”切换后仍缺少返回入口并提高可发现性：从一个结构化事项进入另一个当前事项时同样记录来源步骤，不要求来源项先完成或消失；步骤按钮移动到助手提示与回复控件之间，图片上传等高内容不得把它推到回复区之后。

- [x] 6.22 根据“对话过程僵硬”反馈增加真实的事项切换承接和克制的方向动效：用户主动切换仍待处理事项时，獬豸助手说明当前先处理项和仍保留的来源项；助手消息与回复控件使用相反方向的短暂进入动效，不伪造输入、思考或等待。
  - 验证：以用户截图对应的“多个待办中切换到检材照片”路径补 Hook/组件失败用例，断言仍待处理的来源项可返回、可恢复最新当前项，且按钮在回复控件之前；运行引导定向测试、页面回归、类型检查、Impeccable 检测及 Level 2 门控。
- [x] 6.23 为獬豸助手形象增加克制的生命感：角色可见时以长间隔、低幅度呼吸，当前事项变化时点头一次；页面隐藏、角色离开视口或用户选择减少动态效果时停止非必要运动，不改变布局和业务状态。
  - 验证：先以组件失败用例区分事项变化前后的角色动作身份；实施后运行引导组件定向测试、前端类型检查、Impeccable 检测及 Level 2 门控。
- [x] 6.24 根据检材补录反馈，在“不完整”回复区增加快捷批量添加：明确提示一行一项、手机/平板、一部、中文全角括号和行末检材编号的输入规范；解析后先展示结构化预览，格式错误、批次内或现有编号重复时逐行提示并阻止写入；确认后把全部合法项追加到现有 `introduction.evidence_list`，标记为用户确认类型且无法提取，继续复用既有自动保存、完整性确认和结构化编辑器。
  - 验证：先以组件失败用例覆盖输入规范、三行预览、错误行、重复编号、确认追加及不覆盖既有检材；实施后运行引导组件/页面定向测试、前端类型检查、`verify:quick`、scoped strict docs、OpenSpec strict validate 与 `git diff --check`。
- [x] 6.25 根据快捷补录布局反馈，把“解析并预览”“一键排序”和既有“确认检材完整”操作做成具有 Tooltip 与明确可访问名称的相邻圆形图标，放在输入框下方同一操作组；一键排序复用报告识别的多段数字自然升序规则，可排序当前合法预览或已有检材，无法安全排序时保持原顺序并明确说明，且不得在后续保存中覆盖用户拖拽顺序。
  - 验证：先以组件失败用例覆盖三图标、相邻顺序、无可见重复文字、`JC1/JC2/JC10` 自然排序、排序后确认追加、已有检材排序、不可识别编号保持顺序和窄屏换行；实施后运行引导组件/页面定向测试、前端类型检查、Impeccable 单次检测及 Level 2 门控。
- [x] 6.26 根据工作台视觉与文案密度反馈收敛快捷补录区域：移除常驻大面积信息 Alert，把输入规范压缩为单行并由输入框示例承接具体写法；回复区改用案件工作台的白色表面、靛蓝强调、柔和阴影及统一控件状态，解析、排序和确认图标的既有顺序、语义与业务逻辑保持不变。
  - 验证：复用既有引导组件与页面测试核对规范文本和三图标合同；运行前端类型检查、Impeccable 单次检测，并在实际页面检查桌面与 390px 视口的文案行数、按钮排列和横向溢出。
- [x] 6.27 修复解析预览后的“确认添加 N 项检材”仍使用 Ant 默认蓝色的问题：结果区主操作增加确认图标，并统一使用案件工作台的靛蓝主色、圆角、柔和阴影、悬停与键盘焦点样式；动态数量文字和确认追加逻辑保持不变。
  - 验证：复用批量预览组件用例断言结果按钮的专用样式身份、确认图标和原确认写入行为；运行定向测试、前端类型检查、Impeccable 单次检测与差异检查。
- [x] 6.28 根据结果反馈层级建议，把解析成功、排序成功和确认添加成功从表单内绿色 Alert 改为屏幕正上方的全局短时成功提示，并使用稳定 key 避免连续操作堆叠；格式错误、重复编号和无法安全排序等需用户处理的信息继续保留在输入区内。
  - 验证：组件用例断言解析成功信息进入全局 message 容器且快捷补录区内不再存在成功 Alert，同时保留排序、确认写入与错误阻断回归；运行定向测试、前端类型检查、Impeccable 单次检测及差异检查。
- [x] 6.29 根据检材完整性初始回复截图统一“完整 / 不完整”按钮：两枚圆形图标收敛为 44px 与 8px 间距，完整操作使用工作台靛蓝主按钮，不完整操作使用中性次按钮，并统一阴影、悬停、禁用和键盘焦点状态；既有 Tooltip、可访问名称和回调保持不变。
  - 验证：复用检材完整性组件用例核对两枚图标、可访问名称与完整确认/不完整展开行为；运行定向测试、前端类型检查、Impeccable 单次检测与差异检查。
- [x] 6.30 根据底部操作截图把“完整审核编辑”圆形主按钮从 Ant 默认蓝色统一为案件工作台靛蓝，并补齐同体系的悬停、阴影与键盘焦点状态；其余三枚工具按钮继续保持中性次按钮外观，图标、Tooltip、可访问名称与回调不变。
  - 验证：组件用例断言完整审核按钮保留主按钮语义、编辑图标与专用样式身份；运行定向测试、前端类型检查、Impeccable 单次检测、严格文档检查及差异检查。
- [x] 6.31 修复底部信息面板与检材轨迹反馈：用户点击“查看全部当前事项”或“查看已整理信息”后，展开面板必须立即进入同一滚动视口的可见范围并获得可预测焦点，无需继续向下滚动；用户在报告识别检材基础上补充检材后，历史轨迹更新为最终已处理总数，并简要区分报告识别数与用户补充数，不记录逐字输入。
  - 验证：先补组件失败用例断言两类面板展开后的滚动与焦点；补 Hook 失败用例覆盖报告识别 2 项、用户补充 3 项后轨迹更新为已处理 5 项；实施后运行引导组件/Hook 定向测试、前端类型检查、Impeccable 单次检测、`verify:quick`、scoped strict docs、OpenSpec strict validate 与 `git diff --check`。
- [x] 6.32 按用户选择把獬豸助手升级为“更明显的角色型”对话体验：当前页面会话保留最近三轮不含逐字敏感输入的用户完成摘要与助手因果承接，并允许从对应轮次返回既有结构化控件修改；角色使用同一形象的倾听、核对、严肃提醒和完成四态表情及一次性语义动作，错误/冲突不使用欢快反馈，减少动态效果、离屏和页面隐藏时继续降级；检材补录等复杂事项先选择快捷批量或逐项编辑后再展开对应控件；当前回复保持唯一主操作，全局事项、整理信息、完整编辑和返回工作台继续采用既有圆形图标工具栏。
  - 验证：先补组件/页面失败用例覆盖三轮会话、轮次修改、四态角色身份、错误状态克制动作、检材补录分步和工具层级；使用 SYNTHETIC/TEST 数据，不回显逐字输入；实施后运行引导组件/Hook/页面定向测试、前端类型检查与生产构建，执行 Impeccable 单次检测、`verify:quick`、scoped strict docs、OpenSpec strict validate、`git diff --check`，并在安全可用的合成页面检查桌面与窄屏；无合成实页时记录 N/A，不读取真实案件替代。
- [x] 6.33 根据用户截图反馈恢复底部四枚圆形图标工具按钮：全部事项保留数量角标，已整理信息、完整审核编辑和返回工作台恢复直接图标入口，继续提供 Tooltip、可访问名称、主次颜色、面板自动滚动与焦点；移除常驻文字和“更多操作”菜单。同时清除四态獬豸精灵图中的浅色底板与背景雾，保留真实透明通道、角色四态和现有裁切位置。
  - 验证：先以组件失败用例区分文字按钮与圆形图标工具栏；实施后运行引导组件/页面定向回归、类型检查、生产构建、Impeccable 单次检测、资产卫生、scoped strict docs、OpenSpec strict validate 与 `git diff --check`。
- [x] 6.34 根据透明角色截图继续修正视觉融合：将当前对话容器由浅蓝灰表面改为页面一致的纯白背景并移除浅蓝边框，保留角色阴影、圆角、布局、滚动和全部交互行为。
  - 验证：核对截图颜色来源与 PNG Alpha，运行前端类型检查、生产构建、scoped strict docs 与 `git diff --check`；纯样式反馈不机械新增行为测试。
- [x] 6.35 根据纯白容器仍呈现方形画布的反馈，将当前对话舞台进一步改为透明表面，直接继承页面底色；不再铺设任何角色背景色或边框，保留内容气泡、角色投影、布局和交互。
  - 验证：核对透明 PNG 与父级表面叠加关系，运行前端类型检查、生产构建、scoped strict docs 与 `git diff --check`；纯样式反馈不机械新增行为测试。
- [x] 6.36 根据用户明确反馈移除獬豸角色的全部 CSS 投影：删除静态 `drop-shadow` 及呼吸动画中的阴影变化，只保留角色本身、透明背景和原有轻微位移缩放。
  - 验证：搜索确认角色样式不再含 `drop-shadow`，运行前端类型检查、生产构建、scoped strict docs 与 `git diff --check`；纯样式反馈不机械新增行为测试。
- [x] 6.37 根据用户给出的工具栏参考图统一獬豸助手完整按钮体系：直接回复、检材补充、模式切换、解析结果确认、新增/删除检材、历史修改、步骤返回与兜底编辑入口均使用 44px 圆形图标按钮，主操作为靛蓝实心、次操作为白底描边、删除操作保留红色危险语义，文字移入 Tooltip 与可访问名称；待办事项面板继续保留整行列表导航，原操作语义、禁用状态和回调保持不变。
- [x] 6.38 修正獬豸助手的正常办理顺序并补齐检材确认上下文：恢复类异常继续优先；无异常时先选择压缩时机，再填写介质编号，随后才按现有动态待办处理文号、委托时间等事项。检材完整性确认卡在用户选择“完整/不完整”前直接展示当前全部检材的编号、设备、类型与可提取情况；未识别到检材时明确显示空态，不要求先进入补录模式。
  - 文件：`packages/frontend/src/hooks/useGuidedReviewCards.ts`、`packages/frontend/src/hooks/useGuidedReviewCards.test.ts`、`packages/frontend/src/components/GuidedReviewCard.tsx`、`packages/frontend/src/components/GuidedReviewView.test.tsx`、`packages/frontend/src/reviewWorkspace.css`、本包 delta 与 living spec。
  - 验证：定向 Vitest 区分“压缩时机→介质编号→文号”的正常顺序、恢复事项优先级和选择稍后后的继续办理；组件测试断言未点击“不完整”时已可见全部 SYNTHETIC/TEST 检材及空态；运行 `npm run verify:quick`、scoped strict docs、OpenSpec strict validate、Impeccable 单次检测与 `git diff --check`。
  - 验证：复用组件用例断言各类直接操作均为无常驻文字的圆形图标按钮并保留主次语义，运行定向测试、前端类型检查、生产构建、scoped strict docs 与 `git diff --check`。
- [x] 6.39 补齐獬豸助手的案件简要情况用户输入：即使报告已经解析出案件简要情况，也在本次页面会话中提供预填的多行输入框供人工核对和修改；输入继续复用现有报告草稿与自动保存，确认后本次会话不重复询问，清空后仍按既有必填规则重新出现。
  - 文件：`packages/frontend/src/hooks/useGuidedReviewCards.ts`、`packages/frontend/src/pages/CaseRecordGeneratePage.tsx`、`packages/frontend/src/components/GuidedReviewCard.tsx`、对应前端测试、本包 delta 与 living spec。
  - 验证：定向 Vitest 区分“解析值仍展示输入框”“确认后会话内不重复询问”“修改写入 `introduction.case_summary`”；运行 `npm run verify:quick`、受影响前端测试、scoped strict docs 与 `git diff --check`。

## 当前状态

- `implementation_status: complete`：6.43 引导分栏铺满主工作区并调整为严格等宽，已实施并完成验证。
- `feedback_scope_status: complete`：铺满宽度、等宽分栏、响应式布局及交换顺序均已核对。
- `spec_sync_status: synced`：铺满与等宽分栏最终行为已核对并同步到 living spec。

## 2026-08-31 案件简要情况输入补齐证据

- `case_summary_input_contract: PASS`：报告已有解析值时，獬豸助手仍生成一次“请确认案件简要情况”操作，并使用现有 `Input.TextArea` 预填当前值；修改继续调用 `updateReport('introduction.case_summary', value)`，沿用既有草稿自动保存。
- `case_summary_session_flow: PASS`：用户确认后，本次页面会话立即推进到下一动态事项且不重复询问；案件切换或重新进入会重新要求人工核对，确认后若字段被清空，既有必填缺失项仍会重新出现。
- `case_summary_verification: PASS`：相关 Hook/组件/页面 Vitest 共 48 个用例通过；`npm run typecheck`、`npm run verify:quick` 通过。测试拆分遵循组件职责，`GuidedReviewView.test.tsx` 回到 600 行以内。

## 2026-08-30 快捷补录视觉收敛证据

- `quick_evidence_visual_hierarchy: PASS`：常驻蓝灰信息 Alert 已移除，回复区只保留一层白色工作表面；标题图标、输入框和三枚操作图标统一复用案件工作台的靛蓝、浅色表面、圆角与柔和阴影语言，错误和成功 Alert 仍仅在对应反馈状态出现。
- `quick_evidence_copy_density: PASS`：规范收敛为“每行一项：设备名称＋手机/平板一部＋（原因）＋编号；全角括号，编号置于行末。”，具体双行示例继续由输入框占位内容提供；实际桌面页面测得说明为 1 行且无溢出。
- `quick_evidence_visual_acceptance: PASS`：实际案件页在默认桌面视口与 390×844 视口检查通过；窄屏无页面横向溢出，解析、排序和确认三个 44px 图标保持同一行，视口覆盖已在检查后恢复。
- `quick_evidence_result_action: PASS`：解析结果的确认添加按钮具有专用样式身份、确认图标与明确可访问名称，使用工作台靛蓝主色、10px 圆角、柔和阴影及独立焦点环，不再落回 Ant 默认蓝色。
- `quick_evidence_global_success: PASS`：解析、排序和确认添加成功均进入顶部全局 message 容器并以稳定 key 更新，快捷补录内容区不再渲染成功 Alert；警告和错误仍留在输入上下文内。
- `evidence_completeness_choice_style: PASS`：“完整 / 不完整”两枚回复图标统一为 44px 与 8px 间距，分别使用工作台靛蓝主按钮和中性次按钮状态；既有 Tooltip、可访问名称、确认回调与展开补录行为由组件 10/10 回归覆盖。
- `guided_review_full_editor_button_style: PASS`：底部“完整审核编辑”圆形主按钮具有独立样式身份并改用工作台靛蓝，包含同体系的悬停、柔和阴影和键盘焦点状态；其余三枚工具按钮及所有交互合同保持不变。
- `quick_evidence_regression: PASS`：前端类型检查通过；`GuidedReviewView.test.tsx` 10/10 与 `CaseRecordGeneratePage.test.tsx` 20/20 通过，保留既有 jsdom `getComputedStyle` 与 React `act` 警告；Impeccable 对本轮目标文件的检测仅报告 `reviewWorkspace.css` 第 167、314 行本次差异外的既有侧边强调线与宽度过渡，本次区域无发现；`verify:quick`、scoped strict docs 与 `git diff --check` 均通过。

## 2026-08-30 面板可见性与检材轨迹总数证据

- `guided_panel_visibility: PASS`：“查看全部当前事项”和“查看已整理信息”展开后均聚焦对应具名区域，并通过最近边界滚动立即带入同一纵向视口；未新增弹窗、嵌套滚动或业务副作用。
- `evidence_history_total: PASS`：检材事实摘要显示当前最终已处理总数；报告识别 2 项后用户补充 3 项时更新为“当前已处理 5 项检材，其中报告识别 2 项、用户补充 3 项”，不记录逐字检材内容。
- `guided_feedback_targeted_tests: PASS`：先得到面板焦点缺失与历史摘要数量缺失的 2 个失败用例，实施后 `GuidedReviewView.test.tsx` 10/10、`useGuidedReviewCards.test.ts` 12/12 通过。
- `guided_feedback_quality: PASS`：`npm run verify:quick`、OpenSpec change strict validate、Impeccable 单次检测（0 项）与 `git diff --check` 通过；scoped strict docs 在任务勾选前仅准确报告 6.31 未完成，勾选后复跑确认。
- `guided_feedback_manual_acceptance: N/A`：面板滚动调用、焦点归属、两类入口和 2+3 检材动态更新均由可区分的组件/Hook 自动化回归覆盖，本次不新增视觉样式或需真实案件数据的环境行为。

## 2026-08-30 快捷排序与图标操作组证据

- `quick_evidence_sort_contract: PASS`：输入框下方依次相邻展示文件检索、自然升序和确认完整三个圆形图标，均具有 Tooltip 与明确可访问名称且无重复可见文字；操作组可自然换行，单个目标不小于 44px。
- `quick_evidence_sort_behavior: PASS`：用户显式点击后按报告识别相同的安全多段数字键自然升序排序当前预览或已有检材；`JC1/JC2/JC10` 顺序正确，无法提取数字或数字键冲突时保持原顺序并提示；普通保存和后续拖拽合同不变。
- `quick_evidence_sort_tests: PASS`：`GuidedReviewView.test.tsx` 10/10 与 `CaseRecordGeneratePage.test.tsx` 20/20 通过；覆盖三图标身份、同组顺序、排序后追加、已有检材排序、不可安全排序和页面集成。页面套件仅保留既有 jsdom 样式计算与 React `act` 警告。
- `quick_evidence_sort_quality: PASS`：前端/共享类型检查、Impeccable layout 单次检测（0 项）、`verify:quick`、OpenSpec strict validate 与 `git diff --check` 均通过。
- `quick_evidence_sort_manual_acceptance: N/A`：用户截图用于明确操作位置；本次布局使用既有圆形图标、Tooltip 与 flex-wrap，视觉/焦点顺序、图标身份、触控尺寸和窄屏换行均由组件 DOM、响应式 CSS 与机械检测覆盖。

## 2026-08-30 快捷批量添加检材证据

- `quick_evidence_contract: PASS`：不完整分支明确展示一行一项、手机/平板、一部、中文全角括号和行末编号规范；合法输入先预览再追加，空行忽略，格式错误、批次内重复及与现有编号重复均整批阻止且保留原输入；编号比较忽略首尾空格和英文大小写。
- `quick_evidence_targeted_tests: PASS`：`GuidedReviewView.test.tsx` 8/8 与 `CaseRecordGeneratePage.test.tsx` 20/20 通过；覆盖三项预览、结构化字段、保留现有检材、重复编号、格式错误、输入说明和引导页集成。页面测试只保留既有 jsdom 样式计算与 React `act` 警告。
- `quick_evidence_quality: PASS_WITH_EXISTING_FINDINGS`：前端/共享类型检查与 `verify:quick` 通过；Impeccable 单次检测仅报告 `reviewWorkspace.css` 第 167、314 行本次差异外的既有侧边强调线和 `width` 过渡告警，本次新增区域无发现。
- `quick_evidence_manual_acceptance: N/A`：本次复用既有 Ant 输入、提示、按钮和检材编辑器，只新增紧凑纵向区块；结构层级、窄屏按钮宽度、长文本换行和可访问关联由组件/页面 DOM、响应式 CSS、类型检查及机械检测覆盖。

## 首轮基线证据

- `baseline_targeted_tests: PASS`：引导 Hook/组件/页面共 23 个 SYNTHETIC/TEST 用例通过；页面回归覆盖租约、autosave、图片绑定、归档、GP/YP、单独 Word 和统一导出。
- `baseline_level2_gates: PASS`：`lint:arch`、`typecheck`、`verify:quick`、scoped strict docs、OpenSpec strict validate 与 `git diff --check` 全部通过。
- `baseline_manual_acceptance: PASS`：使用临时 SYNTHETIC/TEST 页面执行桌面、125%、150%、窄屏布局及滚动验收；页级几何显示外层不滚动、历史独立滚动、对话不重叠。独立 Impeccable 完成度复核结论为 `ship`；3440 像素级截图因工具将文件硬裁为 1600×900，以 3440 DOM 几何无溢出证据代替。

## 2026-08-27 界面收敛证据

- `ui_convergence_targeted_tests: PASS`：引导 Hook/组件 6 个用例和审核页面 17 个用例通过；覆盖报告识别事实、历史/对话顺序、助手身份、稳定展开关系、引导模式页头移除及完整编辑模式页头恢复。
- `ui_convergence_gates: PASS`：`npm run verify:quick`、TypeScript、Impeccable layout detector 和 `git diff --check` 通过；scoped strict docs 仍因 6.2–6.8 的 7 个反馈任务未完成而按预期保持失败。
- `ui_convergence_browser_check: PASS`：本地现有案件只读验收显示桌面历史区 445px、当前对话区 219px、旧页头数量为 0；390×844 窄屏无横向溢出，四个对话操作目标均为 44px，历史仍为主要区域且当前对话复杂内容可独立滚动。

## 2026-08-27 保存、租约与焦点恢复证据

- `recovery_targeted_tests: PASS`：`useGuidedReviewCards.test.ts` 4 个用例与 `CaseRecordGeneratePage.test.tsx` 19 个用例全部通过；新增覆盖保存失败、revision conflict、重试保存、加载服务端版本、租约获取失败、只读强制接管、恢复事项消失、当前卡片稳定和双向模式切换焦点。
- `recovery_typecheck: PASS`：`npm run typecheck` 通过；本次只复用既有 autosave、租约和页面会话接口，没有新增后端、共享 DTO 或持久化合同。
- `recovery_browser_check: PASS`：使用临时 SYNTHETIC/TEST 报告验收；1280×720 下历史区约 434px、当前对话区约 230px、旧页头数量为 0且无横向溢出；guided→full 后焦点为 `#review-editor-title`，full→guided 后焦点为 `#guided-review-conversation-title`；390×844 下无横向溢出，四个全局操作目标均为 44px。
- `recovery_impeccable_detector: PASS_WITH_EXISTING_FINDINGS`：对本次 UI 目标运行机械检测，命中 `reviewWorkspace.css` 中既有待办卡片左侧色边与既有进度条 `width` 过渡两项告警；两行均不在本次差异中，未扩大变更范围。
- `recovery_level2_gates: PARTIAL_PASS`：`npm run verify:quick`、OpenSpec change strict validate 与 `git diff --check` 通过；scoped strict docs 准确报告 6 个未完成反馈主项，待 6.2/6.3/6.5–6.8 全部收口后再转为通过，不以本次局部完成提前勾选。

## 2026-08-27 图片读取容错证据

- `photo_tolerance_targeted_tests: PASS`：`useRecordExport.test.tsx`、`useGuidedReviewCards.test.ts`、`useCasePhotoAssets.test.tsx` 与 `CaseRecordGeneratePage.test.tsx` 共 49 个 SYNTHETIC/TEST 用例通过；覆盖图片绑定离页保护、持久化图片读取失败后继续单独 Word 导出、附件2明确省略提示、恢复事项投影及“返回图片控件”焦点。
- `photo_tolerance_typecheck: PASS`：`npm run typecheck` 通过；本次仅把既有导出结果投影为会话级警告，没有新增后端、共享 DTO、持久化字段或导出门控。
- `photo_tolerance_impeccable_detector: PASS_WITH_EXISTING_FINDINGS`：对当前 UI 目标执行一次机械检测，仅命中 `reviewWorkspace.css` 中既有待办卡片左侧色边与既有进度条 `width` 过渡；两行均不在本次图片容错差异中。
- `photo_tolerance_diff_check: PASS`：`git diff --check` 通过；统一导出、归档和介质映射实现未改动。
- `photo_tolerance_level2_gates: PARTIAL_PASS`：`npm run verify:quick` 与 `openspec validate conversational-review-shell --type change --strict --no-interactive` 通过；scoped strict docs 准确报告 6.3、6.6、6.7、6.8 共 4 个未完成主项，待完整反馈范围收口后再通过。

## 2026-08-27 终态与并行状态证据

- `terminal_state_targeted_tests: PASS`：`useGuidedReviewCards.test.ts` 7 个、`GuidedReviewView.test.tsx` 3 个和 `CaseRecordGeneratePage.test.tsx` 19 个用例通过；覆盖 deferred、queued、archiving、图片上传与归档并行、archive verified 待介质编号、单独 Word 成功及 exported 统一导出终态。
- `terminal_state_contract: PASS`：单独 Word 成功仅投影“Word 已导出”；`archive_queued`/`archiving` 统一投影“后台归档处理中”并保留其他待办；`archive_verified` 仅表达“后台归档已完成校验”；只有 `exported` 表达“统一导出已完成”。
- `terminal_state_typecheck_and_detector: PASS`：`npm run typecheck` 通过；对 `useGuidedReviewCards.ts` 与 `CaseRecordGeneratePage.tsx` 的单次 Impeccable 机械检测为零发现。
- `terminal_state_level2_gates: PARTIAL_PASS`：`npm run verify:quick` 与 OpenSpec change strict validate 通过；scoped strict docs 准确报告 6.3、6.7、6.8 共 3 个未完成主项，待缩放验收、最终同步和整体人工验收完成后再通过。

## 2026-08-27 人工验收前自动化收口证据

- `pre_acceptance_targeted_tests: PASS`：`GuidedReviewView.test.tsx`、`useGuidedReviewCards.test.ts`、`useRecordExport.test.tsx` 与 `CaseRecordGeneratePage.test.tsx` 共 41 个 SYNTHETIC/TEST 用例通过；测试进程退出码为 0。jsdom 的 `getComputedStyle(..., pseudoElt)` 与既有 React `act(...)` 信息仅写入 stderr，未形成失败用例。
- `pre_acceptance_spec_sync: PASS`：living spec 中 `REQ-GUIDED-REVIEW-SHELL` 与 delta 均为 125 行且内容精确一致；“獙豸”残留为 0。
- `pre_acceptance_level2_automation: PARTIAL_PASS`：`npm run verify:quick`、OpenSpec change strict validate 与 `git diff --check` 通过；scoped strict docs 仅报告 6.3、6.7、6.8 三项未完成，待用户人工验收后复跑并完成 6.7。
- `pre_acceptance_impeccable_detector: PASS_WITH_EXISTING_FINDINGS`：机械检测仍只命中 `reviewWorkspace.css` 第 67 行既有左侧色边与第 214 行既有 `width` 过渡；两处均不属于本次差异，未扩大修改范围。

## 2026-08-27 最终人工验收证据

- `final_manual_acceptance: PASS`：用户确认使用 SYNTHETIC/TEST 案件完成视觉人工验收并通过；覆盖 125%/150%/200% 缩放与窄屏、恢复操作和长文案、模式切换焦点、历史/当前对话布局、后台归档与三类终态。
- `final_manual_acceptance_asset_scope: PASS`：验收未授权也未记录真实案件数据、人员信息、设备编号或生成输出进入仓库。
- `final_level2_gates: PASS`：引导定向测试 41/41、`npm run verify:quick`、`npm run verify:docs:strict -- --change conversational-review-shell`、OpenSpec change strict validate 与 `git diff --check` 全部通过。

## 2026-08-27 助手逐步提示证据

- `assistant_prompt_targeted_tests: PASS`：`useGuidedReviewCards.test.ts` 8 个与 `GuidedReviewView.test.tsx` 3 个用例全部通过；页面集成测试 19/19 通过。新增区分“请输入文号”“请选择委托时间”“请确认检材完整性”、恢复、压缩、等待和生成提示，并断言非待办说明只出现一次。
- `assistant_prompt_contract: PASS`：当前事项先进入具名且 `aria-live` 的“獬豸助手提示”消息区，结构化控件位于消息之后；动作仍由现有动态待办与状态投影生成，不新增固定题序、业务规则或持久化聊天记录。
- `assistant_prompt_gates: PASS`：`npm run verify:quick`、前端生产构建与 `git diff --check` 通过；Impeccable 检测仅命中本次差异外已记录的两处旧样式告警。

## 2026-08-27 逐轮对话证据

- `conversation_turn_contract: PASS`：助手提示和当前结构化控件已分成左右消息块；事项从动态动作集中消失时只生成“字段已填写/恢复已完成”等非逐字回执和助手承接语，不复制或持久化用户输入，案件标识变化时立即清空。
- `conversation_turn_targeted_tests: PASS`：`GuidedReviewView.test.tsx` 4/4、`useGuidedReviewCards.test.ts` 8/8、`CaseRecordGeneratePage.test.tsx` 19/19 通过；页面既有 jsdom `getComputedStyle` 与 React `act` 警告不影响结果。
- `conversation_turn_gates: PASS`：`npm run typecheck`、`npm run verify:quick`、前端生产构建、scoped strict docs、OpenSpec change strict validate 与 `git diff --check` 通过；构建保留既有大包提示，Impeccable 仅报告本次差异外第 67、214 行两处既存告警。

## 2026-08-27 历史轨迹密度证据

- `history_density_scope: PASS`：标题栏垂直占用由约 56px 收敛至约 44px，普通单行轨迹由约 60px 收敛至约 40px；时间线图标同步由 28px 调整为 24px，空状态留白同步压缩，历史区的 flex 主区域与滚动机制保持不变。
- `history_density_gates: PASS`：历史滚动组件测试 4/4、前端类型检查、`npm run verify:quick`、生产构建、布局检测、scoped strict docs 与 `git diff --check` 通过；构建仅保留既有大包提示。

## 2026-08-27 外置助手形象证据

- `assistant_avatar_alignment: PASS`：DOM 与视觉顺序均为右侧上一轮回复、外置獬豸形象与助手消息、右侧当前回复控件；形象不再占据整个对话区左栏，长提示和窄屏仍由消息列自然换行。
- `assistant_avatar_gates: PASS`：结构失败用例实施后转绿，组件测试 4/4、前端类型检查、`npm run verify:quick`、生产构建、布局检测、scoped strict docs 与 `git diff --check` 通过；构建仅保留既有大包提示。

## 2026-08-27 主内容边界外置证据

- `assistant_outside_content_boundary: PASS`：獬豸形象与对话正文使用相互独立的角色层和内容层；宽度达到 1360px 时以 120px 形象和 16px 间隔定位到主内容左边界外，较窄窗口改回 96–120px 响应式侧栏，760px 以下进一步收敛为 64–72px。
- `assistant_outside_browser_visual: PASS`：在 1536px 实际本地页面中复核，历史与对话正文左边界为 x=288，獬豸形象位于 x=152–272，边界间隔 16px；图片资源已加载，命中检测与截图均确认角色可见且未被外层 `overflow-x` 裁切。
- `assistant_outside_gates: PASS`：组件测试 4/4、`npm run verify:quick`、生产构建、布局检测、scoped strict docs、OpenSpec change strict validate 与 `git diff --check` 通过；构建仅保留既有大包提示。

## 2026-08-27 助手滚动联动证据

- `assistant_scroll_linkage_contract: PASS`：角色层和正文内容层共同位于 `.guided-review-conversation__body` 滚动容器；宽屏由滚动容器内部预留 136px 外置区域，正文左边界和右侧滚动条位置不变，窄屏继续使用响应式双列布局。
- `assistant_scroll_linkage_browser_visual: PASS`：在 1536px 实际本地页面中将当前对话滚动 60px，獬豸形象与助手消息均同步上移 60px；角色仍位于 x=152–272，正文左边界为 x=288，间隔保持 16px，并随对话窗口纵向裁切。
- `assistant_scroll_linkage_gates: PASS`：失败用例实施后转绿，组件测试 4/4、前端类型检查、`npm run verify:quick`、生产构建、布局检测、scoped strict docs、OpenSpec change strict validate 与 `git diff --check` 全部通过；构建仅保留既有大包提示。

## 2026-08-27 当前事项主舞台与对话节奏证据

- `current_stage_contract: PASS`：当前对话在 DOM 与视觉顺序中先于历史处理轨迹；历史默认只展示事实数量、最近事实与可访问展开入口，展开后继续使用既有事实列表和末端跟随逻辑。事项真实完成后仅显示非逐字完成回执，并根据下一项生成“已确认—接下来”的情境化承接语，不伪造业务处理中状态或新增持久化聊天记录。
- `current_stage_targeted_tests: PASS`：先调整失败用例，再实现至 `GuidedReviewView.test.tsx` 4/4 与 `CaseRecordGeneratePage.test.tsx` 19/19 通过；覆盖当前对话/历史顺序、历史展开关系、空历史、完成回执、等待状态、模式切换及导出事实查看。
- `current_stage_browser_visual: PASS`：实际本地只读案件在 1440×900 下当前主舞台高度约 342px、历史折叠摘要约 54px，页面无横向溢出；390×844 下对话正文、响应区和工具区宽度约 249px，响应区完整落在内容列内，文档与对话均无横向溢出或内部裁切。窄屏角色缩为 40px 行内状态标记，当前对话不再建立独占角色列或内部纵向滚动。
- `current_stage_gates: PASS`：前端类型检查、生产构建、Impeccable 检测（0 项）、`npm run verify:quick`、scoped strict docs、OpenSpec change strict validate 与 `git diff --check` 全部通过；构建仅保留既有大包提示。

## 2026-08-27 对话视口单轨证据

- `conversation_viewport_contract: PASS`：完整历史与当前对话共用 `.guided-review-scroll`；首次进入和切换案件使用滚动容器相对几何坐标锚定当前对话。历史新增时，当前办理舞台保留其视口内相对位置，已上滑阅读历史时保持原 `scrollTop`；事项与摘要面板不再建立第二条纵向滚动轨道。
- `conversation_viewport_targeted_tests: PASS`：`GuidedReviewView.test.tsx` 4/4、`CaseRecordGeneratePage.test.tsx` 19/19 通过；用例区分默认锚点、轻微上滑后的历史阅读位置，以及当前对话内部非零视口偏移的保持策略。页面测试保留既有 jsdom `getComputedStyle` 与 React `act` 警告，不影响结果。
- `conversation_viewport_browser_visual: PASS`：使用 SYNTHETIC/TEST 案件在 1440×900 与 390×844 实际页面复核；两种尺寸默认均由当前对话完整占据 856px/804px 可用滚动视口，历史位于视口上方，向上滚动后完整出现。两种尺寸横向溢出均为 0、嵌套纵向滚动均为 0，窄屏全局按钮最小高度为 44px。
- `conversation_viewport_gates: PASS`：生产构建、Impeccable layout 检测（0 项）、`npm run verify:quick`、scoped strict docs、OpenSpec change strict validate 与 `git diff --check` 通过；构建仅保留既有大包提示。
- `conversation_viewport_spec_sync: PASS_WITH_GLOBAL_BASELINE_ISSUES`：本包 delta 与 living spec 的目标 Scenario 已同步，scoped strict docs 为 14/14 通过。额外运行的全局 living-spec validate 仍报告本次范围外的既存结构问题：`electronic-inspection-record` 两个旧 Requirement 缺少 MUST/SHALL 且旧 `REQ-ARCHIVE-STORAGE-SETTINGS` 位于主 Requirements 区外，`harness-workflow` 一个旧 Requirement 缺少 MUST/SHALL。

## 2026-08-28 文本事项 Enter 确认证据

- `text_enter_confirmation_contract: PASS`：文本字段每次输入继续更新现有报告草稿和自动保存，但当前卡片与完成轨迹保持到用户按下 Enter；确认后才移除当前卡片、形成非逐字完成回执并推进下一事项。日期、确认按钮和其他显式操作未改为 Enter 门控。
- `text_enter_confirmation_hardening: PASS`：输入法组合态 Enter 不推进；多行输入的 Shift+Enter 保留换行；用户聚焦文本控件后才锁定当前事项，未开始输入时新增的保存、租约等恢复事项仍沿用既有优先级。
- `text_enter_confirmation_tests: PASS`：`useGuidedReviewCards.test.ts` 9/9、`GuidedReviewView.test.tsx` 5/5、`CaseRecordGeneratePage.test.tsx` 19/19 通过；页面测试保留既有 jsdom `getComputedStyle` 与 React `act` 警告，不影响结果。
- `text_enter_confirmation_manual_acceptance: N/A`：本次为键盘事件与会话投影状态修复，无新增布局或视觉合同；IME、Shift+Enter、单字符停留、Enter 推进和恢复事项优先级均由可区分的自动化用例覆盖。
- `text_enter_confirmation_gates: PASS`：前端类型检查、生产构建、Impeccable 检测（0 项）、`npm run verify:quick`、scoped strict docs、OpenSpec change strict validate 与 `git diff --check` 全部通过；构建仅保留既有大包提示。

## 2026-08-28 检材完整性双向选择证据

- `evidence_completeness_interaction: PASS`：引导回复区同时提供具名的完整与不完整图标操作；选择不完整保持当前对话挂载并直接展开既有 `EvidenceEditor`，手工添加继续写入同一 `introduction.evidence_list` 并沿用现有完整性确认与自动保存链路。
- `evidence_completeness_targeted_tests: PASS`：`GuidedReviewView.test.tsx`、`CaseRecordGeneratePage.test.tsx` 与 `StructuredEditors.test.tsx` 共 38/38 通过；新增用例覆盖图标、可访问名称、完整确认回调、不完整后留在当前对话、添加检材更新以及不打开完整审核表单。
- `evidence_completeness_quality: PASS_WITH_EXISTING_FINDINGS`：TypeScript、`verify:quick`、OpenSpec change strict validate 与 `git diff --check` 通过；Impeccable 单次检测只报告 `reviewWorkspace.css` 中本次差异外的既有侧边强调线与 `width` 过渡告警。
- `evidence_completeness_manual_acceptance: N/A`：本次图标、44px 操作目标、对话模式保持和内嵌编辑器呈现均由组件/页面 DOM 回归、类型检查与机械检测覆盖；未改变既有检材编辑器的布局或字段交互。
- `evidence_completeness_browser_visual: N/A`：本地隔离启动时默认工作台数据库为只读，无法在不接触用户现有案件数据的前提下形成合成案件实页；已停止临时服务，不以读取或修改现有案件替代合成验收。

## 2026-08-29 返回上一步证据

- `previous_step_contract: PASS`：结构化事项完成推进后只在当前页面会话保留上一轮动作快照；“返回上一步”复用原 `GuidedReviewCard` 和报告更新链路，“返回当前步骤”恢复最新动态动作，已完成动作不重新进入待处理列表或数量。
- `previous_step_targeted_tests: PASS`：先得到缺少会话导航与按钮的失败证据；实施后 `useGuidedReviewCards.test.ts` 11/11、`GuidedReviewView.test.tsx` 6/6、`CaseRecordGeneratePage.test.tsx` 20/20 通过，覆盖返回上一轮、恢复当前步骤、案件切换清理和待处理数量不回退。
- `previous_step_visibility_regression: PASS`：针对用户截图对应的“文号仍待处理时从全部事项切换到检材照片”补充区分用例，证明来源项不必先完成即可返回；组件 DOM 断言按钮位于助手提示之后、回复控件之前，不再被高图片上传内容推到回复区末尾。
- `previous_step_accessibility: PASS_WITH_EXISTING_FINDINGS`：两个导航按钮具有稳定中文可访问名称和 44px 最小高度；Impeccable 单次检测仅报告 `reviewWorkspace.css` 第 167、314 行两处本次范围外既有告警。
- `previous_step_manual_acceptance: N/A`：本次沿用既有对话容器和 Ant Design 文本按钮，仅增加单行自适应导航；桌面/窄屏可达性、按钮名称、触控高度与往返行为均由组件 DOM、页面集成和机械检测覆盖。
- `previous_step_gates: PASS`：前端类型检查、`npm run verify:quick`、scoped strict docs、OpenSpec change strict validate 与 `git diff --check` 全部通过；页面测试仅保留既有 jsdom `getComputedStyle` 与 React `act` 警告。
- `previous_step_visibility_gates: PASS_WITH_EXISTING_FINDINGS`：截图回归修复后再次通过 `verify:quick`、scoped strict docs、OpenSpec change strict validate 与定向页面回归；Impeccable 仍仅命中 `reviewWorkspace.css` 第 167、314 行两处本次范围外既有告警。

## 2026-08-29 对话灵动性证据

- `conversation_switch_handoff: PASS`：用户从一个仍待处理事项切换到另一个时，助手使用两项的业务标签说明“先处理当前项、来源项仍保留”，不生成完成回执、不复制用户输入，也不新增持久化对话事实。
- `conversation_directional_motion: PASS`：事项切换时助手提示从左侧 6px、回复控件从右侧 8px 短暂进入，仅使用 `transform`、`opacity` 和轻微模糊；无循环、随机文案、假输入、假思考或人为等待，系统启用减少动态效果时动画时长降至 0.01ms。
- `conversation_delight_tests: PASS`：先得到缺少“事项切换说明”的失败证据，实施后 `GuidedReviewView.test.tsx` 7/7；引导 Hook、组件和页面联合回归 38/38 通过。页面测试只保留既有 jsdom `getComputedStyle` 与 React `act` 警告。
- `conversation_delight_quality: PASS_WITH_EXISTING_FINDINGS`：`npm run verify:quick`、OpenSpec change strict validate 与 `git diff --check` 通过；Impeccable 单次检测仅命中 `reviewWorkspace.css` 第 167、314 行两处本次范围外既有告警。
- `conversation_delight_manual_acceptance: N/A`：新增承接语、动作身份、左右分期和减少动态效果降级均由组件 DOM、定向回归、类型检查及机械检测覆盖；未引入需真实案件或桌面环境才能验证的业务行为。

## 2026-08-29 獬豸形象动效证据

- `mascot_motion_contract: PASS`：獬豸图片在独立动作层内以 7.2 秒周期执行一次 2px/1.2% 的低幅度呼吸；当前事项身份变化会替换动作层并触发一次 420ms 点头，不修改外层布局、业务状态或交互时序。
- `mascot_motion_lifecycle: PASS`：`IntersectionObserver` 与页面可见性共同控制非必要循环，角色离开视口或页面隐藏时暂停；无观察器环境保持静态内容可用，减少动态效果媒体查询直接取消角色空间运动。
- `mascot_motion_tests: PASS`：先得到事项变化后缺少角色动作身份的失败证据，实施后 `GuidedReviewView.test.tsx` 7/7 和前端 TypeScript 检查通过。
- `mascot_motion_quality: PASS_WITH_EXISTING_FINDINGS`：`npm run verify:quick`、OpenSpec change strict validate 与 `git diff --check` 通过；Impeccable 单次检测仍仅命中 `reviewWorkspace.css` 第 167、314 行两处本次范围外既有告警。
- `mascot_motion_manual_acceptance: N/A`：动效幅度、触发身份、可见性暂停与减少动态效果降级由组件回归、类型检查和机械检测覆盖；本次不改变角色资产尺寸、布局占位或业务操作。

## 2026-08-30 明显角色型对话体验证据

- `character_conversation_contract: PASS`：同一獬豸角色资产提供倾听、核对、严肃提醒与完成四态；恢复类异常优先映射严肃提醒，后台任务映射核对，事项完成短暂映射完成后回到当前真实状态。当前会话仅保留最近三轮业务完成摘要和修改入口，更早轮次只显示数量，不保存或回显逐字输入。
- `progressive_evidence_and_tools: PASS`：检材不完整后先选择快捷批量或逐项编辑，页面一次仅渲染一条完整路径并可随时切换；“其他事项”“已整理信息”成为具名次级入口，“完整审核编辑”和“返回案件工作台”收进“更多操作”，当前回复继续是唯一主操作。
- `character_targeted_tests: PASS`：`GuidedReviewView.test.tsx` 12/12、`useGuidedReviewCards.test.ts` 12/12、`CaseRecordGeneratePage.test.tsx` 20/20 通过；覆盖四态角色、最近三轮与更早折叠、逐轮修改、案件切换清空、分步检材补录、更多操作及既有编辑/压缩/导出链路。页面用例仅保留既有 jsdom 与 React 测试警告。
- `character_visual_quality: PASS_WITH_TOOL_SCOPE_NOTE`：Impeccable 单次检测对两个改造 TSX 文件报告 0 项；命令误传的 CSS 路径不可访问，因此本次 CSS 差异另行人工核对了精灵裁切、语义动画、窄屏布局与减少动态效果规则，未发现新增阻断问题。
- `character_manual_acceptance: N/A`：本地没有不接触用户现有案件数据即可使用的合成案件实页；未以真实案件替代。桌面/窄屏结构、角色状态身份、操作可达性和动效降级由 DOM 回归、响应式 CSS 差异核对及生产构建覆盖。
- `character_level2_gates: PASS`：前端类型检查、生产构建、`npm run verify:quick`、scoped strict docs 14/14、OpenSpec change strict validate 与 `git diff --check` 全部通过；仓库资产卫生检查包含新增角色精灵图并通过，构建仅保留既有大包提示。

## 2026-08-30 图标工具栏与透明角色资产反馈证据

- `icon_toolbar_regression: PASS`：底部恢复全部事项、已整理信息、完整审核编辑和返回工作台四枚 44px 圆形图标；数量角标、Tooltip、可访问名称、主按钮靛蓝样式、面板展开后的自动滚动与焦点继续保留，常驻文字和“更多操作”入口已经移除。
- `transparent_mascot_asset: PASS`：四态精灵图经内置 ImageGen 背景提取后替换，FFmpeg 检查确认为 PNG `rgba`，浅色矩形底板与背景雾已清除；四宫格顺序、角色身份、表情和现有 CSS 裁切保持不变。
- `icon_toolbar_targeted_tests: PASS`：先得到圆形按钮断言失败证据，实施后 `GuidedReviewView.test.tsx` 12/12、`CaseRecordGeneratePage.test.tsx` 20/20、前端类型检查和生产构建通过；页面测试仅保留既有 jsdom 与 React 测试警告。
- `icon_toolbar_impeccable: PASS_WITH_EXISTING_FINDINGS`：Impeccable 单次检测未报告本次图标工具栏差异问题，仅命中 `reviewWorkspace.css` 第 167、314 行两处本次范围外既有告警。
- `icon_toolbar_level2_gates: PASS`：`npm run verify:quick`、仓库资产卫生、scoped strict docs 14/14、OpenSpec change strict validate 与 `git diff --check` 全部通过；生产构建仅保留既有大包提示。

## 2026-08-30 对话容器纯白融合证据

- `mascot_border_root_cause: PASS`：角色 PNG 四角 Alpha 为 0；用户截图四角 `RGB(251,253,255)` 与当前对话容器原 `#fbfdff` 完全一致，确认可见色块来自父容器而非图片底板。
- `conversation_surface_blend: PASS`：当前对话容器改为纯白 `#ffffff` 并移除 `#cfdde8` 的 1px 边框；角色透明通道、柔和投影、圆角、滚动、布局与交互保持不变。
- `conversation_surface_gates: PASS`：前端类型检查、生产构建与 `git diff --check` 通过；纯样式反馈未机械新增行为测试，构建仅保留既有大包提示。

## 2026-08-30 对话舞台透明融合证据

- `transparent_stage_blend: PASS`：当前对话舞台由纯白表面进一步改为 `transparent`，不再创建与页面底色不同的矩形画布；透明 PNG 直接继承页面背景，角色外只保留非矩形的自然投影。
- `transparent_stage_scope: PASS`：内容气泡、角色四态裁切与动作、圆形工具栏、滚动锚点及全部交互未修改。
- `transparent_stage_gates: PASS`：前端类型检查、生产构建与 `git diff --check` 通过；纯样式反馈未机械新增行为测试，构建仅保留既有大包提示。

## 2026-08-30 角色投影移除证据

- `mascot_shadow_removed: PASS`：角色图片静态样式及呼吸关键帧均不再使用 `drop-shadow`；透明舞台保持不变，角色只保留原有轻微位移与缩放。
- `mascot_shadow_scope: PASS`：四态角色、语义亮度与饱和度反馈、布局、内容气泡、图标工具栏及全部交互均未修改。
- `mascot_shadow_gates: PASS`：前端类型检查、生产构建、投影关键字检索与 `git diff --check` 通过；纯样式反馈未新增行为测试，构建仅保留既有大包提示。

## 2026-08-30 獬豸助手按钮体系统一证据

- `assistant_icon_button_system: PASS`：獬豸助手的直接回复、检材补充方式、解析/排序/确认、模式切换、新增/删除检材、历史修改、步骤返回、兜底编辑和底部工具栏统一复用 44px 圆形图标按钮；主操作使用靛蓝实心，次操作使用白底描边，删除操作保留红色危险语义，悬停、焦点、禁用与阴影状态一致。
- `assistant_action_semantics: PASS`：按钮常驻文字已移入 Tooltip 与可访问名称，原回调、禁用条件和动态数量信息保持不变；全部事项面板的整行选择继续作为列表导航，不机械改成圆形工具按钮。
- `assistant_icon_button_tests: PASS`：`GuidedReviewView.test.tsx` 12/12、`CaseRecordGeneratePage.test.tsx` 20/20、前端类型检查和生产构建通过；页面测试只保留既有 jsdom `getComputedStyle` 与 React `act` 警告，构建只保留既有大包提示。

## 2026-08-31 归档准备顺序与检材清单证据

- `guided_archive_precedence: PASS`：无恢复事项时操作集稳定按“选择压缩时机→介质编号→文号等普通待办”推荐；选择稍后后介质编号成为当前推荐，再次立即压缩入口退到全部事项末尾；保存、租约、来源与图片恢复事项继续保持最高优先级。
- `evidence_context_before_choice: PASS`：检材完整性卡在完整/不完整操作之前直接显示全部有序检材的编号、设备名称、手机/平板类型和可提取情况；零检材时显示明确空态，进入不完整路径后仍复用既有批量/逐项编辑器。
- `guided_order_targeted_tests: PASS`：Hook、引导组件及独立检材摘要测试 27/27 通过；页面集成测试 20/20 通过，覆盖从全部事项非线性进入检材确认，并保留既有 jsdom `getComputedStyle` 与 React `act` 警告。
- `guided_order_architecture: PASS`：检材摘要验证沿自然组件职责迁入独立同目录测试文件，`GuidedReviewView.test.tsx` 保持在 600 行以内；`lint:arch` 通过，无行数豁免。
- `guided_order_impeccable: PASS_WITH_EXISTING_FINDINGS`：单次机械检查未发现本次新增问题，仅报告 `reviewWorkspace.css` 第 167、314 行两处本次范围外既有告警。
- `guided_order_manual_acceptance: N/A`：顺序、全部检材可见性、空态、可访问名称和非线性事项入口均由可区分的 Hook、组件与页面 DOM 回归覆盖；未改变归档业务调用或检材编辑字段本身。
- `guided_order_level2_gates: PASS`：`verify:quick`、scoped strict docs 14/14、OpenSpec change strict validate、仓库资产卫生与定向回归全部通过。

## 2026-08-31 历史预览与对话可交换分栏

- [x] 6.40 将 `packages/frontend/src/components/GuidedReviewView.tsx` 和 `GuidedReviewHistory.tsx` 从历史/对话单一纵向轨道改为桌面左右分栏：历史预览默认在左、当前对话默认在右，并提供可访问的交换位置操作；交换时保持当前回复、会话级完成摘要和业务控件状态。
  - 验证：组件测试区分默认 DOM 顺序、交换后的 DOM/键盘顺序、布局状态文案和当前回复节点不被重建。
- [x] 6.41 调整 `packages/frontend/src/reviewWorkspace.css`，桌面使用约 36%/64% 的历史/对话布局并让两区独立滚动；窄屏降级为无嵌套滚动的单列布局，交换操作切换上下顺序。
  - 验证：运行前端类型检查、生产构建、Impeccable layout 检测，并在可用环境核对桌面与窄屏布局。
- [x] 6.42 将本次最终行为同步到 living spec，并运行 `npm run verify:quick`、`npm run verify:docs:strict -- --change conversational-review-shell`、OpenSpec strict validate 与 scoped `git diff --check`。

### 分栏改造验证记录

- `guided_split_contract: PASS`：桌面默认按约 36%/64% 展示左侧历史预览与右侧当前对话，两区独立滚动；交换操作同步重排 DOM 与键盘顺序，当前回复节点保持原实例，未触发业务写入。
- `guided_split_responsive: PASS_WITH_BROWSER_NA`：760px 以下改为单列、取消两个面板的嵌套滚动，并让同一操作切换上下顺序；Impeccable layout 检测为 0 项。当前会话未暴露可用浏览器控制接口，因此真实桌面/窄屏截图验收记为 N/A，不以源码检查冒充视觉验收。
- `guided_split_regression: PASS`：引导组件与案件页面回归 32/32、全项目 TypeScript、生产构建、`verify:quick`、OpenSpec strict validate 与 scoped `git diff --check` 通过；测试仅保留既有 jsdom 样式测量及 React `act` 提示，生产构建仅保留既有大包告警。

## 2026-08-31 分栏铺满与等宽反馈

- [x] 6.43 根据用户实页截图移除引导模式继承的 `1136px` 最大宽度和左右内边距，让历史/对话分栏铺满主工作区可用宽度；桌面分栏由 36%/64% 调整为严格 1:1，完整审核编辑页和窄屏单列行为保持不变。
  - 文件：`packages/frontend/src/reviewWorkspace.css`、本包 delta 与 living spec。
  - 验证：核对引导模式宽度覆盖与 `repeat(2, minmax(0, 1fr))` 等宽网格，运行前端类型检查、生产构建、Impeccable layout 检测、scoped strict docs 与 `git diff --check`；本次纯布局反馈不机械新增行为测试。

### 铺满与等宽验证记录

- `guided_split_fill_contract: PASS`：`.review-page--guided` 已覆盖通用 `.review-page` 的 `max-width`、居中外边距和左右内边距，只在引导模式铺满主工作区；完整审核编辑继续沿用原 1136px 内容宽度。
- `guided_split_equal_columns: PASS`：桌面网格使用 `repeat(2, minmax(0, 1fr))`，历史预览与当前对话各占一半可用宽度；760px 以下既有单列降级保持不变。
- `guided_split_fill_quality: PASS`：生产构建、TypeScript、`verify:quick`、scoped strict docs 14/14、OpenSpec strict validate 与 scoped `git diff --check` 通过，Impeccable layout 检测 0 项；构建仅保留既有大包提示。

## 2026-08-31 统一导出入口收口

- [x] 6.44 按入口收口反馈移除案件内部审核页的统一导出操作，只保留介质编号填写/映射和单独 Word 导出；统一导出继续由案件工作台卡片触发，后端导出合同、工作台导出和历史状态展示保持不变。
  - 文件：`packages/frontend/src/components/ArchiveCompletionPanel.tsx`、`packages/frontend/src/pages/CaseRecordGeneratePage.tsx` 及相关测试；同步本包 delta 与 `openspec/specs/electronic-inspection-record/spec.md`。
  - 验证：页面与组件定向 Vitest 区分“内部无统一导出入口”和“工作台仍可统一导出”，再运行 `npm run verify:quick`、`npm run verify:docs:strict -- --change conversational-review-shell` 与 `git diff --check`。
  - 证据：归档完成面板、案件内部审核页与案件工作台 3 个前端测试文件共 46 项通过；内部页面断言不出现统一导出按钮且不请求 `/export-bundle`，工作台卡片统一导出回归通过；`verify:quick`、scoped strict docs 与 `git diff --check` 通过。人工验收：N/A（入口可见性与请求边界由可区分的合成前端测试覆盖，未改变视觉版式或桌面目录选择器实现）。

## 2026-08-31 历史预览最终值与分类型展示反馈

- [x] 6.45 将历史预览的业务信息改为当前报告草稿最终值投影：普通字段显示中文标签和值，用户修改覆盖旧识别值，并根据现有字段来源为用户填写或修改的最终值显示“用户填写”标记；长文本完整换行显示，空值不展示，来源、保存、归档、导出和异常仍保留自然语言状态。
  - 文件：`packages/frontend/src/hooks/useGuidedReviewHistoryProjection.ts`、`useGuidedReviewCards.ts`、现有 Hook 测试。
- [x] 6.46 为检材与图片增加逐检材结构化展示，使用“检材 N · 编号”主标签、右侧 `已上传数/2` 进度以及对应检材的最终设备信息；复用现有视觉语言并覆盖窄屏、长编号和可访问语义。
  - 文件：`packages/frontend/src/components/GuidedReviewHistory.tsx`、`packages/frontend/src/reviewWorkspace.css`、现有组件测试。
- [x] 6.47 核对 delta 与最终实现并同步 living spec，运行前端定向测试、类型检查、Impeccable 检测、`verify:quick`、scoped strict docs、OpenSpec strict validate 与 scoped `git diff --check`。

### 历史预览最终值与分类型展示验证记录

- `history_final_value_contract: PASS`：历史业务摘要从当前报告草稿重建，普通字段、多值、长文本和空值使用分类型投影；Hook 回归区分报告识别委托人员、用户修改后的最终人员列表以及清空后的字段移除，不保留被覆盖的旧值。
- `history_user_provenance: PASS`：页面向历史投影传入既有 `FieldState`，字段与检材按稳定来源路径判断 `user`，可见“用户填写”文字标记与蓝色样式同时存在；报告解析与系统默认来源不误标，标记不成为新的业务字段。
- `history_material_photo_rows: PASS`：检材按当前顺序显示“检材 N · 编号”，右侧按现有照片绑定显示 `0/2`、`1/2` 或 `2/2`，完整状态使用既有成功色；设备、类型、IMEI、序列号和无法提取原因在对应检材下展示最终值，图片数量具有完整可访问名称。
- `history_targeted_tests: PASS`：`useGuidedReviewCards.test.ts` 16/16、`GuidedReviewView.test.tsx` 12/12 通过，覆盖最终值刷新、用户来源标记、检材图片进度、结构化 DOM 和分栏交换；生产构建通过，仅保留既有大包提示。
- `history_page_regression: PASS_WITH_OUT_OF_SCOPE_FAILURE`：扩展执行 `CaseRecordGeneratePage.test.tsx` 时 20 项中 19 项通过；与本次历史预览无代码交集的“统一导出入口”旧断言连续两次找不到“请返回案件工作台统一导出”文案，保持现状并未擅自改写该业务合同。测试仍输出既有 jsdom `getComputedStyle` 与 React `act` 提示。
- `history_impeccable: PASS_WITH_EXISTING_FINDINGS`：一次性机械检测仅报告 `reviewWorkspace.css` 第 167 行既有 3px 左边框和第 314 行既有 `width` 过渡，本次新增历史样式无检测项。
- `history_manual_acceptance: N/A`：为避免在未确认测试属性的现有案件上读取或截图业务信息，本轮未进行真实案件视觉验收；合成组件 DOM、长内容换行、760px 响应式规则和可访问名称由自动化与源码检查覆盖。
- `history_level2_gates: PASS`：`lint:arch`、TypeScript、生产构建、`verify:quick`、scoped strict docs、OpenSpec strict validate、仓库资产卫生与 scoped `git diff --check` 通过。

## 2026-09-01 Word 内容预览去除过程轨迹反馈

- [x] 6.48 将左侧区域从“历史预览”收敛为“Word 内容预览”，只展示当前报告草稿中供用户快速核对 Word 正文与附件的最终内容；移除来源确认、保存、编辑权限、归档、导出、异常恢复和字段完成等过程轨迹。
- [x] 6.49 保留过程状态在当前对话、恢复操作与系统状态中的既有表达，更新分栏文案、空态和可访问名称，并用现有 Hook、组件与页面测试区分内容预览与过程状态。
- [x] 6.50 核对 delta 与实现并同步 living spec，运行前端定向测试、类型检查、生产构建、Impeccable 检测、`verify:quick`、scoped strict docs、OpenSpec strict validate 与 `git diff --check`。

### Word 内容预览去除过程轨迹验证记录

- `word_preview_scope: PASS`：预览只由当前报告草稿与字段来源投影，来源确认、保存/权限、归档、导出、异常恢复和字段完成记录均不再进入预览；对应恢复操作与后台系统状态仍沿用当前对话既有能力。
- `word_preview_copy_accessibility: PASS`：区域标题、分栏状态、交换操作和空态统一使用“Word 内容预览”，结构化文书、检材、图片数量与用户填写标记保持可见、可聚焦和可访问。
- `word_preview_targeted_tests: PASS_WITH_EXISTING_OUT_OF_SCOPE_FAILURE`：Hook 与引导组件 28/28 通过，页面集成 20 项中 19 项通过；唯一失败仍为本包既有记录中的“统一导出入口”旧文案断言，与本次预览投影无代码交集。测试保留既有 jsdom `getComputedStyle` 与 React `act` 提示。
- `word_preview_quality: PASS`：前端 TypeScript、生产构建、`verify:quick` 与 Impeccable 单次检测（0 项）通过；人工验收 N/A，内容可见性、状态隔离、实时最终值、空态和可访问名称均由合成 Hook、组件及页面 DOM 回归区分覆盖。

## 2026-09-01 Word 内容预览软件字段去重反馈

- [x] 6.51 从 Word 内容预览中移除重复的“主取证软件”字段，只保留现有“软件工具 N”列表；不得修改报告草稿、主取证软件数据或 Word 生成逻辑。
- [x] 6.52 用现有 Hook 回归区分“软件工具仍展示”和“主取证软件不再展示”，同步 delta 与 living spec，并运行风险相称的前端检查及限定范围文档门控。

### Word 内容预览软件字段去重验证记录

- `word_preview_software_dedup: PASS`：预览投影不再生成“主取证软件”行，现有“软件工具 N”列表继续展示名称与版本；报告中的 `primary_software`、检查结果字段和 Word 生成链路均未修改。
- `word_preview_software_tests: PASS`：`useGuidedReviewCards.test.ts` 16/16 与全项目 TypeScript 通过，新增断言同时证明软件工具保留且重复主软件字段缺席；人工验收 N/A，该展示差异由合成 DOM 投影可区分覆盖。

## 2026-09-01 已填内容与待办集中修改反馈

- [x] 6.53 移除当前对话内会话级“你已完成”历史轮次和逐轮修改按钮，把本次会话已完成的结构化事项统一收纳到“已填内容与待办”面板；保留当前事项、事项切换说明、返回步骤和既有结构化控件。
- [x] 6.54 将独立“完整审核编辑”图标并入“已填内容与待办”面板作为修改其他既有内容的兜底入口，并让红色数量角标只统计真实用户待处理项；后台等待、可生成状态和已填写内容不得计入角标。
- [x] 6.55 保持 Word 内容预览投影、结构、交换分栏及 Word 生成逻辑不变；更新组件/页面回归、同步 delta 与 living spec，并运行风险相称的前端与 Level 2 文档门控。

### 集中修改入口验证记录

- `guided_edit_center_contract: PASS`：当前对话不再渲染“你已完成”轮次；本次会话已完成的结构化事项全部进入“已填内容与待办”，可返回原控件修改，完整审核编辑也作为同一面板内的兜底入口。
- `guided_edit_center_badge: PASS`：红色角标只统计 `pending_item`、恢复和压缩选择等用户可处理事项；`waiting`、`ready` 与本次已填写内容均不计入数量，系统状态仍保留在面板列表。
- `guided_edit_center_scope: PASS`：生产差异未修改 `GuidedReviewHistory.tsx`、历史投影 Hook、报告草稿、Word 预览投影或 Word 生成/导出链路；只调整引导视图、局部样式、现有回归和对应规格。
- `guided_edit_center_tests: PASS_WITH_EXISTING_PAGE_FAILURE`：引导组件 12/12 通过；案件页面 20 项中 19 项通过，唯一失败仍为本包此前已记录的“请返回案件工作台统一导出”旧文案断言，与本次入口调整无代码交集。
- `guided_edit_center_quality: PASS`：架构检查、全项目 TypeScript、生产构建、`verify:quick`、OpenSpec change strict validate、仓库资产卫生与 scoped `git diff --check` 通过；构建仅保留既有大包提示。Impeccable 单次检测只报告 `reviewWorkspace.css` 第 167、314 行两处本次修改前既有告警，本次新增区域无告警。
- `guided_edit_center_manual_acceptance: N/A`：当前环境未提供可安全使用的 SYNTHETIC/TEST 案件页面，未读取或截图现有案件；入口分组、数量语义、会话完成项修改、完整编辑往返、焦点和 Word 预览隔离均由合成组件及页面 DOM 回归区分覆盖。

## 2026-09-01 移除已整理信息入口反馈

- [x] 6.56 从当前对话工具栏移除“查看已整理信息”按钮及其专属摘要面板，保留“已填内容与待办”和“返回案件工作台”；删除仅服务于该入口的组件属性、页面摘要投影与样式，不修改 Word 内容预览、报告草稿或 Word 生成逻辑。
- [x] 6.57 更新组件回归以区分该入口缺席及其余工具入口保留，同步 delta 与 living spec，并运行风险相称的前端检查及 Level 2 文档门控。

### 移除已整理信息入口验证记录

- `guided_summary_entry_contract: PASS`：旧实现先被“工具栏不存在查看已整理信息按钮”的新增断言区分；实施后按钮、专属摘要面板、组件 `summary` 属性、页面摘要投影和对应样式均已移除，“已填内容与待办”及“返回案件工作台”继续保留。
- `guided_summary_entry_tests: PASS`：`GuidedReviewView.test.tsx` 12/12 与全项目 TypeScript 通过；`verify:quick` 的架构、类型、治理文档与仓库资产检查、scoped strict docs、OpenSpec change strict validate 和 `git diff --check` 均通过。
- `guided_summary_entry_impeccable: PASS_WITH_EXISTING_FINDINGS`：一次性机械检测仅报告 `reviewWorkspace.css` 第 167、314 行两处本次修改前既存告警，本次删除区域无检测项。
- `guided_summary_entry_manual_acceptance: N/A`：该入口缺席、其余入口保留及待办面板焦点由合成组件 DOM 回归可区分覆盖，未使用或读取真实案件数据。

## 2026-09-01 分栏顺序持久化反馈

- [x] 6.58 将 Word 内容预览与当前对话的交换顺序保存为浏览器本地界面偏好，使刷新页面和打开其他案件时继续沿用；存储不可用或值无效时安全回退，不写入案件草稿、报告或服务端。
- [x] 6.59 更新组件回归以区分偏好读取、切换写入和跨案件重新挂载复用，同步 delta 与 living spec，并运行风险相称的前端检查及 Level 2 文档门控。

### 分栏顺序持久化验证记录

- `guided_split_order_preference: PASS`：分栏组件首次挂载从 `biji.guidedReview.splitOrder` 读取经过白名单校验的顺序，用户交换后立即写回；刷新或打开其他案件重新挂载时沿用同一浏览器偏好，存储异常或无效值回退为 Word 内容预览在左。
- `guided_split_order_scope: PASS`：偏好只保存 `history-first` 或 `conversation-first` 两个界面值，不进入案件草稿、报告、后端接口或服务端存储，交换仍保持当前回复组件挂载。
- `guided_split_order_tests: PASS`：新增回归先在旧实现上失败，实施后 `GuidedReviewView.test.tsx` 13/13 通过，覆盖偏好读取、切换写入、跨案件重新挂载复用及原有分栏 DOM/键盘顺序行为。
- `guided_split_order_quality: PASS`：架构检查、全项目 TypeScript、治理测试、文档快检、仓库资产卫生、生产构建和 `git diff --check` 通过；Impeccable 单次检测 0 项，构建仅保留既有大包提示。
- `guided_split_order_manual_acceptance: N/A`：持久化键值、重新挂载和跨案件复用由 SYNTHETIC 组件回归可区分覆盖，未读取或写入真实案件数据。
