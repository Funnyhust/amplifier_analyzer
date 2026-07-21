"""Convert the project defense Markdown guide into a standalone XeLaTeX file."""

from pathlib import Path
import re


HERE = Path(__file__).resolve().parent
SOURCE = HERE.parent.parent / "DEFENSE_STUDY_GUIDE.md"
OUTPUT = HERE / "study_guide.tex"


PREAMBLE = r"""\documentclass[12pt,a4paper,oneside]{article}
\usepackage{fontspec}
\setmainfont{Times New Roman}
\setsansfont{Arial}
\setmonofont{Consolas}
\usepackage{amsmath,amssymb}
\usepackage{geometry}
\geometry{top=2cm,bottom=2cm,left=2.4cm,right=2cm}
\usepackage{xcolor}
\usepackage{array,longtable,booktabs}
\usepackage{enumitem}
\usepackage{fvextra}
\usepackage{hyperref}
\usepackage{fancyhdr}
\usepackage{titlesec}
\usepackage{parskip}

\definecolor{guideblue}{HTML}{0B5FA5}
\definecolor{guidelight}{HTML}{EAF4FB}
\definecolor{guidegray}{HTML}{4B5563}
\hypersetup{colorlinks=true,linkcolor=guideblue,urlcolor=guideblue,
            pdftitle={Tài liệu ôn bảo vệ đồ án Amplifier Analyzer}}
\setcounter{tocdepth}{3}
\setcounter{secnumdepth}{3}
\setlist{itemsep=2pt,topsep=4pt,leftmargin=1.8em}
\renewcommand{\arraystretch}{1.18}
\setlength{\headheight}{14pt}
\setlength{\emergencystretch}{3em}
\pagestyle{fancy}
\fancyhf{}
\fancyhead[L]{\small Tài liệu ôn bảo vệ — Amplifier Analyzer}
\fancyhead[R]{\small\thepage}
\renewcommand{\headrulewidth}{0.4pt}
\titleformat{\part}[display]
  {\centering\bfseries\Huge\color{guideblue}}{}{0pt}{}
\titleformat{\section}{\bfseries\LARGE\color{guideblue}}
  {\thesection}{0.6em}{}
\titleformat{\subsection}{\bfseries\Large\color{guideblue}}
  {\thesubsection}{0.6em}{}
\titleformat{\subsubsection}{\bfseries\large\color{guidegray}}
  {\thesubsubsection}{0.6em}{}
\newcommand{\inlinecode}[1]{\texttt{#1}}
\renewcommand{\theHsection}{\arabic{part}.\arabic{section}}
\pdfstringdefDisableCommands{\def\inlinecode#1{#1}}

\begin{document}
\begin{titlepage}
\centering
\vspace*{2.0cm}
{\Large ĐẠI HỌC BÁCH KHOA HÀ NỘI\par}
\vspace{2.2cm}
{\Huge\bfseries\color{guideblue} TÀI LIỆU ÔN BẢO VỆ ĐỒ ÁN\par}
\vspace{0.8cm}
{\LARGE Bộ phân tích mạch khuếch đại\par}
\vspace{1.5cm}
{\large Kiến thức nền — Công thức — Giải thích source code\par}
\vfill
{\large Biên soạn từ source và báo cáo hiện tại của dự án\par}
\vspace{0.8cm}
{\large 2026\par}
\end{titlepage}

\pagenumbering{roman}
\tableofcontents
\clearpage
\pagenumbering{arabic}
"""


POSTAMBLE = r"""
\end{document}
"""


SPECIALS = {
    "\\": r"\textbackslash{}",
    "&": r"\&",
    "%": r"\%",
    "#": r"\#",
    "_": r"\_",
    "{": r"\{",
    "}": r"\}",
    "~": r"\textasciitilde{}",
    "^": r"\textasciicircum{}",
    "<": r"\textless{}",
    ">": r"\textgreater{}",
}


def escape_plain(text: str) -> str:
    return "".join(SPECIALS.get(char, char) for char in text)


def inline(text: str) -> str:
    """Convert inline Markdown while preserving LaTeX between dollar signs."""
    output = []
    index = 0
    while index < len(text):
        if text.startswith("**", index):
            end = text.find("**", index + 2)
            if end >= 0:
                output.append(r"\textbf{" + inline(text[index + 2:end]) + "}")
                index = end + 2
                continue
        if text[index] == "`":
            end = text.find("`", index + 1)
            if end >= 0:
                output.append(r"\inlinecode{" + escape_plain(text[index + 1:end]) + "}")
                index = end + 1
                continue
        if text[index] == "$":
            end = text.find("$", index + 1)
            if end >= 0:
                output.append(text[index:end + 1])
                index = end + 1
                continue
        output.append(escape_plain(text[index]))
        index += 1
    return "".join(output)


def parse_table_row(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def table_column_spec(column_count: int) -> str:
    if column_count == 2:
        widths = (0.28, 0.64)
    elif column_count == 3:
        widths = (0.20, 0.25, 0.47)
    elif column_count == 4:
        widths = (0.16, 0.18, 0.18, 0.38)
    else:
        width = 0.90 / max(column_count, 1)
        widths = tuple(width for _ in range(column_count))
    return "|" + "|".join(
        rf">{{\raggedright\arraybackslash}}p{{{width:.2f}\textwidth}}"
        for width in widths
    ) + "|"


def emit_table(rows: list[list[str]]) -> list[str]:
    column_count = len(rows[0])
    lines = [rf"\begin{{longtable}}{{{table_column_spec(column_count)}}}", r"\hline"]
    header = " & ".join(r"\textbf{" + inline(cell) + "}" for cell in rows[0])
    lines.extend([header + r" \\ \hline", r"\endfirsthead", r"\hline",
                  header + r" \\ \hline", r"\endhead"])
    for row in rows[1:]:
        padded = row + [""] * (column_count - len(row))
        lines.append(" & ".join(inline(cell) for cell in padded[:column_count]) + r" \\ \hline")
    lines.append(r"\end{longtable}")
    return lines


def convert(markdown: str) -> str:
    source_lines = markdown.splitlines()
    result = [PREAMBLE.rstrip()]
    paragraph: list[str] = []
    index = 0
    first_title_skipped = False

    def flush_paragraph() -> None:
        if paragraph:
            result.append(inline(" ".join(part.strip() for part in paragraph)))
            result.append("")
            paragraph.clear()

    while index < len(source_lines):
        line = source_lines[index]
        stripped = line.strip()

        if stripped == "$$":
            flush_paragraph()
            result.append(r"\[")
            index += 1
            while index < len(source_lines) and source_lines[index].strip() != "$$":
                result.append(source_lines[index])
                index += 1
            result.extend([r"\]", ""])
            index += 1
            continue

        if stripped.startswith("```"):
            flush_paragraph()
            result.append(r"\begin{Verbatim}[breaklines=true,breakanywhere=true,fontsize=\small]")
            index += 1
            while index < len(source_lines) and not source_lines[index].strip().startswith("```"):
                result.append(source_lines[index])
                index += 1
            result.extend([r"\end{Verbatim}", ""])
            index += 1
            continue

        if stripped.startswith("|") and index + 1 < len(source_lines):
            separator = source_lines[index + 1].strip()
            if separator.startswith("|") and re.fullmatch(r"[|:\- ]+", separator):
                flush_paragraph()
                rows = [parse_table_row(line)]
                index += 2
                while index < len(source_lines) and source_lines[index].strip().startswith("|"):
                    rows.append(parse_table_row(source_lines[index]))
                    index += 1
                result.extend(emit_table(rows))
                result.append("")
                continue

        heading = re.match(r"^(#{1,4})\s+(.+)$", stripped)
        if heading:
            flush_paragraph()
            level = len(heading.group(1))
            raw_title = heading.group(2)
            if level > 1:
                # Markdown headings already carry display numbers ("1.", "2.3.", ...).
                # Let LaTeX own numbering so the printed heading is not duplicated.
                raw_title = re.sub(r"^\d+(?:\.\d+)*\.\s+", "", raw_title)
            title = inline(raw_title)
            if level == 1 and not first_title_skipped:
                first_title_skipped = True
            elif level == 1:
                result.extend(
                    [r"\clearpage", rf"\part{{{title}}}", r"\setcounter{section}{0}"]
                )
            elif level == 2:
                result.append(rf"\section{{{title}}}")
            elif level == 3:
                result.append(rf"\subsection{{{title}}}")
            else:
                result.append(rf"\subsubsection{{{title}}}")
            result.append("")
            index += 1
            continue

        if stripped == "---":
            flush_paragraph()
            result.extend([r"\clearpage", ""])
            index += 1
            continue

        if re.match(r"^-\s+", stripped):
            flush_paragraph()
            result.append(r"\begin{itemize}")
            while index < len(source_lines):
                item = re.match(r"^-\s+(.+)$", source_lines[index].strip())
                if not item:
                    break
                result.append(r"\item " + inline(item.group(1)))
                index += 1
            result.extend([r"\end{itemize}", ""])
            continue

        if re.match(r"^\d+\.\s+", stripped):
            flush_paragraph()
            result.append(r"\begin{enumerate}")
            while index < len(source_lines):
                item = re.match(r"^\d+\.\s+(.+)$", source_lines[index].strip())
                if not item:
                    break
                result.append(r"\item " + inline(item.group(1)))
                index += 1
            result.extend([r"\end{enumerate}", ""])
            continue

        if not stripped:
            flush_paragraph()
        else:
            paragraph.append(stripped)
        index += 1

    flush_paragraph()
    result.append(POSTAMBLE.strip())
    return "\n".join(result) + "\n"


def main() -> None:
    markdown = SOURCE.read_text(encoding="utf-8")
    OUTPUT.write_text(convert(markdown), encoding="utf-8", newline="\n")
    print(f"Generated: {OUTPUT}")


if __name__ == "__main__":
    main()
