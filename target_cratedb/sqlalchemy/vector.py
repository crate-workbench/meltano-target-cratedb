# TODO: Refactor to CrateDB SQLAlchemy dialect.
import typing as t

import numpy as np
import numpy.typing as npt
import sqlalchemy as sa
from crate.client.sqlalchemy.compiler import CrateTypeCompiler
from crate.client.sqlalchemy.dialect import TYPES_MAP
from sqlalchemy.sql import sqltypes
from sqlalchemy.sql.type_api import TypeEngine

__all__ = ["FloatVector"]


def from_db(value: t.Iterable) -> t.Optional[npt.ArrayLike]:
    # from `pgvector.utils`
    # could be ndarray if already cast by lower-level driver
    if value is None or isinstance(value, np.ndarray):
        return value

    return np.array(value, dtype=np.float32)


def to_db(value: t.Any, dim: t.Optional[int] = None) -> t.Optional[t.List]:
    # from `pgvector.utils`
    if value is None:
        return value

    if isinstance(value, np.ndarray):
        if value.ndim != 1:
            raise ValueError("expected ndim to be 1")

        if not np.issubdtype(value.dtype, np.integer) and not np.issubdtype(value.dtype, np.floating):
            raise ValueError("dtype must be numeric")

        value = value.tolist()

    if dim is not None and len(value) != dim:
        raise ValueError("expected %d dimensions, not %d" % (dim, len(value)))

    return value


class FloatVector(TypeEngine[t.Sequence[t.Any]]):
    """
    An improved implementation of the `FloatVector` data type for CrateDB,
    compared to the previous implementation on behalf of the LangChain adapter.

    https://crate.io/docs/crate/reference/en/master/general/ddl/data-types.html#float-vector
    https://crate.io/docs/crate/reference/en/master/general/builtins/scalar-functions.html#scalar-knn-match

    The previous implementation, based on SQLAlchemy's `UserDefinedType`, didn't
    respect the `python_type` property on backward/reverse resolution of types.
    This was observed on Meltano's database connector machinery doing a
    type cast, which led to a `NotImplementedError`.

        typing.cast(type, sql_type.python_type) => NotImplementedError

    The `UserDefinedType` approach is easier to implement, because it doesn't
    need compiler support.

    To get full SQLAlchemy type support, including support for forward- and
    backward resolution / type casting, the custom data type should derive
    from SQLAlchemy's `TypeEngine` base class instead.

    When deriving from `TypeEngine`, you will need to set the `__visit_name__`
    attribute, and add a corresponding visitor method to the `CrateTypeCompiler`,
    in this case, `visit_FLOAT_VECTOR`.

    Now, rendering a DDL succeeds. However, when reflecting the DDL schema back,
    it doesn't work until you will establish a corresponding reverse type mapping.

    By invoking `SELECT DISTINCT(data_type) FROM information_schema.columns;`,
    you will find out that the internal type name is `float_vector`, so you
    announce it to the dialect using `TYPES_MAP["float_vector"] = FloatVector`.

    Still not there: `NotImplementedError: Default TypeEngine.as_generic() heuristic
    method was unsuccessful for target_cratedb.sqlalchemy.vector.FloatVector. A
    custom as_generic() method must be implemented for this type class.`

    So, as it signals that the type implementation also needs an `as_generic`
    property, let's supply one, returning `sqltypes.ARRAY`.

    It looks like, in exchange to those improvements, the `get_col_spec`
    method is not needed any longer.

    TODO: Would it be a good idea to derive from SQLAlchemy's
          `ARRAY` right away, to get a few of the features without
          the need to redefine them?

    Please note the outcome of this analysis and the corresponding implementation
    has been derived from empirical observations, and from the feeling that we also
    lack corresponding support on the other special data types of CrateDB (ARRAY and
    OBJECT) within the SQLAlchemy dialect, i.e. "that something must be wrong or
    incomplete". In this spirit, it is advisable to review and improve their
    implementations correspondingly.
    """

    cache_ok = True

    __visit_name__ = "FLOAT_VECTOR"

    _is_array = True

    zero_indexes = False

    def __init__(self, dim: t.Optional[int] = None, as_tuple: bool = False) -> None:
        self.dim = dim
        self.as_tuple = as_tuple

    @property
    def hashable(self):
        return self.as_tuple

    @property
    def python_type(self):
        return list

    def as_generic(self):
        return sqltypes.ARRAY

    def bind_processor(self, dialect: sa.Dialect) -> t.Callable:
        def process(value: t.Iterable) -> t.Optional[t.List]:
            return to_db(value, self.dim)

        return process

    def result_processor(self, dialect: sa.Dialect, coltype: t.Any) -> t.Callable:
        def process(value: t.Any) -> t.Optional[npt.ArrayLike]:
            return from_db(value)

        return process

    """
    CrateDB currently only supports the similarity function `VectorSimilarityFunction.EUCLIDEAN`.
    -- https://github.com/crate/crate/blob/1ca5c6dbb2/server/src/main/java/io/crate/types/FloatVectorType.java#L55

    On the other hand, pgvector use a comparator to apply different similarity functions as operators,
    see `pgvector.sqlalchemy.Vector.comparator_factory`.

    <->: l2/euclidean_distance
    <#>: max_inner_product
    <=>: cosine_distance

    TODO: Discuss.
    """  # noqa: E501


# Accompanies the type definition for reverse type lookups.
TYPES_MAP["float_vector"] = FloatVector


def visit_FLOAT_VECTOR(self, type_, **kw):
    return f"FLOAT_VECTOR({type_.dim})"


CrateTypeCompiler.visit_FLOAT_VECTOR = visit_FLOAT_VECTOR
