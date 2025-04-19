from django.apps import AppConfig
from core.logging_utils import get_logger


class FoodConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'food'
    verbose_name = 'Food'
    
    def ready(self):
        # Initialize logger when the app is ready
        self.logger = get_logger(self.name)
        self.logger.info(f"{self.verbose_name} app initialized")
