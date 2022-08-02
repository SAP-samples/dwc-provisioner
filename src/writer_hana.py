import logging
import time, datetime as dt

#from hdbcli import dbapi

import session_config as config

logger = logging.getLogger("hana")

conn = None
cursor = None

timestamps = [ "createTime", "validFrom", "lastSuccessfulConnect", "lastInvalidConnectAttempt", "modification_date", "creation_date" ]
date_fields = [ "LAST_LOGIN_DATE" ]

def hana_connect():
    '''Connect to HANA

    Connect to the specified HANA instance and create a cursor for
    executing DDL and DML operations.  This is a singleton operation
    with the connection and cursor stored as global variables.
    '''

    global conn, cursor

    if conn is None:
        if config.get_config_param("hana", "hana_encrypt") == "True":
            encrypt = True
        else:
            encrypt = False

        if config.get_config_param("hana", "hana_sslverify") == "True":
            ssl = True
        else:
            ssl = False

        conn = dbapi.connect(address=config.get_config_param("hana", "hana_host"),
                             port=config.get_config_param("hana", "hana_port"),
                             user=config.get_config_param("hana", "hana_user"),
                             password=config.get_config_param("hana", "hana_password"),
                             encrypt=encrypt,
                             sslValidateCertificate=ssl
                            )
        
        cursor = conn.cursor()

    return True

def hana_execute(sql_statement, bind_values=[]):
    try:
        if not hana_connect():   # Ensure the connection
            logger.error("Invalid HANA connection")
            logger.error(sql_statement)
            return

        cursor.execute(sql_statement, bind_values)
    except Exception as e:
        logger.error("SQL Error: {}".format(e.errortext))
        logger.error(sql_statement)

def create_ddl(list_obj, args):
    """Create a SQL definition for a list of objects
    """
    logger.debug(f'Entering create_table_sql: {args.prefix}')

    ddl = {}

    drop_sql_tmpl = 'drop table {} cascade'
    create_sql_tmpl = 'create column table {} ('
    insert_sql_tmpl = 'insert into {} values ('

    recurse_columns(ddl, list_obj, args.prefix.upper())

    # Build all the SQL statements for all the columns

    for table_name in ddl:
        # If we have a table with no columns, then all columns
        # of this table were zero-length - skip.
        
        if len(ddl[table_name]["columns"]) == 0:
            continue

        ddl[table_name]["drop"] = drop_sql_tmpl.format(table_name)

        create_sql = create_sql_tmpl.format(table_name)
        insert_sql = insert_sql_tmpl.format(table_name)
        comma = ""

        for column_name in ddl[table_name]["columns"]:
            column_def = ddl[table_name]["columns"][column_name]

            create_sql += "\n" + comma + '"' + column_def["name"] + '" ' + column_def["type"]
            insert_sql += "\n" + comma + ":" + column_def["name"]
            comma = ","

        ddl[table_name]["create"] = create_sql + ')'
        ddl[table_name]["insert"] = insert_sql + ')'

    return ddl

def recurse_columns(ddl, list_data, param_name):
    table_name = param_name.upper()

    # Search through all the rows because some columns are not consistently
    # returned by the URL/REST queries.  Looping over all the rows helps ensure
    # we capture all the possible columns (attributes).
        
    for row in list_data:
        # If we got a list of "not dictionary" skip this recursion.

        if not isinstance(row, dict):
            return

        row_column_names = row.keys()

        if table_name not in ddl:
            ddl[table_name] = { "columns" : {} }

        for column_name in row_column_names:
            if column_name.find("@") != -1:  # Exclude metadata columns.
                continue

            # Figure out the data type over all the rows

            sql_type = None

            if isinstance(row[column_name], int):
                sql_type = "BIGINT"
            elif column_name in timestamps or column_name in date_fields:
                sql_type = "TIMESTAMP"
            elif isinstance(row[column_name], list) or isinstance(row[column_name], dict):
                sql_type = "CLOB"

                if isinstance(row[column_name], list):
                    recurse_columns(ddl, row[column_name], table_name + "_" + column_name)
            else:
                sql_type = "NVARCHAR(5000)"

            # For each column we add, record the name of the column.
            # DWC queries are sometimes inconsistent about columns and we
            # can use this list to ensure all columns are accounted for
            # across all rows.

            if column_name in ddl[table_name]["columns"]:
                column = ddl[table_name]["columns"][column_name]

                if column["type"] is None: 
                    ddl[table_name]["columns"][column_name]["type"] = sql_type
                elif column["type"] == "BIGINT" and sql_type.startswith("NVARCHAR"):
                    ddl[table_name]["columns"][column_name]["type"] = sql_type
                elif column["type"].startswith("NVARCHAR") and sql_type == "CLOB":
                    ddl[table_name]["columns"][column_name]["type"] = sql_type
            else:
                # Fix the name of the column to match the DDL; remove special characters.
                fixed_column = column_name.replace("#", "z")

                ddl[table_name]["columns"][column_name] = { "name" : fixed_column, "type" : sql_type }

def execute_ddl(ddl, statement_name):
    # If values were provided, do some fix-up to make sure they align
    # with the DDL computed earlier - this includes fixing timestamps,
    # adding missing values, and handling complex objects.
    
    for table_name in ddl:
        if statement_name in ddl[table_name]:
            sql_statement = ddl[table_name][statement_name]

            hana_execute(sql_statement)

def execute_dml(ddl, statement_name, list_data, param_name):
    if ddl is None or not isinstance(ddl, dict) or len(ddl) == 0:
        logger.error("Invalid ddl object passed to execute_dml.")
        return

    if list_data is None or isinstance(list_data, list) == False:
        logger.error(f"invalid list object passed to execute_dml - table {table_name}")
        return

    table_name = param_name.upper()

    # There are some lists that are not objects, skip

    if table_name not in ddl:
        return

    if statement_name not in ddl[table_name]:
        return

    sql_stmt = ddl[table_name][statement_name]

    for row in list_data:
        # Build the list of values to pass to the insert statement independant
        # of the actual values.  We need to insert any missing values to make
        # sure all the bind variables are present in the values passed to the
        # statement.

        insert_values = {}

        for column_name in ddl[table_name]["columns"]:
            column_def = ddl[table_name]["columns"][column_name]

            # Check for missing values - not all queries to DWC reliably return exactly the same columns

            if column_name not in row or row[column_name] is None:
                insert_values[column_def["name"]] = None
            else:            
                if column_name in timestamps:
                    # Fix-up timestamps by chopping off extend milliseconds and timezone info.
                    # Note: dateFields do not need adjustment because they have default HANA
                    #       formatting that do not need to be adjusted.

                    insert_values[column_def["name"]] = row[column_name][0:23]
                elif column_name in date_fields:
                    # This is an epoch date, convert the value before
                    epoch_time = time.gmtime(int(row[column_name][0:10]))
                    date_value = dt.datetime(*epoch_time[:7]).strftime("%Y-%m-%d %H:%M:%S")

                    insert_values[column_def["name"]] = date_value
                elif column_def["type"] == 'CLOB':
                    # Convert complex objects to strings that get inserted as CLOB values
                    insert_values[column_def["name"]] = str(row[column_name])

                    # if this is a list, recurse to find additional table types.

                    if isinstance(row[column_name], list):
                        execute_dml(ddl, statement_name, row[column_name], table_name + "_" + column_name)
                else:
                    # Just a normal value
                    insert_values[column_def["name"]] = row[column_name]

        hana_execute(sql_stmt, insert_values)

def write_list(list_data, args):
    logger.setLevel(config.log_level)

    ddl = create_ddl(list_data, args)

    execute_ddl(ddl, "drop")
    execute_ddl(ddl, "create")

    execute_dml(ddl, "insert", list_data, args.prefix)
