# Changelog

## [1.1.0] - 2026-11-24
### Added
- Guidance-status engine (`src/pharmaeval/guidance.py`) and dated registry (`knowledge/guidance_registry.json`, 25 documents).
- Only guidance effective on the evaluation date is accepted as a requirement; drafts must be labelled with a way forward to adoption; withdrawn/superseded documents only as historical.
- New error labels `draft_cited_as_effective` and `missing_applicable_guidance`; release gate requires zero guidance-status errors.
- `watchlist` CLI command and dashboard watchlist; `PHARMAEVAL_AS_OF` for re-evaluation at another date.
- Test cases TT-009 (draft ICH Q1), FDA-007 (tirzepatide PSG), FDA-008 (biosimilar CES draft), EMA-007 (EU Q-code site change).
### Changed
- EU cases use Commission Variations Guidelines C/2025/5045 (Q codes), applicable from 15 Jan 2026.
- FDA 2021 synthetic peptide ANDA guidance treated as withdrawn (28 Jul 2026).

## [1.0.0] - 2026-11-23
### Added
- Initial benchmark: automated graders, SME annotation and agreement, adjudication, risk-tiered scoring, release gate, audit trail, reports.
