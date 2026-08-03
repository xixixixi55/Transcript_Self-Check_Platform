#!/usr/bin/env bash
# verify.sh — package.json 验证入口兼容包装
#
# 用法：
#   bash scripts/verify.sh full --change <name>  全仓库工程检查；严格任务状态仅限当前变更包
#   bash scripts/verify.sh full:all              全局完整验证
#   bash scripts/verify.sh quick   快速验证（等同于 verify:quick）
#
# 推荐使用 npm 命令：npm run verify:quick / npm run verify:full -- --change <name>
#
set -euo pipefail

MODE="${1:-full}"
if [[ $# -gt 0 ]]; then
  shift
fi

case "$MODE" in
  quick)
    npm run verify:quick
    ;;
  full)
    npm run verify:full -- "$@"
    ;;
  full:all)
    npm run verify:full:all
    ;;
  *)
  echo "❌ 未知参数: $MODE"
  echo "用法：bash scripts/verify.sh quick"
  echo "      bash scripts/verify.sh full --change <name>"
  echo "      bash scripts/verify.sh full:all"
  exit 1
    ;;
esac
