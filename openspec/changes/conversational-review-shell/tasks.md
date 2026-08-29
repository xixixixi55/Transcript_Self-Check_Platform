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

## 当前状态

- `implementation_status: complete`：首轮实现与第 6 节流程评审反馈均已完成。
- `feedback_scope_status: complete`：自动化验证与用户执行的 SYNTHETIC/TEST 人工验收均已通过。
- `spec_sync_status: synced`：delta 已同步到 living spec，最终行为与主规格一致。

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
