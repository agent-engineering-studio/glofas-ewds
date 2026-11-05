# Contributing

Issues and pull requests are welcome.

- Run `make check` before pushing: ruff, `mypy --strict` and pytest must be
  clean, the same gate CI runs.
- A change to a cell, a request or a reader should also pass the live
  contract tests (`tests/test_live.py`, needs an EWDS key): see the
  README's Development section. CI runs them weekly.
- Commits follow [Conventional Commits](https://www.conventionalcommits.org/).
- Contributions are accepted under the project's license, Apache-2.0
  (section 5 of the license: inbound = outbound). No separate CLA.
