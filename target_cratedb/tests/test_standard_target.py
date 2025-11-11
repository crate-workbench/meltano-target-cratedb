"""Attempt at making some standard Target Tests."""

from __future__ import annotations

import copy
import io
from contextlib import redirect_stdout

import pytest
import sqlalchemy as sa
from singer_sdk.exceptions import InvalidRecord, MissingKeyPropertiesError
from singer_sdk.testing import sync_end_to_end
from sqlalchemy_cratedb.type import FloatVector
from sqlalchemy_cratedb.type.object import ObjectTypeImpl
from tap_countries.tap import TapCountries
from tap_fundamentals import Fundamentals
from target_postgres.tests.test_target_postgres import verify_data

from target_cratedb.connector import CrateDBConnector
from target_cratedb.sinks import MELTANO_CRATEDB_STRATEGY_DIRECT
from target_cratedb.sqlalchemy.patch import polyfill_refresh_after_dml_engine
from target_cratedb.target import TargetCrateDB

try:
    from importlib.resources import files as resource_files  # type: ignore[attr-defined]
except ImportError:
    from importlib_resources import files as resource_files  # type: ignore[no-redef]


METADATA_COLUMN_PREFIX = "_sdc"


@pytest.fixture(scope="session")
def cratedb_config_with_ssl():
    return {
        "dialect+driver": "crate",
        "host": "localhost",
        "user": "crate",
        "password": "",
        "database": "",
        "port": 4200,
        "ssl_enable": True,
        "ssl_client_certificate_enable": True,
        "ssl_mode": "verify-full",
        "ssl_certificate_authority": "./ssl/root.crt",
        "ssl_client_certificate": "./ssl/cert.crt",
        "ssl_client_private_key": "./ssl/pkey.key",
        "add_record_metadata": True,
        "hard_delete": False,
        "default_target_schema": "melty",
    }


@pytest.fixture(scope="session")
def cratedb_config():
    return {
        "dialect+driver": "crate",
        "host": "localhost",
        "user": "crate",
        "password": "",
        "database": "",
        "port": 4200,
        "add_record_metadata": True,
        "hard_delete": False,
        "default_target_schema": "melty",
    }


@pytest.fixture(scope="session")
def cratedb_config_ssh_tunnel():
    return {
        "sqlalchemy_url": "crate://crate@10.5.0.5:4200/",
        "ssh_tunnel": {
            "enable": True,
            "host": "127.0.0.1",
            "port": 2223,
            "username": "melty",
            "private_key": "-----BEGIN OPENSSH PRIVATE KEY-----\n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\n-----END OPENSSH PRIVATE KEY-----",  # noqa: E501
        },
    }


@pytest.fixture
def cratedb_target(cratedb_config) -> TargetCrateDB:
    return TargetCrateDB(config=cratedb_config)


def create_engine(target_cratedb: TargetCrateDB) -> sa.engine.Engine:
    engine = TargetCrateDB.default_sink_class.connector_class(config=target_cratedb.config)._engine
    polyfill_refresh_after_dml_engine(engine)
    return engine


@pytest.fixture(scope="session", autouse=True)
def initialize_database(cratedb_config):
    delete_table_names = [
        "melty.array_boolean",
        "melty.array_float",
        "melty.array_float_vector",
        "melty.array_number",
        "melty.array_string",
        "melty.array_timestamp",
        "melty.commits",
        "melty.foo",
        "melty.object_mixed",
        "melty.test_activate_version_hard",
        "melty.test_activate_version_deletes_data_properly",
        "melty.test_activate_version_soft",
        "melty.test_new_array_column",
        "melty.test_schema_updates",
    ]
    db = TargetCrateDB(config=cratedb_config)
    engine = create_engine(db)
    with engine.connect() as conn:
        for delete_table_name in delete_table_names:
            conn.exec_driver_sql(f"DROP TABLE IF EXISTS {delete_table_name};")
        conn.exec_driver_sql("CREATE TABLE IF NOT EXISTS melty.foo (a INT);")


def singer_file_to_target(file_name, target) -> None:
    """Singer file to Target, emulates a tap run

    Equivalent to running cat file_path | target-name --config config.json.
    Note that this function loads all lines into memory, so it is
    not good very large files.

    Args:
        file_name: name to file in .tests/data_files to be sent into target
        Target: Target to pass data from file_path into..
    """
    file_path_local = resource_files("target_cratedb.tests") / "data_files" / file_name
    file_path_upstream = resource_files("target_postgres.tests") / "data_files" / file_name
    if file_path_local.exists():
        file_path = file_path_local
    else:
        file_path = file_path_upstream
    buf = io.StringIO()
    with redirect_stdout(buf):
        with open(file_path) as f:
            for line in f:
                # File endings are here, and print adds another line
                # ending, so we need to remove one.
                print(line.rstrip("\r\n"))  # noqa: T201
    buf.seek(0)
    target.listen(buf)


def verify_schema(
    target: TargetCrateDB,
    table_name: str,
    check_columns: dict = None,
):
    """Checks whether the schema of a database table matches the provided column definitions.

    Args:
        target: The target to obtain a database connection from.
        table_name: The schema and table name of the table to check data for.
        check_columns: A dictionary mapping column names to their definitions. Currently,
            it is all about the `type` attribute which is compared.
        metadata_column_prefix: The prefix string for metadata columns. Usually `_sdc`.
    """
    check_columns = check_columns or {}
    engine = create_engine(target)
    schema = target.config["default_target_schema"]
    with engine.connect() as connection:
        meta = sa.MetaData()
        table = sa.Table(table_name, meta, schema=schema, autoload_with=connection)
        for column in table.c:
            # Ignore `_sdc` metadata columns when verifying table schema.
            if column.name.startswith(METADATA_COLUMN_PREFIX):
                continue
            try:
                column_type_expected = check_columns[column.name]["type"]
            except KeyError as ex:
                raise ValueError(f"Invalid check_columns - missing definition for column: {column.name}") from ex
            if not isinstance(column.type, column_type_expected):
                raise TypeError(
                    f"Column '{column.name}' (with type '{column.type}') "
                    f"does not match expected type: {column_type_expected}"
                )
    engine.dispose()


# TODO should set schemas for each tap individually so we don't collide


def test_sqlalchemy_url_config(cratedb_config):
    """Be sure that passing a sqlalchemy_url works

    postgres_config_no_ssl is used because an SQLAlchemy URL will override all SSL
    settings and preclude connecting to a database using SSL.
    """
    host = cratedb_config["host"]
    user = cratedb_config["user"]
    password = cratedb_config["password"]
    database = cratedb_config["database"]
    port = cratedb_config["port"]

    config = {"sqlalchemy_url": f"crate://{user}:{password}@{host}:{port}/{database}"}
    tap = TapCountries(config={}, state=None)
    target = TargetCrateDB(config=config)
    sync_end_to_end(tap, target)


def test_port_default_config():
    """Test that the default config is passed into the engine when the config doesn't provide it"""
    config = {
        "dialect+driver": "crate",
        "host": "localhost",
        "user": "crate",
        "password": "",
        "database": "",
    }
    dialect_driver = config["dialect+driver"]
    host = config["host"]
    user = config["user"]
    password = config["password"]
    database = config["database"]
    target_config = TargetCrateDB(config=config).config
    connector = CrateDBConnector(target_config)

    engine: sa.engine.Engine = connector._engine
    assert (
        engine.url.render_as_string(hide_password=False)
        == f"{dialect_driver}://{user}:{password}@{host}:5432/{database}"
    )


def test_port_config():
    """Test that the port config works"""
    config = {
        "dialect+driver": "crate",
        "host": "localhost",
        "user": "crate",
        "password": "",
        "database": "",
        "port": 4200,
    }
    dialect_driver = config["dialect+driver"]
    host = config["host"]
    user = config["user"]
    password = config["password"]
    database = config["database"]
    target_config = TargetCrateDB(config=config).config
    connector = CrateDBConnector(target_config)

    engine: sa.engine.Engine = connector._engine
    assert (
        engine.url.render_as_string(hide_password=False)
        == f"{dialect_driver}://{user}:{password}@{host}:4200/{database}"
    )


# Test name would work well
def test_countries_to_cratedb(cratedb_config):
    tap = TapCountries(config={}, state=None)
    target = TargetCrateDB(config=cratedb_config)
    sync_end_to_end(tap, target)


@pytest.mark.skip("Fails with: SQLParseException[Limit of total fields [1000] in index [melty.aapl] has been exceeded]")
def test_aapl_to_cratedb(cratedb_config):
    tap = Fundamentals(config={}, state=None)
    target = TargetCrateDB(config=cratedb_config)
    sync_end_to_end(tap, target)


def test_invalid_schema(cratedb_target):
    with pytest.raises(Exception) as e:
        file_name = "invalid_schema.singer"
        singer_file_to_target(file_name, cratedb_target)
    assert str(e.value) == "Line is missing required properties key(s): {'type': 'object'}"


def test_record_missing_key_property(cratedb_target):
    with pytest.raises(MissingKeyPropertiesError) as e:
        file_name = "record_missing_key_property.singer"
        singer_file_to_target(file_name, cratedb_target)
    assert "Record is missing one or more key_properties." in str(e.value)


def test_record_missing_required_property(cratedb_target):
    with pytest.raises(InvalidRecord) as e:
        file_name = "record_missing_required_property.singer"
        singer_file_to_target(file_name, cratedb_target)
    assert "Record Message Validation Error: 'id' is a required property" in str(e.value)


@pytest.mark.skipif(not MELTANO_CRATEDB_STRATEGY_DIRECT, reason="Does not work in temptable/upsert mode")
def test_camelcase(cratedb_target):
    file_name = "camelcase.singer"
    singer_file_to_target(file_name, cratedb_target)


@pytest.mark.skip('InvalidColumnNameException["_id" conflicts with system column pattern]')
def test_special_chars_in_attributes(cratedb_target):
    file_name = "special_chars_in_attributes.singer"
    singer_file_to_target(file_name, cratedb_target)


def test_optional_attributes(cratedb_target):
    file_name = "optional_attributes.singer"
    singer_file_to_target(file_name, cratedb_target)
    row = {"id": 1, "optional": "This is optional"}
    verify_data(cratedb_target, "test_optional_attributes", 4, "id", row)


def test_schema_no_properties(cratedb_target):
    """Expect to fail with ValueError"""
    file_name = "schema_no_properties.singer"
    singer_file_to_target(file_name, cratedb_target)


def test_schema_updates(cratedb_target):
    file_name = "schema_updates.singer"
    singer_file_to_target(file_name, cratedb_target)
    row = {
        "id": 1,
        "a1": 101,  # Decimal("101"),
        "a2": "string1",
        "a3": None,
        "a4": None,
        "a5": None,
        "a6": None,
    }
    verify_data(cratedb_target, "test_schema_updates", 6, "id", row)


def test_multiple_state_messages(cratedb_target):
    file_name = "multiple_state_messages.singer"
    singer_file_to_target(file_name, cratedb_target)
    row = {"id": 1, "metric": 100}
    verify_data(cratedb_target, "test_multiple_state_messages_a", 6, "id", row)
    row = {"id": 1, "metric": 110}
    verify_data(cratedb_target, "test_multiple_state_messages_b", 6, "id", row)


# TODO test that data is correct
def test_multiple_schema_messages(cratedb_target, caplog):
    """Test multiple identical schema messages.

    Multiple schema messages with the same schema should not cause 'schema has changed'
    logging statements. See: https://github.com/MeltanoLabs/target-postgres/issues/124

    Caplog docs: https://docs.pytest.org/en/latest/how-to/logging.html#caplog-fixture
    """
    file_name = "multiple_schema_messages.singer"
    singer_file_to_target(file_name, cratedb_target)
    assert "Schema has changed for stream" not in caplog.text


@pytest.mark.skip("ColumnValidationException[Validation failed for id: Updating a primary key is not supported]")
def test_relational_data(cratedb_target):
    file_name = "user_location_data.singer"
    singer_file_to_target(file_name, cratedb_target)

    file_name = "user_location_upsert_data.singer"
    singer_file_to_target(file_name, cratedb_target)

    users = [
        {"id": 1, "name": "Johny"},
        {"id": 2, "name": "George"},
        {"id": 3, "name": "Jacob"},
        {"id": 4, "name": "Josh"},
        {"id": 5, "name": "Jim"},
        {"id": 8, "name": "Thomas"},
        {"id": 12, "name": "Paul"},
        {"id": 13, "name": "Mary"},
    ]
    locations = [
        {"id": 1, "name": "Philly"},
        {"id": 2, "name": "NY"},
        {"id": 3, "name": "San Francisco"},
        {"id": 6, "name": "Colorado"},
        {"id": 8, "name": "Boston"},
    ]
    user_in_location = [
        {
            "id": 1,
            "user_id": 1,
            "location_id": 4,
            "info": {"weather": "rainy", "mood": "sad"},
        },
        {
            "id": 2,
            "user_id": 2,
            "location_id": 3,
            "info": {"weather": "sunny", "mood": "satisfied"},
        },
        {
            "id": 3,
            "user_id": 1,
            "location_id": 3,
            "info": {"weather": "sunny", "mood": "happy"},
        },
        {
            "id": 6,
            "user_id": 3,
            "location_id": 2,
            "info": {"weather": "sunny", "mood": "happy"},
        },
        {
            "id": 14,
            "user_id": 4,
            "location_id": 1,
            "info": {"weather": "cloudy", "mood": "ok"},
        },
    ]

    verify_data("test_users", 8, "id", users)
    verify_data("test_locations", 5, "id", locations)
    verify_data("test_user_in_location", 5, "id", user_in_location)


def test_no_primary_keys(cratedb_target):
    """We run both of these tests twice just to ensure that no records are removed and append only works properly"""
    engine = create_engine(cratedb_target)
    table_name = "test_no_pk"
    full_table_name = cratedb_target.config["default_target_schema"] + "." + table_name
    with engine.connect() as connection, connection.begin():
        connection.execute(sa.text(f"DROP TABLE IF EXISTS {full_table_name}"))
    file_name = f"{table_name}.singer"
    singer_file_to_target(file_name, cratedb_target)

    file_name = f"{table_name}_append.singer"
    singer_file_to_target(file_name, cratedb_target)

    file_name = f"{table_name}.singer"
    singer_file_to_target(file_name, cratedb_target)

    file_name = f"{table_name}_append.singer"
    singer_file_to_target(file_name, cratedb_target)

    # Will populate 22 records, we run this twice.
    verify_data(cratedb_target, table_name, 16)


def test_no_type(cratedb_target):
    file_name = "test_no_type.singer"
    singer_file_to_target(file_name, cratedb_target)


def test_duplicate_records(cratedb_target):
    file_name = "duplicate_records.singer"
    singer_file_to_target(file_name, cratedb_target)
    row = {"id": 1, "metric": 100}
    verify_data(cratedb_target, "test_duplicate_records", 2, "id", row)


def test_array_boolean(cratedb_target):
    file_name = "array_boolean.singer"
    singer_file_to_target(file_name, cratedb_target)
    row = {"id": 1, "value": [True, False]}
    verify_data(cratedb_target, "array_boolean", 3, "id", row)
    verify_schema(
        cratedb_target,
        "array_boolean",
        check_columns={
            "id": {"type": sa.BIGINT},
            "value": {"type": sa.ARRAY},
        },
    )


@pytest.mark.skip("pgvector patch did not land in upstream target-postgres yet")
@pytest.mark.skipif(not MELTANO_CRATEDB_STRATEGY_DIRECT, reason="Does not work in temptable/upsert mode")
def test_array_float_vector(cratedb_target):
    file_name = "array_float_vector.singer"
    singer_file_to_target(file_name, cratedb_target)
    row = {
        "id": 1,
        "value": [1.1, 2.1, 1.1, 1.3],
    }
    verify_data(cratedb_target, "array_float_vector", 3, "id", row)
    verify_schema(
        cratedb_target,
        "array_float_vector",
        check_columns={
            "id": {"type": sa.BIGINT},
            "value": {"type": FloatVector},
        },
    )


def test_array_number(cratedb_target):
    file_name = "array_number.singer"
    singer_file_to_target(file_name, cratedb_target)
    row = {"id": 1, "value": [42.42, 84.84, 23]}
    verify_data(cratedb_target, "array_number", 3, "id", row)
    verify_schema(
        cratedb_target,
        "array_number",
        check_columns={
            "id": {"type": sa.BIGINT},
            "value": {"type": sa.ARRAY},
        },
    )


def test_array_string(cratedb_target):
    file_name = "array_string.singer"
    singer_file_to_target(file_name, cratedb_target)
    row = {"id": 1, "value": ["apple", "orange", "pear"]}
    verify_data(cratedb_target, "array_string", 4, "id", row)
    verify_schema(
        cratedb_target,
        "array_string",
        check_columns={
            "id": {"type": sa.BIGINT},
            "value": {"type": sa.ARRAY},
        },
    )


def test_array_timestamp(cratedb_target):
    file_name = "array_timestamp.singer"
    singer_file_to_target(file_name, cratedb_target)
    row = {"id": 1, "value": ["2023-12-13T01:15:02", "2023-12-13T01:16:02"]}
    verify_data(cratedb_target, "array_timestamp", 3, "id", row)
    verify_schema(
        cratedb_target,
        "array_timestamp",
        check_columns={
            "id": {"type": sa.BIGINT},
            "value": {"type": sa.ARRAY},
        },
    )


def test_object_mixed(cratedb_target):
    file_name = "object_mixed.singer"
    singer_file_to_target(file_name, cratedb_target)
    row = {
        "id": 1,
        "value": {
            "string": "foo",
            "integer": 42,
            "float": 42.42,
            "timestamp": "2023-12-13T01:15:02",
            "array_boolean": [True, False],
            "array_float": [42.42, 84.84],
            "array_integer": [42, 84],
            "array_string": ["foo", "bar"],
            "nested_object": {"foo": "bar"},
        },
    }
    verify_data(cratedb_target, "object_mixed", 1, "id", row)
    verify_schema(
        cratedb_target,
        "object_mixed",
        check_columns={
            "id": {"type": sa.BIGINT},
            "value": {"type": ObjectTypeImpl},
        },
    )


def test_encoded_string_data(cratedb_target):
    """
    We removed NUL characters from the original encoded_strings.singer as postgres doesn't allow them.
    https://www.postgresql.org/docs/current/functions-string.html#:~:text=chr(0)%20is%20disallowed%20because%20text%20data%20types%20cannot%20store%20that%20character.
    chr(0) is disallowed because text data types cannot store that character.

    Note you will recieve a  ValueError: A string literal cannot contain NUL (0x00) characters.
    Which seems like a reasonable error.

    See issue https://github.com/MeltanoLabs/target-postgres/issues/60 for more details.
    """

    file_name = "encoded_strings.singer"
    singer_file_to_target(file_name, cratedb_target)
    row = {"id": 1, "info": "simple string 2837"}
    verify_data(cratedb_target, "test_strings", 11, "id", row)
    row = {"id": 1, "info": {"name": "simple", "value": "simple string 2837"}}
    verify_data(cratedb_target, "test_strings_in_objects", 11, "id", row)
    row = {"id": 1, "strings": ["simple string", "απλή συμβολοσειρά", "简单的字串"]}
    verify_data(cratedb_target, "test_strings_in_arrays", 6, "id", row)


@pytest.mark.skip("Fails with: SQLParseException[Limit of total fields [1000] in index [melty.aapl] has been exceeded]")
def test_tap_appl(cratedb_target):
    """
    Expect to fail with ValueError due to primary key error.

    https://github.com/MeltanoLabs/target-postgres/issues/54
    """
    file_name = "tap_aapl.singer"
    singer_file_to_target(file_name, cratedb_target)


def test_tap_countries(cratedb_target):
    file_name = "tap_countries.singer"
    singer_file_to_target(file_name, cratedb_target)


def test_missing_value(cratedb_target):
    file_name = "missing_value.singer"
    singer_file_to_target(file_name, cratedb_target)


def test_large_int(cratedb_target):
    file_name = "large_int.singer"
    singer_file_to_target(file_name, cratedb_target)


def test_anyof(cratedb_target):
    """Test that anyOf is handled correctly"""
    engine = create_engine(cratedb_target)
    table_name = "commits"
    file_name = f"{table_name}.singer"
    schema = cratedb_target.config["default_target_schema"]
    singer_file_to_target(file_name, cratedb_target)
    with engine.connect() as connection:
        meta = sa.MetaData()
        table = sa.Table("commits", meta, schema=schema, autoload_with=connection)
        # ruff: noqa: ERA001
        for column in table.c:
            # {"type":"string"}
            if column.name == "id":
                # TODO: CrateDB needs `(sa.TEXT, sa.String)` here.
                #       The original is fine with `sa.TEXT`, so review
                #       the dialect please. Discovered through `test_anyof`.
                assert isinstance(column.type, (sa.TEXT, sa.String))

            # Any of nullable date-time.
            # Note that postgres timestamp is equivalent to jsonschema date-time.
            # {"anyOf":[{"type":"string","format":"date-time"},{"type":"null"}]}
            if column.name in {"authored_date", "committed_date"}:
                assert isinstance(column.type, sa.TIMESTAMP)

            # Any of nullable array of strings or single string.
            # {"anyOf":[{"type":"array","items":{"type":["null","string"]}},{"type":"string"},{"type":"null"}]}
            if column.name == "parent_ids":
                assert isinstance(column.type, sa.ARRAY)

            # Any of nullable string.
            # {"anyOf":[{"type":"string"},{"type":"null"}]}
            # TODO: See above.
            if column.name == "commit_message":
                assert isinstance(column.type, (sa.TEXT, sa.String))

            # Any of nullable string or integer.
            # {"anyOf":[{"type":"string"},{"type":"integer"},{"type":"null"}]}
            # TODO: See above.
            if column.name == "legacy_id":
                assert isinstance(column.type, (sa.TEXT, sa.String))


def test_new_array_column(cratedb_target):
    """Create a new Array column with an existing table"""
    file_name = "new_array_column.singer"
    singer_file_to_target(file_name, cratedb_target)


def test_activate_version_hard_delete(cratedb_config):
    """Activate Version Hard Delete Test"""
    table_name = "test_activate_version_hard"
    file_name = f"{table_name}.singer"
    full_table_name = cratedb_config["default_target_schema"] + "." + table_name
    postgres_config_hard_delete_true = copy.deepcopy(cratedb_config)
    postgres_config_hard_delete_true["hard_delete"] = True
    pg_hard_delete_true = TargetCrateDB(config=postgres_config_hard_delete_true)
    engine = create_engine(pg_hard_delete_true)
    singer_file_to_target(file_name, pg_hard_delete_true)
    with engine.connect() as connection, connection.begin():
        result = connection.execute(sa.text(f"SELECT * FROM {full_table_name}"))
        assert result.rowcount == 8
    with engine.connect() as connection, connection.begin():
        # Add a record like someone would if they weren't using the tap target combo
        result = connection.execute(
            sa.text(f"INSERT INTO {full_table_name}(code, \"name\") VALUES('Manual1', 'Meltano')")
        )
        result = connection.execute(
            sa.text(f"INSERT INTO {full_table_name}(code, \"name\") VALUES('Manual2', 'Meltano')")
        )
        # CrateDB-specific: Synchronize write operations.
        # TODO: Can this case be handled transparently?
        connection.execute(sa.text(f"REFRESH TABLE {full_table_name}"))
    with engine.connect() as connection, connection.begin():
        result = connection.execute(sa.text(f"SELECT * FROM {full_table_name}"))
        assert result.rowcount == 10

    singer_file_to_target(file_name, pg_hard_delete_true)

    # Should remove the 2 records we added manually
    with engine.connect() as connection, connection.begin():
        result = connection.execute(sa.text(f"SELECT * FROM {full_table_name}"))
        assert result.rowcount == 8


def test_activate_version_soft_delete(cratedb_target):
    """Activate Version Soft Delete Test"""
    engine = create_engine(cratedb_target)
    table_name = "test_activate_version_soft"
    file_name = f"{table_name}.singer"
    full_table_name = cratedb_target.config["default_target_schema"] + "." + table_name
    with engine.connect() as connection, connection.begin():
        result = connection.execute(sa.text(f"DROP TABLE IF EXISTS {full_table_name}"))
    postgres_config_soft_delete = copy.deepcopy(cratedb_target._config)
    postgres_config_soft_delete["hard_delete"] = False
    pg_soft_delete = TargetCrateDB(config=postgres_config_soft_delete)
    singer_file_to_target(file_name, pg_soft_delete)

    with engine.connect() as connection:
        result = connection.execute(sa.text(f"SELECT * FROM {full_table_name}"))
        assert result.rowcount == 7
    with engine.connect() as connection, connection.begin():
        # Add a record like someone would if they weren't using the tap target combo
        result = connection.execute(
            sa.text(f"INSERT INTO {full_table_name}(code, \"name\") VALUES('Manual1', 'Meltano')")
        )
        result = connection.execute(
            sa.text(f"INSERT INTO {full_table_name}(code, \"name\") VALUES('Manual2', 'Meltano')")
        )
        # CrateDB-specific: Synchronize write operations.
        # TODO: Can this case be handled transparently?
        connection.execute(sa.text(f"REFRESH TABLE {full_table_name}"))
    with engine.connect() as connection:
        result = connection.execute(sa.text(f"SELECT * FROM {full_table_name}"))
        assert result.rowcount == 9

    singer_file_to_target(file_name, pg_soft_delete)

    # Should have all records including the 2 we added manually
    with engine.connect() as connection:
        result = connection.execute(sa.text(f"SELECT * FROM {full_table_name}"))
        assert result.rowcount == 9

        result = connection.execute(
            sa.text(f'SELECT * FROM {full_table_name} where "{METADATA_COLUMN_PREFIX}_deleted_at" is NOT NULL')
        )
        assert result.rowcount == 2


def test_activate_version_deletes_data_properly(cratedb_target):
    """Activate Version should"""
    engine = create_engine(cratedb_target)
    table_name = "test_activate_version_deletes_data_properly"
    file_name = f"{table_name}.singer"
    full_table_name = cratedb_target.config["default_target_schema"] + "." + table_name
    with engine.connect() as connection, connection.begin():
        result = connection.execute(sa.text(f"DROP TABLE IF EXISTS {full_table_name}"))

    postgres_config_soft_delete = copy.deepcopy(cratedb_target._config)
    postgres_config_soft_delete["hard_delete"] = True
    pg_hard_delete = TargetCrateDB(config=postgres_config_soft_delete)
    singer_file_to_target(file_name, pg_hard_delete)
    # Will populate us with 7 records
    with engine.connect() as connection:
        result = connection.execute(sa.text(f"SELECT * FROM {full_table_name}"))
        assert result.rowcount == 7
    with engine.connect() as connection, connection.begin():
        result = connection.execute(
            sa.text(f"INSERT INTO {full_table_name} (code, \"name\") VALUES('Manual1', 'Meltano')")
        )
        result = connection.execute(
            sa.text(f"INSERT INTO {full_table_name} (code, \"name\") VALUES('Manual2', 'Meltano')")
        )
        # CrateDB-specific: Synchronize write operations.
        # TODO: Can this case be handled transparently?
        connection.execute(sa.text(f"REFRESH TABLE {full_table_name};"))
    with engine.connect() as connection, connection.begin():
        result = connection.execute(sa.text(f"SELECT * FROM {full_table_name}"))
        assert result.rowcount == 9

    # Only has a schema and one activate_version message, should delete all records
    # as it's a higher version than what's currently in the table.
    file_name = f"{table_name}_2.singer"
    singer_file_to_target(file_name, pg_hard_delete)
    with engine.connect() as connection:
        result = connection.execute(sa.text(f"SELECT * FROM {full_table_name}"))
        assert result.rowcount == 0


@pytest.mark.skip('Does not work yet: extraneous input "CHAR"')
def test_reserved_keywords(cratedb_target):
    """Target should work regardless of column names

    Postgres has a number of reserved keywords listed here https://www.postgresql.org/docs/current/sql-keywords-appendix.html.
    """
    file_name = "reserved_keywords.singer"
    singer_file_to_target(file_name, cratedb_target)


@pytest.mark.skipif(not MELTANO_CRATEDB_STRATEGY_DIRECT, reason="Does not work in temptable/upsert mode")
def test_uppercase_stream_name_with_column_alter(cratedb_target):
    """Column Alters need to work with uppercase stream names"""
    file_name = "uppercase_stream_name_with_column_alter.singer"
    singer_file_to_target(file_name, cratedb_target)


@pytest.mark.skip(reason="RelationUnknown[Relation 'melty.account' unknown. Maybe you meant '\"Account\"']")
def test_activate_version_uppercase_stream_name(cratedb_config):
    """Activate Version should work with uppercase stream names"""
    file_name = "test_activate_version_uppercase_stream_name.singer"
    postgres_config_hard_delete = copy.deepcopy(cratedb_config)
    postgres_config_hard_delete["hard_delete"] = True
    pg_hard_delete = TargetCrateDB(config=postgres_config_hard_delete)
    singer_file_to_target(file_name, pg_hard_delete)
