import json, os, logging

import session_config

logger = logging.getLogger("write_json")

def write_list(object, prefix):
    logger.setLevel(session_config.log_level)
    """
        Write out the provided object to the specified file.
    """

    # Ensure the working directory exists before trying to write
    # this file.

    json_path = os.path.join(Path(__file__).parent.absolute(), "working")

    if not os.path.exists(json_path):
        os.mkdir(json_path)

    json_file = os.path.join(json_path, f"{json_name}.json")

    with open(json_file, "w") as outfile:
        outfile.write(json.dumps(object, indent = 4)) # With pretty print

