"""端到端集成测试：md-mid source → LaTeX output"""

from pathlib import Path

from md_mid.parser import parse
from md_mid.comment import process_comments
from md_mid.latex import LaTeXRenderer

FIXTURES = Path(__file__).parent / "fixtures"


def convert(text: str, mode: str = "full") -> str:
    doc = parse(text)
    east = process_comments(doc, "test.md")
    return LaTeXRenderer(mode=mode).render(east)


class TestHeadingParagraph:
    def test_section_with_label(self):
        text = (FIXTURES / "heading_para.mid.md").read_text()
        result = convert(text)
        assert "\\section{Introduction}" in result
        assert "\\label{sec:intro}" in result
        assert "\\subsection{Background}" in result

    def test_inline_formatting(self):
        text = (FIXTURES / "heading_para.mid.md").read_text()
        result = convert(text)
        assert "\\textbf{bold}" in result
        assert "\\textit{italic}" in result

    def test_math(self):
        text = (FIXTURES / "heading_para.mid.md").read_text()
        result = convert(text)
        assert "$x^2$" in result
        # 有 label 的公式块应使用 equation 环境
        assert "\\begin{equation}" in result
        assert "\\label{eq:einstein}" in result


class TestMath:
    def test_inline_math(self):
        text = (FIXTURES / "math.mid.md").read_text()
        result = convert(text)
        assert "$a + b = c$" in result

    def test_block_math_no_label(self):
        text = (FIXTURES / "math.mid.md").read_text()
        result = convert(text)
        assert "\\[" in result
        assert "\\sum" in result

    def test_block_math_with_label(self):
        text = (FIXTURES / "math.mid.md").read_text()
        result = convert(text)
        assert "\\label{eq:integral}" in result


class TestRawAndEnvironment:
    def test_raw_passthrough(self):
        text = "<!-- begin: raw -->\n\\DeclareMathOperator{\\argmin}{argmin}\n<!-- end: raw -->\n"
        result = convert(text)
        assert "\\DeclareMathOperator{\\argmin}{argmin}" in result

    def test_environment(self):
        text = "<!-- begin: theorem -->\nAll primes > 2 are odd.\n<!-- end: theorem -->\n"
        result = convert(text)
        assert "\\begin{theorem}" in result
        assert "\\end{theorem}" in result


class TestFullExample:
    """对照 PRD 13.2 验证完整输出。"""

    def test_preamble(self):
        text = (FIXTURES / "full_example.mid.md").read_text()
        result = convert(text, mode="full")
        assert "\\documentclass[12pt,a4paper]{article}" in result
        assert "\\usepackage{amsmath}" in result
        assert "\\usepackage{algorithm2e}" in result
        assert "\\bibliographystyle{IEEEtran}" in result
        assert "\\title{" in result

    def test_abstract(self):
        text = (FIXTURES / "full_example.mid.md").read_text()
        result = convert(text, mode="full")
        assert "\\begin{abstract}" in result
        assert "FPGA" in result

    def test_sections_and_labels(self):
        text = (FIXTURES / "full_example.mid.md").read_text()
        result = convert(text, mode="full")
        assert "\\section{绪论}" in result
        assert "\\label{sec:intro}" in result
        assert "\\subsection{相关工作}" in result
        assert "\\label{sec:related}" in result

    def test_citations(self):
        text = (FIXTURES / "full_example.mid.md").read_text()
        result = convert(text, mode="full")
        assert "\\cite{wang2024}" in result
        assert "\\cite{fischler1981}" in result
        assert "\\cite{aiger2008}" in result

    def test_cross_refs(self):
        text = (FIXTURES / "full_example.mid.md").read_text()
        result = convert(text, mode="full")
        assert "\\ref{fig:pipeline}" in result
        assert "\\ref{tab:results}" in result
        assert "\\ref{eq:transform}" in result
        assert "\\ref{sec:related}" in result

    def test_figure(self):
        text = (FIXTURES / "full_example.mid.md").read_text()
        result = convert(text, mode="full")
        assert "\\begin{figure}" in result
        assert "\\includegraphics" in result
        assert "figures/pipeline.png" in result
        assert "\\caption{点云配准方法分类与本文方法定位}" in result

    def test_table(self):
        text = (FIXTURES / "full_example.mid.md").read_text()
        result = convert(text, mode="full")
        assert "\\begin{table}" in result
        assert "\\begin{tabular}" in result
        assert "RANSAC" in result

    def test_equation_with_label(self):
        text = (FIXTURES / "full_example.mid.md").read_text()
        result = convert(text, mode="full")
        assert "\\begin{equation}" in result
        assert "\\label{eq:transform}" in result

    def test_enumerate(self):
        text = (FIXTURES / "full_example.mid.md").read_text()
        result = convert(text, mode="full")
        assert "\\begin{enumerate}" in result
        assert "\\item" in result

    def test_bibliography(self):
        text = (FIXTURES / "full_example.mid.md").read_text()
        result = convert(text, mode="full")
        assert "\\bibliography{refs}" in result

    def test_body_mode(self):
        text = (FIXTURES / "full_example.mid.md").read_text()
        result = convert(text, mode="body")
        assert "\\documentclass" not in result
        assert "\\begin{document}" not in result
        assert "\\section{绪论}" in result
        assert "\\cite{wang2024}" in result
