from django.apps import AppConfig
from core.logging_utils import get_logger


class MenuConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'menu'
    verbose_name = 'Menu'

    def ready(self):
        self.logger = get_logger(self.name)
        self.logger.info(f"{self.verbose_name} app initialized")
        import menu.signals  # Register signals
