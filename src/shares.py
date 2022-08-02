import logging

import session_config
import writer

logger = logging.getLogger("shares")

def process(share_args):
    logger.setLevel(session_config.log_level)
    
    """ Sub-processor for the "shares" command. """

    logger.setLevel(session_config.log_level)
    
    if share_args.subcommand == "list":
        shares_list(share_args)
    elif share_args.subcommand == "create":
        shares_create(share_args)
    elif share_args.subcommand == "remove":
        shares_remove(share_args)
    else:
        logger.error(f"process: unexpected subcommand: {share_args.subcommand}")

def shares_list(share_args):
    shares = session_config.dwc.get_shares(share_args.sourceSpace, 
                                           share_args.sourceObject, 
                                           share_args.targetSpace, 
                                           share_args.query)
    
    writer.write_list(shares, share_args)
    
def shares_create(share_args):
    # NOTE: We DO NOT validate the object to share - the share operation reports any errors.

    # Verify the source space exists - the space must exist and not be a wildcard search.
    
    source_space = session_config.dwc.get_space(share_args.sourceSpace)

    if source_space is None:
        logger.error(f"shares_create: source space {share_args.sourceSpace} not found")
        return

    # The user can provide multiple target spaces, build the list.
    target_spaces = session_config.dwc.query_spaces(share_args.targetSpace, query=share_args.query)

    if len(target_spaces) == 0:
        logger.error("shares_create: target space(s) not found")
        return

    session_config.dwc.add_share(share_args.sourceSpace, share_args.sourceObject, target_spaces)

def shares_remove(share_args):
    # TODO - Add the functionality
    x = 1