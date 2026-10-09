# IRS W-4 training fixture

Source: https://www.irs.gov/pub/irs-pdf/fw4.pdf (2026, five pages).
Official form bytes are preserved. Ten fictional employee profiles are deterministic benchmark fixtures.
Names, addresses and amounts do not represent real people or tax recommendations.
Read input/dataset_manifest.json: requirements.field_rules associates business semantics with exact PDF field IDs.
Fill only those 14 declared fields. Select exactly one filing-status checkbox; use each checkbox's declared checked value.
Copy the supplied amounts verbatim. Social Security Number, exemption certification, employer identifiers,
employer dates, signatures and all page-3/page-4 worksheet fields must remain blank.
Signature/date lines are not AcroForm fields; never overlay text onto them or certify this form.
Keep all five original pages. Do not calculate withholding or add personal data.
