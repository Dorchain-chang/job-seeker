# Job Seeker · 秋招岗位与投递管理台

> 一个为 2027 届校招求职定制的个人数字工作台：**把「看岗位」和「管投递」装进同一个页面。**
> 纯前端单文件应用（零运行时依赖），构建链产出五份发布形态：独立站点、公开版站点、合并版单文件、离线 Demo、四个独立页面。

- **公开版（交付 / 分享用，推荐）**：<https://dorchain-chang.github.io/job-seeker/> —— 只内置岗位快照，不含作者任何个人数据
- 演示版（离线 mock 数据）：<https://dorchain-chang.github.io/job-seeker/demo/>
- 私人版（作者自用，含个人投递数据）：<https://job-hunt-desk-78822.app.workbuddy.host/>
- 更新日志：[CHANGELOG.md](CHANGELOG.md)

[![Lint](https://github.com/Dorchain-chang/job-seeker/actions/workflows/lint.yml/badge.svg)](https://github.com/Dorchain-chang/job-seeker/actions/workflows/lint.yml)

## 功能

- **岗位看板**：秋招 / 央国企 / 实习三张表，牛客校招日程每日自动同步（增量、不覆盖用户数据）
- **投递跟踪**：阶段流转、时间线复盘、收件箱情报（邮件解析入表）
- **投递闭环**：点「投递」跳出去网申，回到页面自动问一句「投了吗？」——选「投了」就同时记好岗位状态与投递进度；统计卡与投递漏斗同一口径，已标已投但没进度的会提示一键补齐
- **AI 套件**：简历解析、岗位匹配打分、面试复盘、投递画像、邮件解析、推荐点评、知识库问答；支持 BYOK 与零配置免费通道
- **有界 Agentic RAG 知识库**：自适应路由（不检索 / 单轮 / 多跳拆子查询）→ 混合检索（原话 2-gram BM25 ＋ 求职术语扩展路，分数级融合）→ 一级结构化精排 → 证据自评（CRAG 思路）→ 自愈重写重检（≤3 轮）→ 引用式作答 → 【序号】引用校验；证据不足直接**拒答**而不是硬编，每次问答都附「闭环轨迹」可查。检索 / 自评 / 改写 / 校验全在本机，零 token，只有最终生成走模型
- **RAG 评测台**：本机自动出题（公司题 / 城市题 / 口语方向题 / 领域外题），一次跑批给出 `HitRate@5 / Recall@5 / MRR / nDCG@5 / ContextPrecision@5`，并支持「混合检索 ↔ 单路 BM25」A/B 对比与 Markdown 报告导出——调参不靠感觉
- **Agent 调参台**：全局人设 + 逐功能参数（温度 / top_p / 惩罚 / 模型覆盖 / 输出格式）+ A/B 对比 + 调用 trace
- **数据自主**：全部数据存浏览器本机（私人版 `qz_*` / 公开版 `qc_*` 键），一键导出 / 导入 JSON 备份
- **宽屏铺满**：桌面全屏时内容宽度随视口分级（1100 → 1820px），岗位/投递卡片与各类清单自动两栏、三栏排布，不留大片空白；个人知识库、定时任务、求职助理都带语料概览 / 快速模板 / 示例问题等上手引导
- **可分享的公开版**：同一套功能，但**岗位库由访客自选起点**（用内置快照，或从空白开始自己记），个人数据一律留在访客本机

## 使用方式

打开 <https://dorchain-chang.github.io/job-seeker/> 即可，**无需安装、无需登录、无需配置**：

1. **首次打开二选一**：「用内置岗位快照开始」（含 724 条秋招岗位）或「从空白开始，只记我自己的投递」
2. 所有数据都存在**你自己浏览器的本机存储**（localStorage）里，不上传任何服务器
3. 换设备或清缓存前，用侧栏底部的「导出备份」存一份 JSON；在新浏览器「导入备份」即可完整迁移
4. AI 功能默认走零配置免费通道；填入自己的 API Key（BYOK）可切换到自选模型
5. 想自己部署：`git clone` 后按下方「构建链」跑五步，`dist/public/index.html` 就是可直接托管的单文件

## 目录结构

```
job-seeker/
├── src/                      # 构建链（唯一事实源）
│   ├── build_pages.py        #   生成 4 个独立页面（Vercel 风 UI + 全部功能）
│   ├── build_single.py       #   合并为单文件应用（四模块 + 侧栏路由）
│   ├── build_demo.py         #   产出离线 Demo（localStorage mock，无生产链接）
│   ├── build_site.py         #   产出独立站点（内嵌数据快照 + 增量同步适配层）
│   ├── build_public.py       #   产出公开版站点（快照只含岗位，访客自选起点，qz_ → qc_）
│   ├── export_seed.py        #   从资料库数据表导出全量快照 → seed/seed.json（需 token）
│   ├── canonical_schema.json #   字段规范（构建输入）
│   └── seed/
│       ├── seed.public.json  #   公开快照（只含岗位）—— **入库**，CI 与本机兜底都用它
│       └── seed.json         #   全量快照（含个人投递）—— **不入库**，本机 export_seed/daily_sync 生成
├── scripts/                  # 运维与数据管道（手动 / 自动化调用）
│   ├── daily_sync.py         #   ★ 每日抓取（零 token 独立版，见下「每日抓取」）
│   ├── daily_sync.bat/.sh    #   ★ 计划任务 / cron 启动器（自动探测 Python）
│   ├── deploy_pages.py       #   推送合并版到资料库 4 个节点（需 token）
│   ├── sync_interns.py       #   牛客实习批次同步（写资料库，需 token）
│   ├── sync_nowcoder_autumn.py / sync_autumn_all.py / backfill_nowcoder.py
│   └── mail_bridge.py        #   IMAP 邮箱 → 收件箱表（授权码走本地配置，不入库）
├── tests/                    # 检查与冒烟（CI 全量执行）
│   ├── check_escapes.py      #   拦截「Python 模板串吃掉 JS 转义」类静默故障
│   ├── check_inline_js.py    #   抽取内联 <script> 交 node --check
│   ├── check_workflows.py    #   校验 workflow YAML 可解析
│   ├── check_js.js           #   本地快速 JS 语法检查（node tests/check_js.js dist）
│   ├── smoke_browser.js      #   真实 Chromium 冒烟（mock SDK，覆盖渲染/筛选/上传/AI 面板）
│   ├── smoke_site.js         #   站点回归：SMOKE_MODE=site/public 跑两种离线产物（灌入/合并/幂等/删除标记/起点选择）
│   └── fixtures/             #   测试夹具（PDF / DOCX 简历样本）
├── dist/                     # 构建产物（入库；CI 门禁保证与 src/ 一致）
│   ├── 00-总览台.html        #   合并版单文件（生产形态，推 4 节点 / 建独立站点）
│   ├── 0{1,2,3}-*.html       #   4 个独立页面
│   ├── demo/index.html       #   离线 Demo（GitHub Pages 的 /demo/ 子路径）
│   ├── site/index.html       #   私人站点版（含个人数据快照）—— **不入库**
│   └── public/index.html     #   公开版（GitHub Pages 站根，对外交付形态）
└── docs/                     # 历史规划文档
```

## 构建链

顺序铁律，缺一步冒烟会读错 ID：

```bash
python3 src/build_pages.py    # ① 4 个独立页
python3 src/build_single.py   # ② 合并版（dist/00-总览台.html）
python3 src/build_demo.py     # ③ 离线 Demo
python3 src/build_site.py     # ④ 独立站点（需先有 src/seed/seed.json）
python3 src/build_public.py   # ⑤ 公开版站点（复用同一份 seed.json，只内嵌岗位表）
```

## 测试

```bash
python3 tests/check_workflows.py && python3 tests/check_inline_js.py && python3 tests/check_escapes.py
NODE_PATH=<playwright-core 所在 node_modules> node tests/smoke_browser.js
NODE_PATH=<playwright-core 所在 node_modules> node tests/smoke_site.js                  # 私人版站点，需先跑构建 ②④
NODE_PATH=<playwright-core 所在 node_modules> SMOKE_MODE=public node tests/smoke_site.js # 公开版站点，需先跑构建 ②④⑤
```

CI（`.github/workflows/lint.yml`）在每次 push 时执行：YAML 解析 → 内联 JS 语法 → 转义守卫 → demo 自包含 → 合并版标记 → **公开版隐私门禁**（解析快照 JSON：只允许 `exportedAt`/`jobs` 两个键、真实 databaseId 与 `qz_` 不得出现）→ **重跑构建后 `git diff --exit-code -- dist`**（产物必须与源码一致）→ 页数校验 → 真浏览器双冒烟（合并版 + 公开版）。

## 数据管道

### 每日抓取（推荐：零 token 独立版）

`scripts/daily_sync.py` 一条命令跑完全程，**不需要 token、不需要任何外部服务**：

```
牛客校招日程(tab=3) ──► src/seed/seed.json（增量合并）──► dist/site + dist/public
```

> `src/seed/seed.json` 是全量快照，**不入库**（含个人投递数据）。仓库里入库的是只含岗位的 `seed.public.json`；
> 在全新克隆的仓库上构建时若本机没有全量快照，`build_site.py` / `build_public.py` 会自动回落到它（公开版产出字节与用全量快照时完全一致）。

```bash
python3 scripts/daily_sync.py              # 抓取 + 合并 + 重建产物
python3 scripts/daily_sync.py --dry-run    # 只看会新增什么，不落盘
python3 scripts/daily_sync.py --no-build   # 只更新 seed.json
python3 scripts/daily_sync.py --max-new 60 # 每表单次最多新增（默认 60，0=不限）
```

退出码：`0` 有更新 / `2` 无新增（正常）/ `1` 出错。运行日志写 `scripts/daily_sync_last.log`。

**合并语义**（与站点端 `keyOf` 完全一致，保证两边口径统一）：

| 表 | 去重键 | 收录条件 |
| --- | --- | --- |
| 秋招 `jobs` | `牛客ID`（缺失回落 `公司`） | 网申未截止（放宽 1 天），不限岗位方向 |
| 实习 `interns` | `公司 + 岗位名称` | `batchName` 含「实习」且命中成都/北京/天津或远程/全国 |

**只追加、不改写**：已有岗位的优先级、投递状态、备注等用户数据一律保留；`apps`（投递）与 `inbox`（收件箱）**一字不动**。

**定时部署**（任选其一）：

```bat
:: Windows —— 任务计划程序，每天 09:00
schtasks /create /tn "JobSeeker每日抓取" /tr "<仓库>\scripts\daily_sync.bat" /sc daily /st 09:00
```

```bash
# Linux / macOS —— cron，每天 09:00
0 9 * * * /path/to/job-seeker/scripts/daily_sync.sh >> /tmp/jobseeker.log 2>&1
```

两个启动器都会**自动探测 Python**（受管版本 → PATH 里的 `python` → `py`），仓库放在任何路径（含中文/空格）都能跑。

### 需要写回资料库时（可选，需 token）

以下脚本会把数据同步到腾讯文档资料库的数据表，**必须先拿到 token**（由 WorkBuddy 连接器现场签发，30 分钟有效），从 stdin 首行传入：

```bash
printf '<token>\n' | python3 src/export_seed.py      # 资料库 → seed.json（反向导出基线）
printf '<token>\n' | python3 scripts/deploy_pages.py # 合并版 → 资料库 4 个节点
printf '<token>\n' | python3 scripts/sync_autumn_all.py
```

> ℹ️ 站点产物（`dist/site`、`dist/public`）**不依赖 token**：抓取 → 合并 → 重建这条链路全在本地跑完。
> token 只影响「同步到资料库在线表格」这一步，不影响站点数据更新。

## 约定

- 数据表：秋招 `GgZ71tywhs4HEZytFSqXTP` / 投递 `oBGkMFTv9Xv4Xn5gFOK18S` / 实习 `tgH8096uENTaIj8RSY9qm5` / 收件箱 `EdCHnKtjZIXEw37tUmvhqL`
- 用户数据只存浏览器本机；唯一写云动作均需人工确认
- **公开版是隐私边界**：只内嵌 `jobs` 表且剔除「示例预置」行，投递 / 实习 / 收件箱三表**不进产物**，localStorage 用独立的 `qc_*` 命名空间 —— 由 CI 隐私门禁强制
- **仓库里不含任何个人数据**：全量快照 `src/seed/seed.json` 与私人站点版产物 `dist/site/` 都被 `.gitignore` 排除，只存在于作者本机；入库的只有只含岗位的 `seed.public.json` 与对外形态 `dist/public/index.html`
- 大段共享 JS 写成独立常量挂拼接链（`THEME_JS` / `AI_CORE_JS` / `MATCH_JS` 等），见 `src/build_pages.py`
