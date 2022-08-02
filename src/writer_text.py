import logging, re, time, sys, math, os

import constants, session_config
import json_tools as jt

logger = logging.getLogger("write_text")

class FieldFormat:
    #data members of class
    spec = None
    format = None
    width = None
   
    #class default constructor
    def __init__(self,format_spec=None):  
        self.set_spec(format_spec)

    def set_spec(self, format_spec):
        self.spec = format_spec

        if format_spec is None:
            self.format = None
            self.width = None
        else:
            self.format = format_spec[-1]
            self.width = int(format_spec[0:-1])

    def get_width(self):
        return self.width
    
    def get_format(self):
        return self.format
    
    def is_epoch(self):
        return self.get_format() == "e"
    
    def is_gigabyte(self):
        return self.get_format() == "g"
    
    def is_utc(self):
        return self.get_format() == "u"
    
def lookup_value(data, field_def):
    # Get the requested value - invalid lookups always return a None value.
    lookup_value = ""
    
    # Set a default formatting to None
    format = FieldFormat()
    
    # Did we get a field specification from the template that includes a path?
    if isinstance(field_def, dict):  
        if "path" in field_def:
            lookup_value = jt.json_path(data, field_def["path"])
        else:
            # Must include a { "path" : "??" } attribute
            logger.debug("lookup_value: path not found")
            return lookup_value

        # There may be a formatting specification for this field definition.        
        if "format" in field_def:
            format.set_spec(field_def["format"])

    elif isinstance(field_def, str):
        # Specific "path" string not included in a field definition.
        # The caller really should just call json_path.
        lookup_value = jt.json_path(data, field_def)
    else:
        logger.debug(f"lookup_value: path not found: {field_def}")
        return lookup_value

    # We have value (if the value exists), handle type conversion and formatting.
    
    if lookup_value is None:
        lookup_value = ""
        
    # Test for scaler values first...
    if isinstance(lookup_value, str) or isinstance(lookup_value, bool) or isinstance(lookup_value, int):
        if isinstance(lookup_value, bool) or isinstance(lookup_value, int):
            lookup_value = str(lookup_value)
            
        # Handle epoch/unix date formatting.
        if len(lookup_value) > 0 and lookup_value != "" and format.is_epoch():
            lookup_value = time.strftime('%Y-%m-%d', time.gmtime(int(lookup_value[0:10])))

        # Quick and dirty formatting for GB field values.
        if len(lookup_value) > 0 and lookup_value != "" and format.is_gigabyte():
            lookup_value = "{:.2f} GB".format(int(lookup_value) / constants.CONST_GIGABYTE)
    elif isinstance(lookup_value, list):
        # The user passed a list specification, we need to aggregate the values
        # into a single string.
        if "aggregate" not in field_def:
            logger.warning("aggregate specification missing")
        else:
            aggr_value = ""
            comma = ""
            
            for item in lookup_value:
                aggr_value += comma + jt.json_path(item, field_def["aggregate"])
                comma = ", "
            
            lookup_value = aggr_value

    # Force the value to fit in the columns by wrapping the value into multiple line
    # in the width provided.
    
    return_list = []
    
    if format.get_width() is None:
        return_list.append(lookup_value)  # return the value as provided, but in a list
    else:
        width = format.get_width()
        
        if len(lookup_value) <= format.get_width():
            return_list.append((lookup_value + (" " * width))[:width])
        else:
            # Cut the list into chunks - one line per chunk of width
            line_count = math.ceil(len(lookup_value) / width)
            
            for i in range(line_count):
                start_pos = i * width
                
                line_value = lookup_value[start_pos:start_pos + width]
                line_value = (line_value + (" ") * width)[:width]
                
                return_list.append(line_value)

    return return_list

def recurse_format(data, template, output_handle):
    if data is None or not isinstance(data, list):
        logger.warning("recurse_format: invalid data - is None or not a list.")
        return
    
    for item in data:
        # For each item, there will be one or more "rows" attribute
        # containing data and formatting instructions.
        for row in template["rows"]:
            # Locate all the field place holders in the current row
            fields = re.findall("\\{(.*?)\\}", row["layout"]);
            
            # Start the list of values we will put into the place holders.
            values = {}
            formats = {}
            
            # Go get the data for this row/field.
            for field in fields:
                values[field] = lookup_value(item, template["fields"][field])
                formats[field] = FieldFormat(template["fields"][field]["format"])
            
            # Apply the data to the formatting string.  First, ask all the values
            # how many lines they contain (wrapped values).  The output for this
            # total lines of output for this row is driven by how many lines exist
            # across all the values.
            
            max_lines = 0
            for value in values:
                max_lines = max(len(values[value]), max_lines)
            
            # For each line, built the content based on the field values.

            for current_line in range(max_lines):
                output_row = row["layout"] # Start with a fresh layout
                
                for field in fields:  # Place the field values into the format
                    value_lines = values[field]
                    format = formats[field]
                    
                    if len(value_lines) > current_line:
                        # Add the current lines value to the output
                        output_row = output_row.replace("{" + field + "}", value_lines[current_line])
                    else:
                        # Fill line for this value with spaces
                        output_row = output_row.replace("{" + field + "}", " " * format.get_width())
                
                # This line is complete, push it out
                output_handle.write(output_row.rstrip() + "\n")
            
def write_list(list_data, args):
    logger.setLevel(session_config.log_level)

    if args.directory is not None:
        prefix = args.command
        
        if args.prefix is None or len(args.prefix) == 0:
            prefix = args.prefix
            
        filename = os.path.join(args.directory, prefix + ".txt")
        
        output_handle = open(filename, "w")
    else:
        output_handle = sys.stdout
    
    if list_data is None:
        logger.warning(f"write_list_text: {args.command} - empty list")
        return

    if isinstance(list_data, dict):
        # Convert to a list.
        list_data = [ list_data ] # We love lists

    if args.command not in constants.templates:
        logger.error(f"write_list_text: {args.command} template not found.")
        return

    # Get the template based on the name of the command we are
    # running.    
    template = constants.templates[args.command]

    # Loop over each item and build output lines based on the template.
    recurse_format(list_data, template, output_handle)

    # If we are writing to an output file, close the file.    
    if args.directory is not None:
        output_handle.close()

if __name__ == '__main__':
    format = FieldFormat("20s")
    print(1)