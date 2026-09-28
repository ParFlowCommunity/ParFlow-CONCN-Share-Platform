#!/usr/bin/env bash
# Uses the activated conda environment; each service stays in the foreground.
set -euo pipefail
PROJECT_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
ACTION="${1:-help}"
case "$ACTION" in
    web)
        cd "$PROJECT_ROOT/backend"
        exec python -B -u app.py
        ;;
    worker)
        cd "$PROJECT_ROOT/backend"
        exec python -B -u -m datahub.workers.queue
        ;;
    build)
        cd "$PROJECT_ROOT/frontend"
        exec npm run build
        ;;
    check)
        cd "$PROJECT_ROOT/backend"
        python -B -c 'from datahub import config; import os, urllib.request; port = int(os.environ.get("CONCN_PORT", "8000")); client = urllib.request.build_opener(urllib.request.ProxyHandler({})); print(client.open(f"http://127.0.0.1:{port}/api/health", timeout=10).read().decode())'
        ;;
    help|-h|--help)
        echo '用法：bash scripts/run-linux.sh {web|worker|build|check}'
        echo '先 conda activate concnshare；web 与 worker 分别在独立终端运行。'
        ;;
    *)
        echo "未知操作：$ACTION" >&2
        exit 2
        ;;
esac
