from dynaconf import Dynaconf

settings = Dynaconf(
    envvar_prefix="FLUXLORA",
    settings_files=["src/settings.toml", "src/.secrets.toml"],
    lowercase_read=False,
)
