# Contributing

1. Fork and create a branch.
2. Install: `pip install -r requirements.txt && pip install -e .`
3. Make changes; run `python -m pharmaeval validate` and `pytest -q`.
4. Open a pull request describing the change and its regulatory source.

## Rules for regulatory content
- Cite only official sources (ICH, FDA, EMA/EC, Health Canada, TGA, MHRA, pharmacopoeias). Put the URL and `verified_on` date in the registry entry.
- Never mark a draft as `final`. Give every draft an `adoption_path`.
- When a document is withdrawn or replaced, set `withdrawn_on` / `superseded_on` and `superseded_by`; do not delete the entry.
- Test cases and model responses in `data/` are synthetic. Do not commit confidential product, patient or company data.
