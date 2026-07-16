# Authoritative-source reconciliation for project notes

Use this when a vault project plan contains technical claims that can be checked against a local manual, specification, contract, or other primary source.

## Reconciliation pass

1. Identify the canonical project surfaces: hub/MOC, working checklist or log, specifications/procedures reference, and shopping/parts list.
2. Read the primary source directly. For a large PDF, extract/search by page and preserve both PDF page numbers and the document’s printed section/page labels.
3. Build a claim matrix before editing:
   - **Confirmed:** exact source-backed value or procedure.
   - **Corrected:** vault statement conflicts with the source.
   - **Condition-dependent:** source requires inspection or a threshold, not automatic replacement.
   - **Conservative extra:** sensible project practice, but not a source requirement.
   - **Unproven diagnosis:** plausible leading suspect, not established until tested.
4. Propagate each correction across every canonical surface. A correct reference note is not enough if the MOC, checklist, or shopping list still gives stale advice.
5. Convert newly exposed requirements into actionable shopping/checklist items. Include conditional sealing parts, one-time-use hardware, and replacement-as-a-set rules; invalidate stale cost totals when new unknowns make them misleading.
6. Separate sequencing boundaries explicitly—for example, prerequisites for a stationary diagnostic run versus prerequisites for safe movement or operation.
7. Search for the superseded wording and likely paraphrases after editing. Resolve duplicate checkboxes and contradictions rather than merely adding a newer paragraph.
8. Read back every modified note, review the diff, validate frontmatter/Markdown, then follow the vault’s synchronization rules.

## Precision rules

- Do not promote a rough mechanical screen into a factory measurement. Record the proper test conditions, standard, and service limit.
- Do not infer “safe” from appearance when the source specifies a time-based replacement interval.
- Do not present an aftermarket cross-reference as the factory designation; label each separately.
- When a source says components must be replaced as a set, update both the work plan and shopping list.
- If the source itself appears internally inconsistent, check later service-data tables or supplements and record the discrepancy rather than silently choosing a value.
- Preserve useful restoration judgment, but label it as an extra or chosen sequencing decision instead of attributing it to the manufacturer.
