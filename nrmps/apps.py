from django.apps import AppConfig


class NrmpsConfig(AppConfig):
    """Configuration of the simulation app."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "nrmps"

    def ready(self) -> None:
        """Register the system checks of the help registry."""
        from . import checks  # noqa: F401 (registers the checks)
