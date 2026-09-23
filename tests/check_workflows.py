#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""自检 .github/workflows/*.yml 能不能被 YAML 解析。

workflow 文件写坏时，GitHub 只给一个「0 个 job、不到 1 秒就挂」的红色运行，
连日志都没有，很难定位。所以在 CI 最前面先把语法问题挡掉。

本地：python3 tests/check_workflows.py（需要 PyYAML）
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# CI 里仓库根 == 项目根；本地开发时 workflow 在 github_repo/ 子目录下，两种都认
WF_DIR = ROOT / ".github" / "workflows"
if not WF_DIR.is_dir():
    alt = ROOT / "github_repo" / ".github" / "workflows"
    if alt.is_dir():
        WF_DIR = alt


def main() -> int:
    try:
        import yaml
    except ImportError:
        print("SKIP pyyaml not installed, skip workflow YAML check")
        return 0

    files = sorted(WF_DIR.glob("*.y*ml"))
    if not files:
        print("FAIL no workflow file found under .github/workflows/")
        return 1

    failed = []
    for f in files:
        try:
            data = yaml.safe_load(f.read_text(encoding="utf-8"))
        except yaml.YAMLError as exc:
            print("FAIL %s" % f.name)
            for line in str(exc).splitlines():
                print("     %s" % line)
            failed.append(f.name)
            continue

        if not isinstance(data, dict) or not data.get("jobs"):
            print("FAIL %s  (缺少 jobs 段)" % f.name)
            failed.append(f.name)
            continue
        print("OK   %s" % f.name)

    if failed:
        print("FAIL %d workflow file(s) invalid" % len(failed))
        return 1
    print("OK   workflow YAML ok (%d file(s))" % len(files))
    return 0


if __name__ == "__main__":
    sys.exit(main())
