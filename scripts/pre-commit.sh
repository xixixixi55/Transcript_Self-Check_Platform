#!/usr/bin/env bash
# pre-commit.sh — 提交前自动检查
#
# 用法：npm run pre-commit
# 由 .husky/pre-commit 自动触发

set -e

echo "═══════════════════════════════════════"
echo "  🚦 Pre-commit Check"
echo "═══════════════════════════════════════"
echo ""

# 1. 架构约束 + 类型 + 构建
echo "▶ [1/3] 代码验证..."
bash scripts/verify.sh
echo ""

# 2. 自动化测试
echo "▶ [2/3] 自动化测试..."
pnpm test
echo ""

# 3. 文档一致性
echo "▶ [3/3] 文档一致性检查..."
npx tsx scripts/check-docs.ts
echo ""

echo "═══════════════════════════════════════"
echo "  ✅ Pre-commit 全部通过，可以提交！"
echo "═══════════════════════════════════════"
