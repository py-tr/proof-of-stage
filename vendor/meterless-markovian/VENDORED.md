# Vendored: Meterless Markovian reference

- Upstream: https://github.com/Meterless/Meterless, `engines/markovian/`
- Commit: `4eb96f27723ed54c837cc41a94d1e90f54db3324` (2026-10-18)
- Licence: Apache-2.0 (`LICENSE`, copied unmodified)
- Files: `reference/src/*.ts`, `reference/package.json`, `reference/tsconfig.json`, `conformance/runner.ts`, `conformance/README.md`
- **Unmodified.** Our integration lives in `app/engine/`, never in this folder.
- Conformance: `node --experimental-transform-types --no-warnings conformance/runner.ts` with `MARKOVIAN_IMPL` pointing at `reference/src/index.ts` (see `tests/test_markovian.py`).
