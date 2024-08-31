from dynaconf import Dynaconf

settings = Dynaconf(
    envvar_prefix="FLUXLORA",
    settings_files=["settings.toml", "settings.local.toml", ".secrets.toml"],
    environments=True,
    load_dotenv=True,
    lowercase_read=False,
)
