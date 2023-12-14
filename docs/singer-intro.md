## About

An introduction to the Singer ecosystem of data pipeline components for
composable open source ETL. 

Singer, Meltano, PipelineWise, and Airbyte, provide components and integration
engines adhering to the Singer specification.

On the database integration side, the [connectors] of Singer and Meltano are
based on [SQLAlchemy].


## Overview

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

Singer reads and writes Singer-formatted JSONL messages, following the [Singer Spec].

> The Singer specification was started in 2016 by Stitch Data. It specified a
> data transfer format that would allow any number of data systems, called taps,
> to send data to any data destinations, called targets. Airbyte was incorporated
> in 2020 and created their own specification that was heavily inspired by Singer.
> There are differences, but the core of each specification is sending new-line
> delimited JSON data from STDOUT of a tap to STDIN of a target.


### Meltano

_Unlock all the data that powers your data platform._

> _Say goodbye to writing, maintaining, and scaling your own API integrations
with Meltano's declarative code-first data integration engine, bringing
a number of APIs and DBs to the table._

[Meltano] builds upon Singer technologies, uses configuration files in YAML
syntax instead of JSON, adds an improved SDK and other components, and runs
the central addon registry, [meltano | Hub].

### PipelineWise

> [PipelineWise] is another Data Pipeline Framework using the Singer.io
specification to ingest and replicate data from various sources to
various destinations. The list of [PipelineWise Taps] include another
bunch of high-quality data-source and -sink components.

### Data Mill

> Data Mill helps organizations utilize modern data infrastructure and data
> science to power analytics, products, and services.

- https://github.com/datamill-co
- https://datamill.co/

### SQLAlchemy

> [SQLAlchemy] is the leading Python SQL toolkit and Object Relational Mapper
that gives application developers the full power and flexibility of SQL.
> 
> It provides a full suite of well known enterprise-level persistence patterns,
designed for efficient and high-performing database access, adapted into a
simple and Pythonic domain language.


## Evaluations

### Singer vs. Meltano

Meltano as a framework fills many gaps and makes Singer convenient to actually
use. It is impossible to outline all details and every difference, so we will
focus on the "naming things" aspects for now.

Both ecosystems use different names for the same elements. That may be confusing
at first, but it is easy to learn: For the notion of **data source** vs. **data
sink**, common to all pipeline systems in one way or another, Singer uses the
terms **tap** vs. **target**, while Meltano uses **extractor** vs. **loader**.
Essentially, they are the same things under different names.

| Ecosystem | Data source | Data sink |
|--------|--------|--------|
| Singer | Tap | Target |
| Meltano | Extractor | Loader | 

In Singer jargon, you **tap** data from a source, and send it to a **target**.
In Meltano jargon, you **extract** data from a source, and then **load** it
into the target system.


### Singer and Airbyte criticism

- https://airbyte.com/etl-tools/singer-alternative-airbyte
- https://airbyte.com/blog/airbyte-vs-singer-why-airbyte-is-not-built-on-top-of-singer
- https://airbyte.com/blog/why-you-should-not-build-your-data-pipeline-on-top-of-singer
- https://airbyte.com/blog/a-new-license-to-future-proof-the-commoditization-of-data-integration
- [Clarify in docs relationship to Singer project from Stitch/Talend]
- [Unfair comparison to PipelineWise and Meltano]


[Apache Lucene]: https://lucene.apache.org/
[Clarify in docs relationship to Singer project from Stitch/Talend]: https://github.com/airbytehq/airbyte/issues/445
[connectors]: https://hub.meltano.com/
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
[Unfair comparison to PipelineWise and Meltano]: https://github.com/airbytehq/airbyte/issues/9253
[vanilla package on PyPI]: https://pypi.org/project/meltano-target-cratedb/
