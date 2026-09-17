"""Markdown <-> Apple Notes HTML conversion for apple-notes-pkm (stdlib only).

Apple Notes accepts a small HTML subset when a note body is set through
Automation: h1-h3, div/br, b/i/u/s, tt/pre (monospaced), ul/ol/li, a,
blockquote, table. Everything here targets that subset. Obsidian-specific
syntax (frontmatter, wikilinks, embeds, callouts) is flattened into plain,
searchable text so no legacy link target is lost.
"""
from __future__ import annotations

import html
import re
from html.parser import HTMLParser
from typing import Any

WIKILINK_RE = re.compile(r"(!?)\[\[([^\]\|#]*)(?:#([^\]\|]*))?(?:\|([^\]]*))?\]\]")
MD_IMAGE_RE = re.compile(r"!\[([^\]]*)\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
MD_LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
AUTOLINK_RE = re.compile(r"(?<![\"'>=\w])(https?://[^\s<>()\]]+[^\s<>()\].,;:!?\"'])")
CODE_RE = re.compile(r"`([^`]+)`")
BOLD_RE = re.compile(r"\*\*(.+?)\*\*|__(.+?)__")
ITALIC_RE = re.compile(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])|(?<![\w_])_(?!\s)(.+?)(?<!\s)_(?![\w_])")
STRIKE_RE = re.compile(r"~~(.+?)~~")
HIGHLIGHT_RE = re.compile(r"==(.+?)==")
HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
LIST_RE = re.compile(r"^(\s*)([-*+]|\d+[.)])\s+(.*)$")
CHECK_RE = re.compile(r"^\[([ xX])\]\s+(.*)$")
TABLE_SEP_RE = re.compile(r"^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?\s*$")
CALLOUT_RE = re.compile(r"^\[!(\w+)\]([+-]?)\s*(.*)$")
HR_RE = re.compile(r"^\s*([-*_])(\s*\1){2,}\s*$")
FENCE_RE = re.compile(r"^\s*(```|~~~)")
COMMENT_RE = re.compile(r"%%.*?%%", re.S)

# Frontmatter keys that materially aid retrieval when kept as visible text.
RETAINED_META_KEYS = (
    "aliases", "Aliases", "title", "description", "related", "source", "sources",
    "link", "author", "chapter", "concept", "date", "created", "updated", "status",
    "type", "week", "supersedes", "superseded_by", "superseded_on", "tags",
)


# --------------------------------------------------------------------------
# Frontmatter
# --------------------------------------------------------------------------

def split_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    """Return (frontmatter dict, body). Tolerant of the vault's hand-written YAML."""
    if not text.startswith("---"):
        return {}, text
    lines = text.splitlines()
    if lines[0].strip() != "---":
        return {}, text
    end = None
    for index in range(1, len(lines)):
        if lines[index].strip() in ("---", "..."):
            end = index
            break
    if end is None:
        return {}, text
    meta = _parse_simple_yaml(lines[1:end])
    body = "\n".join(lines[end + 1:])
    return meta, body.lstrip("\n")


def _parse_simple_yaml(lines: list[str]) -> dict[str, Any]:
    meta: dict[str, Any] = {}
    key: str | None = None
    for raw in lines:
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        if raw.startswith((" ", "\t")) and key is not None:
            stripped = raw.strip()
            if stripped.startswith("- "):
                value = meta.get(key)
                if not isinstance(value, list):
                    value = [] if value in (None, "") else [value]
                value.append(_yaml_scalar(stripped[2:]))
                meta[key] = value
            else:
                existing = meta.get(key)
                meta[key] = (f"{existing} {stripped}".strip() if isinstance(existing, str) else stripped)
            continue
        match = re.match(r"^([A-Za-z0-9_-]+)\s*:\s*(.*)$", raw)
        if not match:
            continue
        key, value = match.group(1), match.group(2).strip()
        if value.startswith("[") and value.endswith("]") and _is_inline_list(value):
            inner = value[1:-1].strip()
            meta[key] = [_yaml_scalar(v) for v in _split_inline_list(inner)] if inner else []
        else:
            meta[key] = _yaml_scalar(value) if value else ""
    return meta


def _is_inline_list(value: str) -> bool:
    """True for `[a, b]` / `[[[A]], [[B]]]`, false for a bare `[[A]], [[B]]` string
    or a single `[[A]]` wikilink scalar."""
    if value.startswith("[[") and not value.startswith("[[["):
        return False
    inner = value[1:-1]
    depth = 0
    for ch in inner:
        depth += 1 if ch == "[" else -1 if ch == "]" else 0
        if depth < 0:
            return False
    return depth == 0


def _split_inline_list(inner: str) -> list[str]:
    out, depth, current = [], 0, ""
    for ch in inner:
        if ch == "[":
            depth += 1
        elif ch == "]":
            depth -= 1
        if ch == "," and depth == 0:
            out.append(current)
            current = ""
        else:
            current += ch
    if current.strip():
        out.append(current)
    return [item.strip() for item in out]


def _yaml_scalar(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        return value[1:-1]
    return value


def flatten_wikilinks(text: str) -> str:
    """Replace wikilinks with plain searchable text that keeps the target title."""
    def repl(match: re.Match[str]) -> str:
        embed, target, section, alias = match.groups()
        target = (target or "").strip()
        section = (section or "").strip()
        alias = (alias or "").strip()
        if embed:
            name = target or section
            return f"[attachment: {name}]"
        if not target and section:
            return alias or f"› {section}"
        shown = target + (f" › {section}" if section else "")
        if alias and alias != target and alias != shown:
            return f"{alias} ({shown})"
        return shown
    return WIKILINK_RE.sub(repl, text)


def meta_lines(meta: dict[str, Any]) -> list[str]:
    """Frontmatter values worth keeping as visible text, in a stable order."""
    lines: list[str] = []
    for key in RETAINED_META_KEYS:
        if key not in meta:
            continue
        value = meta[key]
        if isinstance(value, list):
            rendered = ", ".join(str(v) for v in value if str(v).strip())
        else:
            rendered = str(value).strip()
        if not rendered:
            continue
        lines.append(f"{key.capitalize() if key != 'superseded_by' else 'Superseded by'}: {flatten_wikilinks(rendered)}")
    return lines


def stage_markdown(text: str, *, title: str) -> tuple[str, dict[str, Any], list[str]]:
    """Transform one vault note into Apple-friendly Markdown for import.

    Returns (staged markdown, frontmatter, embed names). Frontmatter is removed
    and its retrieval-relevant values appended as plain text; wikilinks keep
    their target titles as visible text; callout headers become bold lines;
    embeds become `[attachment: name]` placeholders (the files themselves are
    attached separately when they resolve)."""
    meta, body = split_frontmatter(text)
    embeds = [m.group(2).strip() or m.group(3).strip() for m in WIKILINK_RE.finditer(body) if m.group(1)]
    body = COMMENT_RE.sub("", body)
    body = flatten_wikilinks(body)
    body = re.sub(r"^(\s*>\s*)\[!(\w+)\][+-]?\s*(.*)$",
                  lambda m: f"{m.group(1)}**{m.group(2).capitalize()}{': ' + m.group(3).strip().replace('**', '') if m.group(3).strip() else ''}**",
                  body, flags=re.M)
    lines = _demote_title_heading(body.splitlines(), title)
    staged = "\n".join(lines).strip("\n") + "\n"
    extra = meta_lines(meta)
    if extra:
        staged += "\n" + "\n".join(extra) + "\n"
    return staged, meta, embeds


# --------------------------------------------------------------------------
# Markdown -> Notes HTML
# --------------------------------------------------------------------------

def inline_html(text: str) -> str:
    """Escape then apply inline Markdown. Wikilinks/embeds are flattened first."""
    text = COMMENT_RE.sub("", text)
    text = flatten_wikilinks(text)
    # Protect code spans from further formatting.
    codes: list[str] = []

    def stash_code(match: re.Match[str]) -> str:
        codes.append(match.group(1))
        return f"\x00{len(codes) - 1}\x00"

    text = CODE_RE.sub(stash_code, text)
    text = html.escape(text, quote=False)
    # The text is already HTML-escaped, so hrefs must not be escaped a second time.
    text = MD_IMAGE_RE.sub(lambda m: f'<a href="{m.group(2)}">{m.group(1) or m.group(2)}</a>', text)
    text = MD_LINK_RE.sub(lambda m: f'<a href="{m.group(2)}">{m.group(1)}</a>', text)
    text = AUTOLINK_RE.sub(lambda m: f'<a href="{m.group(1)}">{m.group(1)}</a>', text)
    text = BOLD_RE.sub(lambda m: f"<b>{m.group(1) or m.group(2)}</b>", text)
    text = ITALIC_RE.sub(lambda m: f"<i>{m.group(1) or m.group(2)}</i>", text)
    text = STRIKE_RE.sub(r"<s>\1</s>", text)
    text = HIGHLIGHT_RE.sub(r"<b>\1</b>", text)
    text = re.sub(r"\x00(\d+)\x00", lambda m: f"<tt>{html.escape(codes[int(m.group(1))], quote=False)}</tt>", text)
    return text.replace("\n", "<br>")


def markdown_to_notes_html(markdown: str, *, title: str | None = None, meta: dict[str, Any] | None = None) -> str:
    """Convert Markdown to the HTML subset Apple Notes keeps. The first block
    is an <h1> holding the note title (Notes derives its title from it)."""
    parts: list[str] = []
    lines = markdown.splitlines()
    if title:
        parts.append(f"<div><h1>{html.escape(title, quote=False)}</h1></div>")
        lines = _demote_title_heading(lines, title)
    parts.extend(_render_blocks(lines))
    extra = meta_lines(meta or {})
    if extra:
        parts.append("<div><br></div>")
        for line in extra:
            parts.append(f"<div>{inline_html(line)}</div>")
    return "".join(parts)


def _demote_title_heading(lines: list[str], title: str) -> list[str]:
    """The note title already occupies the H1 slot. A leading body H1 that
    repeats it is dropped; every other body H1 becomes an H2 so Notes keeps
    exactly one title line."""
    out: list[str] = []
    seen_content = False
    for line in lines:
        heading = HEADING_RE.match(line)
        if heading and len(heading.group(1)) == 1:
            text = heading.group(2).strip()
            if not seen_content and text.casefold() == title.casefold():
                seen_content = True
                continue
            out.append("## " + text)
            seen_content = True
            continue
        if line.strip():
            seen_content = True
        out.append(line)
    return out


def _render_blocks(lines: list[str]) -> list[str]:
    out: list[str] = []
    index = 0
    n = len(lines)
    while index < n:
        line = lines[index]
        stripped = line.strip()
        if not stripped:
            out.append("<div><br></div>")
            index += 1
            continue
        if FENCE_RE.match(line):
            fence = FENCE_RE.match(line).group(1)
            index += 1
            code: list[str] = []
            while index < n and not lines[index].strip().startswith(fence):
                code.append(lines[index])
                index += 1
            index += 1  # closing fence
            for code_line in code or [""]:
                out.append(f"<div><tt>{html.escape(code_line, quote=False) or '<br>'}</tt></div>")
            continue
        heading = HEADING_RE.match(line)
        if heading:
            level = min(len(heading.group(1)), 3)
            out.append(f"<div><h{level}>{inline_html(heading.group(2))}</h{level}></div>")
            index += 1
            continue
        if HR_RE.match(line):
            out.append("<div><hr></div>")
            index += 1
            continue
        if stripped.startswith(">"):
            quote: list[str] = []
            while index < n and lines[index].strip().startswith(">"):
                quote.append(re.sub(r"^\s*>\s?", "", lines[index]))
                index += 1
            out.append(_render_quote(quote))
            continue
        if stripped.startswith("|") and index + 1 < n and TABLE_SEP_RE.match(lines[index + 1]):
            rows: list[str] = []
            while index < n and lines[index].strip().startswith("|"):
                rows.append(lines[index])
                index += 1
            out.append(_render_table(rows))
            continue
        if LIST_RE.match(line):
            items: list[str] = []
            while index < n and (LIST_RE.match(lines[index]) or (lines[index].startswith((" ", "\t")) and lines[index].strip())):
                items.append(lines[index])
                index += 1
            out.append(_render_list(items))
            continue
        # Paragraph: consecutive non-blank, non-block lines; newlines become <br>.
        para: list[str] = []
        while index < n and lines[index].strip() and not _starts_block(lines[index], lines[index + 1] if index + 1 < n else ""):
            para.append(lines[index].rstrip())
            index += 1
        if not para:  # defensive: never loop forever on an unexpected line
            para.append(lines[index].rstrip())
            index += 1
        out.append("<div>" + inline_html("\n".join(para)) + "</div>")
    return out


def _starts_block(line: str, next_line: str) -> bool:
    stripped = line.strip()
    return bool(
        FENCE_RE.match(line) or HEADING_RE.match(line) or HR_RE.match(line)
        or stripped.startswith(">") or LIST_RE.match(line)
        or (stripped.startswith("|") and TABLE_SEP_RE.match(next_line))
    )


def _render_quote(lines: list[str]) -> str:
    body = list(lines)
    label = None
    if body:
        callout = CALLOUT_RE.match(body[0].strip())
        if callout:
            kind, _fold, heading = callout.groups()
            label = kind.capitalize() + (f": {heading}" if heading.strip() else "")
            body = body[1:]
    inner = _render_blocks(body)
    prefix = f"<div><b>{inline_html(label)}</b></div>" if label else ""
    return f"<blockquote>{prefix}{''.join(inner)}</blockquote>"


def _render_table(rows: list[str]) -> str:
    cells = []
    for row_index, row in enumerate(rows):
        if row_index == 1 and TABLE_SEP_RE.match(row):
            continue
        row = flatten_wikilinks(row.strip())
        if row.startswith("|"):
            row = row[1:]
        if row.endswith("|") and not row.endswith("\\|"):
            row = row[:-1]
        parts = [p.strip() for p in re.split(r"(?<!\\)\|", row)]
        parts = [p.replace("\\|", "|") for p in parts]
        tag = "th" if row_index == 0 else "td"
        cells.append("<tr>" + "".join(f"<{tag}>{inline_html(p)}</{tag}>" for p in parts) + "</tr>")
    return "<table>" + "".join(cells) + "</table>"


def _render_list(lines: list[str]) -> str:
    """Nested lists from indentation. Checklist items keep a visible box glyph."""
    items: list[tuple[int, bool, str]] = []  # (indent, ordered, text)
    for line in lines:
        match = LIST_RE.match(line)
        if match:
            indent = len(match.group(1).replace("\t", "    "))
            ordered = match.group(2)[0].isdigit()
            text = match.group(3)
            check = CHECK_RE.match(text)
            if check:
                box = "☑" if check.group(1).lower() == "x" else "☐"
                text = f"{box} {check.group(2)}"
            items.append((indent, ordered, text))
        elif items:
            indent, ordered, text = items[-1]
            items[-1] = (indent, ordered, text + "\n" + line.strip())
    out: list[str] = []
    stack: list[tuple[int, str]] = []
    for indent, ordered, text in items:
        tag = "ol" if ordered else "ul"
        while stack and indent < stack[-1][0]:
            out.append(f"</{stack.pop()[1]}>")
        if not stack or indent > stack[-1][0]:
            out.append(f"<{tag}>")
            stack.append((indent, tag))
        elif stack[-1][1] != tag:
            # Notes merges adjacent lists of different kinds into one; a blank
            # line between them keeps numbering intact.
            out.append(f"</{stack.pop()[1]}>" + ("<div><br></div>" if not stack else "") + f"<{tag}>")
            stack.append((indent, tag))
        out.append(f"<li>{inline_html(text)}</li>")
    while stack:
        out.append(f"</{stack.pop()[1]}>")
    return "".join(out)


# --------------------------------------------------------------------------
# Notes HTML -> Markdown (for reads; never emits inline media)
# --------------------------------------------------------------------------

class _NotesHTMLToMarkdown(HTMLParser):
    BLOCK = {"div", "p", "h1", "h2", "h3", "h4", "h5", "h6", "ul", "ol", "li", "blockquote", "table", "tr", "pre", "hr"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.out: list[str] = []
        self.list_stack: list[tuple[str, int]] = []
        self.href: str | None = None
        self.link_text: list[str] = []
        self.in_quote = 0
        self.in_cell = False
        self.row: list[str] = []
        self.table_rows: list[list[str]] = []
        self.in_table = False
        self.pending_heading: str | None = None
        self.mono = 0

    def _emit(self, text: str) -> None:
        if self.href is not None:
            self.link_text.append(text)
        elif self.in_cell:
            self.row[-1] += text
        else:
            self.out.append(text)

    def _newline(self) -> None:
        if self.in_cell:
            return
        if self.out and not self.out[-1].endswith("\n"):
            self.out.append("\n")

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            self._newline()
            self._emit("#" * min(int(tag[1]), 6) + " ")
        elif tag == "br":
            self._emit("\n" if not self.in_cell else " ")
        elif tag in ("div", "p"):
            self._newline()
            if self.in_quote:
                self._emit("> ")
        elif tag == "hr":
            self._newline()
            self._emit("---\n")
        elif tag in ("b", "strong"):
            self._emit("**")
        elif tag in ("i", "em"):
            self._emit("*")
        elif tag in ("s", "strike", "del"):
            self._emit("~~")
        elif tag in ("tt", "code"):
            self.mono += 1
            self._emit("`")
        elif tag == "pre":
            self._newline()
            self._emit("```\n")
        elif tag in ("ul", "ol"):
            self.list_stack.append((tag, 0))
        elif tag == "li":
            self._newline()
            depth = max(len(self.list_stack) - 1, 0)
            if self.list_stack and self.list_stack[-1][0] == "ol":
                kind, count = self.list_stack[-1]
                self.list_stack[-1] = (kind, count + 1)
                self._emit("  " * depth + f"{count + 1}. ")
            else:
                self._emit("  " * depth + "- ")
        elif tag == "blockquote":
            self.in_quote += 1
            self._newline()
            self._emit("> ")
        elif tag == "a":
            self.href = attrs.get("href")
            self.link_text = []
        elif tag == "table":
            self.in_table = True
            self.table_rows = []
        elif tag == "tr":
            self.row = []
        elif tag in ("td", "th"):
            self.in_cell = True
            self.row.append("")
        elif tag == "img":
            src = attrs.get("src") or ""
            label = attrs.get("alt") or ("" if src.startswith("data:") else src[:80])
            self._emit(f"[image: {label}]" if label else "[image]")
        elif tag == "object":
            self._emit("[attachment]")

    def handle_endtag(self, tag):
        if tag in ("b", "strong"):
            self._emit("**")
        elif tag in ("i", "em"):
            self._emit("*")
        elif tag in ("s", "strike", "del"):
            self._emit("~~")
        elif tag in ("tt", "code"):
            self.mono = max(self.mono - 1, 0)
            self._emit("`")
        elif tag == "pre":
            self._newline()
            self._emit("```\n")
        elif tag in ("ul", "ol"):
            if self.list_stack:
                self.list_stack.pop()
            self._newline()
        elif tag == "blockquote":
            self.in_quote = max(self.in_quote - 1, 0)
            self._newline()
        elif tag == "a":
            text = "".join(self.link_text).strip()
            href = self.href
            self.href = None
            if href and href != text and not href.startswith("applenotes:"):
                self._emit(f"[{text or href}]({href})")
            else:
                self._emit(text or href or "")
        elif tag in ("td", "th"):
            self.in_cell = False
        elif tag == "tr":
            self.table_rows.append(self.row)
        elif tag == "table":
            self.in_table = False
            self._newline()
            if self.table_rows:
                width = max(len(r) for r in self.table_rows)
                rows = [r + [""] * (width - len(r)) for r in self.table_rows]
                cell = lambda c: c.strip().replace("|", "\\|")  # noqa: E731
                self.out.append("| " + " | ".join(cell(c) for c in rows[0]) + " |\n")
                self.out.append("|" + "---|" * width + "\n")
                for r in rows[1:]:
                    self.out.append("| " + " | ".join(cell(c) for c in r) + " |\n")
        elif tag in ("div", "p", "h1", "h2", "h3", "h4", "h5", "h6"):
            self._newline()

    def handle_data(self, data):
        if self.in_table and not self.in_cell:
            return
        # Newlines between block tags are formatting in the source HTML, not content.
        if "\n" in data and not data.strip() and (not self.out or self.out[-1].endswith("\n")):
            return
        text = data.replace("\xa0", " ")
        if not self.mono:
            text = re.sub(r"[ \t]+", " ", text)
        self._emit(text)


NOTES_HEADING_RE = re.compile(
    r'<b>(?:<font[^>]*>)?<span style="font-size: (\d+)px">(.*?)</span>(?:</font>)?</b>', re.S)
NOTES_INLINE_CODE_RE = re.compile(r'<font face="Courier"><span style="font-size: \d+px">(.*?)</span></font>', re.S)
NOTES_BLOCK_CODE_RE = re.compile(r'<div><font face="Courier"><tt>(.*?)</tt></font>(?:<span[^>]*><tt><br></tt></span>)?</div>', re.S)
DATA_URI_RE = re.compile(r'(src|href)="data:([^;"]+);base64,[^"]*"')


def _heading_tag(match: re.Match[str]) -> str:
    size = int(match.group(1))
    level = 1 if size >= 22 else 2 if size >= 17 else 3
    return f"<h{level}>{match.group(2)}</h{level}>"


def normalize_notes_html(body: str) -> str:
    """Map Apple Notes' presentational HTML back onto semantic tags before parsing."""
    body = body or ""
    body = NOTES_HEADING_RE.sub(_heading_tag, body)
    body = NOTES_BLOCK_CODE_RE.sub(r"<pre>\1</pre>", body)
    body = NOTES_INLINE_CODE_RE.sub(r"<tt>\1</tt>", body)
    body = re.sub(r'<font face="Courier">(.*?)</font>', r"<tt>\1</tt>", body, flags=re.S)
    body = re.sub(r"</?font[^>]*>", "", body)
    body = re.sub(r"<span[^>]*>|</span>", "", body)
    body = re.sub(r"<object>\s*(<table)", r"\1", body)
    body = re.sub(r"(</table>)\s*</object>", r"\1", body)
    return body


def scrub_data_uris(body: str) -> str:
    """Replace inline base64 media with a short marker; never ship it to callers."""
    return DATA_URI_RE.sub(lambda m: f'{m.group(1)}="data:{m.group(2)};base64,[omitted]"', body or "")


def notes_html_to_markdown(body: str) -> str:
    parser = _NotesHTMLToMarkdown()
    parser.feed(normalize_notes_html(body))
    parser.close()
    text = "".join(parser.out)
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = text.replace("```\n```\n", "")  # merge adjacent code-block lines
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip() + ("\n" if text.strip() else "")
