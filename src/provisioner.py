"""
This is a general purpose script to retrieve information from the DWC instance.  The
major elements of the GUI are available for download:

    users     - retrieve all the users from DWC
    spaces    - retrieve space details from DWC - including data/business builder and data access objects 

There are various options that can be set to control the operation of this script.
"""

import os, sys, logging

import session_config
import cmdparse, connections, spaces, shares, users, utility

from session import DWCSession

logger = logging.getLogger("dwc_tool")

if __name__ == '__main__':
    if sys.version_info<(3,8,0):
        sys.stderr.write("You need python 3.8 or later to run this tool.\n")
        sys.exit(1)

    # Track how long this process runs across all commands.
    utility.start_timer("dwc_tool")
            
    # Capture the command line arguments.
    # Note: The args this script names as the first param - remove it.
    args = cmdparse.parse(sys.argv[1:])  

    # Make sure our configuration is present and valid.    
    session_config.ensure_config(args)

    # For the configuration operation, there's nothing else to do.
    if args.command == "config":
        sys.exit(0)

    # Update our logging level based on the configuration we just loaded.
    logger.setLevel(session_config.log_level)        
    
    # Build the full list of commands, including multiple commands
    # coming from a script.
    
    commands = []  # We love lists to loop over.

    # Check if a script was provided on the command line.  If so, the
    # commands in the script file will be added to the commands to
    # run - in addition to the global parameters.

    if args.command != 'script':
        commands.append(args)
    else:
        if not os.path.exists(args.filename):
            logger.fatal("Script {} not found.".format(args.filename))
            sys.exit(1)

        # Read all the commands from the script - stop if we
        # encounter the "exit" command.  Also, skip any "config"
        # commands.

        with open(args.filename, "r") as script:
            commandScript = script.readlines()
    
        # Append them to the list of commands after parsing their arguments
        for command in commandScript:
            script_args = command.strip()

            # Only process non-blank and non-comment lines in the file.
            if len(script_args) == 0 or script_args[0] == "#":   
                continue
            
            # If we see "exit" we are done with this script.
            if script_args.startswith("exit"):
                break
            
            # Invalid script commands - skip.    
            if script_args.startswith("config"):
                logger.warning("config commands are not permitted in script files - skipped")
                continue
            
            logger.debug("..script cmd: {}".format(script_args))

            # Add this command to the list we will process later.  Go ahead
            # and parse the commands to verify the arguments.
            script_args = script_args.split(" ")
            commands.append(cmdparse.parse(script_args))

    # We are good to go, login to the DWC tenant
    
    session_config.dwc = DWCSession(
        url=session_config.get_config_param("dwc", "dwc_url"), 
        user=session_config.get_config_param("dwc", "dwc_user"), 
        password=session_config.get_config_param("dwc", "dwc_password"))
    
    # Push the logging level into the DWC session.
    session_config.dwc.setLevel(logger.getEffectiveLevel())

    # Start the interaction with DWC by logging in.

    if session_config.dwc.login() == False:
        sys.exit(1)
        
    # Loop over the commands processing each with their own arguments.
    
    for command_args in commands:
        if command_args.command == "spaces":
            spaces.process(command_args)
        elif command_args.command == "connections":
            connections.process(command_args)
        elif command_args.command == "users":
            users.process(command_args)
        elif command_args.command == "shares":
            shares.process(command_args)
        elif command_args.command == "exit":
            break
        
    logger.info(utility.log_timer("dwc_tool", "DWC Operation"))
