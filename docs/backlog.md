# Backlog

## Iteration +1
- Unlock configuring dedicated database schema, not just `melty`.
  Why doesn't `"crate://crate@localhost/?schema=foo"` work? Confirm this?
- Submit a few patches to `meltanolabs-target-postgres`, about proper
  quoting of schema and table names.
- Submit a few other patches to crate-python, in order to clean up here.
- Release v0.0.1
- Submit registration to Meltano Hub

## Iteration +2
- Venerable schema name propagation flaw hits again, but differently?
  ```
  TypeError: PostgresConnector.get_table_columns() got an unexpected keyword argument 'full_table_name'
  ```

## Obstacles
Upstream some workarounds to crate-python.
- `TypeError: Invalid argument(s) 'json_serializer','json_deserializer' sent to create_engine(), using configuration CrateDialect/QueuePool/Engine.  Please check that the keyword arguments are appropriate for this combination of components.`
- `UnsupportedFeatureException[Cannot use columns of type "object" as primary key]`
- `NotImplementedError: Default TypeEngine.as_generic() heuristic method was unsuccessful for crate.client.sqlalchemy.types._ObjectArray. A custom as_generic() method must be implemented for this type class.`
- `sqlalchemy.exc.DBAPIError: (crate.client.exceptions.TimezoneUnawareException) Timezone aware datetime objects are not supported`
- `NotImplementedError: This backend does not support multiple-table criteria within UPDATE`
- `ColumnValidationException[Validation failed for code: Updating a primary key is not supported]`

## Notes
- Missing `CREATE SCHEMA` is tedious, and currently needs a workaround.


## Done
- Document use with CrateDB Cloud.
