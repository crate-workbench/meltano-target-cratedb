# Meltano/Singer Target for CrateDB

[![Tests](https://github.com/crate-workbench/meltano-target-cratedb/actions/workflows/main.yml/badge.svg)](https://github.com/crate-workbench/meltano-target-cratedb/actions/workflows/main.yml)
[![Test coverage](https://img.shields.io/codecov/c/gh/crate-workbench/meltano-target-cratedb.svg)](https://codecov.io/gh/crate-workbench/meltano-target-cratedb/)
[![Python versions](https://img.shields.io/pypi/pyversions/meltano-target-cratedb.svg)](https://pypi.org/project/meltano-target-cratedb/)

[![License](https://img.shields.io/github/license/crate-workbench/meltano-target-cratedb.svg)](https://github.com/crate-workbench/meltano-target-cratedb/blob/main/LICENSE)
[![Status](https://img.shields.io/pypi/status/meltano-target-cratedb.svg)](https://pypi.org/project/meltano-target-cratedb/)
[![PyPI](https://img.shields.io/pypi/v/meltano-target-cratedb.svg)](https://pypi.org/project/meltano-target-cratedb/)
[![Downloads](https://pepy.tech/badge/meltano-target-cratedb/month)](https://pepy.tech/project/meltano-target-cratedb/)

## About

A Singer target for [CrateDB], built with the Meltano SDK for Singer Targets,
and based on the PostgreSQL target [meltanolabs-target-postgres].


## Details

In Singer ELT jargon, a "target" conceptionally wraps a data sink, where you
"load" data into.

CrateDB is a distributed and scalable SQL database for storing and analyzing
massive amounts of data in near real-time, even with complex queries. It is
PostgreSQL-compatible, and based on Apache Lucene.


[CrateDB]: https://github.com/crate/crate
[meltanolabs-target-postgres]: https://pypi.org/project/meltanolabs-target-postgres/
