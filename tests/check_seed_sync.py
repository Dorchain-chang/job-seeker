#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""本地守卫：全量快照与入库的公开快照必须同步。

背景（v49 实际踩过一次，排查成本远高于这一个断言）：
    seed.json（全量，含个人投递）不入库；seed.public.json（只含 jobs）入库。
    CI 拿不到全量快照，会回落到公开快照重建 dist/public —— 两者一旦不同步，
    远端 lint 的 `git diff --exit-code -- dist` 就会红，且报错信息指向 dist 而不是种子。

CI 里 seed.json 是从 seed.public.json 复制来的（Provide seed 步骤），两者必然一致，
所以本检查只在本地跑构建链之前有价值。无全量快照时 SKIP。

用法: python3 tests/check_seed_sync.py      # 退出码 0 = 通过 / 跳过
"""
import io
import json
import sys
from pathlib import Path

HERE = Path(__file__).parent
SEED_DIR = HERE.parent / "src" / "seed"
FULL = SEED_DIR / "seed.json"
PUB = SEED_DIR / "seed.public.json"


def main():
    if not FULL.exists():
        print("SEED_SYNC_SKIP  本机无全量快照（src/seed/seed.json），跳过")
        return 0
    if not PUB.exists():
        print("SEED_SYNC_FAIL  缺少入库的公开快照 %s" % PUB)
        return 1

    full = json.load(io.open(FULL, encoding="utf-8"))
    pub = json.load(io.open(PUB, encoding="utf-8"))
    problems = []

    if list(pub.keys()) != ["exportedAt", "jobs"]:
        problems.append("公开快照只应含 exportedAt + jobs（隐私），现为 %s" % list(pub.keys()))
    if full.get("exportedAt") != pub.get("exportedAt"):
        problems.append("exportedAt 不同步：全量 %r / 公开 %r" % (full.get("exportedAt"), pub.get("exportedAt")))

    # 顺序敏感：jobs 的先后会直接决定公开版渲染顺序，不能只比集合
    fj = json.dumps(full.get("jobs", []), ensure_ascii=False)
    pj = json.dumps(pub.get("jobs", []), ensure_ascii=False)
    if fj != pj:
        problems.append("jobs 不同步：全量 %d 条 / 公开 %d 条（改过全量快照就必须同步公开快照）"
                        % (len(full.get("jobs", [])), len(pub.get("jobs", []))))

    if problems:
        print("SEED_SYNC_FAIL")
        for p in problems:
            print("  -", p)
        print("  修法：重跑 scripts/daily_sync.py（save_seed 会自动同步），"
              "或跑 src/export_seed.py 重新导出")
        return 1

    print("SEED_SYNC_OK   全量 / 公开快照一致（jobs=%d）" % len(full.get("jobs", [])))
    return 0


if __name__ == "__main__":
    sys.exit(main())
