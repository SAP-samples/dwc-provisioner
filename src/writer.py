import logging

import session_config
import writer_hana, writer_csv, writer_text, writer_json

logger = logging.getLogger('writer')
        
def write_list(list_data, args=None):
    logger.setLevel(session_config.log_level)
    
    if list_data is None or len(list_data) == 0:
        logger.error(f'invalid list passed to write_list: target {args.format}.')
        return

    if args.format == "hana":
        writer_hana.write_list(list_data, args)
    elif args.format == "csv":
        writer_csv.write_list(list_data, args)
    elif args.format == "json":
        writer_json.write_list(list_data, args)
    elif args.format == "text":
        writer_text.write_list(list_data, args)
    else:
        logger.warn(f"Unexpected target for output: {format}")
