---
target: 截图中的草稿已保存并稍后处理状态
total_score: 21
max_score: 40
na_heuristics:
p0_count: 0
p1_count: 2
timestamp: 2026-09-09T13-46-53Z
slug: kages-frontend-src-components-guidedreviewview-tsx
---
Method: dual-agent (A: /root/design_assessment · B: /root/detector_assessment)

## Design Health Score

| # | Heuristic | Score | Key Issue |
|---|---|---:|---|
| 1 | Visibility of System Status | 2/4 | 已说明草稿保存和稍后处理，但完成态仍被展示成当前步骤。 |
| 2 | Match System / Real World | 2/4 | 文案说返回案件列表，实际产品入口称案件工作台。 |
| 3 | User Control and Freedom | 2/4 | 可返回上一步，但真正安全出口不是主操作。 |
| 4 | Consistency and Standards | 2/4 | success/complete 视觉与普通步骤导航语义冲突。 |
| 5 | Error Prevention | 3/4 | 自动保存说明降低丢失焦虑，但强主色后退按钮会诱导误操作。 |
| 6 | Recognition Rather Than Recall | 1/4 | 唯一可见操作是无常驻文字的左箭头；“现在压缩”入口需用户猜测。 |
| 7 | Flexibility and Efficiency | 2/4 | 有历史导航和事项中心，但缺少终态的一步式出口。 |
| 8 | Aesthetic and Minimalist Design | 3/4 | 卡片简洁清楚，但极简隐藏了关键下一步。 |
| 9 | Error Recovery | 2/4 | 可回看修改，但当前画面不说明左箭头会返回何处。 |
| 10 | Help and Documentation | 2/4 | 正文有指导，但指导词与实际控件名称不对应。 |
| **Total** | | **21/40** | **Acceptable；终态闭环需修正** |

## Design Specificity Verdict

用户的直觉是对的：`archive_deferred` 是“已选择稍后压缩后的完成/安全退出结果”，不是待用户继续完成的普通业务步骤。当前实现却把它加入可导航 action 集合，再以 complete/success 外观渲染，导致状态语义互相冲突。界面带有獬豸助手和电子数据检查术语，但完成态仍沿用通用 wizard 的“当前卡片 + 上一步箭头”，没有形成文枢自己的案件收尾闭环。

确定性 detector 对 `GuidedReviewView.tsx` 返回 0 findings。这说明按钮的 aria-label、组件结构等机械规则没有违规；它不能识别“成功终态为什么把倒退设为唯一显眼操作”这种运行时语义问题。截图、状态源和样式证据共同确认问题真实存在。

## Overall Impression

保存成功的文案本来能让用户放心，随后出现的孤立紫色左箭头却立刻破坏了完成感。最大机会不是改颜色，而是把该状态改造成明确的终态结果：告诉用户已经完成什么，并把正确去向放在同一个结果卡片里。

## What's Working

- “草稿已保存”“可安全返回”清楚传达数据安全，能降低高风险业务中的丢失焦虑。
- 状态已使用 success/complete 视觉，而不是警告色，视觉基调本身正确。
- 返回按钮已有 44px 触控尺寸、Tooltip、aria-label 和焦点样式，基础可访问性合格。

## Priority Issues

1. **[P1] 终态被伪装成当前步骤**
   - Why it matters: 用户无法判断流程是否真的完成，可能误以为还必须继续操作。
   - Fix: 将 `archive_deferred` 定义为 terminal outcome/milestone；可保留历史含义，但使用专用终态布局，不再作为普通待办步骤呈现。
   - Suggested command: `$impeccable clarify`

2. **[P1] 主操作层级完全反转**
   - Why it matters: 正文建议返回工作台，唯一高强调按钮却是返回上一步，诱导用户逆行和重复修改。
   - Fix: 卡片内设置主按钮“返回案件工作台”，次按钮“现在压缩”，把“返回上一步修改”降为低强调动作。
   - Suggested command: `$impeccable layout`

3. **[P2] “现在压缩”被藏进名不对应的事项入口**
   - Why it matters: “全部事项”和“已填内容与待办”需要用户自行做概念映射。
   - Fix: 终态卡片直接提供“现在压缩”或“重新选择压缩时机”。
   - Suggested command: `$impeccable clarify`

4. **[P2] 图标-only 后退不适合高风险终态**
   - Why it matters: 触屏没有稳定 Tooltip，用户也不知道将返回哪个具体事项。
   - Fix: 在终态使用带文字的“返回上一步修改”，必要时带上目标名称。
   - Suggested command: `$impeccable harden`

5. **[P3] 文案与构图缺少完成闭环**
   - Why it matters: “草稿已保存并稍后处理”混合了保存结果和压缩选择，“案件列表/案件工作台”也不一致。
   - Fix: 标题改为“草稿已保存”，状态摘要为“压缩已设为稍后处理”，统一使用“案件工作台”。
   - Suggested command: `$impeccable polish`

## Persona Red Flags

- **Jordan（首次使用者）**：看见“可安全返回案件列表”却找不到同名按钮；会把紫色左箭头当成必须执行的下一步。
- **Sam（无障碍用户）**：aria-label 可读，但“返回上一步”没有说明具体目标；终态、当前节点和成功状态仍依赖文案拼接。
- **Casey（易被打断的移动用户）**：回来后只看到醒目的逆向箭头，真正的退出动作没有与保存确认同屏分组。

## Minor Observations

- standalone 导航脱离消息卡悬空，既不像卡片操作，也不像全局导航。
- `archive_deferred` 与“请选择压缩时机”同时出现在 action 集合时，若不区分“结果”和“可选后续”，会被理解为两个并列待办。
- 这不是删除后退能力的问题，而是应改变它在终态中的语义角色和视觉权重。

## Questions to Consider

- 完成后的第一推荐动作是否应该无条件是“返回案件工作台”？
- “稍后压缩”需要成为历史里程碑，还是只需要成为案件状态摘要？
- 用户若想反悔，最自然的动作是“现在压缩”还是“重新选择压缩时机”？
