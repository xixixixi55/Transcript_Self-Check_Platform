---
name: harness-propose
description: "创建需求变更包并按 Harness 架构约束编排。当用户想要开发新功能、提出新需求、开始新迭代、说'我要做 XX 功能'、'新增 XX'、'propose'时触发。"
---

完整读取项目工具目录下的 `commands/harness/propose.md` 并执行。该命令是渐进式路由器：先关联活跃 change 和判断 Level，再按需读取当前阶段资料；不得预先加载完整 `iteration-guide.md`、`architecture.md` 或全部变更包正文。

输出必须包含关联结论、Level、实际读取的资料、创建/复用的工件和下一步。Level 1 不创建 change；Level 2 只使用 tasks + delta；Level 3 才进入完整 OpenSpec 流程。
