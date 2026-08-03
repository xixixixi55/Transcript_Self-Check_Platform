#!/usr/bin/env bash
# pre-commit.sh — 提交前快速检查
#
# 用法：bash scripts/pre-commit.sh（或通过 npm run pre-commit）
# 执行快速验证：架构检查 + 类型检查 + 文档检查（默认模式）
#
# 注意：Husky (.husky/pre-commit) 现在直接调用 npm run verify:quick，
# 不再经过本脚本。本脚本保留作为 legacy wrapper，供习惯直接调用的开发者使用。

set -e

echo "═══════════════════════════════════════"
echo "  🚦 Pre-commit Check (快速验证)"
echo "═══════════════════════════════════════"
echo ""

bash scripts/verify.sh quick
echo ""

echo "═══════════════════════════════════════"
echo "  ✅ Pre-commit 通过！"
echo "  💡 当前变更推送前建议运行：npm run verify:full -- --change <name>"
echo "═══════════════════════════════════════"
