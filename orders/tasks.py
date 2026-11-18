import logging
import json
from celery import shared_task
from users.utils import SMSService

logger = logging.getLogger(__name__)

VAPID_PUBLIC_KEY = "BLymNQ0DAvVqm6zISqV6s7z9tc8-UgRmIZ4Utz4Bj0WsyK8Y-QxEUNugVCaspGhJ2lzYR__gSh1fGsnkyiP9OAI"
VAPID_PRIVATE_KEY = "fsrVoKSPUjLm2TqyAgmZ8q0zT_Nz7mEMoRd7234qgeQ"
VAPID_CLAIMS = {"sub": "mailto:support@javan-foods.ir"}


def send_web_push_notification(user, title, body, url="/student-dashboard?tab=orders"):
    """
    Sends Web Push notification to user's registered browsers/devices.
    Works even when the browser is closed and phone screen is off.
    """
    try:
        from users.models import WebPushSubscription
        from pywebpush import webpush, WebPushException

        subscriptions = list(WebPushSubscription.objects.filter(user=user))
        if not subscriptions:
            logger.info(f"[WebPush] No push subscriptions found for user {user.phone_number}")
            return False

        payload = json.dumps({
            "title": title,
            "body": body,
            "icon": "/icons/icon-192x192.png",
            "badge": "/icons/icon-192x192.png",
            "url": url,
            "tag": f"javanfoods-order-{user.id}",
        })

        sent_count = 0
        for sub in subscriptions:
            try:
                webpush(
                    subscription_info={
                        "endpoint": sub.endpoint,
                        "keys": {
                            "p256dh": sub.p256dh,
                            "auth": sub.auth,
                        }
                    },
                    data=payload,
                    vapid_private_key=VAPID_PRIVATE_KEY,
                    vapid_claims=VAPID_CLAIMS,
                    ttl=86400,
                    headers={
                        "Urgency": "high",
                        "TTL": "86400",
                    },
                    timeout=10,
                )
                sent_count += 1
                logger.info(f"[WebPush] Successfully sent high-urgency push notification to {user.phone_number}")
            except WebPushException as ex:
                logger.warning(f"[WebPush] Push failed for {user.phone_number}: {ex}")
                if ex.response is not None and ex.response.status_code in (404, 410):
                    # Subscription is expired or unregistered
                    sub.delete()
            except Exception as e:
                logger.error(f"[WebPush] Error sending push: {e}")

        return sent_count > 0
    except Exception as e:
        logger.error(f"[WebPush] Overall push error: {e}")
        return False


@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def send_pickup_notification_task(self, reservation_id):
    """
    Asynchronous Celery task to send Web Push pickup notifications.
    Decoupled from database transactions to prevent hanging locks and rollbacks.
    SMS is disabled (Push Notification only).
    """
    from orders.models import Reservation
    try:
        reservation = Reservation.objects.select_related('student', 'food').get(id=reservation_id)
        student = reservation.student
        if not student:
            logger.warning(f"No student for reservation {reservation_id}, skipping notifications.")
            return "Skipped: no student"

        # Send native Web Push Notification (even if browser is closed / phone screen off)
        food_name = "غذا"
        try:
            if hasattr(reservation, 'food') and reservation.food and reservation.food.name:
                food_name = reservation.food.name
            elif hasattr(reservation, 'daily_menu_item') and reservation.daily_menu_item and hasattr(reservation.daily_menu_item, 'food'):
                food_name = reservation.daily_menu_item.food.name
        except Exception:
            pass

        delivery_code = getattr(reservation, 'delivery_code', '')
        code_text = f" (کد تحویل: {delivery_code})" if delivery_code else ""
        title = "غذای شما آماده تحویل است 🍲"
        body = f"سفارش «{food_name}»{code_text} در سلف آماده تحویل است."
        push_sent = send_web_push_notification(student, title, body)
        logger.info(f"[WebPush Task] Push sent for order {reservation.id} to user {student.phone_number}: {push_sent}")

        return {"status": "success", "push_sent": push_sent}
    except Exception as exc:
        logger.error(f"[Push Task] Failed to send push for order {reservation_id}: {str(exc)}", exc_info=True)
        # Retry with exponential backoff on transient errors
        try:
            self.retry(exc=exc)
        except Exception:
            pass
        return f"Error: {str(exc)}"

