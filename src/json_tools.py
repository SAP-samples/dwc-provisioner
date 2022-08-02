import logging, re

logger = logging.getLogger("json_tools")

# JSONPath	       Description
# $	               the root object/element
# @	               the current object/element
# . or []          child operator
# ..               recursive descent. JSONPath borrows this syntax from E4X.
# *                search. All objects/elements regardless their names.
# []               subscript operator. XPath uses it to iterate over element collections and for predicates. In Javascript and JSON it is the native array operator.
# [,]              Union operator in XPath results in a combination of node sets. JSONPath allows alternate names or array indices as a set.
# [start:end:step] array slice operator borrowed from ES4.
# ?()              applies a filter (script) expression.
# ()               script expression, using the underlying script engine.

def json_path(data, field):
    if not isinstance(field, str) or len(field.strip()) == 0:
        logger.error("json_value: invalid JSON spec".format(str(field)))
        return None

    # Always return None if the lookup fails.    
    json_value = None
    
    # We want to be able to subscript the path elements as we loop - split on dot.
    path_specs = field.strip().split(".")  
    
    for path_indx in range(len(path_specs)):
        path_spec = path_specs[path_indx]
        
        if path_spec == "$":
            json_value = data
        elif path_spec.startswith("*"):  # Expecting a dictionary
            # Maybe we have a list of subscripts following the search
            array_spec = re.search(r"\[(.*?)\]", path_spec)  

            # We must be on a dictionary or array.
            if isinstance(json_value, list):
                return json_value
            
            if isinstance(json_value, dict):
                dict_value = []
                
                for key in json_value.keys():
                    dict_value.append({ "key" : key, "value" : json_value[key] })
                    
                return dict_value
        elif path_spec.find("[") != -1 and path_spec.endswith("]"):
            array_spec = re.search(r"\[(.*?)\]", path_spec)
            path_spec = path_spec[0:path_spec.find("[")]

            json_value = json_value[path_spec]  # Pull out the array
            
            if array_spec.group(1) != "*":
                array_index = int(array_spec.group(1))
                
                if len(json_value) == 0 or array_index > len(json_value) - 1:
                    json_value = None
                else:
                    json_value = [ json_value[array_index] ]                
        else:
            if path_spec not in json_value:
                logger.debug(f"json_value: invalid path - {path_spec}")
                json_value = None
                break
            else:
                if json_value is None:
                    logger.debug(f"json_value: invalid path {path_spec}")
                    break
                
                json_value = json_value[path_spec]
    
    return json_value

if __name__ == '__main__':
    test_data = { "simpleField" : "simple fld value", 
                 "subobj" : { "test" : "bob", 
                               "members" : [ "mark", "sally" ] } }
    
    print(json_path(test_data, "$.simpleField"))
    print(json_path(test_data, "$.subobj.members"))
    