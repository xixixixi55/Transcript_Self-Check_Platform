---
target: 獬豸助手当前对话体验
total_score: 24
max_score: 40
na_heuristics:
p0_count: 0
p1_count: 3
timestamp: 2026-08-27T13-11-09Z
slug: kages-frontend-src-components-guidedreviewview-tsx
---
# 獬豸助手对话体验评审

Method: dual-agent (A: xiezhi_design_review · B: xiezhi_evidence_review)

## Design Health Score

| # | Heuristic | Score | Key Issue |
|---|---|---:|---|
| 1 | Visibility of System Status | 3/4 | 待处理数量与只读告警可见，但动作后的处理中与完成过渡不足 |
| 2 | Match System / Real World | 3/4 | 办案术语大体准确，“编辑租约”等内部表达仍需转译 |
| 3 | User Control and Freedom | 2/4 | 有返回与旁路，强制接管的影响和替代路径不清楚 |
| 4 | Consistency and Standards | 3/4 | 组件一致，但对话与审核工具仍是两套交互语法 |
| 5 | Error Prevention | 2/4 | 能识别只读风险，高影响动作缺少充分的前置说明 |
| 6 | Recognition Rather Than Recall | 3/4 | 历史和事项入口可见，仍需跨滚动区拼合上下文 |
| 7 | Flexibility and Efficiency | 2/4 | 有非线性入口，缺少专家加速与键盘线索 |
| 8 | Aesthetic and Minimalist Design | 2/4 | 历史区过重，当前任务偏弱，焦点分配失衡 |
| 9 | Error Recovery | 2/4 | 提供强制接管，但原因、影响和失败恢复解释不足 |
| 10 | Help and Documentation | 2/4 | 高风险决策点缺少情境化帮助 |
| **Total** | | **24/40** | **Acceptable — significant improvements needed** |

## Design Specificity Verdict

**LLM assessment:** 产品语义有专属性，交互语法仍偏通用。历史处理轨迹、当前待办、恢复编辑权限等明显属于电子数据检查笔录场景；但布局仍是可替换文案后用于客服工单或审批后台的“时间线 + 助手插画 + 表单卡片 + 工具按钮”。它缺的不是更多气泡，而是办件状态如何被助手实时接住、解释并推动的专有交互语法。

**Deterministic scan:** `detect.mjs` 对 `packages/frontend/src/components/GuidedReviewView.tsx` 返回 0 项，exit 0，无误报。自动规则干净但体验仍僵硬，说明根因不是常见 CSS 反模式，而是信息主次、轮次因果和状态编排。

**Browser evidence:** 未获得可靠的用户可见检测覆盖层，因为浏览器 evaluate 为只读，无法完成可变脚本注入。回退证据采用 CLI JSON、DOM、computed geometry、滚动指标和控制台日志。桌面无页面级水平溢出；390px 下固定侧栏后主区只剩 310px，对话内容可见宽约 194px，回复区域超出内容列 26px并被内部裁切。

## Overall Impression

当前界面只有对话的外形，没有对话的因果连续性。用户操作后主要看到整块内容替换，而不是“已接收—核验中—已完成—下一项”的可感知回应。最大的机会是把“上方日志 + 下方助手表单”改成状态驱动的办件舞台。

## What's Working

1. 专业边界明确：没有引入自由聊天，也没有把办案系统娱乐化。
2. 非线性能力存在：全部事项、已整理信息和完整审核编辑允许专业用户旁路校核。
3. 系统事实表达清楚：历史、状态标签与告警语义基本准确，视觉克制。

## Priority Issues

### [P1] 当前任务不是视觉主角

**Why it matters:** 历史轨迹占据桌面首屏大部分空间，当前事项接近下缘，容易被误认为辅助信息。

**Fix:** 将历史压缩成“已自动整理 4 条事实”的可展开摘要，只在当前轮带入一条相关事实。

**Suggested command:** `$impeccable layout`

### [P1] 轮次缺少因果连续性

**Why it matters:** 固定的“已收到，我继续提示下一项”不能证明系统理解了什么，用户感觉自己只是在提交表单。

**Fix:** 每次操作后在原位置依次呈现“已接收—正在核验—结果—下一项缘由”。仅保留上一轮和当前轮，不持久化自由聊天。

**Suggested command:** `$impeccable shape`

### [P1] 窄屏布局破坏对话空间

**Why it matters:** 390px 下固定侧栏、头像列和多个内部滚动区把消息压成窄文字柱，回复区还被裁切 26px。

**Fix:** 窄屏收起侧栏，头像改为 32–40px 行内身份标记，只保留一个主滚动容器，主操作进入可触达区。

**Suggested command:** `$impeccable adapt`

### [P2] 助手形象与状态没有联动

**Why it matters:** 獬豸只是装饰，无法帮助用户识别处理中、风险和完成；静态萌化形象在权限冲突时也可能削弱专业感。

**Fix:** 使用一次性的 120–180ms 状态环或确认反馈，并遵守 `prefers-reduced-motion`，不做持续动画。

**Suggested command:** `$impeccable animate`

### [P2] 其他操作与主任务竞争

**Why it matters:** 当前主动作与四个辅助入口同时可见，单个决策点超过四个选项。

**Fix:** 当前轮只保留一个主操作和一个安全退出，将全部事项、摘要和完整编辑合并成“审核工具”。

**Suggested command:** `$impeccable distill`

## Cognitive Load

8 项中约 4 项失败，属于偏高负荷：单一焦点、视觉层级、一次一件事、最少选择。分块、信息分组、工作记忆和渐进披露基本成立。问题不是信息总量，而是背景信息与当前决策没有拉开权重差。

## Emotional Journey

开场的自动识别与事实整理建立了可靠感；进入“编辑权限需要恢复/强制接管”时形成高摩擦低谷，但助手没有解释影响和可逆性。每轮完成后也没有明确呈现“解决了什么”，因此没有释放感、峰值和完成收束。

## Persona Red Flags

**Alex（熟练用户）：** 历史区拖慢定位；同级辅助入口降低扫描效率；没有明显键盘路径；固定确认文案很快显得机械。

**Jordan（首次用户）：** “编辑租约”和“强制接管”缺少通俗解释；不清楚是否影响另一页面或覆盖数据；历史看起来像必须阅读的步骤。

**Casey（窄屏用户）：** 固定侧栏与头像列挤占主内容；多重滚动打断空间连续性；主动作容易落在视口下方；中断后缺少“现在只需完成这一项”的恢复锚点。

## Minor Observations

- “2 项待处理”没有区分阻塞项与普通补全项。
- 历史轨迹继续增长后会成为日志墙。
- 窄屏结构化表单不适合继续模仿宽聊天气泡。
- 当前、背景、风险三层的明度差仍不够明显。
- 后续状态转场需避免通过 `role="status"` 反复播报整段内容。

## Questions to Consider

1. 首轮应优先做“轮次状态编排”“首屏重排”还是“移动端修复”？
2. 助手气质应保持“专业克制”，还是加入“克制但更有温度”的状态反馈？
3. 改造范围应覆盖全部五项，还是先完成三个 P1？
