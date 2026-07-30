# Validation Report

Validated before packaging:

- Python syntax: `scripts/build.py`, `scripts/self_test.py`
- Synthetic Notion schema self-test: `SELF_TEST_OK`
- Payload validation for all five JSON files
- Browser rendering at 1900 px width for:
  - `polar-progress.html`
  - `phase-voyage.html`
- No JavaScript console errors or page errors in the two new components
- Backward-compatibility test with the previous JSON field names
- No `undefined` text under old or new schemas
- Passed-chapter state selects `island-passed.webp`
- Active-chapter state selects `island-active.webp`
- Inline JavaScript syntax checked with Node.js for all five HTML pages

The GitHub Actions workflow repeats the schema self-test before every deployment.
