# paper-bilingual-reader

把英文文献 PDF 做成**左英右中、可同步滚动、可划重点**的单文件 HTML 双语阅读器，
并输出中英术语表 CSV。为「反复要读英文文献」的人做的，一次配好，之后每篇文献一条命令。

```
paper.pdf  ──►  blocks.json + 图表  ──►  逐块翻译  ──►  单文件双语 HTML + 术语表
             (脚本，确定性)            (AI，质量核心)      (脚本，确定性)
```

## 它产出什么

| 文件 | 说明 |
|---|---|
| `paper-bilingual.html` | 主产物。单文件、图片内嵌，双击就能用，可以单独发给别人 |
| `paper-glossary.csv` | 中英术语表，UTF-8 带 BOM，Excel 直接打开不乱码 |
| `paper_pbr/` | 中间层，改译文时要用到，别删 |

阅读器里有什么：

- **同步滚动** — 两栏独立滚动，滚一侧另一侧自动对齐到对应段落；顶栏可关
- **并排吸附** — 把每对段落拉成同高、整页单滚动条，对齐绝对精确，适合逐句精读
- **划重点** — 选中文字弹工具条，4 色高亮 + 笔记，存浏览器本地，关掉再开还在
- **导出标注** — 一键导出 Markdown，带页码、原文、译文、笔记
- **查看原页** — 每段右侧 `p3` 按钮，弹出该页原始版式并红框标出当前段，随时核对
- **打印** — Ctrl+P 直接打成双语 PDF

## 为什么不是直接用 pdf2zh / 沉浸式翻译

| | 那些工具 | 这个 skill |
|---|---|---|
| 排版 | PDF 重排，保真最强 | HTML 块级重建 + 原页兜底 |
| 左右对照 | PDF 拼宽页，只能整页翻 | 真·滚动联动 |
| 划重点 / 笔记 / 导出 | 无 | 有，可导出 Markdown |
| 翻译质量 | 取决于你接的 Google/DeepL API | 由 AI 逐块翻译，术语表锁死译法 |
| API Key | 多数需要 | 不需要 |

一句话：**要存档 PDF 用 pdf2zh，要读懂并做笔记用这个。**

## 安装

### 0. 先装依赖（只要两个）

```bash
pip install -U pymupdf pillow
python3 scripts/check_env.py     # 自检，缺什么会直说
```

需要 Python 3.9+。Windows 上路径请用正斜杠绝对路径（`C:/Users/me/paper.pdf`）。

### 1. 装进你用的 AI

**Claude Code**

```bash
mkdir -p ~/.claude/skills
cp -r paper-bilingual-reader ~/.claude/skills/
```

**Codex / OpenClaw**

```bash
mkdir -p ~/.agents/skills
cp -r paper-bilingual-reader ~/.agents/skills/
```

**Cursor / 其他支持 `.cursor/rules` 或自定义指令的编辑器**
把 `SKILL.md` 的内容放进项目规则或全局规则即可。

**ChatGPT / 豆包 / 任何其他 AI（不支持 skill 机制）**
直接把 `AGENT_PROMPT.md` 的内容整段粘给 AI，再告诉它 PDF 路径。那份文档是
自包含的，AI 照着做就能跑完整个流程。

装好后重启一下 AI，之后直接说「翻译这篇文献」+ 给 PDF 路径即可自动触发。

## 手动跑（不用 AI 也行，但翻译得自己做）

```bash
cd paper-bilingual-reader

# 1. 解析
python3 scripts/extract.py "C:/abs/path/paper.pdf" -o "C:/abs/path/paper_pbr"

# 2. 翻译：人工填写 paper_pbr/tr/batch_001.json，格式 {"b0001":"中文", ...}
#    参考 references/translation-guide.md 的规范

# 3. 构建
python3 scripts/build_html.py "C:/abs/path/paper_pbr" -o "C:/abs/path/paper-bilingual.html"

# 4. 术语表
python3 scripts/make_glossary.py "C:/abs/path/paper_pbr/glossary.json" -o "C:/abs/path/paper-glossary.csv"

# 可选：标题位置不对时，只重排顺序（译文不用重做）
python3 scripts/reflow.py "C:/abs/path/paper.pdf" -o "C:/abs/path/paper_pbr"
python3 scripts/build_html.py "C:/abs/path/paper_pbr" -o "C:/abs/path/paper-bilingual.html"
```

## 先看效果

直接双击打开 `demo/bilingual-reader-demo.html`（演示用的一篇合成论文，0.4 MB），
同步滚动、并排吸附、划重点、查看原页都能现场试。确认是你想要的东西再装。

## 目录结构

```
paper-bilingual-reader/
├── SKILL.md                     # 给 AI 看的 workflow（含触发词）
├── AGENT_PROMPT.md              # 不支持 skill 的 AI：整段粘贴这份
├── README.md                    # 本文件
├── requirements.txt
├── .gitignore                   # 忽略 Python 缓存与 *_pbr 中间目录
├── LICENSE                      # MIT
├── scripts/
│   ├── check_env.py             # 环境自检
│   ├── extract.py               # PDF → blocks.json + 图 + 页渲染图
│   ├── reflow.py                # 只重排阅读顺序（标题位置不对时用，不用重翻）
│   ├── build_html.py            # 译文 + 术语表 → 单文件 HTML
│   └── make_glossary.py         # 术语表 → CSV
├── assets/
│   └── reader_template.html     # 阅读器模板（CSS + JS，改样式改这里）
├── references/
│   └── translation-guide.md     # 学术翻译规范 + 化学术语对照表
└── demo/
    ├── bilingual-reader-demo.html   # 成品长什么样，双击看
    └── glossary-demo.csv            # 术语表长什么样
```

## 发给别人时怎么给

| 对方的情况 | 怎么给 |
|---|---|
| 用 Claude Code / Codex / OpenClaw（支持 skill） | 整个文件夹或 zip 发过去，按上面的路径放好，**什么都不用粘** |
| 用 ChatGPT / 豆包 等纯聊天 AI | 对方先解压到本地，再把 `AGENT_PROMPT.md` **整段粘给 AI**，并告诉它解压后的绝对路径 |
| AI 能读本地文件（Claude Code / Cursor Agent） | 发 zip 解压即可，直接说「按 paper-bilingual-reader 跑这篇 PDF」 |
| AI 完全碰不到本地文件（纯网页版） | 跑不了——脚本必须在本地执行，只能让对方自己走「手动跑」那四步 |

**只发 `AGENT_PROMPT.md` 一个文件是不够的**：它只是说明书，真正干活的 `scripts/` 和
`assets/` 必须留在磁盘上。AI 要读的确实只有那一份，但要用的不止。

## 已知边界

- **扫描件 PDF 不行**，没有文本层，请先 OCR。
- 表格依赖 PyMuPDF 的识别，失败时会降级成段落，需要人工修。
- 公式不翻译，整块渲染成图片（这样永远不会乱码）。
- 参考文献不翻译，按 `[n]` 断行显示。
- 作者、单位、邮箱、DOI 不翻译，原样保留。

## 协议

MIT。
