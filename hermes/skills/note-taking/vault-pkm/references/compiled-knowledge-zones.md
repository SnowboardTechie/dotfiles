# Compiled Knowledge Zones in a Mixed Personal Vault

Use this when a personal vault has mature clusters that resemble an LLM-maintained wiki, but the whole vault also contains journals, archives, one-off notes, and private material.

## Core stance

Do not normalize the entire vault into a global `raw/`, `entities/`, `concepts/`, or `queries/` hierarchy. Let mature domains become **compiled knowledge zones** inside the existing vault. The agent maintains them; the human governs meaning and authorship.

A zone has recognizable roles rather than mandatory folders:

| Role | Function |
|---|---|
| MOC / hub | Current orientation and routes into the zone; not the detail dump |
| Source / reference | Stable facts, specifications, procedures, and evidence |
| Project / log | Changing state, findings, completed work, and next actions |
| Exploration / decision | Reasoning history, trade-offs, and choices |

A topic has earned zone treatment when it has several durable, related notes or source-backed work that must stay consistent. Do not pre-create empty roles.

## Audit workflow

1. Read local vault rules and representative MOCs, references, logs, explorations, and decisions.
2. Inventory active notes, local primary sources, wikilinks, explicit MOC tags, and implicit high-link hubs.
3. Check local indexes against actual files. Repair incomplete orientation before normalizing metadata.
4. Identify source-sensitive references: safety, health, money, legal, specifications, and procedures.
5. Inspect those references for traceable primary sources, unsupported precision, model/version ambiguity, and claims repeated across sibling notes.
6. Scope link and contradiction lint to the active zone. Exclude journals, archives, templates, and intentional forward links unless they caused a real retrieval failure.
7. Prefer low-risk structural repairs now: mark existing hubs, refresh MOCs/indexes, clarify canonical roles, remove unsupported claims, and reconcile exact contradictions.
8. Put broad provenance cleanup into an **update-on-touch queue**. Do not churn hundreds of historical notes merely to make metadata uniform.

## Proportional provenance

Treat local manuals, standards, contracts, and other primary documents as immutable inputs. Corrections belong in interpreting notes.

For consequential claims, distinguish:

- **Source-required** — explicitly prescribed by the source.
- **Source-supported** — consistent with the source but not mandated.
- **Extra-conservative** — prudent situational guidance added beyond the source.
- **Source-conflicting** — contradicted by the applicable source and requiring correction.

Use inline citations where claim-to-source connection matters and a `## Sources` section for multi-source reference notes. Include exact section/page and exact model/year/version when available. Label adjacent-version or community evidence rather than presenting it as exact authority.

Do not add decorative citations to personal reflection, original reasoning, or work logs with no external factual claims.

## Targeted lint

At natural work boundaries, check the active zone for:

- MOCs that omit live spokes or promote superseded guidance;
- important pages with no route from the MOC;
- broken links that block real navigation;
- conflicting values copied across hub/reference/log pages;
- duplicated or superseded tasks;
- unresolved placeholders and stale status;
- consequential claims with no traceable source.

A broken or orphaned historical note is not automatically a defect. Treat an observed retrieval failure as an after-action review and repair the route that failed.

## Verification sequence

After edits:

1. Validate frontmatter and index coverage.
2. Resolve wikilinks in changed note content, allowing only documented intentional forward links and template examples.
3. Search the **entire active zone** for every superseded value or phrase—not only the files initially identified. A correction often has a sibling copy in a hub, comparison callout, or checklist.
4. Review the diff and run whitespace/syntax checks available to the vault.
5. Commit and synchronize according to local rules.
6. Repeat the contradiction search after the commit if the first search reveals another copy; use a follow-up commit rather than rewriting pushed history.

## Interoperability boundary

Markdown + YAML + Git may resemble exchange formats such as OKF, but do not retrofit an authoring vault without a real consumer. If interoperability becomes concrete, prefer a curated/generated export that excludes private or irrelevant material and transforms vault-native links and metadata at the boundary.
