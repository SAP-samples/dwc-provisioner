CONST_GIGABYTE = 1000000000
CONST_DEFAULT_SPACE_STORAGE = 1 * CONST_GIGABYTE
CONST_DEFAULT_SPACE_MEMORY = int(.5 * CONST_GIGABYTE)

CONST_SPACE_ID = 0
CONST_BUSINESS = 1
CONST_DISK = 2
CONST_MEMORY = 3
CONST_TEMPLATE = 4
CONST_FORCE = 5
CONST_USERS = 6

user_action = """[
  {
    "userName": "#UNAME",
    "operator": "#ACTION",
    "parameters": [
      { "name": "FIRST_NAME",    "value": "#FIRST" },
      { "name": "LAST_NAME",     "value": "#LAST" },
      { "name": "DISPLAY_NAME",  "value": "#DISPLAY" },
      { "name": "EMAIL",         "value": "#EMAIL" },
      { "name": "MANAGER",       "value": "#MANAGER" },
      { "name": "IS_CONCURRENT", "value": "0" }
    ],
    "metadata": {
      "samlUserMapping": [
        {
          "userName": "#UNAME",
          "provider": "ORCAHANAGWIDP",
          "samlUserName": "#EMAIL"
        }
      ],
      "isSamlEnabled": true
    },
    "roles": "PROFILE:sap.epm:Application_Creator;PROFILE:sap.epm:BI_Admin;PROFILE:sap.epm:BI_Content_Creator",
    "setUserConcurrent": false
  }
]"""

default_space_definition = {
    "spaceDefinition": {
        "version": "1.0.4",
        "label": "",
        "assignedStorage": 1000000000,
        "assignedRam": 500000000,
        "priority": 5,
        "auditing": {
            "dppRead": {
                "retentionPeriod": 7,
                "isAuditPolicyActive": False
            },
            "dppChange": {
                "retentionPeriod": 7,
                "isAuditPolicyActive": False
            }
        },
        "allowConsumption": False,
        "enableDataLake": False,
        "members": [],
        "dbusers": {},
        "hdicontainers": {},
        "workloadClass": {
            "totalStatementMemoryLimit": {
                "value": None,
                "unit": "Gigabyte"
            },
            "totalStatementThreadLimit": {
                "value": None,
                "unit": "Counter"
            }
        },
        "workloadType": "default"
    }
}

# s = string
# e = epoch date
# g = gigabyte (=#/1GB)
#       { "type" : "row", "path" : "roles_list", "layout" : "  Role: {role_name}\n" }

templates = {
  "users" : {
    "fields" : {
      "user_name"         : { "path" : "$.userName",               "format" : "25s", "heading" : "User" },
      "user_email"        : { "path" : "$.EMAIL",                  "format" : "35s", "heading" : "Email" },
      "user_lastLogin"    : { "path" : "$.LAST_LOGIN_DATE",        "format" : "10e", "heading" : "Last Login" },
      "user_days_visited" : { "path" : "$.NUMBER_OF_DAYS_VISITED", "format" : "10s", "heading" : "Days Visited" },
      "role_name"         : { "path" : "$.roleName",               "format" : "30s", "heading" : "Role" }
    },
    "rows" : [
      { "type" : "row", "layout" : "{user_name} {user_email} {user_lastLogin} {user_days_visited}" }
    ]
  },
  "spaces" : {
    "fields" : {
      "space_name"            : { "path" : "$.name",                      "format" : "30s" },
      "space_memory_assigned" : { "path" : "$.resources.memory.assigned", "format" : "10g"  },
      "space_memory_used"     : { "path" : "$.resources.memory.used",     "format" : "10g"  },
      "enabledDataLake"       : { "path" : "$.enableDataLake",            "format" : "10s" },
      "space_members"         : { "path" : "$.members[*]",                "format" : "30s", "aggregate" : "$.name" },
      "space_dbusers"         : { "path" : "$.dbusers.*",                 "format" : "30s", "aggregate" : "$.key" },
      "member_name"           : { "path" : "$.name",                      "format" : "30s" }
    },
    "rows" : [
      { "type" : "row", "layout" : "{space_name} {space_memory_assigned} {space_memory_used} {enabledDataLake} {space_dbusers}" },
      { "type" : "row", "path" : "$.members", "layout" : "  Member(s): {space_members}" }
    ]
    },
    "shares" : {
      "fields" : {
        "space_name"   : { "path" : "$.spaceName",   "format" : "30s" },
        "object_name"  : { "path" : "$.objectName",  "format" : "30s" },
        "target_space" : { "path" : "$.targetSpace", "format" : "30s" }
      },
      "rows" : [
        { "type" : "row", "layout" : "{space_name} {object_name} {target_space}" },
      ]
    },
    "members" : {
      "fields" : {
        "space_name" : { "path" : "$.space_name", "format" : "30s" },
        "user_name"  : { "path" : "$.name",       "format" : "30s" },
        "user_type"  : { "path" : "$.type",       "format" : "10s" },
        "user_email" : { "path" : "$.email",      "format" : "30s" }
      },
      "rows" : [
        { "type" : "row", "layout" : "{space_name} {user_name} {user_email} {user_type}" },
      ]
    },
    "connections" : {
      "fields" : {
        "space_name"    : { "path" : "$.space_name",        "format" : "30s" },
        "business_name" : { "path" : "$.businessName",      "format" : "30s" },
        "type_id"       : { "path" : "$.typeId",            "format" : "20s" },
        "mod_date"      : { "path" : "$.modification_date", "format" : "35s" }
      },
      "rows" : [
        { "type" : "row", "layout" : "{space_name} {business_name} {type_id} {mod_date}" },
      ]
    }

  }
