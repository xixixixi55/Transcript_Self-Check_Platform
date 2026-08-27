# Tasks: 默认对话式审核外壳

workflow_level: 2

> 目标：案件审核地址默认只展示对话式引导，上方为历史处理轨迹，下方为当前对话和操作；现有完整审核编辑按用户操作切换显示。两种视图共用现有案件会话和全部业务机制；本包只改变前端展示与导航，不创建第二套业务流程。

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
- [ ] 6.2 Layer 10：扩展 `packages/frontend/src/hooks/useGuidedReviewCards.ts` 及测试，把现有 autosave `failed/conflict`、可恢复租约状态和图片上传/绑定/读取异常投影为可执行恢复事项；当前操作已开始编辑时只加入历史与全部待办，不突然抢占当前卡片。
  - 验证：SYNTHETIC/TEST 用例覆盖保存失败、revision conflict、租约 expired/failed、图片绑定失败、图片读取容错提示和恢复后事项自动消失；断言不复制保存、图片或导出业务规则。
- [ ] 6.3 Layer 11：调整 `packages/frontend/src/components/GuidedReviewView.tsx`、`GuidedReviewCard.tsx`、相关测试与 `reviewWorkspace.css`，为恢复事项提供现有“重试保存/加载服务端版本/恢复租约/打开图片控件”操作；为待办与摘要开关建立稳定 `aria-controls` 关系，并保证窄屏和浏览器缩放下操作目标、长错误文案及焦点可见。
  - 验证：组件测试覆盖恢复按钮回调、展开控件关系、错误文案、键盘顺序和只读状态；浏览器人工验收覆盖 125%/150%/200% 缩放与窄屏触控，不以颜色、图标或角色表情单独表达状态。
- [ ] 6.4 Layer 12：调整 `packages/frontend/src/pages/CaseRecordGeneratePage.tsx` 及页面测试，接通既有 autosave retry/load-server-version 与租约恢复能力；guided→full 切换后聚焦目标字段或完整编辑区标题，full→guided 后聚焦当前对话标题/卡片；卸载原按钮时不得留下不可预测焦点。
  - 验证：页面测试覆盖保存失败/冲突后保留输入和恢复、expired/failed 租约可执行恢复、双向模式切换焦点、刷新重建，以及恢复过程不创建第二份 session、不改变 lifecycle。
- [ ] 6.5 保持图片与导出合同：图片上传/绑定失败继续显示可恢复事项并保留现有离页保护；单独 Word 等待图片超时或持久化图片读取失败时，页面明确提示附件2将被省略并提供返回图片控件的入口，但继续遵守既有非阻断导出合同；统一导出、归档和介质映射门控不变。
  - 验证：复用并扩展 `packages/frontend/src/pages/CaseRecordGeneratePage.test.tsx`、`useCasePhotoAssets.test.tsx` 和既有导出测试，区分“图片未安全绑定阻止离页”与“单独 Word 图片读取容错提示”，防止静默声称图片已进入 Word。
- [ ] 6.6 明确办理终态与并行状态：助手不得把“选择立即压缩”、`archive_queued`、`archiving` 或图片上传请求返回视为办理完成；分别表达“草稿已保存并稍后处理”“后台归档处理中”“单独 Word 已导出”和“统一导出已完成”，后台状态不得阻断用户继续处理其他待办。
  - 验证：引导 Hook/组件/页面测试覆盖 deferred、queued、archiving、archive verified 待 GP/YP、单独 Word 成功和统一导出成功，断言不出现固定题号或虚假统一完成态。
- [ ] 6.7 完成反馈实现后重新核对 delta，修正 living spec 中“獙豸”为“獬豸”并同步本次新增场景；运行引导定向测试、`npm run verify:quick`、`npm run verify:docs:strict -- --change conversational-review-shell`、OpenSpec strict validate 与 `git diff --check`。
- [ ] 6.8 使用 SYNTHETIC/TEST 案件重新人工验收恢复与无损切换：保存失败/冲突、租约失效、图片绑定失败、图片读取容错、归档中断、模式切换焦点和三类终态；不得使用或提交真实案件数据、人员信息、设备编号或生成输出。

## 当前状态

- `implementation_status: reopened_for_feedback`：首轮 Layer 10 → Layer 11 → Layer 12 实现仍作为基线保留；第 6 节新增反馈尚未实现。
- `feedback_scope_status: requirements_updated_implementation_pending`：本次只更新 change 工件，未修改应用代码。
- `spec_sync_status: pending_resync`：living spec 仍反映首轮基线，待第 6 节实现与核对完成后再同步。

## 首轮基线证据

- `baseline_targeted_tests: PASS`：引导 Hook/组件/页面共 23 个 SYNTHETIC/TEST 用例通过；页面回归覆盖租约、autosave、图片绑定、归档、GP/YP、单独 Word 和统一导出。
- `baseline_level2_gates: PASS`：`lint:arch`、`typecheck`、`verify:quick`、scoped strict docs、OpenSpec strict validate 与 `git diff --check` 全部通过。
- `baseline_manual_acceptance: PASS`：使用临时 SYNTHETIC/TEST 页面执行桌面、125%、150%、窄屏布局及滚动验收；页级几何显示外层不滚动、历史独立滚动、对话不重叠。独立 Impeccable 完成度复核结论为 `ship`；3440 像素级截图因工具将文件硬裁为 1600×900，以 3440 DOM 几何无溢出证据代替。
