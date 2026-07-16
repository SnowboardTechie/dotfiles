# Authoritative-source validation for vault plans

Use this when a vault contains a manual, standard, contract, datasheet, policy, or other primary source relevant to an existing plan.

## Validation method

1. Read the original source directly; do not treat the vault's summary note as proof.
2. Confirm that the source applies to the exact model, year, jurisdiction, version, or variant. Separate base-manual rules from supplements and variant tables.
3. Build a claim-by-claim comparison rather than giving a blanket “confirmed” verdict.
4. Classify each plan item:
   - **Source-required** — explicitly prescribed by the primary source.
   - **Source-supported** — consistent with inspection limits or procedures.
   - **Extra-conservative** — sensible for restoration or risk reduction, but not required by the source.
   - **Source-conflicting** — contradicts an interval, specification, replacement rule, or procedure.
5. Quote or record exact specifications, service limits, replacement intervals, cautions, sequence constraints, and torque values. Cite both the printed section/page and PDF page when they differ.
6. Treat diagnostic evidence precisely. A qualitative check can establish rotation, airflow, or some compression, but must not be promoted to a factory pressure, tolerance, or pass/fail result without the prescribed test conditions.
7. Distinguish prerequisites for operation from prerequisites for use. For example, a stationary diagnostic start may require engine/fuel/oil readiness while brakes, tires, and wheel hardware are mandatory before riding.
8. Surface differences prominently, especially safety intervals that visual inspection does not supersede.
9. Do not silently edit the vault during validation. Present the corrected plan first; at the resting point, name the existing note and proposed section changes before writing.

## PDF extraction pattern

For large scanned manuals with a text layer:

- Use PyMuPDF to inspect page count and sample extraction quality.
- Search the extracted page text for each claim's terminology and synonyms.
- Read complete relevant page ranges, including cautions and reassembly sections—not only keyword snippets.
- Check supplements and service-data tables for year/model-specific overrides.
- If text extraction mangles fractions or symbols, verify from surrounding text or render the page visually before recording the value.

## Common pitfalls

- Confirming the headline task while missing contradictions elsewhere in the plan.
- Treating modern best practice as if the older manual required it.
- Treating “looks good” as equivalent to a time-based replacement interval.
- Reporting an aftermarket cross-reference as the factory part specification.
- Declaring an engine healthy from a qualitative cranking check when the manual specifies a warm, wide-open-throttle pressure test.
- Requiring all roadworthiness work before a controlled stationary start when the source only requires it before riding.
