import logging, os, sys, configparser, base64, zlib

# Configure the global logging with a default logging
# level of info.

logging.basicConfig(format="%(asctime)s %(levelname)s %(name)s : %(message)s")

# Default logging level for all operations is NOTSET
log_level = logging.NOTSET

logger = logging.getLogger("config")

config_params = { "sections" : [
                    { "name"       : "dwc", 
                      "parameters" : [ "dwc_url", "dwc_user", "dwc_password" ] },
                    { "name"       : "hana",
                      "parameters" : [ "hana_host", "hana_port", "hana_user", "hana_password", "hana_encrypt", "hana_sslverify" ] }
                  ]
                }

# At load, there is no configuration.
session_config = None

def ensure_config(args):
    global log_level, session_config
    
    # Make sure the configuration file is present and has been initialized. The configuration
    # file is built based on the sections and parameters list above and any command line
    # arguments passed to the script.  Individual command line parameters can be passed to
    # to update individual configuration parameters.
    
    # When this routine finishs, the configuration for this session is ready for use.
    
    if args.config is None:
        config_path = os.getcwd()
        config_file = os.path.join(config_path, "config.ini")
    else:
        config_file = args.config

    config_exists = os.path.exists(config_file)
    
    if args.command != "config" and not config_exists:
        logger.critical("Configuration file not found - please use the config command.")
        sys.exit(1)

    session_config = configparser.ConfigParser()
    write_config = False
    
    if config_exists:
      session_config.read(config_file)
    
    for section in config_params["sections"]:
      # Make sure the section is present.
      if section["name"] not in session_config:
        session_config[section["name"]] = {}
        write_config = True
      
      # Check for mandatory parameter - trailing '+' means optional
      
      for parameter in section["parameters"]:
        if parameter[-1] == '+':
          param_name = parameter[:-1]
          required = False
        else:
          param_name = parameter
          required = True
        
        # If the parameter is on the command line, assign the value
        # to the configuration.
            
        if param_name in vars(args): # Was the parameter on the command line?
          param_value = str(vars(args)[param_name])
          
          # Obscure any parameter with "password" in the name.
          if param_name.find("password") == -1:
            session_config[section["name"]][param_name] = param_value
          else:
            session_config[section["name"]][param_name] = fn_blur(param_value)
            
          write_config = True
    
    # If anything was changed, (re)write the config file.
    
    if write_config:
      with open(config_file, 'w') as config_handle:
        session_config.write(config_handle)
      
    # Figure out the logging level - default is info.

    if args.logging is not None:
        if args.logging == "info":
            logger.setLevel(logging.INFO)
            logger.info("Logging set to INFO")
        else:
            logger.setLevel(logging.DEBUG)
            logger.info("Logging set to DEBUG")

    # Set the level so subsequent commands can set their
    # level to match.

    log_level = logger.getEffectiveLevel()

def get_config_section(section):
  for config in config_params["sections"]:
    if config["name"] == section:
      return config
    
  return None

def get_config_param(section, parameter):
  # Make sure the section and parameter are valid configuration
  # values - must be official.

  config_section = get_config_section(section)
  
  if config_section is None:
    logger.error(f"get_config_param: request for invalid section {section}.")
    return

  config_parameters = config_section["parameters"]

  param_optional = parameter + "+"
  
  if parameter not in config_parameters and param_optional not in config_parameters:
    logger.error(f"get_config_param: request for invalid parameter {parameter}.")
    return

  if param_optional in config_parameters:
    required = False
  else:
    required = True
    
  # We know the request is valid, make sure the configuration
  # for the current session is loaded.
  
  if session_config is None:
    logger.error("get_config_param: configuration has not been initialized.")
    return
  
  # The configuration could be corrupt - make sure the section
  # exists in the current session.
  
  if section not in session_config.sections():
    logger.error(f"get_config_param: configuration file is invalid - section {section} not found.")
    return None
  
  section_params = session_config[section]
  
  # Test to see if we have an official parameter name.
  
  if parameter not in section_params and required:
    logger.error(f"get_config_param: required configuration parameter {parameter} has no value.")
    return None      

  param_value = session_config[section][parameter]
  
  if parameter.find("password") == -1:
    return param_value
  else:
    return fn_unblur(param_value)

def fn_blur(value):
    value_b = str.encode(value)
    value_b64 = base64.b64encode(value_b)
    value_z = zlib.compress(value_b64)
    value_z_b64 = base64.b64encode(value_z)
    
    return str(value_z_b64, 'UTF-8')

def fn_unblur(value_z_b64):
    value_z = base64.b64decode(value_z_b64)
    value_b64 = zlib.decompress(value_z)
    value_b = base64.b64decode(value_b64)
    value = value_b.decode()
    
    return value
