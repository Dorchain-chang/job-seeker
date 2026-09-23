# Job Seeker · 秋招岗位与投递管理台

> 一个为 2027 届校招求职定制的个人数字工作台：**把「看岗位」和「管投递」装进同一个页面。**
> 纯前端单文件应用（零运行时依赖），构建链产出四份发布形态：独立站点、合并版单文件、离线 Demo、四个独立页面。

- 在线站点：<https://job-hunt-desk-78822.app.workbuddy.host/>
- GitHub Pages 演示（离线数据版）：由 CI 自动发布
- 更新日志：[CHANGELOG.md](CHANGELOG.md)

[![Lint](https://github.com/Dorchain-chang/job-seeker/actions/workflows/lint.yml/badge.svg)](https://github.com/Dorchain-chang/job-seeker/actions/workflows/lint.yml)

## 功能

- **岗位看板**：秋招 / 央国企 / 实习三张表，牛客校招日程每日自动同步（增量、不覆盖用户数据）
- **投递跟踪**：阶段流转、时间线复盘、收件箱情报（邮件解析入表）
- **AI 套件**：简历解析、岗位匹配打分、面试复盘、投递画像、邮件解析、推荐点评、知识库问答（本地 RAG）；支持 BYOK 与零配置免费通道
- **Agent 调参台**：全局人设 + 逐功能参数（温度 / top_p / 惩罚 / 模型覆盖 / 输出格式）+ A/B 对比 + 调用 trace
- **数据自主**：全部数据存浏览器本机（`qz_*` 键），一键导出 / 导入 JSON 备份

## 目录结构

```
job-seeker/
├── src/                      # 构建链（唯一事实源）
│   ├── build_pages.py        #   生成 4 个独立页面（Vercel 风 UI + 全部功能）
│   ├── build_single.py       #   合并为单文件应用（四模块 + 侧栏路由）
│   ├── build_demo.py         #   产出离线 Demo（localStorage mock，无生产链接）
│   ├── build_site.py         #   产出独立站点（内嵌数据快照 + 增量同步适配层）
│   ├── export_seed.py        #   从资料库数据表导出快照 → seed/seed.json
│   ├── canonical_schema.json #   字段规范（构建输入）
│   └── seed/seed.json        #   站点数据快照（每日抓取后重新导出）
├── scripts/                  # 运维与数据管道（手动 / 自动化调用）
│   ├── deploy_pages.py       #   推送合并版到资料库 4 个节点
│   ├── sync_interns.py       #   牛客实习批次同步（含技术岗标注）
│   ├── sync_nowcoder_autumn.py / sync_autumn_all.py / backfill_nowcoder.py
│   └── mail_bridge.py        #   IMAP 邮箱 → 收件箱表（授权码走本地配置，不入库）
├── tests/                    # 检查与冒烟（CI 全量执行）
│   ├── check_escapes.py      #   拦截「Python 模板串吃掉 JS 转义」类静默故障
│   ├── check_inline_js.py    #   抽取内联 <script> 交 node --check
│   ├── check_workflows.py    #   校验 workflow YAML 可解析
│   ├── check_js.js           #   本地快速 JS 语法检查（node tests/check_js.js dist）
│   ├── smoke_browser.js      #   真实 Chromium 冒烟（mock SDK，覆盖渲染/筛选/上传/AI 面板）
│   ├── smoke_site.js         #   站点增量同步回归（灌入 / 合并 / 幂等 / 删除标记）
│   └── fixtures/             #   测试夹具（PDF / DOCX 简历样本）
├── dist/                     # 构建产物（入库；CI 门禁保证与 src/ 一致）
│   ├── 00-总览台.html        #   合并版单文件（生产形态，推 4 节点 / 建独立站点）
│   ├── 0{1,2,3}-*.html       #   4 个独立页面
│   ├── demo/index.html       #   GitHub Pages 演示
│   └── site/index.html       #   独立站点
└── docs/                     # 历史规划文档
```

## 构建链

顺序铁律，缺一步冒烟会读错 ID：

```bash
python3 src/build_pages.py    # ① 4 个独立页
python3 src/build_single.py   # ② 合并版（dist/00-总览台.html）
python3 src/build_demo.py     # ③ 离线 Demo
python3 src/build_site.py     # ④ 独立站点（需先有 src/seed/seed.json）
```

## 测试

```bash
python3 tests/check_workflows.py && python3 tests/check_inline_js.py && python3 tests/check_escapes.py
NODE_PATH=<playwright-core 所在 node_modules> node tests/smoke_browser.js
NODE_PATH=<playwright-core 所在 node_modules> node tests/smoke_site.js     # 需先跑构建 ②④
```

CI（`.github/workflows/lint.yml`）在每次 push 时执行：YAML 解析 → 内联 JS 语法 → 转义守卫 → demo 自包含 → 合并版标记 → **重跑构建后 `git diff --exit-code -- dist`**（产物必须与源码一致）→ 页数校验 → 真浏览器双冒烟。

## 数据管道

- **每日抓取**（外部自动化，非本仓库 CI）：牛客校招日程 → 资料库数据表 → `export_seed.py` 重导快照 → `build_site.py` 重建 → 重新发布独立站点；站点打开时按牛客ID 增量合并，不动用户已有投递状态
- **手动部署**：`printf '<token>\n' | python3 scripts/deploy_pages.py`（推送合并版到资料库 4 节点）
- **更新岗位数据**：`printf '<token>\n' | python3 src/export_seed.py` → 重跑构建 ④ → 重新发布

## 约定

- 数据表：秋招 `GgZ71tywhs4HEZytFSqXTP` / 投递 `oBGkMFTv9Xv4Xn5gFOK18S` / 实习 `tgH8096uENTaIj8RSY9qm5` / 收件箱 `EdCHnKtjZIXEw37tUmvhqL`
- 用户数据只存浏览器本机；唯一写云动作均需人工确认
- 大段共享 JS 写成独立常量挂拼接链（`THEME_JS` / `AI_CORE_JS` / `MATCH_JS` 等），见 `src/build_pages.py`
