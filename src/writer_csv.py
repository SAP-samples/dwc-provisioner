import logging

import session_config

logger = logging.getLogger("writer_csv")

def recurse_columns(columns, list_data, prefix):
    csv_name = prefix.upper()

    # Search through all the rows because some columns are not consistently
    # returned by the URL/REST queries.  Looping over all the rows helps ensure
    # we capture all the possible columns (attributes).
        
    for row in list_data:
        if not isinstance(row, dict):
            continue
        
        row_column_names = row.keys()

        # Lazy instantiation of the column list - we may see
        # not see the same csv content in every pass through
        # list objects.
        
        if csv_name not in columns:
            columns[csv_name] = { "columns": [], "file_handle" : None }

        for column_name in row_column_names:
            if column_name.find("@") != -1:  # Exclude metadata columns.
                continue

            # For each column we add, record the name of the column.
            # DWC queries are sometimes inconsistent about columns and we
            # can use this list to ensure all columns are accounted for
            # across all rows in the CSV file.

            if column_name not in columns[csv_name]["columns"]:
                columns[csv_name]["columns"].append(column_name)

                if isinstance(row[column_name], list):
                    recurse_columns(columns, row[column_name], csv_name + "_" + column_name)

def write_csv(columns, list_data, prefix):
    csv_name = prefix.upper()
    csv_file = csv_name + ".csv"

    if csv_name not in columns:
        logger.warn(f"write_csv passed unexpected CSV object name: {csv_name}")

    if columns[csv_name]["file_handle"] is None:
        # Open the file and output the heading row for this file.

        columns[csv_name]["file_handle"] = open(csv_file, "w")

        heading_line = ""
        comma = ""

        for heading in columns[csv_name]["columns"]:
            heading_line += comma + '"' + heading + '"'
            comma = ","

        columns[csv_name]["file_handle"].write(f"{heading_line}\n")

    for row in list_data:
        output_line = ""
        comma = ""
        
        for column_name in columns[csv_name]["columns"]:
            if column_name in row:
                output_line += comma + str(row[column_name])
                comma = ","
            
        columns[csv_name]["file_handle"].write(f"{output_line}\n")
    
def write_list(list_data, args):
    logger.setLevel(session_config.log_level)

    # Build out the full defintions or all the CSV files we will be
    # creating from this object.  There may be many sub-objects
    # in the JSON - each one gets a separate file.
    columns = {}
    
    recurse_columns(columns, list_data, args.prefix)

    write_csv(columns, list_data, args.prefix)

    # Every sub-list may have generated an open file, close them all.
    
    for csv_name in columns:
        if columns[csv_name]["file_handle"] is not None and columns[csv_name]["file_handle"].closed == False:
            columns[csv_name]["file_handle"].close()