# Commands

## Table of Contents
* [Command Sytax](#syntax)
* [Config](#config)
* [Users](#users)
* [Spaces](#spaces)
* [Spaces Bulk](#bulk)
* [Spaces Members](#members)
* [Connections](#connections)
* [Shares](#shares)

## <a href="#syntax"></a>Command Syntax
The provisioner tool accepts the following commands:
|Command|Description|
|-------|-----------|
|config|Set the **provisioner** environment configuration|
|users|User actions against the tenant, including list, create, and delete|
|spaces|Create, delete and list spaces.  This includes bulk loading and member assignment|
|shares|Create, delete and list objects shared to other space(s)|
|connections|Create, delete and list connections in one, or more spaces|
|script|Run a list of commands from a script file.|

|Parameter|Values|
|---------|------|
|--config|Configuration file name (optional)|
|--logging|Generate logging message, options: 'none', 'info', 'debug', 'warn', 'error'

---

## <a href="#config"></a>Command: `config`
This command saves connection information for both an SAP Data Warehouse Cloud tenant and optionally an SAP HANA Cloud (or on-premise) database.  After running this command, a new configuration file named `config.ini` is created in the current working directory.

> Note: the `config` command does not validate the tenant or SAP HANA configuration values.

|Parameter|Values|
|---------|------|
|--dwc-url|Target SAP Data Warehouse Cloud tenant|
|--dwc-user|User name with administrative privileges on the tenant|
|--dwc-password|Password for the user specified in the --dwc-user parameter|
|--hana-host|HANA host name|
|--hana-port|HANA port|
|--hana-user|HANA username|
|--hana-password|HANA password|
|--hana-encrypt|Include the option to encrypt SAP HANA communications (default=False)|
|--hana-sslverify|Validate the HANA certificate (default=False)|

**Examples**:
1. Set the configuration for the SAP Data Warehouse Cloud tenant:

```
(.venv) c:\tools\dwc-provisioner> provisioner config 
    --dwc-url https://notarealtenant.us10.hcs.cloud.sap
    --dwc-user not.a.real.user@dummy.sap
    --dwc-password NotARealPassword!
```

After running this command, the `config.ini` file has the following content:

```
(.venv) c:\tools\dwc-provisioner> type config.ini

[dwc]
dwc_url = https://mytenant.us10.hcs.cloud.sap
dwc_user = not.a.real.user@dummy.sap
dwc_password = eJwLz8vxDDT0M04xMDFKzPE0BQAqfgTD
```

> Note: password values never appear in plain text.

2. Set both the SAP Data Warehouse Cloud and HANA Data Access user credentials.  This example connects to the SAP Data Warehouse Cloud tenant and a Data Access User named PROVISIONER defined in the space ADMINSPACE, i.e., ADMINSPACE#PROVISIONER.

```(.venv) c:\tools\provisioner> provisioner config
    --dwc-url https://notarealtenant.us10.hcs.cloud.sap
    --dwc-user not.a.real.user@dummy.sap
    --dwc-password NotARealPassword!
    --hana-host 9dc97f57.hana.prod-us10.hanacloud.ondemand.com
    --hana-port 443
    --hana-user ADMINSPACE#PROVISIONER
    --hana-password notMyPassword 
    --hana-encrypt
```

---

## <a href="#users"></a>Command: `users`
The `users` command lists, creates, and deletes users from an SAP Data Warehouse Cloud tenant.

### Command: `users list`
The `users list` command retrieves user information from the SAP Data Warehouse Cloud tenant.

|Parameter|Description|
|---------|-----------|
|-f, --format|output style: 'hana', 'csv', 'json', 'text' - default=text|
|-p, --prefix|prefix for output, default="DWC_USERS"|
|-s, --search|seach user names or emails on substring (default = false)|
|-d, --directory|directory for output|
|-q, --query|query users as substring searches|
|userName|user name(s) to list, separated by spaces|

**Examples:**
1. List all the users in the tenant to the console.

```
provisioner users list
```

2. List all the user and output the information in CSV format to the specified output directory.  The output file names will be DWC_USERS.csv and DWC_USERS_role_members.csv.

```
provisioner users list -f csv -d c:\temp
```

3. Search the users in the tenant for users with "sap.com" appearing anywhere in their definition (including email), as well as any user with the word "greynolds" in their definition.

```
provisioner users list -S sap.com greynolds
```

### Command: `users create`

*Work in progress*

### Command: `users delete`

*Work in progress*

---

## <a href="#spaces"></a>Command: `spaces`
The spaces command can create, delete and list spaces in the tenant.

### Command: `spaces list`
The `spaces list` command queries the SAP Data Warehouse Cloud tenant for details for all spaces, specific spaces, or substring searches of available spaces.  If no space ids are provided, all spaces in the tenant will be included.  For instance, adding the `--query` flag with a space id of "TRAINING" finds spaces with names such as "TRAINING_LOB", "FINANCE_TRAINING", and "HRTRAINING".

|Parameter|Description|
|---------|-----------|
|-f, --format|output style: 'hana', 'csv', 'json', 'text'|
|-p, --prefix|prefix for output, default="DWC_SPACES"|
|-q, --query|seach space names on substring (default = false)|
|-d, --directory|filename for output|
|spaceID|space id(s) to list|

**Examples:**
1. List all spaces in the tenant to the console.

```
provisioner spaces list
```

2. List all spaces containing the word "TRAINING" and the space containing "FINANCE_DATA."

```
provisioner spaces list TRAINING FINANCE_DATA
```

3. List all the spaces to HANA tables.

```
provisioner spaces list --format hana
```

### Command: `spaces create`
The `spaces create` command creates a new space in  the SAP Data Warehouse Cloud tenant.  If the --template option is specified, the provided space ID is used to lookup an existing Space to use as a template.

|Parameter|Description|
|---------|-----------|
|-b, --businesss | optional business name to assign - defaults to spaceID|
|-t, --template | space id to use as a template|
|-d, --disk | disk allocated to space|
|-m, --memory | memory allocated to space|
|-f, --force | force the re-creation if space exists|
|spaceID | space id to create|
|users | users to add to the space|

**Examples:**

1. Create a new space using only command line options having 1 GB of disk storage and .5 GB of in-memory storage.

```
provisioner spaces create --disk 1 --memory .5 MYNEWSPACE
```

2. Create a new space from an existing template.  If the new space already exists, delete it before re-creating (--force).

```
provisioner spaces create --template FINANCE_DATA --force MYNEWSPACE
```

### Command: `spaces delete`
Delete one, or more spaces by listing their space IDs on the command line.

|Parameter|Description|
|---------|-----------|
| spaceID | space id(s) to create |

> **Note**: the --query option for space IDs is not supported for space delete operations.

**Examples:**

1. Delete a single space.

```
provisioner spaces delete MYSPACEID
```

2. Delete multiple spaces in a single operation.

```
provisioner spaces delete TRAINING_1 TRANING_2 RANDOMSPACE THEOTHERSPACE
```

---

## <a href="#bulk"></a>Command: `spaces bulk`
The `spaces bulk` command creates or deletes multiple spaces using a CSV file to provides the
list of spaces.  For `bulk create` operations, the CSV file must have the following columns:

```
Space Id, Business Name, Disk, Memory, Template, Force, User 1, User 2, User 3, etc
```

> **Note**: Any number of users for a space may be included as comma separated values.

For bulk delete operations, only the space ID column is required - all other values are ignored.

### Command: `spaces bulk create`
Create spaces defined in a CSV file.

|Parameter|Description|
|---------|-----------|
|-s, --skip | header lines to skip in the CSV file, default="1" |
|-f, --force | force the re-creation if space exists |
|-t, --template | Space ID to use as a template if not specified per space |
|filename | CSV file containing spaces to create |

**Example:**

```
provisioner spaces bulk create c:\tools\new-spaces.csv
```

### Command: `spaces bulk delete`
This command is similar to the `spaces delete` command and is intended to quickly delete the spaces created with the `spaces bulk create` command.  The CSV file requires only 1 column containing the space IDs to be deleted.

|Parameter|Description|
|---------|-----------|
| -s, --skip | header lines to skip in the CSV file, default="1" |
| filename | CSV file containing space names to delete |

**Example:**

```
provisioner spaces bulk create c:\tools\new-spaces.csv
```

---

## <a href="#members"></a>Command: `spaces members`
The `space members` can command list existing space members, add members to a space, or remove members from a space.

### Command: `spaces member list`

List the members in one or more spaces.

|Parameter|Description|
|---------|-----------|
|-q, --query|seach space names on substring (default = false)|
|-f, --format|output style: 'hana', 'csv', 'json', 'text'|
|-p, --prefix|prefix for output, default="DWC_SPACES"|
|-d, --directory|filename for output|
|spaceID|space id(s) to list|

**Example:**
1. List the members in all spaces in the tenant.

```
provisioner spaces members list
```

2. List the members for two spaces: MYSPACE and FINANCE_DATA.

```
provisioner spaces members list MYSPACE FINANCE_DATA
```

3. List the member of all spaces having the word TRAINING in the space ID and FINANCE_DATA.

```
provisioner spaces members list --query FINANCE_DATA TRAINING
```

### Command: `spaces member add`
Add a tenant one, or more users to an existing space.  By default, this command expects "USER ID" values; the "USER ID" values are not email addresses.  To include users by either "USER ID" or email address, use the --query option to search for users based on the provided string.

|Parameter|Description|
|---------|-----------|
|-q, --query|seach space names on substring (default = false)|
|spaceID|space id(s) to list|
|user|one or more user names to add to the space|

**Examples:**

1. Add a user to a space.

```
provisioner spaces member add MYSPACE MGREYNOLDS
```

2. Add multiple users to a space.

```
provisioner spaces member add MYSPACE MGREYNOLDS BSMITH
```

3. Add multiple users have email addresses containing "mycompany.com" to a space.

```
provisioner spaces member add --query MYSPACE mycompany.com
```

### Command: `spaces member remove`
Remove one, or more tenant users from an existing space.  By default, this command expects "USER ID" values; the "USER ID" values are not email addresses.  To users users by either "USER ID" or email address, use the --query option to search for users based on the provided string.

|Parameter|Description|
|---------|-----------|
|-q, --query|seach space names on substring (default = false)|
|spaceID|space id(s) to list|
|user|one or more user names to remove to the space|

**Examples:**

1. Remove a user from a space.

```
provisioner spaces member remove MYSPACE MGREYNOLDS
```

2. Remove multiple users from a space.

```
provisioner spaces member remove MYSPACE MGREYNOLDS BSMITH
```

3. Remove multiple users have email addresses containing "mycompany.com" to a space.

```
provisioner spaces member remove --query MYSPACE mycompany.com
```

---

## <a href="#shares"></a>Command: `shares`
#### 9.4.1 - Command: `shares list`
#### 9.4.2 - Command: `shares create`
#### 9.4.3 - Command: `shares delete`

---

## <a href="#connections"></a>Command: `connections`

The `connections` command can list, create, and delete connections from spaces.  Spaces may be explicitly identified by ID or searched for based on a search strings.

### Command: `connections list`
List the connections from one, or more spaces.
|Parameter|Description|
|---------|-----------|
|-q, --query|seach space names on substring (default = false)|
|-c, --connection|connection name to list|
|-f, --format|output style: 'hana', 'csv', 'json', 'text' - default=text|
|-p, --prefix|output prefix, default=DWC_CONNECTIONS|
|-d, --directory|directory for output files|
|spaceID|space id(s) to list connections|

**Examples:**

1. List the connections from a single space.

```
provisioner connections list MYSPACE
```

2. List the connections from spaces having "TRAINING" in the space ID.

```
provisioner connections list --query TRAINING
```

3. List the specific connection "HANA on-premise" in all spaces.

```
provisioner connections list --connection "HANA on-premise"
```

### Command: `connection create`
### Command: `connection delete`
