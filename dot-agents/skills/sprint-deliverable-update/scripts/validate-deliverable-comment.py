#!/usr/bin/env python3
"""Gate a sprint-update or deliverable-summary artifact before review or posting.

Enforces the Key Rules in ../SKILL.md mechanically. Errors block (exit 1);
warnings are heuristics that print but do not block.

    validate-deliverable-comment.py --artifact sprint-update --mode review \
        --root ./bundle bundle/comment.md

    validate-deliverable-comment.py --artifact deliverable-summary --mode post \
        --check-urls comment.md

Run --selftest to check the checks.
"""

import argparse
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

TAG = "@juchang111"

# Images arrive in two forms: Markdown, and the raw <img> tag GitHub's own
# composer inserts for a pasted screenshot. Both count.
MD_IMAGE = re.compile(r"!\[(?P<alt>[^\]]*)\]\((?P<target>[^)\s]+)")
HTML_IMAGE = re.compile(r"""<img\b[^>]*?src=["'](?P<target>[^"']+)["'][^>]*>""", re.I)
HTML_ALT = re.compile(r"""\balt=["'](?P<alt>[^"']*)["']""", re.I)

# ponytail: curated placeholder patterns, not a general template engine. Every
# entry below is a literal token from a SKILL.md template or a word that only
# appears in unfinished copy.
PLACEHOLDER = re.compile(
    r"\bTODO\b|\bTBD\b|\bFIXME\b|\bXXX\b|RESOLVED_IMAGE_TARGET|\{NUMBER\}"
    r"|\bSprint X\.Y\b|\bX\.Y\+1\b|\[emoji\]|\bplaceholder\b",
    re.I,
)
EDITORIAL = re.compile(
    r"(?i)\b(consider adding|we could add|should add|to be added|coming soon"
    r"|add (?:a |the )?screenshot|attach (?:a |the )?screenshot)\b"
)
# A bracketed lowercase phrase that is not a link label and not a task checkbox
# is almost always an unfilled template slot: "[deliverable name]", "[goal 1]".
UNFILLED_SLOT = re.compile(r"\[(?P<slot>[a-z][a-z0-9 ,./'\"-]{2,})\](?!\()")
NUMBERED_LABEL = re.compile(
    r"(?im)^#{2,4}\s*(?:criteri(?:on|a)|metric|ac)\s*#?\d+\b"
)
LOCAL_TARGET = re.compile(r"^(?:file://|/tmp/|/private/tmp/|~|[A-Za-z]:\\)")
ISSUE_LINK = re.compile(r"https?://\S*?/issues/\d+|(?<![\w/])#\d+\b")
ANY_LINK = re.compile(r"\]\((?P<url>[^)\s]+)")
# A #NNN that is not a link label ("[#355](...)") and not part of a URL or a
# "repo#NNN" ref. GitHub resolves it against the repo the comment is posted on
# (simpler-grants-gov), not the repo the drafter meant.
BARE_REF = re.compile(r"(?<![\w/\[&])#\d+\b(?!\]\()")

SHAPES = {
    "sprint-update": {
        "required": [
            (re.compile(r"(?m)^##\s+Sprint\s+\d+\.\d+\s+updates\b"), "`## Sprint X.Y updates` heading"),
            (re.compile(r"(?im)^#{2,3}\s*Sprint goal\b"), "Sprint goal section"),
            (re.compile(r"(?im)^#{2,3}\s*Accomplishments\b"), "Accomplishments section"),
            (re.compile(r"(?im)^#{2,3}\s*Rollover\b"), "Rollover section"),
            (re.compile(r"(?im)^#{2,3}\s*Risks\b"), "Risks section"),
            (re.compile(r"(?im)^#{2,3}\s*Next sprint\b"), "Next sprint section"),
        ],
        "forbidden": [
            (re.compile(r"(?m)^#{1,2}\s+Deliverable summary\b"), "deliverable-summary heading in a sprint update"),
            (re.compile(r"(?im)^#{3,4}\s*Criteria completed\b"), "'Criteria completed' must be an H2, not H3/H4"),
        ],
    },
    "deliverable-summary": {
        "required": [
            # SKILL.md defaults to H1, but posted precedent uses H2; either satisfies the gate.
            (re.compile(r"(?m)^#{1,2}\s+Deliverable summary\b"), "`# Deliverable summary` heading"),
            (re.compile(r"(?im)^##\s*Acceptance criteria\b"), "Acceptance criteria section"),
            (re.compile(r"(?im)^##\s*Metrics\b"), "Metrics section"),
        ],
        "forbidden": [
            (re.compile(r"(?im)^#{2,3}\s*(?:Sprint goal|Rollover|Risks|Next sprint)\b"),
             "sprint-update section in a deliverable summary"),
            (re.compile(r"(?m)^##\s+Sprint\s+\d+\.\d+\s+updates\b"),
             "sprint-update heading in a deliverable summary"),
        ],
    },
}


class Report:
    def __init__(self, path):
        self.path = path
        self.errors = []
        self.warnings = []

    def error(self, line, msg):
        self.errors.append(f"ERROR {self.path}:{line}: {msg}")

    def warn(self, line, msg):
        self.warnings.append(f"WARN  {self.path}:{line}: {msg}")

    def ok(self):
        return not self.errors


def line_of(text, index):
    return text.count("\n", 0, index) + 1


def images(text):
    """[(line, target, alt)] for both Markdown and HTML image syntax."""
    found = []
    for m in MD_IMAGE.finditer(text):
        found.append((line_of(text, m.start()), m.group("target"), m.group("alt").strip()))
    for m in HTML_IMAGE.finditer(text):
        alt = HTML_ALT.search(m.group(0))
        found.append((line_of(text, m.start()), m.group("target"), (alt.group("alt").strip() if alt else "")))
    return found


def section(text, heading):
    """Body of the named section, up to the next heading of any level."""
    start = re.search(rf"(?im)^#{{2,4}}\s*{heading}\b.*$", text)
    if not start:
        return "", 0
    rest = text[start.end():]
    nxt = re.search(r"(?m)^#{1,4}\s", rest)
    body = rest[: nxt.start()] if nxt else rest
    return body, line_of(text, start.end())


def check_content(text, report):
    if TAG not in text:
        report.error(1, f"missing {TAG} — every comment opens by tagging Julius (rule 1)")

    for pattern, label in ((PLACEHOLDER, "placeholder/TODO"), (EDITORIAL, "editorial instruction")):
        for m in pattern.finditer(text):
            report.error(line_of(text, m.start()),
                         f"{label} in user-facing copy: {m.group(0)!r} — final means final (rule 6)")

    for m in UNFILLED_SLOT.finditer(text):
        report.error(line_of(text, m.start()),
                     f"unfilled template slot: [{m.group('slot')}] (rule 6)")

    for m in BARE_REF.finditer(text):
        report.error(line_of(text, m.start()),
                     f"bare reference {m.group(0)!r} resolves against the repo the comment is posted on "
                     "— use a full-URL link (rule 9)")

    for m in NUMBERED_LABEL.finditer(text):
        report.error(line_of(text, m.start()),
                     f"numbered label {m.group(0).strip()!r} — use the bolded name from the deliverable (rule 2)")


def check_images(text, report, mode, root, check_urls):
    found = images(text)

    if re.search(r"(?i)screenshot", text) and not found:
        report.error(1, "copy mentions a screenshot but no image is embedded — embed or omit (rule 7)")

    for line, target, alt in found:
        if not alt:
            report.error(line, f"image {target} has empty alt text")

        if LOCAL_TARGET.match(target):
            report.error(line, f"local image path {target!r} is never postable (rule 8)")
            continue

        remote = target.startswith("http://") or target.startswith("https://")

        if mode == "review":
            if remote:
                if target.startswith("http://"):
                    report.error(line, f"insecure image URL {target!r} — https required (rule 8)")
                continue
            if root is None:
                report.error(line, "review mode with relative image targets requires --root")
                continue
            if not (root / target).is_file():
                report.error(line, f"relative image {target!r} is not in the bundle at {root}")
        else:  # post
            if not target.startswith("https://"):
                report.error(line, f"post-ready comment needs a live HTTPS image URL, got {target!r} (rule 8)")
                continue
            if check_urls:
                status = fetch_status(target)
                if status is None or status >= 400:
                    report.error(line, f"image URL not reachable ({status or 'no response'}): {target}")

    return found


def fetch_status(url, timeout=15):
    request = urllib.request.Request(url, method="GET", headers={"User-Agent": "deliverable-comment-validator"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status
    except urllib.error.HTTPError as exc:
        return exc.code
    except (urllib.error.URLError, TimeoutError, OSError):
        return None


def check_narrative(text, artifact, report):
    """Heuristics for rule 5: accomplishments are outcomes, not a ticket list."""
    body, first_line = section(text, "Accomplishments" if artifact == "sprint-update" else "Acceptance criteria")
    if not body.strip():
        return

    bullets = [(i, b) for i, b in enumerate(re.findall(r"(?m)^\s*[-*]\s+.*$", body))]
    linked = 0
    for offset, bullet in bullets:
        links = ANY_LINK.findall(bullet)
        if links:
            linked += 1
        if ISSUE_LINK.search(bullet) and not [u for u in links if "/issues/" not in u]:
            report.warn(first_line + offset,
                        "bullet links only to a ticket — link the feature, spec, docs, or release (rule 5)")

    if len(bullets) >= 3 and linked == 0:
        report.warn(first_line, f"{len(bullets)} bullets, no links — a reader cannot see what changed (rule 5)")


def validate(path, artifact, mode, root, check_urls):
    text = Path(path).read_text(encoding="utf-8")
    report = Report(path)

    shape = SHAPES[artifact]
    for pattern, label in shape["required"]:
        if not pattern.search(text):
            report.error(1, f"missing {label} for artifact {artifact}")
    for pattern, label in shape["forbidden"]:
        m = pattern.search(text)
        if m:
            report.error(line_of(text, m.start()), label)

    check_content(text, report)
    found = check_images(text, report, mode, root, check_urls)
    check_narrative(text, artifact, report)
    return report, len(found)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("markdown", nargs="?", help="artifact to validate")
    parser.add_argument("--artifact", choices=sorted(SHAPES), help="required; the two formats are not interchangeable")
    parser.add_argument("--mode", choices=("review", "post"), default="review")
    parser.add_argument("--root", type=Path, help="bundle directory relative image targets resolve against")
    parser.add_argument("--check-urls", action="store_true", help="post mode: fetch every image URL")
    parser.add_argument("--selftest", action="store_true", help="run the built-in checks and exit")
    args = parser.parse_args(argv)

    if args.selftest:
        return selftest()
    if not args.markdown or not args.artifact:
        parser.error("markdown and --artifact are required")
    if not Path(args.markdown).is_file():
        parser.error(f"no such file: {args.markdown}")

    report, image_count = validate(args.markdown, args.artifact, args.mode, args.root, args.check_urls)
    for line in report.warnings:
        print(line)
    for line in report.errors:
        print(line)
    verdict = "PASS" if report.ok() else "FAIL"
    print(f"{verdict} {args.markdown} [{args.artifact}/{args.mode}] "
          f"{image_count} image(s), {len(report.errors)} error(s), {len(report.warnings)} warning(s)")
    if report.ok() and args.mode == "post":
        print("Reminder: after posting, verify the rendered <img> count (references/visual-evidence-and-posting.md).")
    return 0 if report.ok() else 1


GOOD_SPRINT = """## Sprint 6.2 updates

@juchang111 here's our end-of-sprint report for CommonGrants. Let us know if you have
any questions!

**Status:** 🟢

### Sprint goal

- Ship custom filters end to end.

### Accomplishments

- Consumers can now filter searches on grants.gov-specific fields; the
  [filter reference](https://commongrants.org/protocol/filters) documents the shape.

### Rollover

- None

### Risks

- None

### Next sprint (Sprint 6.3)

- Awards spec review.
"""

BAD_SPRINT = """## Sprint X.Y updates

Here's the report for [deliverable name].

### Sprint goal

- TODO fill this in

### Accomplishments

- Closed https://github.com/HHS/simpler-grants-gov/issues/8801
- Closed [#8802](https://github.com/HHS/simpler-grants-gov/issues/8802)
- Also [#8803](https://github.com/HHS/simpler-grants-gov/issues/8803)
- Review the pull request for #355

### Rollover

- Consider adding a screenshot of the new filter UI here.

### Risks

- None

### Next sprint

- More work

![](/tmp/shot.png)
"""


def selftest():
    import tempfile

    failures = []

    def check(name, condition):
        print(f"{'ok  ' if condition else 'FAIL'} {name}")
        if not condition:
            failures.append(name)

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        good = tmp / "good.md"
        good.write_text(GOOD_SPRINT, encoding="utf-8")
        report, count = validate(good, "sprint-update", "review", tmp, False)
        check("clean sprint update passes", report.ok())
        check("clean sprint update has no warnings", not report.warnings)
        check("no images counted in text-only update", count == 0)

        bad = tmp / "bad.md"
        bad.write_text(BAD_SPRINT, encoding="utf-8")
        report, _ = validate(bad, "sprint-update", "review", tmp, False)
        blob = "\n".join(report.errors)
        check("bad update fails", not report.ok())
        check("missing tag caught", TAG in blob)
        check("unfilled slot caught", "deliverable name" in blob)
        check("TODO caught", "TODO" in blob)
        check("editorial instruction caught", "Consider adding" in blob)
        check("literal Sprint X.Y caught", "Sprint X.Y" in blob)
        check("local /tmp target caught", "/tmp/shot.png" in blob)
        check("empty alt caught", "empty alt text" in blob)
        check("ticket-only bullets warned", sum("only to a ticket" in w for w in report.warnings) == 4)
        check("bare #355 caught", "'#355'" in blob)
        check("linked refs not flagged as bare", "'#8802'" not in blob and "'#8803'" not in blob)

        # Wrong artifact flag on the same file must fail on shape.
        report, _ = validate(good, "deliverable-summary", "review", tmp, False)
        check("sprint update rejected as deliverable summary", not report.ok())
        check("shape mismatch names the heading",
              any("Deliverable summary" in e for e in report.errors))

        # Image resolution: same doc, present vs absent bundle file.
        shot = tmp / "shot.png"
        embedded = tmp / "img.md"
        embedded.write_text(
            GOOD_SPRINT + '\n<img alt="Filter results" src="shot.png" />\n', encoding="utf-8"
        )
        report, count = validate(embedded, "sprint-update", "review", tmp, False)
        check("relative image missing from bundle fails", not report.ok() and count == 1)
        shot.write_bytes(b"\x89PNG\r\n")
        report, _ = validate(embedded, "sprint-update", "review", tmp, False)
        check("relative image present in bundle passes", report.ok())
        report, _ = validate(embedded, "sprint-update", "post", tmp, False)
        check("relative image rejected in post mode", not report.ok())

        live = tmp / "live.md"
        live.write_text(
            GOOD_SPRINT
            + '\n<img alt="Filter results" src="https://github.com/user-attachments/assets/abc" />\n',
            encoding="utf-8",
        )
        report, _ = validate(live, "sprint-update", "post", tmp, False)
        check("https image passes post mode", report.ok())

        summary = tmp / "summary.md"
        summary.write_text(
            "# Deliverable summary\n\n@juchang111 evidence below.\n\n"
            "## Acceptance criteria\n\n### Custom Fields Catalog\n\n"
            "> - [x] **Custom Fields Catalog:** Catalog exists.\n\n"
            "Published at https://commongrants.org/protocol/fields.\n\n"
            "## Metrics\n\n### SGG Adoption\n\n"
            "> - [x] **SGG Adoption (metric):** One consumer integrated.\n\n"
            "The search endpoint serves it in production.\n",
            encoding="utf-8",
        )
        report, _ = validate(summary, "deliverable-summary", "review", tmp, False)
        check("clean deliverable summary passes", report.ok())
        check("quoted AC checkboxes are not slots", not any("slot" in e for e in report.errors))

        numbered = tmp / "numbered.md"
        numbered.write_text(
            summary.read_text(encoding="utf-8").replace("### Custom Fields Catalog", "### Criteria 1"),
            encoding="utf-8",
        )
        report, _ = validate(numbered, "deliverable-summary", "review", tmp, False)
        check("numbered criteria label caught", any("rule 2" in e for e in report.errors))

    print(f"\n{'selftest passed' if not failures else f'selftest FAILED: {failures}'}")
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
