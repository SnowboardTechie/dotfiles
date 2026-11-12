# Presenter companion page

Every runbook also gets a presenter companion page: a small, self-contained HTML page Bryan keeps open beside the meeting. It isn't shared on screen. It holds what he needs while presenting: the order of items, the talk track, every link he might follow, Q&A, and the fallback. It doesn't replace the runbook; the runbook stays the record.

## Shape

Start from `templates/presenter-companion.html`. It's one file with no build step and no external assets. Each `<section data-label="...">` becomes a tab in the top bar.

1. **Prep:** the presenting tabs as exact links, an "Open all presenting tabs" button, the pre-meeting checklist as checkboxes, and any "don't say" warning in an amber box.
2. **Opening**, then **one section per demo item**. Each has:
   - a meta line with the framing and pacing ("A mention, not a demo · target ≈1:00 · done by about 1:15");
   - a "Screen" box with the exact URL to have on screen and what it shows at that anchor;
   - the talk track, word for word from the runbook, in large type. Wrap the first sentences to cut in `<span class="cut">` so they show dimmed with an "optional:" label. Don't use strikethrough; it reads as "don't say this."
   - a collapsed "Links" `<details>` holding every PR, issue, comment, or page behind the item, each with a one-line label.
3. **Q&A:** each likely question as a `<details>`, with the short answer and its links inside.
4. **Fallback:** the offline facts per item and a backup screen link for each.

The template's script provides tab switching (← →, 1–9), and an elapsed-time timer in the top bar (T to start or pause, R to reset; it turns amber past a set threshold). Set `OVER_MS` to the slot's ceiling minus some slack.

## Rules

- **The talk track must match the runbook exactly.** Edit both together, and re-run `scripts/talk-track-timing.py` on the runbook after any wording change.
- **Every link opens in a new tab** (`target="_blank"`), so the companion stays put.
- **Check every link.** Load the page in a headless browser, collect every `a[href^=http]`, and request each one. Each must return 200, apart from deliberate exceptions such as private repos. Also screenshot the Prep slide and one item slide, and look at them.
- **Keep it presenter-only.** Say so on the Prep slide ("Share only the browser window, not this one").
- **Keep it out of public repos.** Save it beside the runbook in the project vault, under `vault/assets/<meeting>-<YYYY-MM-DD>/index.html`, and commit it with the runbook.

## Publishing

Bryan views it from other devices, so give him a tailnet URL. A `file://` or localhost URL won't work there.

1. Publish it to the Artifact Shelf as a symlink, so later edits to the vault copy go live without republishing:
   ```bash
   artifact-shelf publish --link --slug YYYY-MM-DD-<name> \
     --title "<Meeting> presenter companion" --project <PROJECT> \
     --description "<when>: talk track, links, Q&A, fallback, timer. Presenter-only." \
     vault/assets/<meeting>-<YYYY-MM-DD>
   artifact-shelf url YYYY-MM-DD-<name>
   ```
   Slugs allow only `YYYY-MM-DD-` followed by lowercase letters, digits, and hyphens, so write "7.5" as "7-5".
2. Fetch the shelf URL and confirm it returns 200 before sharing it.
3. Put the shelf URL at the top of the runbook's screen plan.
4. After the meeting, once Bryan says it's done, run `artifact-shelf retire <slug>`. The vault copy stays.

If `artifact-shelf` isn't installed on the host, serve the folder on a tailnet-only `tailscale serve` HTTPS URL on the host's ts.net name instead.

## Handoff links

The handoff message always includes web links:

- the companion's tailnet URL;
- the runbook's forge URL (Forgejo `.../src/branch/main/<path>` for the SGG workspace). Read the URL back through the forge API (`tea api repos/<owner>/<repo>/contents/<path>?ref=main` → `html_url`). A private repo returns 404 when fetched without auth, so mention that the link needs a login;
- the companion source's forge URL.
