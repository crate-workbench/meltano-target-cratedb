"""Init CrateDB."""
from target_cratedb.patch import patch_sqlalchemy

patch_sqlalchemy()
