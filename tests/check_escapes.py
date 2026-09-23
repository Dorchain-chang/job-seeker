#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""构建守卫：拦截「Python 模板串吃掉 JS 反斜杠转义」这一类静默故障。

背景（2026-09-14 实际踩到的坑）：
    build_pages.py / build_single.py 里的大段 JS 是用普通（非 raw）三引号串拼接的，
    于是 JS 里的 `\\u0000`、`\\x1f`、`\\b`、`\\v` 会被 Python 当成自己的转义先解析成真实
    控制字符写进 HTML。HTML 解析阶段又把裸控制字符替换成 U+FFFD，正则就变成
    「Range out of order in character class」，整页 <script> 直接语法错误、页面全白。
    这类故障 node --check 和 new Function 都发现不了（文件里是合法的 NUL 字节），
    只有真正用浏览器加载才会炸。

本脚本做两件事：
  1) 扫源文件里所有「会被 Python 解释」的反斜杠转义，命中即失败（\\n \\t 等刻意换行除外）；
  2) 扫构建产物里是否有裸控制字符（NUL / 0x01-0x1f / 0x7f），有即失败。

用法: python3 tests/check_escapes.py      # 退出码 0 = 通过
"""
import io
import re
import sys
from pathlib import Path

HERE = Path(__file__).parent
SRC_DIR = HERE.parent / "src"
SOURCES = ["build_pages.py", "build_single.py", "build_public.py"]
ARTIFACTS = sorted((HERE.parent / "dist").rglob("*.html"))

# Python 会解释的转义：\n \t \r \b \f \v \a \0 \xHH \uHHHH \N{..} \UHHHHHHHH
# \n \t 在模板里通常是刻意的换行/缩进，单独放行。
_ESCAPE_RE = re.compile(
    r"\\" + r"(?:[ntrbfva0]|x[0-9a-fA-F]{2}|u[0-9a-fA-F]{4}|N\{" + r"[^}]*\}|U[0-9a-fA-F]{8})"
)
_ALLOWED = {"\\n", "\\t"}


def scan_sources():
    bad = []
    for name in SOURCES:
        path = SRC_DIR / name
        if not path.exists():
            continue
        text = io.open(path, encoding="utf-8").read()
        for lineno, line in enumerate(text.splitlines(), 1):
            for m in _ESCAPE_RE.finditer(line):
                if m.group(0) in _ALLOWED:
                    continue
                bad.append(f"{name}:{lineno} 出现会被 Python 解释的转义 {m.group(0)!r}（请改成非转义写法或改用 raw 字符串）")
    return bad


def scan_artifacts():
    bad = []
    for path in ARTIFACTS:
        text = io.open(path, encoding="utf-8", errors="replace").read()
        for i, ch in enumerate(text):
            o = ord(ch)
            if o < 32 and ch not in "\n\r\t":
                bad.append(f"{path.name}: 偏移 {i} 存在裸控制字符 U+{o:04X}（HTML 解析会变 U+FFFD，正则可能整页失效）")
                break
            if o == 127:
                bad.append(f"{path.name}: 偏移 {i} 存在 DEL 字符 U+007F")
                break
    return bad


def main():
    problems = scan_sources() + scan_artifacts()
    if problems:
        print("ESCAPE_CHECK_FAIL")
        for p in problems:
            print("  -", p)
        return 1
    print(f"ESCAPE_CHECK_OK  源文件 {len(SOURCES)} 个 / 产物 {len(ARTIFACTS)} 个均无隐患")
    return 0


if __name__ == "__main__":
    sys.exit(main())
