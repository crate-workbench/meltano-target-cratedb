# Changelog for Meltano/Singer Target for CrateDB

## In progress
- Add support for container types `ARRAY`, `OBJECT`, and `FLOAT_VECTOR`.
- Improve write operations to be closer to `target-postgres`.
- Switch to new SQLAlchemy dialect for CrateDB.
- Removed workaround for `_`-prefixed column names, which needs
  CrateDB 6.2 and higher.

## 2023-12-08 v0.0.1
- Make it work. It can run the canonical Meltano GitHub -> DB example.
