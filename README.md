# Meltano/Singer Target for CrateDB

[![Tests](https://github.com/crate-workbench/meltano-target-cratedb/actions/workflows/main.yml/badge.svg)](https://github.com/crate-workbench/meltano-target-cratedb/actions/workflows/main.yml)
[![Test coverage](https://img.shields.io/codecov/c/gh/crate-workbench/meltano-target-cratedb.svg)](https://codecov.io/gh/crate-workbench/meltano-target-cratedb/)
[![Python versions](https://img.shields.io/pypi/pyversions/meltano-target-cratedb.svg)](https://pypi.org/project/meltano-target-cratedb/)

[![License](https://img.shields.io/github/license/crate-workbench/meltano-target-cratedb.svg)](https://github.com/crate-workbench/meltano-target-cratedb/blob/main/LICENSE)
[![Status](https://img.shields.io/pypi/status/meltano-target-cratedb.svg)](https://pypi.org/project/meltano-target-cratedb/)
[![PyPI](https://img.shields.io/pypi/v/meltano-target-cratedb.svg)](https://pypi.org/project/meltano-target-cratedb/)
[![Downloads](https://pepy.tech/badge/meltano-target-cratedb/month)](https://pepy.tech/project/meltano-target-cratedb/)


## About

A [Singer] target for [CrateDB], built with the [Meltano SDK] for custom extractors
and loaders, and based on the [Meltano PostgreSQL target]. It connects a library of
[600+ connectors] with CrateDB, and vice versa.

In Singer ELT jargon, a "target" conceptually wraps a data sink, where you
"load" data into.

Singer, Meltano, and PipelineWise provide foundational components and
an integration engine for composable Open Source ETL with [600+ connectors].
On the database integration side, they are heavily based on [SQLAlchemy].


### CrateDB

[CrateDB] is a distributed and scalable SQL database for storing and analyzing
massive amounts of data in near real-time, even with complex queries. It is
PostgreSQL-compatible, and based on [Apache Lucene].

CrateDB offers a Python SQLAlchemy dialect, in order to plug into the
comprehensive Python data-science and -wrangling ecosystems.

### Singer

_The open-source standard for writing scripts that move data._

[Singer] is an open source specification and software framework for [ETL]/[ELT]
data exchange between a range of different systems. For talking to SQL databases,
it employs a metadata subsystem based on SQLAlchemy.

Singer reads and writes Singer-formatted messages, following the [Singer Spec].
Effectively, those are JSONL files.

### Meltano

_Unlock all the data that powers your data platform._

_Say goodbye to writing, maintaining, and scaling your own API integrations
with Meltano's declarative code-first data integration engine, bringing
600+ APIs and DBs to the table._

[Meltano] builds upon Singer technologies, uses configuration files in YAML
syntax instead of JSON, adds an improved SDK and other components, and runs
the central addon registry, [meltano | Hub].

### PipelineWise

[PipelineWise] is another Data Pipeline Framework using the Singer.io
specification to ingest and replicate data from various sources to
various destinations. The list of [PipelineWise Taps] include another
20+ high-quality data-source and -sink components.

### SQLAlchemy

[SQLAlchemy] is the leading Python SQL toolkit and Object Relational Mapper
that gives application developers the full power and flexibility of SQL.

It provides a full suite of well known enterprise-level persistence patterns,
designed for efficient and high-performing database access, adapted into a
simple and Pythonic domain language.


## Install

Usually, you will not install this package directly, but on behalf
of a Meltano definition instead, for example. A corresponding snippet
is outlined in the next section. After adding it to your `meltano.yml`
configuration file, you can install all defined components and their
dependencies.
```
meltano install
```


## Usage

You can run the CrateDB Singer target `target-cratedb` by itself, or
in a pipeline using Meltano.

### Meltano

Using the `meltano add` subcommand, you can add the plugin to your
Meltano project.
```shell
meltano add loader target-cratedb
```
NB: It will only work like this when released and registered on Meltano Hub.
    In the meanwhile, please add the configuration snippet manually.


#### CrateDB Cloud

In order to connect to [CrateDB Cloud], configure the `sqlalchemy_url` setting
within your `meltano.yml` configuration file like this.
```yaml
- name: target-cratedb
  namespace: cratedb
  variant: cratedb
  pip_url: meltano-target-cratedb
  config:
    sqlalchemy_url: "crate://admin:K4IgMXNvQBJM3CiElOiPHuSp6CiXPCiQYhB4I9dLccVHGvvvitPSYr1vTpt4@example.aks1.westeurope.azure.cratedb.net:4200?ssl=true"}
    add_record_metadata: true
```


#### On localhost
In order to connect to a standalone or on-premise instance of CrateDB, configure
the `sqlalchemy_url` setting within your `meltano.yml` configuration file like this.
```yaml
- name: target-cratedb
  namespace: cratedb
  variant: cratedb
  pip_url: meltano-target-cratedb
  config:
    sqlalchemy_url: crate://crate@localhost/
    add_record_metadata: true
```

Then, invoke the pipeline by using `meltano run`, similar like this.
```shell
meltano run tap-xyz target-cratedb
```

### Standalone

You can also invoke it standalone by using the `target-cratedb` program.
This example demonstrates how to load a file into the database.

First, acquire an example file in Singer format, including the list of
countries of the world.
```shell
wget https://github.com/MeltanoLabs/target-postgres/raw/v0.0.9/target_postgres/tests/data_files/tap_countries.singer
```

Now, define the database connection string including credentials in
SQLAlchemy format.
```shell
echo '{"sqlalchemy_url": "crate://crate@localhost/"}' > settings.json
```

By using Unix pipes, load the data file into the database, referencing
the path to the configuration file.
```shell
cat tap_countries.singer | target-cratedb --config=settings.json
```

Using the interactive terminal program, `crash`, you can run SQL
statements on CrateDB.
```shell
pip install crash
crash --hosts localhost:4200
```

Now, you can verify that the data has been loaded correctly.
```sql
SELECT
    "code", "name", "capital", "emoji", "languages[1]"
FROM
    "melty"."countries"
ORDER BY
    "name"
LIMIT
    42;
```


## Development

In order to work on this adapter dialect on behalf of a real pipeline definition,
link your sandbox to a development installation of [meltano-target-cratedb], and
configure the `pip_url` of the component to point to a different location than the
[vanilla package on PyPI].

Use this URL to directly point to a specific Git repository reference.
```yaml
pip_url: git+https://github.com/crate-workbench/meltano-target-cratedb.git@main
```

Use a `pip`-like notation to link the CrateDB Singer target in development mode,
so you can work on it at the same time while running the pipeline, and iterating
on its definition.
```yaml
pip_url: --editable=/path/to/sources/meltano-target-cratedb
```


[600+ connectors]: https://hub.meltano.com/
[Apache Lucene]: https://lucene.apache.org/
[CrateDB]: https://cratedb.com/product
[CrateDB Cloud]: https://console.cratedb.cloud/
[ELT]: https://en.wikipedia.org/wiki/Extract,_load,_transform
[ETL]: https://en.wikipedia.org/wiki/Extract,_transform,_load
[Meltano]: https://meltano.com/
[meltano | Hub]: https://hub.meltano.com/
[Meltano SDK]: https://github.com/meltano/sdk
[Meltano PostgreSQL target]: https://pypi.org/project/meltanolabs-target-postgres/
[meltano-target-cratedb]: https://github.com/crate-workbench/meltano-target-cratedb
[Singer]: https://www.singer.io/
[Singer Spec]: https://hub.meltano.com/singer/spec/
[PipelineWise]: https://transferwise.github.io/pipelinewise/
[PipelineWise Taps]: https://transferwise.github.io/pipelinewise/user_guide/yaml_config.html
[SQLAlchemy]: https://www.sqlalchemy.org/
[vanilla package on PyPI]: https://pypi.org/project/meltano-target-cratedb/
