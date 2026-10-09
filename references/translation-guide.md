# 学术翻译规范（中英文献对照用）

目标是**可对照的忠实译文**，不是润色后的漂亮中文。读者会拿它跟原文逐句比对，所以宁可略硬，不可走样。

## 硬规则

1. **块级一一对应**：一个英文块 = 一个中文块。不许合并相邻块、不许把一个块拆成两段、不许漏译。
2. **原样保留**：化学式与化合物编号（`1a`、`2b`）、数字与单位（`12 μM`、`350 nm`、`298 K`）、希腊字母与数学符号、基因/蛋白名、期刊缩写、文献引用标号（`[3]`、`ref. 24`）、DOI、网址。
3. **不新增内容**：不许补背景、不许加解释性插入语、不许写译者注。读者要的是原文。
4. **不删内容**：尤其是不确定性、否定、局限性、方法学 caveat。这些被吃掉是学术翻译最严重的错误。
5. **术语一致**：同一英文术语全篇用同一中文译法。拿不准时先查 `glossary.json`，没有就按首现定名并写入术语表。

## 语气与 hedging 对照表

| 英文 | 中文 |
|---|---|
| suggest / indicate / imply | 表明 / 提示 / 暗示 |
| demonstrate / prove | 证明 |
| reveal / show | 揭示 / 显示 |
| we propose / we speculate | 我们提出 / 我们推测 |
| cannot be excluded | 不能排除 |
| appears to / seems to | 似乎 |
| to the best of our knowledge | 据我们所知 |
| however / notably / interestingly | 然而 / 值得注意的是 / 有趣的是 |
| remains elusive / challenging | 仍难以实现 / 仍具挑战性 |

不要把 `suggest` 翻成 `证明`，也不要把 `we speculate` 翻成 `我们确定`。

## 化学/材料领域常用译法

| English | 中文 |
|---|---|
| cycloparaphenylene (CPP) | 环对亚苯基 |
| Kekulene / kekulene | 凯库勒烯 |
| nanographene | 纳米石墨烯 |
| polycyclic aromatic hydrocarbon (PAH) | 多环芳烃 |
| molecular ferroelectric | 分子铁电体 |
| magnetoelectric coupling | 磁电耦合 |
| domain / domain switching | 电畴 / 畴翻转 |
| coercive field | 矫顽场 |
| remanent polarization | 剩余极化强度 |
| Curie temperature | 居里温度 |
| phase transition | 相变 |
| differential scanning calorimetry (DSC) | 差示扫描量热法 |
| second-harmonic generation (SHG) | 二次谐波产生 |
| piezoresponse force microscopy (PFM) | 压电力显微镜 |
| dielectric constant / permittivity | 介电常数 |
| yield / isolated yield | 收率 / 分离收率 |
| single-crystal X-ray diffraction | 单晶 X 射线衍射 |
| DFT calculation | 密度泛函理论计算 |
| HOMO / LUMO | HOMO / LUMO（保留） |
| aromaticity | 芳香性 |
| strain / curvature | 张力 / 曲率 |

首现时用「中文（缩写）」，如「环对亚苯基（CPP）」，之后用缩写。

## 特殊块的处理

- **图表注（caption）**：必须翻，逐句翻。`Figure 1 |` 保留结构，写作「图 1 |」。面板标注 `a`、`b` 原样保留。
- **表格（table）**：保持 markdown 结构，逐单元格翻。表头翻。数字、单位、样品编号不动。
- **参考文献（reference，带 `no_translate`）**：不翻，直接跳过，不要写进批次文件。
- **标题（heading）**：短、准，不加句号。
- **致谢 / 利益声明 / 数据可用性**：翻，但保留署名与基金号原文。

## 分批与自检

- 每批 1500–2500 字符，翻完立刻写 `{out}/tr/batch_00N.json`。
- 每批翻完自检三项：块数对不对、有没有漏掉数字、有没有把 hedge 翻硬。
- 全部翻完后检查 `blocks.json` 里的 id 是否都被覆盖（构建脚本会报告 `untranslated` 数量）。
