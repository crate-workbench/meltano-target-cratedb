# Changelog for Meltano/Singer Target for CrateDB

## In progress
- Add support for container types `ARRAY`, `OBJECT`, and `FLOAT_VECTOR`.
- Improve write operations to be closer to `target-postgres`.
- Removed workaround for `_`-prefixed column names.
  The package now requires CrateDB 6.2 or higher.

## 2023-12-08 v0.0.1
- Make it work. It can run the canonical Meltano GitHub -> DB example.
