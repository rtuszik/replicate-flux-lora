from dynaconf import Dynaconf

settings = Dynaconf(
    envvar_prefix="FLUXLORA",
    settings_files=["settings.toml", "settings.local.toml", ".secrets.toml"],
    environments=True,
    load_dotenv=True,
    lowercase_read=False,
)


def get_api_key():
    return settings.get("REPLICATE_API_KEY") or settings.get("replicate_api_key")
