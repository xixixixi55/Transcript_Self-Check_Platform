#!/usr/bin/env bash
# verify.sh — 代码验证门控脚本
#
# 运行代码层面的检查：架构约束 + 类型检查 + 构建验证
# 用法：npm run verify

set -e

echo "═══════════════════════════════════════"
echo "  🔍 笔录自检平台（文枢）— 综合验证"
echo "═══════════════════════════════════════"
echo ""

# Step 1: 架构约束检查
echo "▶ [1/3] 架构约束检查 (lint:arch)..."
npx tsx scripts/lint-arch.ts
echo ""

# Step 2: TypeScript 类型检查
echo "▶ [2/3] TypeScript 类型检查 (tsc)..."
pnpm typecheck
echo "✅ TypeScript 类型检查通过"
echo ""

# Step 3: 构建验证
echo "▶ [3/3] 构建验证..."
pnpm build
echo "✅ 构建通过"
echo ""

echo "═══════════════════════════════════════"
echo "  ✅ 所有验证通过！"
echo "═══════════════════════════════════════"
