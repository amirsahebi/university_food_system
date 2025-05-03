from celery import shared_task
from university_food_system.tasks_with_logging import task_with_logging
from utils.logging_strategy import (
    get_logger, 
    create_audit_log, 
    security_log
)
from django.core.cache import cache
from django.utils import timezone
from datetime import timedelta

logger = get_logger('tasks.background_tasks')

@shared_task
@task_with_logging
def cleanup_expired_reservations():
    """
    Background task to clean up expired reservations
    """
    from orders.models import Reservation
    
    # Find reservations older than 24 hours that are still pending
    expiration_time = timezone.now() - timedelta(hours=24)
    expired_reservations = Reservation.objects.filter(
        status='pending', 
        created_at__lt=expiration_time
    )
    
    # Log number of expired reservations
    logger.info(
        f'Cleaning up {expired_reservations.count()} expired reservations', 
        extra={'expiration_time': str(expiration_time)}
    )
    
    # Cancel expired reservations
    for reservation in expired_reservations:
        try:
            reservation.status = 'cancelled'
            reservation.save()
            
            # Audit log for reservation cancellation
            create_audit_log(
                reservation.user, 
                'reservation_expired', 
                {
                    'reservation_id': reservation.id,
                    'original_status': 'pending'
                }
            )
        except Exception as e:
            logger.error(
                f'Failed to cancel reservation {reservation.id}', 
                extra={'error': str(e)}
            )
    
    return f'Cleaned up {expired_reservations.count()} expired reservations'

@shared_task
@task_with_logging
def cache_menu_popularity():
    """
    Background task to cache menu item popularity
    """
    from menu.models import MenuItem
    
    try:
        # Calculate menu item popularity based on recent orders
        menu_popularity = MenuItem.objects.annotate_popularity()
        
        # Cache menu popularity for quick access
        cache.set('menu_popularity', menu_popularity, timeout=3600)  # 1 hour cache
        
        logger.info(
            'Menu popularity cached successfully', 
            extra={'items_cached': len(menu_popularity)}
        )
        
        # Audit log for menu popularity caching
        create_audit_log(
            None,  # System task
            'menu_popularity_cached', 
            {'items_cached': len(menu_popularity)}
        )
        
        return f'Cached popularity for {len(menu_popularity)} menu items'
    
    except Exception as e:
        logger.error(
            'Failed to cache menu popularity', 
            extra={'error': str(e)}
        )
        
        # Security log for task failure
        security_log(
            'background_task_failure', 
            details={
                'task': 'cache_menu_popularity',
                'error': str(e)
            }
        )
        
        return 'Failed to cache menu popularity'

@shared_task
@task_with_logging
def cancel_pending_payment_reservations():
    """
    Background task to cancel reservations that have been in pending_payment status for more than 10 minutes
    """
    from orders.models import Reservation
    
    # Find reservations older than 10 minutes that are still in pending_payment
    expiration_time = timezone.now() - timedelta(minutes=10)
    logger.info(f"Checking for pending payment reservations older than {expiration_time}")
    
    expired_reservations = Reservation.objects.filter(
        status='pending_payment', 
        created_at__lt=expiration_time
    )
    
    total_expired = expired_reservations.count()
    logger.info(f"Found {total_expired} reservations to cancel")
    
    if total_expired == 0:
        logger.info("No reservations to cancel")
        return
    
    # Cancel expired reservations
    for reservation in expired_reservations:
        try:
            logger.info(f"Cancelling reservation {reservation.id} for student {reservation.student_id}")
            reservation.status = 'cancelled'
            reservation.save()
            
            # Audit log for reservation cancellation
            create_audit_log(
                reservation.student, 
                'reservation_payment_expired', 
                {
                    'reservation_id': reservation.id,
                    'original_status': 'pending_payment'
                }
            )
            logger.info(f"Successfully cancelled reservation {reservation.id}")
        except Exception as e:
            logger.error(
                f'Failed to cancel reservation {reservation.id}',
                exc_info=True,
                extra={'reservation_id': reservation.id}
            )
    
    logger.info(f"Successfully cancelled {total_expired} reservations")

@shared_task
@task_with_logging
def generate_daily_sales_report():
    """
    Background task to generate daily sales report
    """
    from orders.models import Order
    from django.core.mail import send_mail
    from django.template.loader import render_to_string
    
    try:
        # Calculate daily sales
        today = timezone.now().date()
        daily_sales = Order.objects.filter(
            created_at__date=today, 
            status='completed'
        ).aggregate_sales()
        
        # Render report email
        report_html = render_to_string('reports/daily_sales.html', {
            'date': today,
            'total_sales': daily_sales['total'],
            'order_count': daily_sales['count']
        })
        
        # Send report to admin
        send_mail(
            f'Daily Sales Report - {today}',
            '',  # Plain text version
            'admin@university_food_system.com',
            ['admin@university_food_system.com'],
            html_message=report_html
        )
        
        logger.info(
            'Daily sales report generated', 
            extra={
                'date': str(today),
                'total_sales': daily_sales['total'],
                'order_count': daily_sales['count']
            }
        )
        
        # Audit log for report generation
        create_audit_log(
            None,  # System task
            'daily_sales_report_generated', 
            {
                'date': str(today),
                'total_sales': daily_sales['total'],
                'order_count': daily_sales['count']
            }
        )
        
        return f'Generated daily sales report for {today}'
    
    except Exception as e:
        logger.error(
            'Failed to generate daily sales report', 
            extra={'error': str(e)}
        )
        
        # Security log for task failure
        security_log(
            'background_task_failure', 
            details={
                'task': 'generate_daily_sales_report',
                'error': str(e)
            }
        )
        
        return 'Failed to generate daily sales report'
