"""Init CrateDB."""

from target_cratedb.sqlalchemy.patch import patch_sqlalchemy

patch_sqlalchemy()
