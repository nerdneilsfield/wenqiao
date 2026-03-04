# md-mid

**学术写作中间格式与多目标转换工具**

md-mid 定义了一种基于 Markdown 的学术写作中间格式，作为论文的唯一数据源。
只需编写一份 Markdown，即可转换为 LaTeX、富 Markdown 或自包含 HTML。

## 功能特性

- **多目标输出** — LaTeX (`.tex`)、富 Markdown (`.md`) 和带 MathJax 的 HTML
- **引用支持** — `cite`、`citep`、`citet`、`citeauthor`、`citeyear`、`textcite`、
  `parencite`、`autocite`，支持 BibTeX 文件解析
- **数学公式** — 行内 `$...$` 与行间 `$$...$$`，支持标签和方程环境
- **交叉引用** — `<!-- label: sec:intro -->` 与 `[第1节](ref:sec:intro)`
- **图表** — 通过 HTML 注释指令设置元数据（caption、label、width、placement）
- **环境块** — `<!-- begin: algorithm -->` / `<!-- end: algorithm -->`
- **TeX 嵌入** — `<!-- include-tex: fragment.tex -->` 引入外部 LaTeX 片段
- **AI 图片生成** — 可选的 nanobanana 兼容 runner 图片生成管线
- **配置层级** — CLI > 行内指令 > 配置文件 > 模板 > 默认值
- **国际化** — 支持 `zh`（中文）和 `en`（英文）标签

## 技术栈

| 分类 | 工具 | 版本 |
|------|------|------|
| 语言 | Python | >= 3.14 |
| 解析器 | markdown-it-py | >= 3.0 |
| 解析器插件 | mdit-py-plugins | >= 0.4 |
| YAML | ruamel-yaml | >= 0.18 |
| CLI | Click | >= 8.0 |
| 构建 | hatchling | — |
| 包管理 | uv | 最新 |
| 检查 / 格式化 | ruff | >= 0.9 |
| 类型检查 | mypy (strict) | >= 1.15 |
| 测试 | pytest | >= 8.0 |

## 架构

```
input.mid.md
    │
    ▼
┌──────────────────────┐
│  Markdown 解析器     │  markdown-it-py + dollarmath / footnote / table 插件
└──────────┬───────────┘
           ▼
┌──────────────────────┐
│  注释处理器          │  4 阶段指令提取（文档级 → 环境 → include → attach）
└──────────┬───────────┘
           ▼
┌──────────────────────┐
│  增强 AST (EAST)     │  32 种节点类型 — 核心数据结构
└──────────┬───────────┘
           │
     ┌─────┼─────┐
     ▼     ▼     ▼
  LaTeX  Markdown  HTML
```

每个渲染器支持三种输出模式：

| 模式 | 说明 |
|------|------|
| `full` | 完整文档，含导言区、`\begin{document}`、参考文献 |
| `body` | 仅正文，`\begin{document}...\end{document}` 内部 |
| `fragment` | 裸内容，标题降级，适合嵌入其他文档 |

## 快速开始

### 前置条件

- Python 3.14+
- [uv](https://docs.astral.sh/uv/) 包管理器

### 安装

```bash
git clone https://github.com/<owner>/academic-md2latex.git
cd academic-md2latex
uv sync
```

### 基本用法

```bash
# Markdown → LaTeX（默认）
md-mid paper.mid.md -o paper.tex

# Markdown → HTML
md-mid paper.mid.md -o paper.html -t html

# Markdown → 富 Markdown
md-mid paper.mid.md -o paper.md -t markdown

# 从标准输入读取
cat paper.mid.md | md-mid - -o paper.tex

# 导出增强 AST 为 JSON
md-mid paper.mid.md --dump-east
```

### CLI 选项

```
用法: md-mid [OPTIONS] INPUT

选项:
  -o, --output PATH                   输出文件（省略则输出到 stdout）
  -t, --target [latex|markdown|html]  输出格式（默认: latex）
  --mode [full|body|fragment]         输出范围
  --config PATH                       配置文件（md-mid.yaml）
  --template PATH                     LaTeX 模板（.yaml）
  --bib PATH                          参考文献文件（.bib）
  --bibliography-mode MODE            auto | standalone | external | none
  --code-style [lstlisting|minted]    代码块样式
  --heading-id-style [attr|html]      标题锚点格式
  --locale [zh|en]                    输出语言
  --generate-figures                  启用 AI 图片生成
  --figures-runner PATH               图片生成 runner 脚本
  --figures-config PATH               runner 配置（TOML）
  --force-regenerate                  强制重新生成已有图片
  --strict                            严格解析模式
  --verbose                           详细输出
  --dump-east                         导出增强 AST 为 JSON
  --version                           显示版本号
```

## 文档格式

md-mid 文档是标准 Markdown 文件（`.mid.md`），元数据通过 HTML 注释编码。
这样源文件在任何 Markdown 阅读器中都可读，同时携带完整的学术语义信息。

### 文档级指令

```markdown
<!-- documentclass: article -->
<!-- classoptions: [12pt, a4paper] -->
<!-- packages: [amsmath, graphicx, hyperref] -->
<!-- bibliography: refs.bib -->
<!-- title: 论文标题 -->
<!-- author: 作者 -->
<!-- date: 2026 -->
<!-- abstract: |
  本文提出了一种新方法……
-->
```

### 引用

```markdown
先前的工作 [Wang et al.](cite:wang2024) 表明……
经典方法 [1](citep:fischler1981) 存在局限性。
```

支持的引用命令：`cite`、`citep`、`citet`、`citeauthor`、`citeyear`、`textcite`、
`parencite`、`autocite`。

### 交叉引用

```markdown
<!-- label: sec:intro -->
如 [第1节](ref:sec:intro) 所示……
```

### 带元数据的图片

```markdown
![流程概览](figures/pipeline.png)
<!-- caption: 点云配准流程 -->
<!-- label: fig:pipeline -->
<!-- width: 0.85\textwidth -->
```

### 环境块

```markdown
<!-- begin: algorithm -->
1. 初始化……
2. 迭代……
<!-- end: algorithm -->
```

### 完整示例

参见 [`tests/fixtures/full_example.mid.md`](tests/fixtures/full_example.mid.md)，
展示了所有功能的完整用例。

## 配置

md-mid 通过五层优先级链解析配置：

```
CLI 参数  >  行内指令  >  配置文件  >  模板  >  默认值
```

### 配置文件（`md-mid.yaml`）

```yaml
documentclass: article
classoptions: [12pt, a4paper]
packages: [amsmath, graphicx]
code_style: lstlisting
locale: zh
target: latex
```

### 模板文件

模板为特定投稿目标提供可复用的默认配置：

```bash
md-mid paper.mid.md --template templates/ieee.yaml -o paper.tex
```

## 项目结构

```
academic-md2latex/
├── src/md_mid/          # 源代码
│   ├── parser.py        #   Markdown → EAST 解析器
│   ├── nodes.py         #   EAST 节点定义（32 种类型）
│   ├── comment.py       #   注释指令处理器
│   ├── latex.py          #   LaTeX 渲染器
│   ├── markdown.py       #   富 Markdown 渲染器
│   ├── html.py           #   HTML 渲染器（MathJax）
│   ├── config.py         #   配置解析
│   ├── cli.py            #   Click CLI 入口
│   ├── bibtex.py         #   BibTeX 解析器
│   ├── genfig.py         #   AI 图片生成
│   ├── escape.py         #   LaTeX 转义工具
│   ├── sanitize.py       #   输入清洗
│   ├── url_check.py      #   URL 安全验证
│   ├── ai_meta.py        #   共享 AI 元数据渲染
│   └── diagnostic.py     #   错误/警告诊断
├── tests/               # 测试套件（16 个文件，425+ 测试）
│   ├── fixtures/        #   测试用 Markdown 文档
│   └── conftest.py      #   共享 fixtures
├── templates/           # LaTeX 投稿模板
├── docs/                # 文档与计划
├── pyproject.toml       # 项目元数据
└── Makefile             # 构建命令
```

## 开发

### 环境搭建

```bash
uv sync                  # 安装所有依赖
```

### 命令

```bash
make check               # 运行 lint + 类型检查 + 测试（提交前必须执行）
make test                # 运行 pytest
make lint                # 运行 ruff 检查
make format              # 运行 ruff 格式化
make typecheck           # 运行 mypy（严格模式）
make fix                 # 自动修复 lint 问题并格式化
```

### 编码规范

- **类型注解** — 所有函数和方法必须有完整的类型注解
- **双语注释** — 英文 + 中文：`# Calculate average (计算平均值)`
- **文档字符串** — Google 风格，含双语描述
- **行长** — 最大 100 字符
- **命名** — 函数/模块用 `snake_case`，类用 `PascalCase`，常量用 `UPPER_SNAKE_CASE`

### 测试

测试文件与源代码模块一一对应。运行全部测试：

```bash
make test
```

测试命名规范：`test_<函数名>_<场景>`。

`tests/fixtures/` 下的测试夹具提供可复用的 `.mid.md` 文档，覆盖标题、数学公式、
引用、交叉引用、注释指令及完整多功能示例。

## 贡献指南

1. Fork 本仓库
2. 创建功能分支
3. 先写测试（推荐 TDD）
4. 确保 `make check` 通过（ruff、mypy、pytest）
5. 提交 Pull Request

所有代码必须包含完整的类型注解和双语注释。
