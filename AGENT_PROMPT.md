# 给你（AI）的任务说明：把英文文献做成双语对照阅读器

> 这份文档是自包含的。把你手上的英文 PDF 路径交给用户确认后，按下面的步骤执行即可。
> 脚本目录记作 `<SKILL_DIR>`——就是本文件旁边那个含 `scripts/` 和 `assets/` 的目录，
> 执行前请先用绝对路径替换它。
>
> **转发者须知**：AI 只需要「读」本文件这一份；但 `scripts/`、`assets/`、`references/`
> 必须留在 AI 能访问到的磁盘上（AI 不用读它们的源码，只是调用）。
> 只把这一个 .md 单独拷走是跑不起来的。

## 哪些文件是必需的

| 文件 | 给谁 | AI 要不要读 |
|---|---|---|
| `AGENT_PROMPT.md`（本文件） | AI | **要读**，整段粘贴 |
| `scripts/*.py` | AI 调用 | 不用读，留在磁盘上即可 |
| `assets/reader_template.html` | 脚本调用 | 不用读，同上 |
| `references/translation-guide.md` | AI（可选） | 翻译规范，术语拿不准时再读 |
| `README.md` / `requirements.txt` / `LICENSE` | 人 | 不用给 AI |
| `demo/` | 人 | 不用给 AI |

## 目标

把用户给的英文文献 PDF 变成一份**左英右中**的单文件 HTML 双语阅读器：块级对齐、
同步关联滚动、可划重点、图表保真并带原页兜底核对；同时输出中英术语表 CSV。

## 环境

依赖只有两个。先自检：

```bash
python3 <SKILL_DIR>/scripts/check_env.py
```

缺什么就 `pip install -U pymupdf pillow`。需要 Python 3.9+。
Windows 上路径请一律用**正斜杠绝对路径**（`C:/Users/me/paper.pdf`），避免转义问题。

## 步骤

### 1. 解析

```bash
python3 <SKILL_DIR>/scripts/extract.py "<PDF 绝对路径>" -o "<工作目录，建议 PDF 同目录下 <stem>_pbr>"
```

产出 `<工作目录>/blocks.json`，每个块含 `id`、`page`、`bbox`、`type`。
type 取值：`heading` / `paragraph` / `caption` / `figure` / `equation` / `table` / `reference` / `noise`。

读一下 `blocks.json` 的 `meta` 和块类型分布，判断页数和待翻字数，再决定分批规模。

### 2. 逐批翻译（质量全靠这一步）

按块的原文顺序分批，每批 1500–2500 字符，逐批写入 `<工作目录>/tr/batch_001.json`、
`batch_002.json`……，格式为纯映射：

```json
{"b0042": "中文译文", "b0043": "中文译文"}
```

**每翻完一批立刻落盘**，不要攒到最后，这样长文可以中断续跑。

硬性规则：

- **块级一一对应**：一个英文块 = 一个中文块。不合并、不拆分、不漏译。
- **原样保留**：化学式与化合物编号（`1a`、`2b`）、数字与单位（`12 μM`、`350 nm`、`298 K`）、
  希腊字母与数学符号、基因/蛋白名、期刊缩写、文献引用标号（`[3]`、`ref. 24`）、DOI、网址。
- **不新增、不删减**：不许补背景、不许加解释、尤其不许吃掉不确定性、否定、局限性。
- **术语一致**：同一术语全篇同一译法。拿不准的先定名并写进术语表。

语气对照（不要把不确定翻成确定）：

| 英文 | 中文 |
|---|---|
| suggest / indicate / imply | 表明 / 提示 / 暗示 |
| demonstrate / prove | 证明 |
| we propose / we speculate | 我们提出 / 我们推测 |
| cannot be excluded | 不能排除 |
| appears to / seems to | 似乎 |

**不要翻译这些块**，它们带 `no_translate: true`，直接跳过：

- `reference`（参考文献）
- `noise`（页眉页脚、刊名、版权行、下载水印）
- 作者行、单位地址、邮箱、DOI 引用行（译人名和地址是学术翻译最容易出错的地方）

**必须翻译**：图注表注（最需要对照的部分）、标题、正文、致谢、利益声明、数据可用性声明。
表格块保持 markdown 结构，逐单元格译，数字单位不动。

更完整的规范见 `<SKILL_DIR>/references/translation-guide.md`。

### 2.5 术语表

同步维护 `<工作目录>/glossary.json`，只收反复出现的专业术语与缩写（一般 15–60 条）：

```json
{"terms": [{"en": "cycloparaphenylene", "zh": "环对亚苯基", "note": "CPP"}]}
```

### 3. 构建

```bash
python3 <SKILL_DIR>/scripts/build_html.py "<工作目录>" -o "<输出 HTML 绝对路径>"
```

翻译来源默认读 `<工作目录>/tr/` 下全部 `.json` 并自动合并。
缺译的块会原文回填，终端会列出未翻译的 id——看到就补翻再重跑。

### 3.5 检查顺序（重要）

构建出来后**务必扫一眼开头几页**，看大标题、章节标题有没有跑到正文或作者行后面。
有的话**不要重跑第 1 步**，直接用重排脚本：

```bash
python3 <SKILL_DIR>/scripts/reflow.py "<PDF 绝对路径>" -o "<工作目录>"
```

它只重排阅读顺序，块的 `id`、`bbox`、类型、正文全部不动，所以**译文一条都不用重翻**，
用户已有的划重点也不会丢（标注按 id + 字符偏移存储）。跑完再执行一次第 3 步即可。
想先看看会动多少，加 `--dry-run`。

若重排后仍不对，再试 `extract.py --cols 2`（强制双栏）或 `--no-split`（退化为纯上下排序）。

### 4. 术语表 CSV

```bash
python3 <SKILL_DIR>/scripts/make_glossary.py "<工作目录>/glossary.json" -o "<输出 CSV 绝对路径>"
```

### 5. 交付

把 HTML 打开给用户，并说明：未翻译块数、术语表条数，以及阅读器的四个开关
（同步滚动 / 并排吸附 / 划重点 / 导出标注）。

## 边界

- 扫描件 PDF 没有文本层，请先提示用户去 OCR，不要硬跑。
- 表格识别失败会降级成段落，交付时如实说明。
- 公式不翻译，整块渲染成图片——这是刻意的，PDF 文本层抽公式必然乱码。
- 参考文献不翻译，按 `[n]` 断行。
- 版面识别是启发式的：遇到特殊排版的期刊（标题跨栏、左栏整列是脚注等）仍可能出错，
  用第 3.5 步的 `reflow.py` 修，修不好再让用户手工调整，不要为了对齐而改动译文。

## 改译文的正确姿势

直接编辑 `<工作目录>/tr/` 里对应 id，重跑第 3 步即可。
用户做的划重点不会丢（标注按块 id + 字符偏移存储，与译文解耦）。
