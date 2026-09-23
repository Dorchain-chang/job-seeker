# 更新日志（CHANGELOG）

Job Seeker · 秋招岗位与投递管理台。按版本倒序记录，日期为提交日期。

- 在线站点：<https://job-hunt-desk-78822.app.workbuddy.host/>
- 仓库：<https://github.com/Dorchain-chang/job-seeker>（v42 起迁移至此；旧仓库 [Dorchain-chang/-](https://github.com/Dorchain-chang/-) 为 v27–v41 历史，只读归档）
- GitHub Pages 演示（离线数据版）：由 CI 自动发布

---

## v43 · 2026-09-23 · 公开版站点（可分享的隐私安全形态）

此前只有一个独立站点，它内嵌了**四张表的完整快照** —— 把它分享给别人，等于把自己的 5 条投递记录、14 条实习意向、收件箱情报一起送出去。本版新增一份只面向他人的发布形态。

- **新增 `src/build_public.py`**（构建链第 ⑤ 步，复用 `build_site.py` 的结构）
  - **只内嵌 `jobs` 表**，且剔除「来源 = 示例预置」的 5 条演示行；`apps` / `interns` / `inbox` **完全不进产物**（实测 729 → 724 条）
  - **独立 localStorage 命名空间 `qc_*`**，与私人站点版的 `qz_*` 互不干扰（同一浏览器可并存、互不污染）
  - **访客自选起点**：首次打开弹二选一 —— 「用内置快照开始」或「从空白开始，自己记投递」；选择记在 `qc_pubAsked`，之后不再打扰
  - 工具条 + 导出 / 导入 / 重置（文件名 `JobSeeker公开版备份_YYYYMMDD.json`）随适配层注入；`qc_*` 数据可自行备份迁移
- **隐私门禁进 CI**（`lint.yml` 新增步骤）：产物中不得出现三张隐私表的真实 `databaseId`、不得出现 `"apps":` / `"interns":` / `"inbox":` 键、不得残留 `qz_` 前缀，且必须使用 `qc_` —— 任一违反即失败
- **测试参数化**：`tests/smoke_site.js` 用 `SMOKE_MODE=site|public` 一份脚本跑两种产物（路径 / 前缀 / 期望岗位数 / 端口全部按模式派生），公开版新增场景 D「选空白起点」；`check_inline_js.py` / `check_escapes.py` / 页数校验 / 冒烟 job 同步纳入 `dist/public/`
- **修复 · `sync_autumn_all.py` 跑不起来**：模块级 `LOG_PATH = os.path.join(...)` 用到 `os` 但从未 `import os`，加载即 `NameError`。已补上（AST 体检确认这是全部 14 个 Python 文件中唯一一处）
- **修复 · 文档路径过时**：`export_seed.py` docstring 的输出路径由 `pages/seed/seed.json` 更正为 `src/seed/seed.json`
- **验证**：四构建重跑后 6 个既有产物 SHA1 **逐字节一致**（纯增量）；`smoke_site.js` 两种模式全绿；合并版浏览器冒烟零错误
- 说明：公开版**尚未发布**，本版只产出 `dist/public/index.html`；发布入口待定

## v42 · 2026-09-23 · 仓库重组为专业结构

从旧仓库（`pages/` 平铺 + 产物散落根目录）迁移到新仓库，按职责分层。**纯结构迁移，功能零变化。**

- **目录分层**：`src/`（构建链 + canonical_schema + seed 快照）/ `scripts/`（运维与数据管道）/ `tests/`（全部检查与冒烟 + `fixtures/` 夹具）/ `dist/`（构建产物统一出口）/ `docs/`（历史文档）
- **产物单一出口**：4 独立页、合并版、`demo/`、`site/` 全部收敛到 `dist/`，不再向仓库根写副本
- **CI 门禁适配**：幂等检查改为重跑四构建后 `git diff --exit-code -- dist`；页数校验扩到 4+1+1；内联 JS 检查把 `dist/site/` 纳入范围
- **脚本去 cwd 化**：全部改为 `__file__` 相对定位；`sync_autumn_all.py` 的写死日志路径改为脚本旁相对路径
- **清理**：删除根目录产物副本、同步日志、一次性调试脚本（`ab_cache.js` / `audit_data.py` / `check_dups.py` / `verify_autumn.py` / `preflight.py` / `refresh_union.py`）、调试截图、`schema_union.json` 中间产物
- **修复 · 构建可复现**：`.gitignore` 的 `src/canonical_*.json` 把构建输入 `src/canonical_schema.json` 一起忽略了，全新检出会生成 options 全空的站点（CI 表现为 `dist/site/index.html` 与提交版本不一致）。已加 `!src/canonical_schema.json` 白名单并入库；`build_pages.py` 缺该文件时直接失败，不再静默产出残页
- **启用 GitHub Pages**：新仓库首次部署前 Pages 未开启，已通过 API 打开（build_type=workflow），`deploy-demo.yml` 自动发布演示站

## v41 · 2026-09-23 · 每日抓取打通独立站点

此前「每日抓取」只写资料库数据表，独立站点用的是静态快照，且种子只在首次打开时灌一次 —— 用户在站点上看到的岗位会永远停在快照那天。本版把这条链路接上。

- **站点改为增量同步**（`build_site.py` 的 SITE_ADAPTER）
  - 打开站点时与内置快照对账，只补「快照里有、本机没有」的岗位；去重键为岗位表的牛客ID（缺失时回落公司名）、实习表的公司+岗位名
  - **不动用户已有数据**：投递状态、备注、优先级等一律保留
  - **不复活删掉的条目**：删除时把去重键记进 `qz_seedGone`，下次同步跳过（重置快照时清空）
  - 幂等：重复刷新不会重复增长
  - 顶部工具条显示「已载入 / 本次新增 N 个岗位」
- **两个抓取自动化接上发布步骤**：每日同步完 → `export_seed.py` 重导快照 → `build_site.py` 重建 → 重新发布站点，用户零操作
- **实习抓取放宽**（`sync_interns.py`）
  - 数据源由 `tab=2`（只有 35 条）换成 `tab=3` 全量校招日程（707 条），再靠「batchName 必须含实习」硬条件筛，池子从 35 → 37 条实习批次
  - 城市放宽：成都/北京/天津 + 远程·线上·居家·全国·不限·多地 + 没写城市的条目
  - 岗位方向不再硬过滤（池子太小），改为在备注前缀标注「技术岗 · / 非技术岗 · 」供用户自行筛
  - 实测实习表 3 条 → 14 条
- **测试**：新增 `pages/smoke_site.js`，真实 Chromium 跑 4 组场景（全新访客灌满 / 老用户只补新增且不动自有数据 / 二次刷新不翻倍 / 删除标记不报错），已接入 CI 的 smoke job

## v40 · 2026-09-22 · 简历上传改为 Word / PDF

- **上传格式收敛**：简历档案只接受 `Word（.doc / .docx）` 和 `PDF`，**移除 TXT / Markdown** 入口（`accept`、提示文案、空态引导全部同步）
- **PDF 直接上传**：新增零依赖 PDF 文本抽取（`RSPDF_JS`）
  - 浏览器原生 `DecompressionStream` 解 FlateDecode 流，先按 zlib 试、失败再按裸 deflate 试
  - 按 `/Length` 精确截断流，避免尾随字节导致解压失败
  - 解析 `ToUnicode` CMap（`beginbfchar` / `beginbfrange`），把 CID 字形码还原成 Unicode，**中文简历可正常提取**
  - 只取文字操作符（`Tj` / `TJ` / `'` / `"`）的操作数，`Td` / `Tm` / `ET` 当换行，中英文混排都保序
  - 抽不到文字时如实提示「多半是扫描件/图片版」，引导走「粘贴文本」，不假装成功
- **体验**：解析期间按钮显示「解析中…」；老式 `.doc` 明确提示先另存为 `.docx` 或 `.pdf`；选中不支持的格式会清空输入框便于重选
- **测试**：新增 PDF 夹具 `pages/test_resume.pdf`；冒烟新增 3 条断言（accept 正确 / 中文抽取并保存成功 / TXT 被拒）

## v39 · 2026-09-22 · Agent 高度自定义（`71f6376`）

- 全局人设：一段背景描述拼到所有功能的 system 最前
- 逐功能参数覆盖：温度 / 最大 token / System Prompt / top_p / 频率与存在惩罚 / 模型覆盖 / 输出格式 / 长度 / 语言
- 5 套预设方案一键套用，参数可导出导入备份
- 修复「调参台填的 System Prompt 从未下发给模型」的缺陷：`agBuildMessages` 统一组装，`agSetTune` 改为合并语义（不再互相覆盖）

## v38 · 2026-09-21 · UI 专业化改版（Vercel Geist 风）（`8e6a9b1`）

- 去渐变、墨色主色 `#171717`、唯一强调蓝 `#0070f3`、1px 发丝线、8px 圆角、等宽数字
- Hero 改白底标题条，侧栏激活态改浅灰底 + 墨色左标，统计卡左对齐
- 主题预设换色板（`--grad` 改为单色，跟随主色）

## v37 · 2026-09-21 · 品牌升级 Job Seeker（`bb77d48`）

- 全站改名 **Job Seeker**，新 Logo（渐变徽章 · 手提箱 + 对勾）与内联 SVG favicon
- 独立站点上线：无需登录、数据存本机、支持导出/导入/重置备份

## v35 · 2026-09-19 · AI 零配置开箱即用（`fd1e37c`）

- 未填 Key 时默认走免注册免费通道，失败自动重试，仍不通回落演示模式
- 零经验用户打开即用，无需任何配置

## v34 · 2026-09-19 · 免费 AI 通道 + 提醒 + 语音复盘（`8996406`）

- 免费预设通道、桌面提醒、语音复盘录入、知识库检索修复

## v33 · 2026-09-19 · 新 UI：侧栏三组导航（`2a68d15`）

- 「发现 / 我的 / 配置」三组侧栏 + 我的空间（简历 / 画像 / 日程 / 助理 / 收件箱）

## v31–v32 · 2026-09-18 · 本地知识库问答 + CI 修复（`729fb50` / `42187a5`）

- 本地 RAG：BM25 检索本机语料（岗位 / JD / 投递 / 复盘 / 简历）+ 字段加权与 2-gram 分词 + 引用式作答
- 修好连续失败的 lint：单页版 / demo 不再残留生产资料库深链

## v30 · 2026-09-16 · 数据洞察（`48c3b6d`）

- 词典匹配 + 2-gram + TF-IDF 岗位关键词挖掘、城市 Top 与「城市 × 方向」交叉分析（纯本地、零 AI 消耗）

## v27–v29 · 2026-09-15 · AI 能力铺齐（`103ae93` / `3dcd5ac` / `56dce2f` / `b8e591a`）

- 简历档案（多份 + 意向备注 + AI 解析）、岗位匹配打分（贴 JD、按匹配度排序）
- 面试复盘 / 批量打分 / 今日 AI 推荐 / 邮件 AI 解析 + 抓 JD 书签
- 简历上传支持 Word（`.docx`）
- Agent 调参台（参数分层 / 可观测 / A-B 对比）

## v20–v26 · 2026-09-13～09-14 · 工作台基础能力

- 总览拆「今日提醒 + 个人中心」、申请热力图（26 周）、情报收件箱、阶段快捷按钮
- 主题色自定义（7 款预设 + 任意取色）
- 邮件接入双路线（IMAP 直读桥 + 粘贴解析）、公司情报面板改参考链接
- 四页合并单文件版、GitHub Pages 演示页、GitHub Actions（lint + smoke + Pages）

---

## 版本规则

- 每个版本 = 一次提交，提交信息以 `vNN：` 开头
- 改动顺序：改 `src/*.py` → 五构建（`build_pages` → `build_single` → `build_demo` → `build_site` → `build_public`，顺序铁律）→ `check_workflows` / `check_escapes` / `check_inline_js` → 冒烟（`smoke_browser.js` + `smoke_site.js` 两种模式）→ 发布站点与资料库节点 → 提交推送
- 产物统一写 `dist/`，CI 会重跑全部构建并比对 `git diff --exit-code -- dist`，产物与源码不一致即失败
