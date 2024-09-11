import configparser
import os

config = configparser.ConfigParser()
config.read(["settings.ini", "settings.local.ini"])


def get_api_key():
    return os.environ.get("REPLICATE_API_KEY") or config.get(
        "secrets", "REPLICATE_API_KEY", fallback=None
    )


def get_setting(section, key, fallback=None):
    try:
        return config.get(section, key)
    except (configparser.NoSectionError, configparser.NoOptionError):
        return fallback


def set_setting(section, key, value):
    if not config.has_section(section):
        config.add_section(section)
    config.set(section, key, str(value))


def save_settings():
    with open("settings.local.ini", "w") as configfile:
        config.write(configfile)
