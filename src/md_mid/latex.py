"""LaTeX Renderer：EAST → LaTeX 文本。

支持三种输出模式：
- full: 完整 .tex 文档（含 preamble、title、abstract、bibliography）
- body: 仅 \\begin{document}...\\end{document} 内部正文
- fragment: 纯正文片段，heading 降级为纯文本
"""

from __future__ import annotations

from md_mid.escape import escape_latex, escape_latex_with_protection
from md_mid.nodes import Node


_HEADING_CMDS = {
    1: "section",
    2: "subsection",
    3: "subsubsection",
    4: "paragraph",
    5: "subparagraph",
    6: "subparagraph",
}


class LaTeXRenderer:
    def __init__(self, mode: str = "full", ref_tilde: bool = True) -> None:
        self.mode = mode
        self.ref_tilde = ref_tilde

    def render(self, node: Node) -> str:
        method_name = f"render_{node.type}"
        method = getattr(self, method_name, None)
        if method is None:
            return self.render_children(node)
        return method(node)

    def render_children(self, node: Node) -> str:
        return "".join(self.render(child) for child in node.children)

    # -- 文档 ----------------------------------------------------------------

    def render_document(self, node: Node) -> str:
        body = self.render_children(node)

        if self.mode in ("body", "fragment"):
            return body

        # full mode
        meta = node.metadata
        lines: list[str] = []

        # documentclass
        cls = meta.get("documentclass", "article")
        opts = meta.get("classoptions", [])
        opts_str = f"[{','.join(opts)}]" if opts else ""
        lines.append(f"\\documentclass{opts_str}{{{cls}}}")

        # packages (带 options)
        pkg_opts = meta.get("package_options", {})
        for pkg in meta.get("packages", []):
            if pkg in pkg_opts:
                lines.append(f"\\usepackage[{pkg_opts[pkg]}]{{{pkg}}}")
            else:
                lines.append(f"\\usepackage{{{pkg}}}")

        # 如果 package_options 中有不在 packages 列表中的包
        for pkg, opts in pkg_opts.items():
            if pkg not in meta.get("packages", []):
                lines.append(f"\\usepackage[{opts}]{{{pkg}}}")

        # bibstyle
        if bibstyle := meta.get("bibstyle"):
            lines.append(f"\\bibliographystyle{{{bibstyle}}}")

        # title/author/date
        for key in ("title", "author", "date"):
            if val := meta.get(key):
                lines.append(f"\\{key}{{{val}}}")

        # extra preamble
        if preamble := meta.get("preamble"):
            lines.append(preamble)

        lines.append("")
        lines.append("\\begin{document}")
        lines.append("\\maketitle")

        # abstract
        if abstract := meta.get("abstract"):
            lines.append("")
            lines.append("\\begin{abstract}")
            lines.append(abstract.strip())
            lines.append("\\end{abstract}")

        lines.append("")
        lines.append(body)

        # bibliography
        bib = meta.get("bibliography", "")
        bib_mode = meta.get("bibliography_mode", "auto")
        if bib and bib_mode in ("auto", "standalone"):
            bib_name = bib.removesuffix(".bib")
            lines.append(f"\\bibliography{{{bib_name}}}")

        lines.append("")
        lines.append("\\end{document}")
        return "\n".join(lines) + "\n"

    # -- 块级节点 ------------------------------------------------------------

    def render_heading(self, node: Node) -> str:
        if self.mode == "fragment":
            # fragment 模式：heading 输出为纯文本段落
            text = self.render_children(node)
            return f"{text}\n\n"

        cmd = _HEADING_CMDS.get(node.level, "subparagraph")
        text = self.render_children(node)
        result = f"\\{cmd}{{{text}}}\n"
        if label := node.metadata.get("label"):
            result += f"\\label{{{label}}}\n"
        return result

    def render_paragraph(self, node: Node) -> str:
        text = self.render_children(node)
        return f"{text}\n\n"

    def render_math_block(self, node: Node) -> str:
        content = node.content
        if label := node.metadata.get("label"):
            return (
                f"\\begin{{equation}}\n"
                f"{content}\n"
                f"\\label{{{label}}}\n"
                f"\\end{{equation}}\n"
            )
        return f"\\[\n{content}\n\\]\n"

    def render_code_block(self, node: Node) -> str:
        lang = node.language
        if lang:
            return (
                f"\\begin{{lstlisting}}[language={lang}]\n"
                f"{node.content}\n"
                f"\\end{{lstlisting}}\n"
            )
        return f"\\begin{{lstlisting}}\n{node.content}\n\\end{{lstlisting}}\n"

    def render_list(self, node: Node) -> str:
        env = "enumerate" if node.ordered else "itemize"
        items = self.render_children(node)
        return f"\\begin{{{env}}}\n{items}\\end{{{env}}}\n"

    def render_list_item(self, node: Node) -> str:
        content = self.render_children(node).strip()
        return f"\\item {content}\n"

    def render_blockquote(self, node: Node) -> str:
        content = self.render_children(node)
        return f"\\begin{{quotation}}\n{content}\\end{{quotation}}\n"

    def render_raw_block(self, node: Node) -> str:
        return f"{node.content}\n"

    def render_environment(self, node: Node) -> str:
        name = node.name
        meta = node.metadata
        opts = meta.get("options", "")
        args = meta.get("args", "")

        header = f"\\begin{{{name}}}"
        if opts:
            header += f"[{opts}]"
        if args:
            header += f"{{{args}}}"

        content = self.render_children(node)
        result = f"{header}\n{content}\\end{{{name}}}\n"

        if label := meta.get("label"):
            result = f"{header}\n\\label{{{label}}}\n{content}\\end{{{name}}}\n"

        return result

    def render_thematic_break(self, node: Node) -> str:
        return "\\newpage\n"

    def render_figure(self, node: Node) -> str:
        meta = node.metadata
        placement = meta.get("placement", "htbp")
        width = meta.get("width", "")
        caption = meta.get("caption", "")
        label = meta.get("label", "")

        lines = [f"\\begin{{figure}}[{placement}]"]
        lines.append("\\centering")

        gfx_opts = f"width={width}" if width else ""
        if gfx_opts:
            lines.append(f"\\includegraphics[{gfx_opts}]{{{node.src}}}")
        else:
            lines.append(f"\\includegraphics{{{node.src}}}")

        if caption:
            lines.append(f"\\caption{{{caption}}}")
        if label:
            lines.append(f"\\label{{{label}}}")

        lines.append("\\end{figure}")
        return "\n".join(lines) + "\n"

    def render_image(self, node: Node) -> str:
        # Image without figure wrapping — if metadata has caption/label,
        # promote to figure-like rendering
        meta = node.metadata
        if meta.get("caption") or meta.get("label"):
            placement = meta.get("placement", "htbp")
            width = meta.get("width", "")
            caption = meta.get("caption", "")
            label = meta.get("label", "")

            lines = [f"\\begin{{figure}}[{placement}]"]
            lines.append("\\centering")

            gfx_opts = f"width={width}" if width else ""
            if gfx_opts:
                lines.append(f"\\includegraphics[{gfx_opts}]{{{node.src}}}")
            else:
                lines.append(f"\\includegraphics{{{node.src}}}")

            if caption:
                lines.append(f"\\caption{{{caption}}}")
            if label:
                lines.append(f"\\label{{{label}}}")

            lines.append("\\end{figure}")
            return "\n".join(lines) + "\n"

        return f"\\includegraphics{{{node.src}}}"

    def render_table(self, node: Node) -> str:
        meta = node.metadata
        caption = meta.get("caption", "")
        label = meta.get("label", "")
        placement = meta.get("placement", "htbp")

        # Column alignment
        align_map = {"left": "l", "right": "r", "center": "c"}
        col_spec = "".join(align_map.get(a, "l") for a in node.alignments)
        if not col_spec:
            col_spec = "l" * len(node.headers)

        lines = [f"\\begin{{table}}[{placement}]"]
        lines.append("\\centering")

        if caption:
            lines.append(f"\\caption{{{caption}}}")
        if label:
            lines.append(f"\\label{{{label}}}")

        lines.append(f"\\begin{{tabular}}{{{col_spec}}}")
        lines.append("\\hline")

        # Header row
        header_row = " & ".join(escape_latex(h) for h in node.headers)
        lines.append(f"{header_row} \\\\")
        lines.append("\\hline")

        # Data rows
        for row in node.rows:
            data_row = " & ".join(escape_latex(cell) for cell in row)
            lines.append(f"{data_row} \\\\")

        lines.append("\\hline")
        lines.append("\\end{tabular}")
        lines.append("\\end{table}")
        return "\n".join(lines) + "\n"

    # -- 行内节点 ------------------------------------------------------------

    def render_text(self, node: Node) -> str:
        return escape_latex_with_protection(node.content)

    def render_strong(self, node: Node) -> str:
        content = self.render_children(node)
        return f"\\textbf{{{content}}}"

    def render_emphasis(self, node: Node) -> str:
        content = self.render_children(node)
        return f"\\textit{{{content}}}"

    def render_code_inline(self, node: Node) -> str:
        return f"\\texttt{{{node.content}}}"

    def render_math_inline(self, node: Node) -> str:
        return f"${node.content}$"

    def render_link(self, node: Node) -> str:
        text = self.render_children(node)
        return f"\\href{{{node.url}}}{{{text}}}"

    def render_softbreak(self, node: Node) -> str:
        return "\n"

    def render_hardbreak(self, node: Node) -> str:
        return "\\\\\n"

    def render_citation(self, node: Node) -> str:
        keys = ",".join(node.keys)
        return f"\\{node.cmd}{{{keys}}}"

    def render_cross_ref(self, node: Node) -> str:
        sep = "~" if self.ref_tilde else ""
        return f"{node.display_text}{sep}\\ref{{{node.label}}}"

    def render_footnote_ref(self, node: Node) -> str:
        return f"\\footnotemark[{node.ref_id}]"

    def render_footnote_def(self, node: Node) -> str:
        content = self.render_children(node).strip()
        return f"\\footnotetext[{node.def_id}]{{{content}}}\n"
