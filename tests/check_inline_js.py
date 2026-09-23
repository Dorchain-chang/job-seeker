#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""抽取 dist/ 下构建产物里的内联 <script>，交给 `node --check` 做语法检查。

本地：python3 tests/check_inline_js.py
CI  ：.github/workflows/lint.yml 直接调用本文件。

为什么要单独一个脚本：如果把这段 python 直接写进 workflow 的 `run: |` 块标量，
顶格的代码行会被 YAML 当成块外内容，导致整个 workflow 解析失败
（GitHub 的表现是「0 个 job、秒挂」的红色运行，极难排查）。
"""
from __future__ import annotations

import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT_RE = re.compile(r"<script>\s*(.*?)\s*</script>", re.S)


def targets():
    """页面清单：dist/ 下的全部构建产物（4 独立页 + 合并版 + demo + site）。"""
    d = ROOT / "dist"
    found = sorted(d.glob("*.html")) + sorted(d.glob("demo/*.html")) + sorted(d.glob("site/*.html"))
    return [p for p in found if p.is_file()]


def main() -> int:
    node = shutil.which("node")
    if node is None:
        print("SKIP node not found, skip inline JS syntax check")
        return 0

    files = targets()
    if not files:
        print("FAIL no html pages found under dist/")
        return 1

    failed = []
    with tempfile.TemporaryDirectory() as tmp:
        for src in files:
            name = src.relative_to(ROOT).as_posix()
            chunks = SCRIPT_RE.findall(src.read_text(encoding="utf-8"))
            if not chunks:
                print("FAIL %s  (no inline <script>)" % name)
                failed.append(name)
                continue

            js_file = Path(tmp) / (src.stem + ".js")
            js_file.write_text("\n;\n".join(chunks), encoding="utf-8")
            proc = subprocess.run(
                [node, "--check", str(js_file)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
            )
            if proc.returncode == 0:
                print("OK   %s" % name)
            else:
                print("FAIL %s" % name)
                sys.stdout.write((proc.stderr or "").strip() + "\n")
                failed.append(name)

    if failed:
        print("FAIL %d file(s) have broken inline JS" % len(failed))
        return 1
    print("OK   inline JS syntax ok (%d file(s))" % len(files))
    return 0


if __name__ == "__main__":
    sys.exit(main())
