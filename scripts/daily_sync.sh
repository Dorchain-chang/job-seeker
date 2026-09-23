#!/usr/bin/env bash
# 每日抓取启动器（Linux/macOS cron 用）。
# 用法：  0 9 * * *  /path/to/job-seeker/scripts/daily_sync.sh >> /tmp/jobseeker.log 2>&1
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$HERE/.."

# 依次尝试：环境中的 python3 / 受管 python
PY="${PYTHON:-}"
if [ -z "$PY" ]; then
  if command -v python3 >/dev/null 2>&1; then
    PY=python3
  else
    echo "[ERROR] python3 not found" >&2
    exit 1
  fi
fi

"$PY" scripts/daily_sync.py "$@"
