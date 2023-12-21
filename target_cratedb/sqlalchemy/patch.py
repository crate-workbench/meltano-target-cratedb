from datetime import datetime

import sqlalchemy as sa
from _decimal import Decimal
from crate.client.http import CrateJsonEncoder
from sqlalchemy_cratedb.dialect import TYPES_MAP, DateTime
from sqlalchemy_cratedb.type.array import _ObjectArray


def patch_sqlalchemy():
    patch_types()
    patch_json_encoder()


def patch_types():
    """
    Register missing data types, and fix erroneous ones.

    TODO: Upstream to crate-python.
    """
    # abc()
    TYPES_MAP["bigint"] = sa.BIGINT
    TYPES_MAP["bigint_array"] = sa.ARRAY(sa.BIGINT)
    TYPES_MAP["long"] = sa.BIGINT
    TYPES_MAP["long_array"] = sa.ARRAY(sa.BIGINT)
    TYPES_MAP["real"] = sa.DOUBLE
    TYPES_MAP["real_array"] = sa.ARRAY(sa.DOUBLE)
    TYPES_MAP["timestamp without time zone"] = sa.TIMESTAMP
    TYPES_MAP["timestamp with time zone"] = sa.TIMESTAMP

    # TODO: Can `ARRAY` be inherited from PostgreSQL's
    #       `ARRAY`, to make type checking work?

    def as_generic(self):
        return sa.ARRAY

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


def patch_json_encoder():
    """
    `Decimal` types have been rendered as strings.

    TODO: Upstream to crate-python.
    """

    json_encoder_default = CrateJsonEncoder.default

    def default(self, o):
        if isinstance(o, Decimal):
            return float(o)
        return json_encoder_default(o)

    CrateJsonEncoder.default = default


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
