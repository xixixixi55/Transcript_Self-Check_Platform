# Tasks: 默认对话式审核外壳

workflow_level: 2

> 目标：案件审核地址默认只展示对话式引导，上方为历史处理轨迹，下方为当前对话和操作；现有完整审核编辑按用户操作切换显示。两种视图共用现有案件会话和全部业务机制；本包只改变前端展示与导航，不创建第二套业务流程。

## 1. 关联结论与边界

- [x] 复用 `review-page-modern-government-ui` 已实现的待核对派生、字段定位、响应式审核布局和可访问交互，但按用户要求以独立包承载默认对话式外壳，不改写该包的既有任务与 delta。
- [x] 复用 `audit-edit-enhancement` 已实现的字段、检查人员、检材、文号、图片和导出控件；默认检查人员信息完整时不重复询问，不修改默认设置或人员快照机制。
- [x] 复用 `background-compression-archive-completion` 已实现的立即/稍后压缩、后台状态、GP/YP 介质映射和统一导出；不修改归档状态机、容量档位、Manifest、CAS 或导出合同。
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

## 实施证据

- `implementation_status: complete`：Layer 10 → Layer 11 → Layer 12 已按顺序实施，不含后端、数据库、共享 DTO 或生成管线修改。
- `targeted_tests: PASS`：引导 Hook/组件/页面共 23 个 SYNTHETIC/TEST 用例通过；页面回归继续覆盖租约、autosave、图片绑定、归档、GP/YP、单独 Word 和统一导出。
- `level2_gates: PASS`：`lint:arch`、`typecheck`、`verify:quick`、scoped strict docs、OpenSpec strict validate 与 `git diff --check` 全部通过。
- `manual_acceptance: PASS`：使用临时 SYNTHETIC/TEST 页面执行桌面、125%、150%、窄屏布局及滚动验收；页级几何显示外层不滚动、历史独立滚动、对话不重叠。独立 Impeccable 完成度复核结论为 `ship`；3440 像素级截图因工具将文件硬裁为 1600×900，以 3440 DOM 几何无溢出证据代替。
- `spec_sync_status: synced`：`REQ-GUIDED-REVIEW-SHELL` 已同步到 living spec，本包仍保持未归档状态。
