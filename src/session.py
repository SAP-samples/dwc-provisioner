from bs4 import BeautifulSoup
from os.path import exists

import requests, urllib, urllib3, subprocess
import logging, time, json, re, copy

import utility

logger = logging.getLogger("session")

class DWCSession:
    # Since we are impersonating a browser we need to identify what kind.
    headers = { 'User-Agent' : 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:63.0) Gecko/20100101 Firefox/63.0' }

    def __init__(self, url, user, password):
        logger.debug("ENTERING: DWCSession (__init__)")

        self.urls = { "authenticate"      : "#dwc_url/dwaas-ui/index.html",
                      "logon"             : "#dwc_url/sap/fpa/services/rest/epm/session?action=logon",
                      "spaces"            : "#dwc_url/dwaas-core/repository/spaces",
                      "spaces_resources"  : "#dwc_url/dwaas-core/resources/spaces",
                      "space"             : "#dwc_url/dwaas-core/api/v1/content?space={spaceID}&spaceDefinition=true",
                      "shares"            : "#dwc_url/dwaas-core/repository/shares",
                      "share_list"        : "#dwc_url/dwaas-core/repository/shares?spaceName={spaceID}&objectNames={objectNames}",
                      "connections"       : "#dwc_url/dwaas-core/repository/remotes?space_ids={spaceGUID}&inSpaceManagement=true&details=",
                      "connection"        : '#dwc_url/dwaas-core/repository/remotes/?space_ids={}&inSpaceManagement=true',
                      "connection_delete" : "#dwc_url/dwaas-core/repository/remotes/{}?space_ids={}",
                      "remotetables"      : "#dwc_url/dwaas-core/monitor/{spaceID}/remoteTables?includeBusinessNames=true",
                      "businessbuilder"   : "#dwc_url/dwaas-core/c4s/internal_services/loadContent",
                      "users"             : "#dwc_url/sap/fpa/services/rest/epm/security/list/users?detail=true&parameter=key_value&includePending=true&forceLicensingCheck=true&tenant={tenant_id}"
                    }

        # To eliminate lots of warning messages, disable the SSL cert validation.
        # This could be eliminated if we updated the cert chain for Python with
        # the SAP trusted authority.

        urllib3.disable_warnings()

        self.j_username = user
        self.j_password = password

        self.dwc_url = url
        self.dwc_user_info = None

        self.spaces_cache = None
        self.users_cache = None

        # Instantiate a "requests" session - no network traffic happens here.
        # The Session object handles the HTTP(s) and cookie processing.

        self.session = requests.Session()
        self.session.headers = self.headers

        logging.basicConfig(format="%(asctime)s %(levelname)s %(name)s %(message)s")
        self.logger = logging.getLogger('dwc-session')

        self.elapsed = 0

    def setLevel(self, level):
        logger.setLevel(level)

    def set_dwc_url(self, dwc_url):
        self.dwc_url = dwc_url

    def get_dwc_url(self):
        return self.dwc_url

    def get_tenant_id(self):
        return self.dwc_user_info["session"]["tenant"][0]["id"]

    def get_url(self, url_name):
        # Get the specified URL from the DWC urls.  Update the tenant prefix
        return self.urls[url_name].replace("#dwc_url", self.dwc_url)

    def login(self):
        t0 = time.perf_counter()

        url = self.get_url('authenticate')
        logger.debug("login url: %s" % url)

        # Logging in to the DWC using SAML is a multi-step process.

        try:
            # Access the login target URL.  We expect this page to
            # send back a redirect to the login page, along with
            # initial session security attributes.
  
            response = self.session.get(url, verify=False)

            # These are standard cookies we need to complete the login.  In the last
            # step of the login process, these cookies are required.
            
            self.session.cookies.set('fragmentAfterLogin', '%23%2Fadministration%26%2Fadm%2Fonpremise', path="/")
            self.session.cookies.set('locationAfterLogin', '%2Fdwaas-ui%2Findex.html', path="/")

            signature_pattern = re.compile(".*signature=(.*?);")
            signature = signature_pattern.match(response.text).group(1)
            self.session.cookies.set('signature', signature, path="/")
    
            # Pull out the URL for the next step from the response.
            
            location_pattern = re.compile(".*location=\"(.*)\"")  # looking for the "location=" string in the response.
            location_url = location_pattern.match(response.text).group(1)
            
            # Ask the new URL for the login page.
            
            response = self.session.get(location_url, verify=False)
            soup = BeautifulSoup(response.text, "html.parser");
            
            redirect_url = location_url[0:location_url.find("/oauth") + 1]
            self.passcode_url = redirect_url + "passcode"

            redirect_url += soup.find("a")['href']
            
            response = self.session.get(redirect_url, verify=False)
            soup = BeautifulSoup(response.text, "html.parser")
            
            # We have landed on the doorstep of the HANA Cloud Services IDP.
            # Take the URL and invoke a post operation to get to the login page.
            
            post_url = response.url
            response = self.session.post(post_url, verify=False)
            soup = BeautifulSoup(response.text, "html.parser")
            
            # We have the login page, compose the logon response.
            
            data = {
                "authenticity_token"        : soup.find(attrs={"name":"authenticity_token"})['value'],
                "idpSSOEndpoint"            : soup.find(attrs={"name":"idpSSOEndpoint"})['value'],
                "j_password"                : self.j_password,
                "j_username"                : self.j_username,
                "method"                    : "GET",
                "mobileSSOToken"            : "",
                "org"                       : "",
                "RelayState"                : soup.find(attrs={"name":"RelayState"})['value'],
                "SAMLRequest"               : soup.find(attrs={"name":"SAMLRequest"})['value'],
                "sourceUrl"                 : "",
                "spId"                      : soup.find(attrs={"name":"spId"})['value'],
                "spName"                    : soup.find(attrs={"name":"spName"})['value'],
                "targetUrl"                 : "",
                "tfaToken"                  : "",
                "xsrfProtection"            : soup.find(attrs={"name":"xsrfProtection"})['value'],
                "utf8"                      : "&#x2713;"
            }
    
            response = self.session.post(post_url, data=data, verify=False)
            soup = BeautifulSoup(response.text, "html.parser")
    
            # We should now be authenticated!!!  Build out the last call to punch in the
            # authentication code.
            
            data = {
                "authenticity_token" : soup.find(attrs={"name":"authenticity_token"})['value'],
                "SAMLResponse"       : soup.find(attrs={"name":"SAMLResponse"})['value'],
                "RelayState"         : soup.find(attrs={"name":"RelayState"})['value'],
                "utf8"               : "&#x2713;"
            }
    
            callback_url = soup.find("form")['action']
    
            response = self.session.post(callback_url, data=data, verify=False)
            soup=BeautifulSoup(response.text, "html.parser")

            self.elapsed = time.perf_counter() - t0

            logger.debug(f"successfully logged in as {self.j_username}")

            # Initialize the user the same way DWC does after getting authenticated.
            # The key here is to get the details about the user AND the DWC tenant.
    
            self.set_user_info()

            return True
        
        except Exception as e:
            logger.error("Authentication failed.")

            return False

    def set_user_info(self):
        # After the logon, DWC always asks for the user info, we are
        # replicating that request.  This request also returns the
        # "id" value of the tenant used in other operations.

        if self.dwc_user_info is None:  # You can't login more than once, cache the info.
            self.dwc_user_info = self.get_json('logon')

    def get_user_info(self):
        self.set_user_info()
        
        return self.dwc_user_info["user"]

    def get_user_name(self, user=None):
        # Get the userName attribute from a user.  If no user
        # is passed, get the logged-in user name.  We are expecting
        # a DWC user object.
        
        lookup_user = user
        
        # If not otherwise reqe
        if user is None:
            lookup_user = self.get_user_info()
            
        if "userName" in lookup_user:
            return lookup_user["userName"]
        
        return None
    
    def get_spaces(self, force=False):
        # Assume this operation does not need to be repeated during this
        # session - cache the first response unless asked to force a reload.

        if force == False and self.spaces_cache is not None:
            return self.spaces_cache

        # Query for a list of all spaces in the tenant.  Note: this
        # operation is valid regardless of whether the current user
        # is a member of any particular space.

        self.spaces_cache = self.get_json('spaces')["results"]
        
        # As a separate query, ask for the utilization of the spaces.
        self.spaces_resources_cache = self.get_json('spaces_resources')
        
        # Enrich the spaces with consumption information
        for space in self.spaces_cache:
            if space["name"] in self.spaces_resources_cache:
                space["resources"] = self.spaces_resources_cache[space["name"]]
            else:
                space["resources"] = None
            
        return self.spaces_cache

    def get_space_guid(self, space_id):
        if space_id is None or not isinstance(space_id, str) or len(space_id) == 0:
            logger.error("get_space_guid: invalid space ID")
            return None
        
        # Search the available spaces by name and, if found return
        # the internal ID of the space.

        spaces = self.get_spaces()

        for space in spaces:
            if space["name"] == space_id:
                return space["id"]

        return None
        
    def query_spaces(self, search_list, query=True, force=False):
        # Locate the spaces identifed in the search list by comparing space
        # names. If "query" is true, use a "contains" test to match space names.

        # Get all the known spaces in the tenant.
        spaces = self.get_spaces(force=force)

        # If no list is provided, return all spaces.
        if search_list is None:
            return spaces

        # Zero length list is the same as None
        if isinstance(search_list, list) and len(search_list) == 0:
            return spaces

        # Loop over the elements in the spaces to find matching names.

        return_list = []

        # We want to work with a search list - if only one string name was
        # passed, convert it into a list.

        if isinstance(search_list, str):
            search_list = [ search_list ]

        for search_space_name in search_list:
            matched = False

            for space in spaces:
                if query:
                    if space["name"].upper().find(search_space_name.upper()) != -1:
                        return_list.append(space)
                        matched = True
                else:
                    if space["name"] == search_space_name:
                        return_list.append(space)
                        matched = True
                        
                        break  # This specific space has been included, we are done looking

        return return_list

    def fix_space_name(self, space_name):
        return space_name.upper()

    def is_space(self, space_id, query=False):
        space_list = self.query_spaces(space_id, query=False)
        
        if len(space_list) == 0:
            return False
        else:
            return True
        
    def get_space(self, space_name, query=False):
        fixed_space_name = self.fix_space_name(space_name)

        # Lookup the SPACE name to ensure it exists before looking up the details.
        
        space_list = self.query_spaces(space_name, query)
        
        if len(space_list) == 1:
            # Always ask the tenant for a new version of the space.
            space = self.get_json("space", { "spaceID" : fixed_space_name })
        else:
            space = None

        return space

    def get_shares(self, space=None, object_name=None, target=None, query=False):
        shares_list = []
        
        # Figure out which spaces we are looking in - if nothing was passed
        # we will look in all spaces.
        
        spaces = self.query_spaces(space, query=query)
        
        if len(spaces) == 0:
            logger.warn("get_shares: No matching spaces found.")
            return shares_list
        
        # If an object_name was passed (even if search), look for those
        # matching objects across the spaces we are searching (or all).
        
        for space in spaces:
            # Get the list of shared objects for this space.
            objects = self.get_data_builder_objects(space, shared_only=True)
            
            # Skip spaces without any data builder objects that have been shared.
            if len(objects) == 0:
                continue
        
            # Compose the comma separated list of object names having shares
            
            search_objects = ""
            comma = ""
            
            for object in objects:
                search_objects += comma + object["name"]
                comma = ","
                    
            if len(search_objects) == 0:
                continue
            
            # Ask for the all the shares for this space.
            shares = self.get_json("share_list", values={ "spaceID" : space["name"], "objectNames" : search_objects })
            
            # We should get back a dictionary of objects with each object listing
            # their shares.  Loop over to see if we are only looking for a specific
            # space.
            
            for object_name in shares:
                for share in shares[object_name]:
                    share_item = { "spaceName" : space["name"],
                                   "objectName" : object_name,
                                   "targetSpace" : share["name"]
                                 }
            
                    shares_list.append(share_item)
        
        return shares_list
            
    def add_share(self, space_name, object_name, targets):
        # A single share call to DWC can share the same object to many
        # spaces.  Start with an empty list.
        
        data = { "spaceName"         : space_name,
                 "objectNames"       : [ object_name ],
                 "shareSpaceNames"   : [],
                 "unshareSpaceNames" : []
               }

        # If we got a simple string, it must be a specific target
        # space name.

        if isinstance(targets, str):
            data["shareSpaceNames"].append(targets)
        else:
            # We also, could get a list.  This could be a list
            # of target names or a list of space definitions.

            for target in targets:
                if isinstance(target, str):
                    data["shareSpaceNames"].append(target)
                elif isinstance(target, dict) and "name" in target:
                    data["shareSpaceNames"].append(target["name"])
                else:
                    logger.warn("add_share: target {} not valid".format(str(target)))
        
        if len(data["shareSpaceNames"]) > 0:
            self.post(self.get_url("shares"), json.dumps(data))
        else:
            logger.warn("add_share: no valid targets specified.")

    def get_connections(self, space, connection_name=None):
        # The caller could pass 1) a space definition, 2) a space name,
        # or 3) a space ID - figure it out.  If the space name is
        # empty, do nothing.

        if space is None:
            return []

        if isinstance(space, str):
            # If we received a string, assume it's a name and look up the ID.  If the
            # name doesn't resolve, assume it is an ID.

            space_guid = self.get_space_guid(space)

            if space_guid is None:
                space_guid = space
        elif isinstance(space, dict):
            # Do a quick sanity check - if there is no "id" column then
            # this is not a valid space object.

            if "id" in space:
                space_guid = space["id"]
            else:
                return []

        # By now, we should have a value representing a space ID - the space may
        # not exist, but we have a value.

        # Get the connections, the connections query is guarenteed to return a
        # "results" object - even if there are no connections in the space.

        connections = self.get_json("connections", { "spaceGUID" : space_guid})["results"]

        if connection_name is None:
            # If we didn't get a specific name to find, return all the connections.
            return connections
        else:
            # Look for a matching connection name.

            results = []

            for connection in connections:
                if connection["name"] == connection_name:
                    results.append(connection)

            return results

        return []

    def connection_add(self, space, conn_file, force=False):
        space_guid = self.get_space_guid(space)

        if space_guid is None:
            logger.error("add_connection: space not found")
            return None

        # Compute the URL for the POST command to add a connection.
        space_url = self.get_url("connection").format(space_guid)

        # Load the specified JSON file of the connection - this must be a valid
        # JSON that includes the username and password values of the connection.

        try:
            with open(conn_file, "r") as json_file:
                conn_json = json.load(json_file)
        except IOError:
            logger.error(f"add_connection: space {space_guid} - file {conn_file} not found.")
            return None

        # Do a quick sanity check on the JSON we just loaded from a file to 
        # ensure it looks like a connection.

        if "data" not in conn_json or "name" not in conn_json["data"]:
            logger.error(f"add_connection: file is not a valid connection")
            return None

        conn_name = conn_json["data"]["name"]

        # Check to see if the connection already exists in the space.

        connection = self.get_connections(space_guid, conn_name)

        if len(connection) == 1:
            if force:
                # The user asked us to delete any existing connection before
                # re-creating the same name - delete the connection.

                self.delete_connection(space_guid, conn_name)
            else:
                # Let the user know the connection already exists.

                logger.warning("add_connection: connection already exists")
                return None

        # Create the connection with a POST operation
        return self.post(space_url, json.dumps(conn_json))

    def connection_delete(self, space_name, conn_name):
        space_id = self.get_space_guid(space_name)

        if space_id is None:
            logger.error(f"delete_connection: space {space_name} not found.")
            return None

        # Check to see if the connection already exists in the space.

        connection = self.get_connections(space_name, conn_name)

        if connection is None:
            logger.warning(f"delete_connection: space {space_name} - connection {conn_name} not found.")
            return None

        connection_id = connection[0]["id"]

        # Compute the URL for the POST command needed to delete a connection.
        space_url = self.get_url("connection_delete").format(connection_id, space_id)

        # Delete the connection with a DELETE operation.
        return self.delete(space_url)

    def is_dwc_user(self, user):
        # Test is the passed user exists in the DWC tenant list of users.
        user = self.get_users(user, query=False)
        
        if len(user) == 1:
            return True
        
        return False
    
    def get_users(self, users_query=None, force=False, query=True):
        '''
        Get the list of user from the tenant as a deep copy.  For repeat calls,
        always start with a cached user list.  Users are considered non-mutable
        for a single session so doing the same call mulitple times is a performance
        bottleneck.
        '''

        if self.users_cache is None or force == True:
            self.users_cache = self.get_json("users", { "tenant_id" : self.get_tenant_id() })

        # Do we have any users in the tenant?  This is never true, but check anyway.
        if len(self.users_cache) == 0:
            return []

        # If no search list was given, return the entire list.

        if users_query is None:
            return copy.deepcopy(self.users_cache)  # Return a mutable list

        # We could get a few different requests:
        # 1. A single string of a username
        # 2. A full user object from previous query
        # 3. A space user object with only "name" and "type" attributes
        # 4. A list of any of the above.
        
        # If we find that we have a dictionary object that looks like a
        # DWC user, simply return the user back as the found user.
        
        if isinstance(users_query, dict) and "userName" in users_query:
            return [ users_query ]  # we don't need to search anything
        
        # We want to search a list of users, convert a simple string into a list

        if isinstance(users_query, str):
            # add the string to the search list - note: we need to get the full user object
            users_query = [ users_query ]

        # If we got a space user object, add the name - note: we need to get the full user object
        if isinstance(users_query, dict) and "name" in users_query and "type" in users_query:
            users_query = [ users_query["name"] ]
            
        # Make sure we have a list with at least one member.

        if not isinstance(users_query, list):
            logger.warning("get_users: invalid users parameter is not a valid list")
            return []

        if len(users_query) == 0:
            return copy.deepcopy(self.users_cache)

        # Setup the mutable return list.

        return_users = []

        for pattern in users_query:
            # If we are boiling down a list of users, pull the
            # username out of the pattern object.
            
            if isinstance(pattern, dict):
                pattern = pattern["userName"]
                
            for user in self.users_cache:
                if query:
                    # For a query search, convert the entire user JSON to a string and
                    # search for any instance of the query pattern.
                    
                    if str(user).upper().find(pattern.upper()) != -1:
                        return_users.append(copy.deepcopy(user))
                else:
                    if user["userName"].upper() == pattern.upper() or user["parameters"]["EMAIL"].upper() == pattern.upper():
                        return_users.append(copy.deepcopy(user))
                        break  # Non-search pattern has been matched, stop looking

        return return_users

    def get_space_id(self, space):
        space_id = None
        
        if isinstance(space, dict):
            # If the name attribute is a direct value of this dictionary,
            # assume this is space from the short space query.
            
            if "name" in space:
                space_id = space["name"]
            else:
                # Assume this is a space object where the name is
                # the FIRST dictionary key.  In this type of object
                # there must be a spaceDefinition object.
                
                space_id = next(iter(space))

                if "spaceDefinition" not in space[space_id]:
                    logger.warn("get_space_name: invalid space object.")
        elif isinstance(space, str):
            # With no other information, simply return the passed name.
            space_name = space

        return space_id

    def get_dbuser_objects(self, space_name, dbuser_hashtags):
        # This routine never produces an error - invalid, or no hashtag keys returns an empty list.
        if dbuser_hashtags is None or len(dbuser_hashtags) == 0:
            return []

        # If we only have one hashtag user, turn it into a list.        
        if isinstance(dbuser_hashtags, str):
            dbuser_hashtags = [ dbuser_hashtags ]

        # See if the user passed a valid space name.
        space_name = self.get_space_id(space_name)

        if space_name is None:
            return []

        # Build the query string to send to DWC - we can lookup as many
        # hashtags as we want in a single query.  This loop looks at
        # just the keys (#tag users) from the dictionary.
        search_path = []
        for dbuser_hashtag in dbuser_hashtags:
            search_path.append({ "id" : dbuser_hashtag, "type" : "schema"})

        # Encode the search string for the URL.                               
        dbuser_path = urllib.parse.quote(str(search_path).replace("'", '"'))
        
        # build the final URL to send to DWC
        dbuser_query = f'#dwc_url/dwaas-core/datasources/getchildren?path={dbuser_path}&space={space_name}'

        # To simplify the get operation, simply punch this URL into the standard list.
        self.urls["dbuser_objects"] = dbuser_query

        objects = self.get_json("dbuser_objects")
        
        if "items" in objects:  # Results are in a sub-object named items
            return objects["items"]
        else:
            return []

    def get_data_builder_objects(self, space, shared_only=False):
        space_id = self.get_space_id(space)

        # Pick the types of objects to include...
        objects_query = '('
        objects_query += 'technical_type:EQ:"DWC_REMOTE_TABLE"'
        objects_query += ' OR technical_type:EQ:"DWC_LOCAL_TABLE"'
        objects_query += ' OR technical_type:EQ:"DWC_VIEW"'
        objects_query += ' OR technical_type:EQ:"DWC_ERMODEL"'
        objects_query += ' OR technical_type:EQ:"DWC_DATAFLOW"'
        objects_query += ' OR technical_type:EQ:"DWC_IDT"'
        objects_query += ' OR kind:EQ:"sap.dis.dataflow"'
        objects_query += ' OR kind:EQ:"sap.dwc.dac"'
        objects_query += ' OR kind:EQ:"sap.dwc.taskChain"'
        objects_query += ')'

        # If asked, make sure to only return objects that have been shared
        if shared_only:
            objects_query += ' AND shared_with_space_name:NE(S):"NULL"'

        # If we have a space_id, add it to the query.            
        if space_id is not None:
            objects_query += f' AND space_name:EQ:"{space_id}"'

        # Complete the query specification by wrapping in a SCOPE   
        objects_query = f"query='SCOPE:SEARCH_DESIGN ({objects_query}) *'"
        
        # URL encode just the objects query piece
        objects_query = urllib.parse.quote(objects_query)
        
        # Build the full search object
        objects_query = f"Search.search({objects_query})"

        CONST_DOLLAR = '%24'

        db_objects_query = CONST_DOLLAR + 'top=99999'
        db_objects_query += '&'
        db_objects_query += CONST_DOLLAR + 'skip=0'
        db_objects_query += '&'
        db_objects_query += CONST_DOLLAR + f"apply=filter({objects_query})"
        db_objects_query += '&'
        db_objects_query += CONST_DOLLAR + 'count=true'

        db_objects_query =  self.get_dwc_url() + "/dwaas-core/repository/search/$all?" + db_objects_query

        # Park the just constructed URL in the list of the session.  This makes
        # calling and getting JSON a standard operation.
        
        self.urls["builder_objects"] = db_objects_query

        # Go get the objects
        builder_objects = self.get_json("builder_objects")
        
        return builder_objects["value"]   # Return the list of objects.

    def get_business_builder_objects(self, space_name):
        business_builder_query = {
            "SpaceID": space_name,
            "Sort": { "Column": "Title", "isDescending": False },
            "HideEmptyPackages": False,
            "PackageSelectionAllowed": True,
            "currentPackage": -1,
            "filterData": [],
            "searchData": [],
            "typeOrder": [
                { "EntityType": "CubeSource",             "index": 0 },
                { "EntityType": "ResponsibilityScenario", "index": 1 },
                { "EntityType": "Business Semantic",      "index": 2 },
                { "EntityType": "MasterDataSource",       "index": 3 },
                { "EntityType": "KPI Model",              "index": 4 },
                { "EntityType": "Package",                "index": 5 },
                { "EntityType": "Perspective",            "index": 6 }
            ]
        }

        response = self.post(self.get_url("businessbuilder"), json.dumps(business_builder_query))
        
        try:
            results = json.loads(response.text)

            if "Content" in results:
                results = results["Content"]
            else:
                return []        
        except:
            logger.error("error parsing JSON")
            results = []
            
            pass
                
        return results

    def get_remote_tables(self, space_name):
        results = self.get_json("remotetables", { "space_name" : space_name })

        if results is not None and "tables" in results:
            remote_tables = results["tables"]
        else:
            remote_tables = []

        return remote_tables

    def is_member(self, space_object, user=None):
        # If not specified, assume we want to know if the current user is a
        # member of the space.
        if user is None:
            user = self.get_user_name()
            
        # Validate the user first to make sure we are looking for a real user.
        if not self.is_dwc_user(user):
            logger.debug("is_member: a valid user was not specified.")
            return False

        # Now validate the space exists.
        if space_object is None:
            logger.debug("is_member: a space_name was not specified.")
            return False

        # Assume we got a dictionary
        space = space_object   
        space_id = None
        
        # We could receive a space id or an actual space definition.  If we
        # get a dictionary, assume the first key is the name of the space.
        
        if isinstance(space_object, dict):
            space_id = next(iter(space_object))
        elif isinstance(space_object, str) and len(space_object) > 0:
            space_id = space_object
            space = self.get_space(space_id)
        
        # Test the object to ensure it is a DWC space definition.
        if space_id is None or space_id not in space or "spaceDefinition" not in space[space_id]:
            logger.warn("is_member: invalid space dictionary.")
            return False
        
        # There may be no members, otherwise search for our user name.
        if "members" in space[space_id]["spaceDefinition"]:
            for member in space[space_id]["spaceDefinition"]["members"]:
                if member["name"] == self.get_user_name(user):  # Are we a member of the space?
                    return True

        return False
        
    def add_members(self, space, users, query=False):
        t0 = time.perf_counter()

        # If we got a string for the space ID, find the space object
        if isinstance(space, str):
            space = self.get_space(space)
            
        # The space must be an actual space object with the expected structure
        if space is None or not isinstance(space, dict):
            logger.error("add_member: invalid space object - not a dictionary")
        else:
            # The first key must be the name of the space.
            space_id = self.get_space_id(space)

            # Check the space object properties.        
            if space_id is None or "spaceDefinition" not in space[space_id]:
                logger.error("add_member: invalid space object")        
            else:
                # Now figure out who's being added - could be many users
                user_list = self.get_users(users, query=query)
                
                if len(user_list) == 0:
                    logger.warning("add_members: invalid list of users")
                else:
                    added_user = False
                    
                    for user in user_list:
                        # If the user is already a member, no action necessary.
                        if not self.is_member(space, user):
                            space[space_id]["spaceDefinition"]["members"].append({ 'name' : user["userName"], 'type' : 'user' })
                            added_user = True
                    
                    if added_user:
                        self.put_space(space)
        
    def remove_members(self, space, users, query=False):
        t0 = time.perf_counter()

        # If we got a name, find the space object
        if isinstance(space, str):
            space = self.get_space(space)
            
        # The space must be an actual space object with the expected structure
        if space is None or not isinstance(space, dict):
            logger.error("remove_member: invalid space object")
            return
        
        # The first key must be the name of the space.
        space_name = self.get_space_name(space)

        # Check the space object properties.        
        if space_name is None or "spaceDefinition" not in space[space_name]:
            logger.error("remove_member: invalid space object")        
            return
        
        # Now figure out who's being added - could be many users
        user_list = self.get_users(users, query=query)
        
        if len(user_list) == 0:
            logger.warning("remove_members: invalid list of users")
            return
        
        removed_user = False
        remaining_member_list = []
        
        # Loop over the space members and exclude any that match
        # our list of users to remove.
        for space_user in space[space_name]["spaceDefinition"]["members"]:
            skip_user = False
            
            for user in user_list:
                if space_user["name"] == user["userName"]:
                    skip_user = True
                    break  # Stop checking this space user
                
            if skip_user:
                removed_user = True
            else:
                # Add this space user into the new list of users because
                # it didn't match the remove list.
                remaining_member_list.append({ 'name' : space_user["name"], 'type' : space_user["type"] })
        
        if removed_user:
            space[space_name]["spaceDefinition"]["members"] = remaining_member_list
            self.put_space(space)

    def put_space(self, space):
        # We are expecting a space object, do a quick sanity check.
        space_id = self.get_space_id(space)
        
        if space_id is None or "spaceDefinition" not in space[space_id]:
            logger.error("put_space: invalid space passed")
            return
        
        url = self.get_url("space")
        url = url.format(**{ "spaceID" : space_id })

        self.put(url, json.dumps(space, separators=(',', ':')))

    def spaces_delete_cli(self, space_id):
        utility.start_timer("spaces_delete_cli")

        process_output = subprocess.run([ '/opt/homebrew/bin/dwc',
                                          'spaces',
                                          'delete',
                                          '-F',
                                          '-H', self.get_dwc_url(),
                                          '-s', space_id, 
                                          '-p', self.get_passcode()
                                        ],
                                        capture_output=True)
        
        logger.info(utility.log_timer("spaces_delete_cli", "space_id {} deleted.".format(space_id)))

        if process_output.returncode != 0:
            logger.error("Invalid CLI result: {}".format(process_output.stdout))
        
    def spaces_create_cli(self, operation, json):
        t0 = time.perf_counter()

        json_obj = None

        if json is None:
            logger.error("CLI {}: A JSON object must be provided.".format(operation))
            return
        elif isinstance(json, str):
            # The string could be either a filename or a string of JSON.  First test to
            # see if it is a filename, otherwise assume it is a JSON string.  If neither
            # is valid, log an error and exit.

            if exists(json):
                json_file = json
            else:
                # Attempt to parse the string into JSON.
                try:
                    json_obj = json.loads(json)
                except Exception as e:
                    logger.error("Invalid JSON string passed to spaces_cli.")
                    return
        else:
            json_obj = json

        if json_obj is not None:
            # Quick sanity check on the json object
            space_name = next(iter(json_obj))  # get first dictionary key - should be the space name

            if "spaceDefinition" not in json_obj[space_name]:
                logger.error("Invalid JSON object passed to spaces_cli")
                return

            json_file = utility.write_json(space_name, json_obj)
            dwc_url = self.get_dwc_url()
            passcode = self.get_passcode()

            process_output = subprocess.run([ '/opt/homebrew/bin/dwc',
                                              'spaces',
                                              'create',
                                              '-H', dwc_url,
                                              '-f', json_file, 
                                              '-p', passcode
                                            ],
                                            capture_output=True)
        
        elapsed = time.perf_counter() - t0
        logger.debug("call_space_cli: operation {} - file {} - elapsed {}.".format(operation, json_file, elapsed))

        if process_output.returncode != 0:
            logger.error("Invalid CLI result: {}".format(process_output.stdout))
            logger.error(process_output.stdout)

    def validate_space_id(self, space_id):
        """ The space ID can only contain uppercase letters, numbers, and underscores (_). Reserved keywords, 
            such as SYS, CREATE, or SYSTEM, must not be used. Unless advised to do so, the ID must not contain 
            prefix _SYS and should not contain prefixes: DWC_, SAP_. The maximum length is 20 characters.

            Reserved keywords: SYS, PUBLIC, CREATE, SYSTEM, DBADMIN, PAL_STEM_TFIDF, SAP_PA_APL, DWC_USER_OWNER,
            DWC_TENANT_OWNER, DWC_AUDIT_READER, DWC_GLOBAL, and DWC_GLOBAL_LOG.

            Also, the keywords that are reserved for the SAP HANA database cannot be used in a space ID. See 
            Reserved Words in the SAP HANA SQL Reference Guide for SAP HANA Platform."""

        prefixes = [ '_SYS', 'DWC_', 'SAP_' ]
        
        reserved = [ "SYS", "PUBLIC", "CREATE", "SYSTEM", "DBADMIN", "PAL_STEM_TFIDF", "SAP_PA_APL", "DWC_USER_OWNER",
                     "DWC_TENANT_OWNER", "DWC_AUDIT_READER", "DWC_GLOBAL", "DWC_GLOBAL_LOG" ]

        if space_id is None:
            return None

        # Do some initial clean-up
        # 1. Spaces -> underscore
        # 2. Remove invalid characters - simply chop them out with a regular expression
        # 3. Test for reserved characters

        valid_space_id = space_id.replace(" ", "_").upper()
        valid_space_id = re.sub("[\W]","", valid_space_id)

        if len(valid_space_id) == 0 or len(valid_space_id) > 20:
            logger.error(f"validate_space_id: {space_id} is invalid and can't be fixed.")
            return None
        
        if len(valid_space_id) > 3 and valid_space_id[0:4] in prefixes:
            logger.error(f"validate_space_id: {space_id} may not start with _SYS, DWC_, or SAP_")
            return None

        if space_id in reserved:
            logger.error(f"validate_space_id: {space_id} is a reserved word.")
            return None

        return valid_space_id

    def validate_space_label(self, space_name, space_label):
        if space_label is None:
            return space_name

        if not isinstance(space_label, str):
            logger.warn("validate_space_label: space labels must be a string value - default to {}.".format(space_name))
            return space_name

        if len(space_label) > 30:
            space_label = space_label[0:30]
            logger.warn("validate_space_label: label too long - truncated to {}.")

        return space_label
            
    def set_header(self, header, value):
        self.session.headers[header] = value
    
    def get_header(self, header):
        if header in self.session.headers:
            return self.session.headers[header]
            
        return None
    
    def clear_cookie(self, domain, path, name):
        self.session.cookies.clear(domain, path, name)

    def remove_header(self, header):
        self.session.headers.pop(header)

    def write_space_json(self, space):
        # Do a quick sanity check by pulling out the space id and then
        # verify the spaceDefinition object is present.

        if space is None or not isinstance(space, dict):
            logger.error("write_space_json: did not receive a dict object.")
            return

        space_id = next(iter(space))  # Get the first attribute - should be the space_id

        if "spaceDefinition" not in space[space_id]:
            logger.error("write_space_json: invalid JSON passed - spaceDefinition attribute missing.")
            return
            
        utility.write_json(space_id, space)

    def get_json(self, url_name, values={}):
        t0 = time.perf_counter()

        # Compose the URL - this includes formatting values into the URL template.
        url = self.get_url(url_name).format(**values)
        
        # Send the URL to DWC via a GET operation.
        response = self.session.get(url, verify=False)

        if response.status_code >= 400:
            logger.error("url_name: {} - error: {} - message: {}".format(url_name, response.status_code, response.text))
            results = []
        else:
            results = json.loads(response.text)

        # Measure and report on the performance of this GET operation.
        self.elapsed = time.perf_counter() - t0

        if "code" in results is not None:
            logger.warning("url_name: {} - error: {} - message: {}".format(url_name, results["code"], results["details"]["message"]))
            return None

        return results

    def post(self, url, data=None):
        t0 = time.perf_counter()

        self.set_header("Content-Type", "application/json")

        if data == None:
            response = self.session.post(url, verify=False)
        else: 
            response = self.session.post(url, data, verify=False)

        self.elapsed = time.perf_counter() - t0

        if response.status_code >= 400:
            logger.warning("post to {} - error {}.".format(url, response.status_code))
            return None

        return response

    def delete(self, url):
        t0 = time.perf_counter()

        response = self.session.delete(url, verify=False)

        self.elapsed = time.perf_counter() - t0

        if response.status_code >= 400:
            logger.warning("delete to {} - error {}.".format(url, response.status_code))

        self.elapsed = time.perf_counter() - t0

        return response

    def put(self, url, data):
        t0 = time.perf_counter()

        put_headers = copy.deepcopy(self.session.headers)
        put_headers["Content-Type"] = "application/json"
        
        response = self.session.put(url, data, verify=False, headers=put_headers)

        self.elapsed = time.perf_counter() - t0

        return response

    def get_passcode(self):
        response = self.session.get(self.passcode_url)
        soup=BeautifulSoup(response.text, "html.parser")

        passcode = soup.find("h2").contents[0].contents[0]

        return passcode

    def getwithdata(self, url, data):
        t0 = time.perf_counter()

        self.response = self.session.get(url, data=data, verify=False)

        self.elapsed = time.perf_counter() - t0

        return self.response

    def getelapsed(self):
        return self.elapsed
