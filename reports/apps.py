from django.apps import AppConfig
from core.logging_utils import get_logger


class ReportsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'reports'
    verbose_name = 'Reports'
    
    def ready(self):
        # Initialize logger when the app is ready
        self.logger = get_logger(self.name)
        self.logger.info(f"{self.verbose_name} app initialized")
