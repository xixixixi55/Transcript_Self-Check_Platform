# 目录结构

> 本文件是 AGENTS.md "目录结构"部分的详细版本。
> 检查粒度为**目录级别**：新增目录 MUST 同步更新此文件，新增文件无需逐个列出。
> 关键入口文件（如 index.ts、layout.tsx 等）SHOULD 列出以帮助导航，但不作为门控条件。

```
笔录自检平台（文枢）/
│
├── AGENTS.md                              # 🗺️ Agent 导航入口
│
├── harness.config.yaml                    # 🔧 Harness 项目配置
│
├── package.json                           # 📦 根包管理（pnpm workspace）
├── pnpm-workspace.yaml                    # 📦 工作区配置
├── tsconfig.json                          # 🔧 根 TypeScript 配置
│
├── openspec/                              # 📋 OpenSpec（内容：需求 + 设计 + 任务）
│   ├── config.yaml                        # 🔧 项目配置（上下文 + 规则）
│   ├── specs/                             # 📋 当前生效的能力 spec（单一真相源）
│   │   ├── data-model.md                  #    💾 数据模型定义
│   │   ├── electronic-inspection-record/  #    📋 电子数据检查笔录
│   │   └── harness-workflow/              #    🛡️ Level 2 工作流合同
│   └── changes/                           # 🔄 变更管理
│       └── archive/                       #    归档（完成的变更包）
│
├── harness/                               # 🛡️ Harness（骨架：流程 + 约束 + 验证）
│   ├── architecture.md                    # 📐 架构约束详情
│   ├── data-model.md                      # 💾 数据建模约束
│   ├── tasks.md                           # ✅ 任务管理规则 + 模板
│   ├── iteration-guide.md                 # 🔄 迭代流程指南
│   ├── entropy-rules.md                   # 🧹 熵治理规则
│   ├── level2-spec-migration-ledger.md     # 🧾 Level 2 living spec 迁移台账
│   ├── directory.md                       # 🗂️ 本文件（目录结构）
│   └── archive/                           # 📦 归档
│       └── iterations/                    #    迭代记录归档
│
├── scripts/                               # 🔨 门控脚本
│   ├── lint-arch.ts                       #    架构约束检查
│   ├── check-docs.ts                      #    文档一致性检查
│   ├── verify.sh                          #    综合验证
│   └── pre-commit.sh                      #    提交前门控
│
├── packaging/                             # 📦 Windows 便携发布清单、PyInstaller 规格和许可声明
│
├── packages/                              # 📦 Monorepo 包
│   ├── shared/                            # 🔗 共享包（Layer 0-2）
│   │   ├── types/                         # Layer 0: 实体、DTO、API 契约
│   │   │   └── index.ts                   #    聚合导出
│   │   ├── constants/                     # Layer 1: 错误码、枚举
│   │   │   └── index.ts                   #    聚合导出
│   │   └── utils/                         # Layer 2: 校验、格式化
│   │       └── index.ts                   #    聚合导出
│   │
│   ├── frontend/                          # 🎨 前端 (React) — Layer 10-12
│   │   └── src/
│   │       ├── hooks/                     # Layer 10: 状态管理
│   │       ├── components/                # Layer 11: UI 组件
│   │       └── pages/                     # Layer 12: 页面路由
│   │
│   ├── backend/                           # ⚙️ 后端 (FastAPI) — Layer 20-23
│       └── app/
│           ├── repository/                # Layer 20: 数据访问
│           │   ├── archive/               #    归档计划、清单、输入快照与发布状态持久化
│           │   ├── case/                  #    案件工作台、生命周期、留存与资源持久化
│           │   └── report/                #    报告格式识别、内容解析与输入快照构建
│           ├── services/                  # Layer 21: 业务逻辑
│           │   ├── archive/               #    归档规划、执行、恢复、发布与运行时协调
│           │   ├── case/                  #    案件草稿、生命周期、资源、提交与留存
│           │   └── report/                #    报告解析、缓存、错误投影与请求协调
│           ├── controllers/               # Layer 22: 请求处理
│           └── routes/                    # Layer 23: 路由定义
│   └── launcher/                          # 🪟 Windows 便携版启动器
│
├── word_templates/                        # 📄 正式运行 Word 模板（template.docx）
├── reports/                               # 📥 HTML 取证报告（输入）
├── output/                                # 📤 生成输出
│   ├── parsed/                            #    解析缓存 JSON
│   ├── compressed/                        #    RAR 压缩包
│   └── exports/                           #    导出 .docx
│
├── tests/                                 # 🧪 测试
│   └── e2e/                               #    E2E 测试（规划中，Playwright 待建设）
│
├── packages/shared/__tests__/              # 🧪 Shared 层测试
├── packages/frontend/src/__tests__/        # 🧪 前端测试
├── packages/backend/app/data/              # ⚙️ 后端配置数据
│
└── .husky/                                # 🪝 Git Hooks
    └── pre-commit                         #    提交前门控
```
