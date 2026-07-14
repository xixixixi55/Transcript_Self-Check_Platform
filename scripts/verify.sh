#!/usr/bin/env bash
# verify.sh — 代码验证门控脚本
#
# 用法：
#   bash scripts/verify.sh         完整验证（等同于 verify:full）
#   bash scripts/verify.sh quick   快速验证（等同于 verify:quick）
#   bash scripts/verify.sh full    完整验证
#
# 推荐使用 npm 命令：npm run verify:quick / npm run verify:full

set -e

MODE="${1:-full}"

if [ "$MODE" = "quick" ]; then
  echo "═══════════════════════════════════════"
  echo "  🔍 快速验证 (verify:quick)"
  echo "═══════════════════════════════════════"
  echo ""

  echo "▶ [1/3] 架构约束检查 (lint:arch)..."
  npx tsx scripts/lint-arch.ts
  echo ""

  echo "▶ [2/3] TypeScript 类型检查 (tsc)..."
  pnpm typecheck
  echo "✅ TypeScript 类型检查通过"
  echo ""

  echo "▶ [3/3] 文档检查（默认模式）..."
  npx tsx scripts/check-docs.ts
  echo ""

  echo "═══════════════════════════════════════"
  echo "  ✅ 快速验证通过！"
  echo "═══════════════════════════════════════"
elif [ "$MODE" = "full" ] || [ -z "${1:-}" ]; then
  echo "═══════════════════════════════════════"
  echo "  🔍 完整验证 (verify:full)"
  echo "═══════════════════════════════════════"
  echo ""

  echo "▶ [1/4] 架构约束检查 (lint:arch)..."
  npx tsx scripts/lint-arch.ts
  echo ""

  echo "▶ [2/4] TypeScript 类型检查 (tsc)..."
  pnpm typecheck
  echo "✅ TypeScript 类型检查通过"
  echo ""

  echo "▶ [3/4] 构建验证..."
  pnpm build
  echo "✅ 构建通过"
  echo ""

  echo "▶ [4/4] 文档检查（严格模式）..."
  npx tsx scripts/check-docs.ts --strict
  echo ""

  echo "═══════════════════════════════════════"
  echo "  ✅ 完整验证通过！"
  echo "═══════════════════════════════════════"
else
  echo "❌ 未知参数: $MODE"
  echo "用法：bash scripts/verify.sh [quick|full]"
  exit 1
fi
