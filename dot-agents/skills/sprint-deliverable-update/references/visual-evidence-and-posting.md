# Visual evidence and posting

Loaded from `SKILL.md`'s **Visual evidence check**. Covers where an image has to live
before a comment can be posted, and how to prove it actually rendered afterward.

Every claim below was checked against `HHS/simpler-grants-gov` and the GitHub REST API.
Counts cited are from that check and will drift; the mechanisms won't.

## Getting an image to a live HTTPS URL

A posted comment needs an HTTPS target. `/tmp`, `file://`, and bare local paths are
forbidden — they render as broken images for every reader but the author.

### Primary: GitHub user attachments

This is what the org actually uses: `github.com/user-attachments/assets/<uuid>` appears in
~850 HHS issue and PR comments, `raw.githubusercontent.com` in none.

There is **no supported REST API for creating one**. The URL is minted by GitHub's own
comment composer when a file is pasted or dropped into the textarea. So:

1. Open the target issue's comment box (browser surface — Claude in Chrome, Playwright MCP,
   or ask the user to do it).
2. Paste or drop the image. Wait for the upload to finish — the composer replaces its
   `Uploading…` placeholder with the real markup.
3. Copy the inserted line out of the textarea. The composer emits an HTML tag, not
   Markdown:

   ```html
   <img width="1536" height="608" alt="image" src="https://github.com/user-attachments/assets/2beae7a6-9797-4264-a597-b92bdf3e0d91" />
   ```

4. **Discard the draft.** The asset URL stays valid — uploading is independent of posting.
   Now assemble the real comment body with that URL in it.
5. Replace the composer's `alt="image"` with descriptive alt text. The validator errors on
   empty alt; `"image"` passes the check but fails the reader.

Both `<img src="…">` and `![alt](…)` are accepted everywhere in this skill, including by
the validator. Real posted summaries use the HTML form because that is what the composer
produces — a Markdown-only image count reads zero on a perfectly good comment.

If there is no browser surface (headless or scheduled run), this path is unavailable. Stop
and ask the user to upload, rather than posting a comment with unresolved images.

### Fallback: commit the asset, use a pinned blob URL

When no composer is reachable and the user wants to proceed, commit the image into a public
repo and reference it:

```
https://github.com/<owner>/<repo>/blob/<commit-sha>/<path>?raw=true
```

Pin the commit SHA, not a branch name, so a later force-push can't swap the evidence.
Caveats worth stating to the user before taking this path: it has no precedent in the org,
it adds a commit someone has to review, and on a **private** repo the URL renders only for
authenticated readers — which defeats the purpose for a stakeholder audience.

Never use link shorteners, third-party image hosts, or signed URLs copied out of a rendered
page (see the expiry note below).

## Verifying the image rendered

Tool success is not proof. The API returns 201 for a comment whose images are all broken.
After posting, compare what the body declares against what GitHub rendered.

Get the comment id (the id of the comment just created, or the last one on the issue):

```bash
gh api "repos/HHS/simpler-grants-gov/issues/{NUMBER}/comments" --jq '.[-1].id'
```

Then compare declared to rendered. The `full+json` media type adds `body_html` alongside
`body`, which is the rendered HTML GitHub serves:

```bash
REPO=HHS/simpler-grants-gov CID=<comment-id>
json=$(gh api "repos/$REPO/issues/comments/$CID" -H "Accept: application/vnd.github.full+json")
declared=$(printf '%s' "$json" | python3 -c 'import json,re,sys; print(len(re.findall(r"!\[[^\]]*\]\(|<img\b", json.load(sys.stdin)["body"])))')
rendered=$(printf '%s' "$json" | python3 -c 'import json,re,sys; print(len(re.findall(r"<img\b", json.load(sys.stdin)["body_html"])))')
echo "declared=$declared rendered=$rendered"
[ "$declared" = "$rendered" ] && echo OK || echo MISMATCH
```

Count `<img` tags. **Do not match on host**: GitHub rewrites the src it serves, so the
rendered tag never carries the URL that was posted. A user attachment comes back as a
signed, expiring URL on a different domain:

```html
<img width="1536" height="608" alt="image"
     src="https://private-user-images.githubusercontent.com/…/628538035-2beae7a6….png?jwt=…" />
```

That `jwt=` query expires, which is why a src copied out of a rendered page is useless as a
stored target. Non-GitHub images are proxied through `camo.githubusercontent.com` instead.

To eyeball the tags rather than count them:

```bash
gh api "repos/$REPO/issues/comments/$CID" -H "Accept: application/vnd.github.full+json" \
  --jq '.body_html' | grep -o '<img[^>]*alt="[^"]*"'
```

## Running the validator

Resolve `<skill-dir>` to the directory containing `SKILL.md`. `--artifact` is always
explicit — the two formats are not interchangeable and the validator will not guess.

Review bundle (relative image targets, every file packaged beside the Markdown):

```bash
<skill-dir>/scripts/validate-deliverable-comment.py \
  --artifact sprint-update --mode review --root ./bundle ./bundle/comment.md
```

Post-ready (every target must be a live HTTPS URL; `--check-urls` fetches each one):

```bash
<skill-dir>/scripts/validate-deliverable-comment.py \
  --artifact deliverable-summary --mode post --check-urls comment.md
```

Errors block. Warnings are the rule-5 heuristics — a bullet whose only link is an issue, or
an Accomplishments section with no links at all — and mean the draft still reads as an issue
list. Fix them rather than shipping past them.

`--selftest` runs the checks against built-in good and bad fixtures; use it after editing
the script.

## Triage

| Symptom | Cause | Fix |
|---|---|---|
| `rendered=0`, `declared>0` | targets aren't reachable HTTPS URLs | re-upload via the composer; never hand-write an attachment URL |
| `declared` exceeds `rendered` | one bad target among good ones | diff the body's srcs against `body_html`'s alt texts to find which |
| Image renders for you, not for teammates | private-repo blob URL, or a signed src was pasted in | move to a user attachment |
| Validator: "relative image not in the bundle" | review bundle is missing the file | copy the image next to the Markdown before asking for review |
| Validator: "copy mentions a screenshot but no image is embedded" | rule 7 | embed it or delete the sentence |
