"""Handles CrateDB interactions."""

from __future__ import annotations

import typing as t
from builtins import issubclass  # noqa: A004
from datetime import datetime

import sqlalchemy as sa
from crate.client.sqlalchemy.types import ObjectType, ObjectTypeImpl, _ObjectArray
from singer_sdk import typing as th
from singer_sdk.helpers._typing import is_array_type, is_boolean_type, is_integer_type, is_number_type, is_object_type
from target_postgres.connector import NOTYPE, PostgresConnector

from target_cratedb.sqlalchemy.patch import polyfill_refresh_after_dml_engine
from target_cratedb.sqlalchemy.vector import FloatVector


class CrateDBConnector(PostgresConnector):
    """Set up SQLAlchemy and database utilities."""

    allow_column_add: bool = True  # Whether ADD COLUMN is supported.
    allow_column_rename: bool = False  # Whether RENAME COLUMN is supported.
    allow_column_alter: bool = False  # Whether altering column types is supported.
    allow_merge_upsert: bool = False  # Whether MERGE UPSERT is supported.
    allow_temp_tables: bool = False  # Whether temp tables are supported.

    def create_engine(self) -> sa.Engine:
        """
        Create an SQLAlchemy engine object.

        Note: Needs to be patched to establish a polyfill which will synchronize write operations.
        """
        engine = super().create_engine()
        polyfill_refresh_after_dml_engine(engine)
        return engine

    @staticmethod
    def to_sql_type(jsonschema_type: dict) -> sa.types.TypeEngine:
        """Return a JSON Schema representation of the provided type.

        Note: Needs to be patched to invoke other static methods on `CrateDBConnector`.

        By default will call `typing.to_sql_type()`.

        Developers may override this method to accept additional input argument types,
        to support non-standard types, or to provide custom typing logic.
        If overriding this method, developers should call the default implementation
        from the base class for all unhandled cases.

        Args:
            jsonschema_type: The JSON Schema representation of the source type.

        Returns:
            The SQLAlchemy type representation of the data type.
        """
        json_type_array = []

        if jsonschema_type.get("type", False):
            if isinstance(jsonschema_type["type"], str):
                json_type_array.append(jsonschema_type)
            elif isinstance(jsonschema_type["type"], list):
                for entry in jsonschema_type["type"]:
                    json_type_dict = {}
                    json_type_dict["type"] = entry
                    if jsonschema_type.get("format", False):
                        json_type_dict["format"] = jsonschema_type["format"]
                    json_type_array.append(json_type_dict)
            else:
                msg = "Invalid format for jsonschema type: not str or list."
                raise RuntimeError(msg)
        elif jsonschema_type.get("anyOf", False):
            for entry in jsonschema_type["anyOf"]:
                json_type_array.append(entry)
        else:
            msg = "Neither type nor anyOf are present. Unable to determine type. " "Defaulting to string."
            return NOTYPE()
        sql_type_array = []
        for json_type in json_type_array:
            picked_type = CrateDBConnector.pick_individual_type(jsonschema_type=json_type)
            if picked_type is not None:
                sql_type_array.append(picked_type)

        return CrateDBConnector.pick_best_sql_type(sql_type_array=sql_type_array)

    @staticmethod
    def pick_individual_type(jsonschema_type: dict):
        """Select the correct sql type assuming jsonschema_type has only a single type.

        Note: Needs to be patched to supply handlers for `object` and `array`.

        Args:
            jsonschema_type: A jsonschema_type array containing only a single type.

        Returns:
            An instance of the appropriate SQL type class based on jsonschema_type.
        """
        if "null" in jsonschema_type["type"]:
            return None
        if "integer" in jsonschema_type["type"]:
            return sa.BIGINT()
        if "object" in jsonschema_type["type"]:
            return ObjectType
        if "array" in jsonschema_type["type"]:
            # Select between different kinds of `ARRAY` data types.
            #
            # This currently leverages an unspecified definition for the Singer SCHEMA,
            # using the `additionalProperties` attribute to convey additional type
            # information, agnostic of the target database.
            #
            # In this case, it is about telling different kinds of `ARRAY` types apart:
            # Either it is a vanilla `ARRAY`, to be stored into a `jsonb[]` type, or,
            # alternatively, it can be a "vector" kind `ARRAY` of floating point
            # numbers, effectively what pgvector is storing in its `VECTOR` type.
            #
            # Still, `type: "vector"` is only a surrogate label here, because other
            # database systems may use different types for implementing the same thing,
            # and need to translate accordingly.
            """
            Schema override rule in `meltano.yml`:

            type: "array"
            items:
              type: "number"
            additionalProperties:
              storage:
                type: "vector"
                dim: 4

            Produced schema annotation in `catalog.json`:

            {"type": "array",
             "items": {"type": "number"},
             "additionalProperties": {"storage": {"type": "vector", "dim": 4}}}
            """
            if "additionalProperties" in jsonschema_type and "storage" in jsonschema_type["additionalProperties"]:
                storage_properties = jsonschema_type["additionalProperties"]["storage"]
                if "type" in storage_properties and storage_properties["type"] == "vector":
                    # On PostgreSQL/pgvector, use the corresponding type definition
                    # from its SQLAlchemy dialect.
                    return FloatVector(dimensions=storage_properties["dim"])

            # Discover/translate inner types.
            inner_type = resolve_array_inner_type(jsonschema_type)
            if inner_type is not None:
                return sa.ARRAY(inner_type)

            # When type discovery fails, assume `TEXT`.
            return sa.ARRAY(sa.TEXT())

        if jsonschema_type.get("format") == "date-time":
            return sa.TIMESTAMP()
        individual_type = th.to_sql_type(jsonschema_type)
        if isinstance(individual_type, sa.VARCHAR):
            return sa.TEXT()
        return individual_type

    @staticmethod
    def pick_best_sql_type(sql_type_array: list):
        """Select the best SQL type from an array of instances of SQL type classes.

        Note: Needs to be patched to supply handler for `ObjectTypeImpl`.

        Args:
            sql_type_array: The array of instances of SQL type classes.

        Returns:
            An instance of the best SQL type class based on defined precedence order.
        """
        precedence_order = [
            sa.ARRAY,
            FloatVector,
            ObjectTypeImpl,
            sa.TEXT,
            sa.TIMESTAMP,
            sa.DATETIME,
            sa.DATE,
            sa.TIME,
            sa.DECIMAL,
            sa.FLOAT,
            sa.BIGINT,
            sa.INTEGER,
            sa.BOOLEAN,
            NOTYPE,
        ]

        for sql_type in precedence_order:
            for obj in sql_type_array:
                if isinstance(obj, sql_type):
                    return obj
        return sa.TEXT()

    def _sort_types(
        self,
        sql_types: t.Iterable[sa.types.TypeEngine],
    ) -> list[sa.types.TypeEngine]:
        """Return the input types sorted from most to least compatible.

        Note: Needs to be patched to supply handlers for `_ObjectArray` and `NOTYPE`.

        For example, [Smallint, Integer, Datetime, String, Double] would become
        [Unicode, String, Double, Integer, Smallint, Datetime].

        String types will be listed first, then decimal types, then integer types,
        then bool types, and finally datetime and date. Higher precision, scale, and
        length will be sorted earlier.

        Args:
            sql_types (List[sqlalchemy.types.TypeEngine]): [description]

        Returns:
            The sorted list.
        """

        def _get_type_sort_key(
            sql_type: sa.types.TypeEngine,
        ) -> tuple[int, int]:
            # return rank, with higher numbers ranking first

            _len = int(getattr(sql_type, "length", 0) or 0)

            if isinstance(sql_type, _ObjectArray):
                return 0, _len
            if isinstance(sql_type, FloatVector):
                return 0, _len
            if isinstance(sql_type, NOTYPE):
                return 0, _len

            _pytype = t.cast(type, sql_type.python_type)
            if issubclass(_pytype, (str, bytes)):
                return 900, _len
            if issubclass(_pytype, datetime):
                return 600, _len
            if issubclass(_pytype, float):
                return 400, _len
            if issubclass(_pytype, int):
                return 300, _len

            return 0, _len

        return sorted(sql_types, key=_get_type_sort_key, reverse=True)

    def copy_table_structure(
        self,
        full_table_name: str,
        from_table: sa.Table,
        connection: sa.engine.Connection,
        as_temp_table: bool = False,
    ) -> sa.Table:
        """Copy table structure.

        Note: Needs to be patched to prevent `Primary key columns cannot be nullable` errors.

        Args:
            full_table_name: the target table name potentially including schema
            from_table: the  source table
            connection: the database connection.
            as_temp_table: True to create a temp table.

        Returns:
            The new table object.
        """
        _, schema_name, table_name = self.parse_full_table_name(full_table_name)
        meta = sa.MetaData(schema=schema_name)
        columns = []
        if self.table_exists(full_table_name=full_table_name):
            raise RuntimeError("Table already exists")
        column: sa.Column
        for column in from_table.columns:
            # CrateDB: Prevent `Primary key columns cannot be nullable` errors.
            if column.primary_key and column.nullable:
                column.nullable = False
            columns.append(column._copy())
        new_table = sa.Table(table_name, meta, *columns)
        new_table.create(bind=connection)
        return new_table

    def prepare_schema(self, schema_name: str) -> None:
        """
        Don't emit `CREATE SCHEMA` statements to CrateDB.
        """
        pass


def resolve_array_inner_type(jsonschema_type: dict) -> t.Union[sa.types.TypeEngine, None]:
    if "items" in jsonschema_type:
        if is_boolean_type(jsonschema_type["items"]):
            return sa.BOOLEAN()
        if is_number_type(jsonschema_type["items"]):
            return sa.FLOAT()
        if is_integer_type(jsonschema_type["items"]):
            return sa.BIGINT()
        if is_object_type(jsonschema_type["items"]):
            return ObjectType()
        if is_array_type(jsonschema_type["items"]):
            return resolve_array_inner_type(jsonschema_type["items"]["type"])
    return None
