import logging, os, copy

import session_config, cmdparse, constants, utility, writer

logger = logging.getLogger("spaces")

def process(space_args):
    """Subprocessor for the "spaces" commands."""

    logger.setLevel(session_config.log_level)

    if space_args.subcommand == "list":
        spaces_list(space_args)
    elif space_args.subcommand == "create":
        spaces_create(space_args)
    elif space_args.subcommand == "delete":
        spaces_delete(space_args)
    elif space_args.subcommand == "bulk":
        process_bulk(space_args)
    elif space_args.subcommand == "member":
        process_members(space_args)

def spaces_create(space_args):
    utility.start_timer("spaces_create")

    # The user could have specified a text name instead of
    # of a space name - fix it to be a functional space name.

    space_id = session_config.dwc.validate_space_id(space_args.spaceID)

    if space_id is None:
        logger.error(f'space_create: a space ID is required')
        return

    space_label = session_config.dwc.validate_space_label(space_id, space_args.business)

    if space_label is None:
        logger.warn(f'Create space {space_args.spaceName} - invalid space label {space_args.label} - defaulting to {space_name}')
        
    # Set defaults for disk and ram.  These can be overridden by
    # a template or by command line values (--disk, --memory).

    assigned_storage = constants.CONST_DEFAULT_SPACE_STORAGE
    assigned_ram = constants.CONST_DEFAULT_SPACE_MEMORY

    # If the user specified the "--force" command line option, this may be overridden
    delete_flag = False

    # Check to see if the space already exists.
    space_def = session_config.dwc.get_space(space_id)

    # Check to see if the space objects (or empty object) has the
    # space_name as a dictionary object - this only valid when
    # a real space is returned.

    if space_def is not None:
        if space_args.force == False:
            logger.warning(f'spaces_create: space {space_args.spaceID} already exists - specify force.')
            return
        else:
            delete_flag = True

    # If a template was specified, make sure it exists.  If there is no template name,
    # compose a minimal space defintion.

    if space_args.template is None:
        new_space_def = {}
        new_space_def[space_id] = copy.deepcopy(constants.default_space_definition)
        
        new_space_def[space_id]["spaceDefinition"]["label"] = space_label
        new_space_def[space_id]["spaceDefinition"]["assignedStorage"] = assigned_storage
        new_space_def[space_id]["spaceDefinition"]["assignedRam"] = assigned_ram

        new_space_def[space_id]["spaceDefinition"]["members"] = []   # We will add members shortly.
    else:
        # Make sure the template space is in the tenant.
        template_space = session_config.dwc.get_space(space_args.template)

        if template_space is None:
            logger.error(f"spaces_create: create space {space_args.spaceID} - template space {space_args.template} - invalid.")
            return

        new_space_def = {}
        new_space_def[space_id] = {}

        # Copy the space definition from the template
        new_space_def[space_id]["spaceDefinition"] = template_space[space_args.template]["spaceDefinition"]
        new_space_def[space_id]["spaceDefinition"]["label"] = space_label
        new_space_def[space_id]["spaceDefinition"]["members"] = []   # We will add members shortly

    # Set values if there are command line arguments for disk and memory. Command line 
    # arguments for disk/memory override default or template values.
    if space_args.disk is not None:
        assigned_storage = int(float(space_args.disk) * constants.CONST_GIGABYTE)
        new_space_def[space_id]["spaceDefinition"]["assignedStorage"] = assigned_storage

    if space_args.memory is not None:
        assigned_ram = int(float(space_args.memory) * constants.CONST_GIGABYTE)
        new_space_def[space_id]["spaceDefinition"]["assignedRam"] = assigned_ram

    # Add members to the space definition.
    users = session_config.dwc.get_users(space_args.users)

    # Let the user know they didn't specify valid users for the space.
    if len(users) == 0:    
        logger.warning(f"spaces_create: create space {space_id} found no matching DWC users.")
        
    # Populate the user list for the new space (if any users were specified).
    for user in users:
        new_space_def[space_id]["spaceDefinition"]["members"].append(
                    { "name" : user["userName"], "type" : "user" } )

    # If we need to force the creation of the space, delete the existing space first.

    if delete_flag:
        logger.info(f"spaces_create: {space_id} forced create - deleting existing space.")

        # Update the arguments with the latest version of the space id - this may
        # have been adjusted during the validation operation.
        space_args.spaceID = space_id
        
        spaces_delete(space_args)

    # The space is ready to be created, call the CLI to do the operation.

    session_config.dwc.put_space(new_space_def)

    logger.info(utility.log_timer("spaces_create", f"spaces_create: {space_id} creation complete"))

def spaces_delete(space_args):
    utility.start_timer("spaces_delete")

    space_list = session_config.dwc.query_spaces(space_args.spaceID, query=False)
    
    if len(space_list) == 0:
        logger.warning("spaces_delete: no spaces found to delete")
        return

    for space in space_list:
        space_id = session_config.dwc.get_space_id(space)
        
        url = session_config.dwc.get_url("space")
        url = url.format(**{ "spaceID" : space_id })
        url += "&connections=true&definitions=true"
        
        session_config.dwc.delete(url)

    space_count = len(space_list)
    logger.debug(utility.log_timer("spaces_delete", f"spaces_delete: {space_count} space(s) deleted"))

def process_bulk(space_args):
    # A file with a list of spaces for the bulk operation is required.

    if not os.path.exists(space_args.filename):
        logger.error(f"spaces_bulk: file not found: {space_args.filename}")
        return

    # Load the file - should be a CSV file

    with open(space_args.filename, "r") as file:
        bulk_text = file.readlines()

    # Remove the header line by clipping starting at the --skip value (default=1).
    bulk_text = bulk_text[int(space_args.skip):]
    
    for text in bulk_text:
        text = text.strip()

        # Skip blank and comment lines - I WANTED THE ABILITY TO COMMENT - so shoot me.
        if len(text) == 0 or text[0] == '#':
            continue

        if space_args.bulk_subcommand == "create":
            spaces_bulk_create(space_args, text)
        elif space_args.bulk_subcommand == "delete":
            spaces_bulk_delete(text)

def spaces_bulk_create(space_args, text):
    # Build the arguments to pass to the spaces_create routine - just like
    # it would appear on a command line.
    
    create_args = [ "spaces", "create" ]

    # Split the row into expected columns.
    text_row = text.split(",")

    space_id = text_row[constants.CONST_SPACE_ID]
    space_business_name = text_row[constants.CONST_BUSINESS]
    space_disk = text_row[constants.CONST_DISK]
    space_memory = text_row[constants.CONST_MEMORY]
    space_template = text_row[constants.CONST_TEMPLATE]
    space_force = text_row[constants.CONST_FORCE]

    # Pass along the force option, if present.
    # Note: command line argument overrides individual spaces in the CSV

    if space_args.force:   # Override from the "spaces bulk create --force" command
        create_args.append("--force")
    else:
        if isinstance(space_force, str) and len(space_force) > 0 and space_force.lower() == 'true':
            create_args.append("--force")
            
    # Pass along the template specified on the command line.
    # Note: command line argument overrides individual templates in the CSV
    
    # Note: we do not validate the specified template Space - that occurs
    # during the create operation.

    if space_template is not None:
        if isinstance(space_template, str) and len(space_template.strip()) > 0:
            # An actual template name was found.
            create_args.append('--template')
            create_args.append(space_template.strip())
        else:
            # We really didn't see a valid template name, check to see if one
            # was passed on the "spaces bulk create --template" command line.
            if space_args.template is not None:
                create_args.append('--template')
                create_args.append(space_args.template)
    else:
        if space_args.template is not None:
            create_args.append('--template')
            create_args.append(space_args.template)

    # Process a label if present in the CSV
    # Note: we do not validate the label name - that occurs during
    #       the create operation.

    if space_business_name is not None and len(space_business_name) > 0:
        create_args.append("--business")
        create_args.append(space_business_name)

    # Note: if disk or memory is not specified for this space
    #       then the values will set to defaults or to the template
    #       values (if specified).

    if space_disk is not None and len(space_disk) > 0:
        create_args.append("--disk")
        create_args.append(space_disk)

    if space_memory is not None and len(space_memory) > 0:
        create_args.append("--memory")
        create_args.append(space_memory)

    # Add the NON-dPTIONAL space id parameter
    create_args.append(space_id)

    # Add in the NON-dPTIONAL list of users
    for user in text_row[constants.CONST_USERS:]:
        if isinstance(user, str) and len(user) > 0:
            create_args.append(user.strip())

    spaces_create(cmdparse.parse(create_args))

def spaces_bulk_delete(text):
    space_args = text.split(",")
    space_id = space_args[0]

    delete_args = [ "spaces", "delete", space_id ]

    spaces_delete(cmdparse.parse(delete_args))

def spaces_list(space_args):
    utility.start_timer("spaces_list")

    # Get the list of all spaces.  This query returns a list of spaces with 
    # only a few attributes per space.
    
    spaces = session_config.dwc.query_spaces(space_args.spaceID, space_args.query)

    # Capture this list of spaces to a file so we can visually review if needed.
    utility.write_json("spaces-list", spaces)  
    
    # Now loop over the spaces list and do additional queries to get all the details for each space.

    space_list = []
    
    for current_space in spaces:
        space_id = current_space["name"]  # This is the technical name for the space.

        logger.debug(f"spaces_list: starting space list for {space_id}")
        
        # Get the space details (including members/dbusers/connections/etc) from DWC.
        # This returns a dict object with the space as the first key.
        space = session_config.dwc.get_space(space_id)

        # Pull out the space details from the query results.
        space_def = space[space_id]["spaceDefinition"]

        # Compose the space row to be written to the output.  This is a combination
        # of all the short space query attributes and the detailed query attributes.
        new_space = copy.deepcopy(current_space)   # Start with a copy of the simple space defintion
        new_space.update(space_def)                # Add the detailed space attributes

        # Add this completed space to the list - we love lists
        space_list.append(new_space)
        
        # Ask for any connections defined for this space.
        new_space["connections"] = session_config.dwc.get_connections(space_id)

        # Create a list object for this space's dbusers containing the list
        # of schema objects available for building views.

        if space_args.extend:
            for object in session_config.dwc.get_dbuser_objects(space_id, new_space["dbusers"]):
                # Add in the hastag username of the user as a distinct field.
                object["dbuser"] = object["id"][:object["id"].find(".")]  
                
                if "dbuser_objects" not in new_space:
                    new_space["dbuser_objects"] = []
                    
                new_space["dbuser_objects"].append(object)
 
        # Ask for additional categories of objects that may be associated with each space.
        # These data are only available for members of the space - we may need to add ourselves.
    
        # Check to see if the current user is a member of this space.  We can't collect
        # info on various object types if we are not a member.

        is_member = session_config.dwc.is_member(space_id)
        remove_member = False
        
        if not is_member:
            if space_args.add:  # Did the user ask to add themselves?
                session_config.add_member(current_space)
                remove_member = True
            
        # Pump out the data builder objects - this returns nothing if we are not a member
        new_space["data_builder"] = session_config.dwc.get_data_builder_objects(space_id)

        # Pump out the remote tables list - this returns nothing if we are not a member
        if space_args.extend:
            new_space["remote_tables"] = session_config.dwc.get_remote_tables(space_id)
        else:
            new_space["remote_tables"] = []

        # Pump out the business builder objects - this returns nothing if we are not a member
        new_space["business_builder"] = session_config.dwc.get_business_builder_objects(space_id)

        # Take ourselves out of the space.
        if remove_member:
            session_config.space_remove_member(current_space)

    if len(space_list) == 0:
        logger.warn("spaces_list: No spaces found.")
    else:
        writer.write_list(space_list, args=space_args)

def process_members(space_args):
    if space_args.member_subcommand == "list":
        members_list(space_args)
    else:
        members_action(space_args)

def members_list(space_args):
    space_list = session_config.dwc.query_spaces(space_args.spaceID, query=space_args.query)

    members_list = []

    for space in space_list:
        space_name = space["name"]

        space = session_config.dwc.get_space(space_name)
        space_def = space[space_name]["spaceDefinition"]

        for member in space_def["members"]:
            user = session_config.dwc.get_users(member["name"], query=False)[0]
            
            members_list.append({ "space_name" : space_name,
                                  "name"       : member["name"], 
                                  "type"       : member["type"],
                                  "email"      : user["parameters"]["EMAIL"]
                                })

    # Set the name for the template used to generate the output
    space_args.command = "members"
    
    writer.write_list(members_list, args=space_args)

def members_action(space_args):
    if not session_config.dwc.is_space(space_args.spaceID,):
        logger.warn("member_action: invalid space name specified")
    else:
        if space_args.member_subcommand == "add":
            session_config.dwc.add_members(space_args.spaceID, space_args.user, space_args.query)
        elif space_args.member_subcommand == "remove":
            session_config.dwc.remove_members(space_args.spaceID, space_args.user, space_args.query)
        else:
            logger.error("members_action: invalid action.")