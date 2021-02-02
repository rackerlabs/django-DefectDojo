from split_settings.tools import optional, include

# New in 1.10.0: A settings.py file providedby Defect Dojo. See below for explenation.
# If you have previously added your own settings.py file, a temporary quickfix is to rename that to local_settings.py

# Defect Dojo uses 3 settings files to get you going:
#
# - settings.dist.py:
#       The main settings are all stored here, it also reads from the environment variables (see contents of settings.dist.py).
# - "env file, i.e. .env.prod" (not stored in git)
#       The settings.dist.py file reads variables from the file with name DD_ENV_PATH (default .env.prod file).
#       Example in template_env file
# - local_settings.py (not stored in git, not used in release mode)
#       A file stored locally / on the server containing more complex customizations such as adding MIDDLEWARE or INSTALLED_APP entries.
#       This file is processed *after* settings.dist.py is processed, so you can modify settings delivered by Defect Dojo out of the box.
#       Example in template-local_settings
#
#
# in docker-compose release mode, files in docker/extra_settings will be copied into dojo/settings/ on startup


include("settings.dist.py", optional("local_settings.py"))
