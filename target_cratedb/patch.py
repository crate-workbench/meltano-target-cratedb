from datetime import datetime

import sqlalchemy as sa
from crate.client.sqlalchemy.dialect import TYPES_MAP, DateTime
from crate.client.sqlalchemy.types import _ObjectArray
from sqlalchemy.sql import sqltypes


def patch_sqlalchemy():
    """
    Register missing timestamp data type.

    TODO: Upstream to crate-python.
    """
    # TODO: Submit patch to `crate-python`.
    TYPES_MAP["timestamp without time zone"] = sqltypes.TIMESTAMP
    TYPES_MAP["timestamp with time zone"] = sqltypes.TIMESTAMP

    def as_generic(self):
        return sqltypes.ARRAY

    _ObjectArray.as_generic = as_generic

    def bind_processor(self, dialect):
        def process(value):
            if value is not None:
                assert isinstance(value, datetime)  # noqa: S101
                # ruff: noqa: ERA001
                # if value.tzinfo is not None:
                #    raise TimezoneUnawareException(DateTime.TZ_ERROR_MSG)
                return value.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
            return value

        return process

    DateTime.bind_processor = bind_processor


def polyfill_refresh_after_dml_engine(engine: sa.Engine):
    def receive_after_execute(
        conn: sa.engine.Connection, clauseelement, multiparams, params, execution_options, result
    ):
        """
        Run a `REFRESH TABLE ...` command after each DML operation (INSERT, UPDATE, DELETE).
        """

        if isinstance(clauseelement, (sa.sql.Insert, sa.sql.Update, sa.sql.Delete)):
            if not isinstance(clauseelement.table, sa.Join):
                conn.execute(sa.text(f'REFRESH TABLE "{clauseelement.table.schema}"."{clauseelement.table.name}";'))

    sa.event.listen(engine, "after_execute", receive_after_execute)
