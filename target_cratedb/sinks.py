"""CrateDB target sink class, which handles writing streams."""
import datetime
import time
from typing import List, Optional, Union

import sqlalchemy
from pendulum import now
from sqlalchemy import Column, Executable, MetaData, Table, bindparam, insert, select, update
from target_postgres.sinks import PostgresSink

from target_cratedb.connector import CrateDBConnector


class CrateDBSink(PostgresSink):
    """CrateDB target sink class."""

    connector_class = CrateDBConnector

    soft_delete_column_name = "__sdc_deleted_at"
    version_column_name = "__sdc_table_version"

    # Record processing

    def _add_sdc_metadata_to_record(
        self,
        record: dict,
        message: dict,
        context: dict,
    ) -> None:
        """Populate metadata _sdc columns from incoming record message.

        Record metadata specs documented at:
        https://sdk.meltano.com/en/latest/implementation/record_metadata.html

        Args:
            record: Individual record in the stream.
            message: The record message.
            context: Stream partition or context dictionary.
        """
        record["__sdc_extracted_at"] = message.get("time_extracted")
        record["__sdc_received_at"] = datetime.datetime.now(
            tz=datetime.timezone.utc,
        ).isoformat()
        record["__sdc_batched_at"] = (
            context.get("batch_start_time", None) or datetime.datetime.now(tz=datetime.timezone.utc)
        ).isoformat()
        record["__sdc_deleted_at"] = record.get("__sdc_deleted_at")
        record["__sdc_sequence"] = int(round(time.time() * 1000))
        record["__sdc_table_version"] = message.get("version")
        record["__sdc_sync_started_at"] = self.sync_started_at

    def _add_sdc_metadata_to_schema(self) -> None:
        """Add _sdc metadata columns.

        Record metadata specs documented at:
        https://sdk.meltano.com/en/latest/implementation/record_metadata.html
        """
        properties_dict = self.schema["properties"]
        for col in (
            "__sdc_extracted_at",
            "__sdc_received_at",
            "__sdc_batched_at",
            "__sdc_deleted_at",
        ):
            properties_dict[col] = {
                "type": ["null", "string"],
                "format": "date-time",
            }
        for col in ("__sdc_sequence", "__sdc_table_version", "__sdc_sync_started_at"):
            properties_dict[col] = {"type": ["null", "integer"]}

    def _remove_sdc_metadata_from_schema(self) -> None:
        """Remove _sdc metadata columns.

        Record metadata specs documented at:
        https://sdk.meltano.com/en/latest/implementation/record_metadata.html
        """
        properties_dict = self.schema["properties"]
        for col in (
            "__sdc_extracted_at",
            "__sdc_received_at",
            "__sdc_batched_at",
            "__sdc_deleted_at",
            "__sdc_sequence",
            "__sdc_table_version",
            "__sdc_sync_started_at",
        ):
            properties_dict.pop(col, None)

    def _remove_sdc_metadata_from_record(self, record: dict) -> None:
        """Remove metadata _sdc columns from incoming record message.

        Record metadata specs documented at:
        https://sdk.meltano.com/en/latest/implementation/record_metadata.html

        Args:
            record: Individual record in the stream.
        """
        record.pop("__sdc_extracted_at", None)
        record.pop("__sdc_received_at", None)
        record.pop("__sdc_batched_at", None)
        record.pop("__sdc_deleted_at", None)
        record.pop("__sdc_sequence", None)
        record.pop("__sdc_table_version", None)
        record.pop("__sdc_sync_started_at", None)

    def process_batch(self, context: dict) -> None:
        """Process a batch with the given batch context.

        Writes a batch to the SQL target. Developers may override this method
        in order to provide a more efficient upload/upsert process.

        Args:
            context: Stream partition or context dictionary.
        """
        # Use one connection so we do this all in a single transaction
        with self.connector._connect() as connection, connection.begin():
            # Check structure of table
            table: sqlalchemy.Table = self.connector.prepare_table(
                full_table_name=self.full_table_name,
                schema=self.schema,
                primary_keys=self.key_properties,
                as_temp_table=False,
                connection=connection,
            )
            # Insert into table
            self.bulk_insert_records(
                table=table,
                schema=self.schema,
                primary_keys=self.key_properties,
                records=context["records"],
                connection=connection,
            )
            # FIXME: Upserts do not work yet.
            """
            # Create a temp table (Creates from the table above)
            temp_table: sqlalchemy.Table = self.connector.copy_table_structure(
                full_table_name=self.temp_table_name,
                from_table=table,
                as_temp_table=True,
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
            """

    def upsertX(
        self,
        from_table: sqlalchemy.Table,
        to_table: sqlalchemy.Table,
        schema: dict,
        join_keys: List[Column],
        connection: sqlalchemy.engine.Connection,
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

        if self.append_only is True:
            # Insert
            select_stmt = select(from_table.columns).select_from(from_table)
            insert_stmt = to_table.insert().from_select(names=list(from_table.columns), select=select_stmt)
            connection.execute(insert_stmt)
        else:
            join_predicates = []
            for key in join_keys:
                from_table_key: sqlalchemy.Column = from_table.columns[key]  # type: ignore[call-overload]
                to_table_key: sqlalchemy.Column = to_table.columns[key]  # type: ignore[call-overload]
                join_predicates.append(from_table_key == to_table_key)  # type: ignore[call-overload]

            join_condition = sqlalchemy.and_(*join_predicates)

            where_predicates = []
            for key in join_keys:
                to_table_key: sqlalchemy.Column = to_table.columns[key]  # type: ignore[call-overload,no-redef]
                where_predicates.append(to_table_key.is_(None))
            where_condition = sqlalchemy.and_(*where_predicates)

            select_stmt = (
                select(from_table.columns)
                .select_from(from_table.outerjoin(to_table, join_condition))
                .where(where_condition)
            )
            insert_stmt = insert(to_table).from_select(names=list(from_table.columns), select=select_stmt)

            connection.execute(insert_stmt)

            # Update
            where_condition = join_condition
            update_columns = {}
            for column_name in self.schema["properties"].keys():
                from_table_column: sqlalchemy.Column = from_table.columns[column_name]
                to_table_column: sqlalchemy.Column = to_table.columns[column_name]
                # Prevent: `Updating a primary key is not supported`
                if to_table_column.primary_key:
                    continue
                update_columns[to_table_column] = from_table_column

            update_stmt = update(to_table).where(where_condition).values(update_columns)
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

        deleted_at = now()
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
                    sqlalchemy.text(
                        f'DELETE FROM "{self.schema_name}"."{self.table_name}" '  # noqa: S608
                        f'WHERE "{self.version_column_name}" <= {new_version} '
                        f'OR "{self.version_column_name}" IS NULL'
                    )
                )
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
            query = sqlalchemy.text(
                f'UPDATE "{self.schema_name}"."{self.table_name}"\n'
                f'SET "{self.soft_delete_column_name}" = :deletedate \n'
                f'WHERE "{self.version_column_name}" < :version '
                f'OR "{self.version_column_name}" IS NULL \n'
                f'  AND "{self.soft_delete_column_name}" IS NULL\n'
            )
            query = query.bindparams(
                bindparam("deletedate", value=deleted_at, type_=datetime_type),
                bindparam("version", value=new_version, type_=integer_type),
            )
            connection.execute(query)

    def generate_insert_statement(
        self,
        full_table_name: str,
        columns: List[Column],
    ) -> Union[str, Executable]:
        """Generate an insert statement for the given records.

        Args:
            full_table_name: the target table name.
            schema: the JSON schema for the new table.

        Returns:
            An insert statement.
        """
        # FIXME:
        metadata = MetaData(schema=self.schema_name)
        table = Table(full_table_name, metadata, *columns)
        return insert(table)
