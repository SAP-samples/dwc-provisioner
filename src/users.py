import logging

import session_config, utility, writer

logger = logging.getLogger("spaces")

def process(user_args):
    logger.setLevel(session_config.log_level)

    # For now, we only implement the list command.
    if user_args.subcommand == "list":
        users_list(user_args)
    # elif "create"
    # elif "delete"

def users_list(user_args):
    utility.start_timer("users_list")

    # Target list of users that will be formatted and/or output.
    user_list = []  # We love lists.
    
    for user in session_config.dwc.get_users(user_args.users, user_args.query):
        # Do some fixup to streamline the user information by pulling some
        # specific attributes up from subobjects.

        utility.copy_scaler_attributes(source=user["parameters"], target=user)
        utility.copy_scaler_attributes(source=user["metadata"], target=user)

        # ETL note:
        # It is possible for a user to have no roles.  If roles are present, pivot
        # the string into a list of roles to support parent/child reporting.
        
        if "roles" in user and len(user["roles"].strip()) > 0:
            # This is a multi-value string field separated by semi-colons
            
            roles = user["roles"].split(";")
            
            # Add the list as a new list to the current user.
            user["roles_list"] = []  

            for role in roles:
                user["roles_list"].append({
                    "userName" : user["userName"],
                    "roleName" : role
                })

        # Add to the list of user we will be writing.
        user_list.append(user)

    # The ETL is complete and we have the users and their roles, output the list.

    writer.write_list(user_list, args=user_args)
    
    logger.debug(utility.log_timer("users_list", "Command: users list"))
