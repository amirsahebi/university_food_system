from django.apps import AppConfig
from core.logging_utils import get_logger


class OrdersConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'orders'
    verbose_name = 'Orders'
    
    def ready(self):
        # Initialize logger when the app is ready
        self.logger = get_logger(self.name)
        self.logger.info(f"{self.verbose_name} app initialized")
        import orders.signals  # Import signal handlers
