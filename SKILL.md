---
name: paper-english-chinese-reader
description: 把英文文献 PDF 做成「左英右中」的单文件 HTML 双语阅读器（单向：英文原文 → 中文译文）——块级对齐、同步关联滚动、划重点标注（本地保存、可导出）、图表保真并带原页兜底核对，公式以图片保留、参考文献按条目断行，同时输出中英术语表 CSV。当用户给出英文 PDF/论文，要求翻译、双语对照、中英对照、文献精读、保留图文排版时使用。不用于中文原文或其它语种的 PDF。
---

# paper-english-chinese-reader

把一篇英文文献 PDF 变成一份可交互的双语对照阅读器。

## 何时使用

用户给出英文 PDF 并提到：翻译 / 双语对照 / 中英对照 / 左右对照 / 文献精读 / 保留图文排版 / 同步阅读 / 划重点。

不要用于：只要摘要翻译、只要要点总结、只要参考文献整理、只要某一句话的解释。

**方向是单向的**：只做英文原文 → 中文译文。中文原文或其它语种的 PDF 不要用这个 skill，
先跟用户确认原文语言；如果原文不是英文，直接说明这个工具不适合。

## 环境准备

先跑一次自检：

```bash
python3 <SKILL_DIR>/scripts/check_env.py
```

缺什么它会直接告诉你。依赖只有两个：

```bash
pip install -U pymupdf pillow
```

`<SKILL_DIR>` 指本 skill 的解压目录（含 `scripts/` 和 `assets/` 的那一级）。
下文所有命令里的 `python3` 换成你这台机器能用的 Python 3.9+ 解释器即可（Windows 上常是 `python`，或某个虚拟环境里的完整路径）。

> Windows 注意：路径一律用**正斜杠**并写绝对路径（如 `C:/Users/me/paper.pdf`），避免反斜杠转义问题。

## 产物

| 文件 | 说明 |
|---|---|
| `{stem}-bilingual.html` | **主产物**，单文件、图片内嵌，双击即用 |
| `{stem}-glossary.csv` | 中英术语表（UTF-8 带 BOM，Excel 直接打开不乱码） |
| `{stem}_pbr/` | 中间层：`blocks.json`、`assets/`、`pages/`、`tr/` 翻译批次 |

## 工作流

### Step 1 · 解析

```bash
python3 <SKILL_DIR>/scripts/extract.py "C:/abs/path/paper.pdf" -o "C:/abs/path/paper_pbr"
```

产出 `blocks.json`。每个块含稳定 `id`、`page`、`bbox`、`type`：

| type | 含义 |
|---|---|
| `heading` | 各级标题 |
| `paragraph` | 正文段落 |
| `caption` | 图注/表注（通常已被并入图块） |
| `figure` | 图片，图注已合并进 `text` |
| `equation` | 公式，整块渲染成图片，**无文本** |
| `table` | markdown 表格 |
| `reference` | 参考文献，带 `no_translate` |
| `noise` | 页眉页脚、刊名、版权行、下载水印，带 `no_translate` |

解析器已经内置处理好的几件事（不用你操心，但要知道）：

- 双栏阅读顺序（左栏走完再走右栏）
- 页眉横幅/装饰小图已被尺寸下限过滤掉
- 数学字体区域整块转图，不会抽出乱码
- 参考文献即使没有 `References` 标题也能识别
- 被 PDF 切碎的连续文本会被重新接起来
- 跨栏大标题按字号识别，不会被挤到正文或作者行后面
- 左栏整列都是作者单位/邮箱而正文在右栏时，先排右栏正文再排左栏脚注

**先读 `blocks.json` 的 meta 与块类型分布**，判断页数、字数，再决定分批规模。

### Step 2 · 逐批翻译（这一步由你来做，质量的关键）

把块按原文顺序分批，每批 **1500–2500 字符**（公式密集或表格多就取小值），逐批写文件：

```
{out}/tr/batch_001.json
{out}/tr/batch_002.json
...
```

文件格式为纯映射：`{"b0042": "中文译文", "b0043": "..."}`。

翻译规则（完整规范见 `references/translation-guide.md`）：

- **块级一一对应**：一个英文块译成一个中文块，不许合并、不许拆分、不许漏译。
- **公式、数字、单位、化合物编号、基因名、文献引用标号原样保留**：`1a`、`Kekulé`、`IC50 = 12 μM`、`[3]`、`ref. 24` 一律不动。
- **化学术语优先用中文规范译名**，生僻或易歧义的用「中文（English）」形式首现。
- **保留 hedging**：suggest → 表明，indicate → 指出，demonstrate → 证明，cannot be excluded → 不能排除。不许把不确定写成确定。
- **图表注必须翻**，它是最需要对照的部分。
- **参考文献块和 `noise` 块不要翻**：带 `no_translate: true` 的块直接跳过，不要出现在批次文件里（构建时会自动回填原文）。
- **作者行、单位地址、邮箱、DOI 引用行不要翻**，原样保留——译人名和地址是学术翻译最容易出错的地方。
- **表格块**：保持 markdown 结构，逐单元格译，表头也要译，数字/单位不动。

每翻完一批就落盘一个文件，不要攒到最后——长文可中断续跑，重跑时只需补缺失的批次。

### Step 2.5 · 术语表

翻译过程中同步维护 `{out}/glossary.json`：

```json
{"terms": [{"en": "cycloparaphenylene", "zh": "环对亚苯基", "note": "CPP"}, ...]}
```

只收**本文反复出现的专业术语与缩写**，一般 15–60 条。

### Step 3 · 构建阅读器

```bash
python3 <SKILL_DIR>/scripts/build_html.py "C:/abs/path/paper_pbr" -o "C:/abs/path/paper-bilingual.html"
```

- 翻译来源默认读 `{out}/tr/` 目录下全部 `.json`（自动合并）。
- 默认把图片内嵌成 data URI，产出真正的单文件；加 `--embed-assets 0` 改为外链（文件更小，但 HTML 必须和 `assets/` 文件夹一起拷走）。
- 缺译的块会原文回填，并在终端列出未翻译 id，方便补翻。
- `--embed-pages 0` 可去掉原页兜底图（体积减半，但「查看原页」会失效）。

### Step 4 · 术语表 CSV

```bash
python3 <SKILL_DIR>/scripts/make_glossary.py "C:/abs/path/paper_pbr/glossary.json" -o "C:/abs/path/paper-glossary.csv"
```

### Step 5 · 交付

打开 HTML，并简短说明：未翻译块数量、术语表条数、阅读器的四个开关（同步滚动 / 并排吸附 / 划重点 / 导出标注）。

## 阅读器功能说明（告诉用户怎么用）

- **同步滚动**：两栏独立滚动，滚一侧另一侧自动对齐到对应块；顶栏可关。
- **并排吸附**：把每对块拉成同一高度、整页单滚动条，对齐绝对精确，适合精读。
- **划重点**：选中文字 → 弹工具条 → 4 色高亮 + 可加笔记；点击高亮可改笔记；存浏览器 localStorage，关掉再开还在。
- **导出标注**：顶栏「导出标注」生成 Markdown（原文 + 译文 + 笔记 + 页码）。
- **查看原页**：每个块右侧 `p3` 按钮，弹出该页原始版式，并用红框标出当前块位置。
- **打印**：Ctrl+P 直接打印成双语 PDF（已写打印样式）。

## 常见故障

| 现象 | 处理 |
|---|---|
| 大标题 / 章节标题排到了正文或作者后面 | 定稿后跑一次 `scripts/reflow.py`（见下节），它会用改进后的顺序逻辑重排，**不用重新翻译** |
| 双栏正文顺序错乱 | 先试 `reflow.py`；仍不对再加 `--cols 2` 强制分栏，或 `--no-split` 退化为纯纵向排序 |
| 图没有被识别 | 确认 PDF 不是扫描件；扫描件请先 OCR，本 skill 不做 OCR |
| 表格抽成了纯文本 | PyMuPDF 表格识别失败时降级为段落，需人工在 HTML 里修 |
| 译文里有大量英文未译 | 检查是否把 reference / noise 块误放进批次文件 |
| 参考文献没有断行 | 断行在构建阶段按 `[n]` 自动完成；若某刊用 `[1a]` 这类写法需手动 |
| HTML 弹窗关不掉 | 确认用的是本 skill 自带的 `assets/reader_template.html`（含 `[hidden]{display:none!important}`） |
| 大段正文被当成公式转图 | 数学字体判据过宽，把 `extract.py` 里 `is_math()` 的 `math >= 0.25` 调高 |

## 只重排顺序（reflow）

已经翻译完、才发现标题位置不对时用这个，**不要重跑 `extract.py`**：

```bash
python3 <SKILL_DIR>/scripts/reflow.py "C:/abs/path/paper.pdf" -o "C:/abs/path/paper_pbr"
```

做法：读取已有 `blocks.json`，只对每页重新执行阅读顺序判定，块的 `id`、`bbox`、类型、正文**全部原样不动**。
译文存在 `tr/*.json` 里按 id 索引，所以一次都不用重翻，划重点也不会丢。首次运行会把旧的写一份 `blocks.json.bak`。
跑完重新执行 Step 3 构建即可。加 `--dry-run` 可以先看「有几个页面的顺序会变」。

## 二次修订

改某个块的译文：直接编辑 `{out}/tr/batch_0XX.json` 里对应 id，重跑 Step 3 即可，**已做的划重点不会丢**（标注按 block id + 字符偏移存储，与译文解耦）。
