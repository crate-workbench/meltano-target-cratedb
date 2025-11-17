"""CrateDB target sink class, which handles writing streams."""

import datetime
import os
from typing import List, Optional, Union

import sqlalchemy as sa
from singer_sdk.sql.connector import FullyQualifiedName
from sqlalchemy.util import asbool
from target_postgres.sinks import PostgresSink

from target_cratedb.connector import CrateDBConnector

MELTANO_CRATEDB_STRATEGY_DIRECT = asbool(os.getenv("MELTANO_CRATEDB_STRATEGY_DIRECT", "true"))


class CrateDBSink(PostgresSink):
    """CrateDB target sink class."""

    connector_class = CrateDBConnector

    def __init__(self, *args, **kwargs):
        """Initialize SQL Sink. See super class for more details."""
        super().__init__(*args, **kwargs)

        # Whether to use the Meltano standard strategy, looping the data
        # through a temporary table, or whether to directly apply the DML
        # operations on the target table.
        self.strategy_direct = MELTANO_CRATEDB_STRATEGY_DIRECT

    def process_batch(self, context: dict) -> None:
        """Process a batch with the given batch context.

        Writes a batch to the SQL target. Developers may override this method
        in order to provide a more efficient upload/upsert process.

        Args:
            context: Stream partition or context dictionary.
        """

        # The PostgreSQL adapter uses only one connection, so we do this all in a single transaction.
        # The CrateDB adapter will use a separate connection, to make `REFRESH TABLE ...` work.
        with self.connector._connect() as connection, connection.begin():
            # Check structure of table
            table: sa.Table = self.connector.prepare_table(
                full_table_name=self.full_table_name,
                schema=self.schema,
                primary_keys=self.key_properties,
                as_temp_table=False,
                connection=connection,
            )

            # Insert directly into target table.
            # This can be used as a surrogate if the regular temptable-upsert
            # procedure doesn't work, or isn't applicable for performance reasons.
            if self.strategy_direct:
                self.bulk_insert_records(
                    table=table,
                    schema=self.schema,
                    primary_keys=self.key_properties,
                    records=context["records"],
                    connection=connection,
                )
                self.refresh_table(table)
                return

            # Create a temp table (Creates from the table above)
            # CrateDB: Need to pre-compute full-qualified table name, and quoted variant,
            #          for satisfying both Meltano, and for running a `REFRESH TABLE`.
            temp_full_table_name = f"{self.schema_name}.{self.temp_table_name}"
            temp_table: sa.Table = self.connector.copy_table_structure(
                full_table_name=temp_full_table_name,
                from_table=table,
                # CrateDB does not provide temporary tables.
                as_temp_table=False,
                connection=connection,
            )
            # Insert into temp table
            self.bulk_insert_records(
                table=temp_table,
                schema=self.schema,
                primary_keys=self.key_properties,
                records=context["records"],
                connection=connection,
            )

        # Run a new "transaction" to synchronize write operations.
        with self.connector._connect() as connection:
            self.refresh_table(temp_table)

            # Merge data from Temp table to main table
            self.upsert(
                from_table=temp_table,
                to_table=table,
                schema=self.schema,
                join_keys=self.key_properties,
                connection=connection,
            )
            # Drop temp table
            self.connector.drop_table(table=temp_table, connection=connection)

        self.refresh_table(table)

    def upsert(
        self,
        from_table: sa.Table,
        to_table: sa.Table,
        schema: dict,
        join_keys: List[str],
        connection: sa.engine.Connection,
    ) -> Optional[int]:
        """Merge upsert data from one table to another.

        Args:
            from_table: The source table.
            to_table: The destination table.
            schema: Singer Schema message.
            join_keys: The merge upsert keys, or `None` to append.
            connection: The database connection.

        Return:
            The number of records copied, if detectable, or `None` if the API does not
            report number of records affected/inserted.

        """
        columns = from_table.columns
        column_names = columns.keys()
        if self.append_only is True:
            # Insert
            select_stmt = sa.select(columns).select_from(from_table)  # type: ignore[call-overload]
            insert_stmt = to_table.insert().from_select(names=column_names, select=select_stmt)
            connection.execute(insert_stmt)
        else:
            join_predicates = []
            to_table_key: sa.Column
            for key in join_keys:
                from_table_key: sa.Column = from_table.columns[key]
                to_table_key = to_table.columns[key]
                join_predicates.append(from_table_key == to_table_key)

            join_condition = sa.and_(*join_predicates)

            where_predicates = []
            for key in join_keys:
                to_table_key = to_table.columns[key]
                where_predicates.append(to_table_key.is_(None))
            where_condition = sa.and_(*where_predicates)

            select_stmt = (
                sa.select(columns)  # type: ignore[call-overload]
                .select_from(from_table.outerjoin(to_table, join_condition))
                .where(where_condition)
            )
            insert_stmt = sa.insert(to_table).from_select(names=column_names, select=select_stmt)

            connection.execute(insert_stmt)

            # Update
            # CrateDB does not support `UPDATE ... FROM` statements.
            # https://github.com/crate/crate/issues/15204
            """
            where_condition = join_condition
            update_columns = {}
            for column_name in self.schema["properties"].keys():
                from_table_column: sa.Column = from_table.columns[column_name]
                to_table_column: sa.Column = to_table.columns[column_name]
                # For CrateDB, skip updating primary key columns. Otherwise, CrateDB
                # will fail like `ColumnValidationException[Validation failed for code:
                # Updating a primary key is not supported]`.
                if to_table_column.primary_key:
                    continue
                update_columns[to_table_column] = from_table_column

            update_stmt = sa.update(to_table).where(where_condition).values(update_columns)
            connection.execute(update_stmt)
            """

            # Update, Python-emulated
            to_table_pks = to_table.primary_key.columns
            from_table_pks = from_table.primary_key.columns

            where_condition = join_condition
            select_stmt = sa.select(from_table).where(where_condition)
            cursor = connection.execute(select_stmt)
            for record in cursor.fetchall():
                record_dict = record._asdict()
                update_where_clauses = []
                for from_table_pk, to_table_pk in zip(from_table_pks, to_table_pks):
                    # Get primary key name and value from record.
                    pk_name = from_table_pk.name
                    pk_value = record_dict[pk_name]

                    # CrateDB: Need to omit primary keys from record.
                    # ColumnValidationException[Validation failed for id: Updating a primary key is not supported]
                    del record_dict[pk_name]

                    # Build up where clauses for UPDATE statement.
                    update_where_clauses.append(to_table_pk == pk_value)

                update_where_condition = sa.and_(*update_where_clauses)
                update_stmt = sa.update(to_table).values(record_dict).where(update_where_condition)
                connection.execute(update_stmt)

        return None

    def activate_version(self, new_version: int) -> None:
        """Bump the active version of the target table.

        Args:
            new_version: The version number to activate.
        """
        # There's nothing to do if the table doesn't exist yet
        # (which it won't the first time the stream is processed)
        if not self.connector.table_exists(self.full_table_name):
            return

        deleted_at = datetime.datetime.now(tz=datetime.timezone.utc)

        # Different from SingerSDK as we need to handle types the
        # same as SCHEMA messsages
        datetime_type = self.connector.to_sql_type({"type": "string", "format": "date-time"})

        # Different from SingerSDK as we need to handle types the
        # same as SCHEMA messsages
        integer_type = self.connector.to_sql_type({"type": "integer"})

        with self.connector._connect() as connection, connection.begin():
            if not self.connector.column_exists(
                full_table_name=self.full_table_name,
                column_name=self.version_column_name,
                connection=connection,
            ):
                self.connector.prepare_column(
                    self.full_table_name,
                    self.version_column_name,
                    sql_type=integer_type,
                    connection=connection,
                )

            self.logger.info("Hard delete: %s", self.config.get("hard_delete"))
            if self.config["hard_delete"] is True:
                connection.execute(
                    sa.text(
                        f'DELETE FROM "{self.schema_name}"."{self.table_name}" '  # noqa: S608
                        f'WHERE "{self.version_column_name}" <= {new_version} '
                        f'OR "{self.version_column_name}" IS NULL'
                    )
                )
                self.refresh_table(self.full_table_name)
                return

            if not self.connector.column_exists(
                full_table_name=self.full_table_name,
                column_name=self.soft_delete_column_name,
                connection=connection,
            ):
                self.connector.prepare_column(
                    self.full_table_name,
                    self.soft_delete_column_name,
                    sql_type=datetime_type,
                    connection=connection,
                )
            # Need to deal with the case where data doesn't exist for the version column
            query = sa.text(
                f'UPDATE "{self.schema_name}"."{self.table_name}"\n'
                f'SET "{self.soft_delete_column_name}" = :deletedate \n'
                f'WHERE "{self.version_column_name}" < :version '
                f'OR "{self.version_column_name}" IS NULL \n'
                f'  AND "{self.soft_delete_column_name}" IS NULL\n'
            )
            query = query.bindparams(
                sa.bindparam("deletedate", value=deleted_at, type_=datetime_type),
                sa.bindparam("version", value=new_version, type_=integer_type),
            )
            connection.execute(query)

            self.refresh_table(self.full_table_name)

    def generate_insert_statement(
        self,
        full_table_name: str,
        columns: List[sa.Column],
    ) -> Union[str, sa.sql.Executable]:
        """Generate an insert statement for the given records.

        Args:
            full_table_name: the target table name.
            schema: the JSON schema for the new table.

        Returns:
            An insert statement.
        """
        # FIXME:
        metadata = sa.MetaData(schema=self.schema_name)
        table = sa.Table(full_table_name, metadata, *columns)
        return sa.insert(table)

    def refresh_table(self, table: Union[sa.Table, str]):
        """
        Synchronize write operations on CrateDB.
        """
        with self.connector._connect() as connection:
            if isinstance(table, FullyQualifiedName):
                table_full = str(table)
            elif isinstance(table, sa.Table):
                table_full = f'"{table.schema}"."{table.name}"'
            elif isinstance(table, str):
                table_full = table
            else:
                raise TypeError(f"Unknown type `{type(table)}` for table: {table}")
            connection.exec_driver_sql(f"REFRESH TABLE {table_full};")
