# users/tasks.py
from celery import shared_task
from django.utils import timezone
from django.utils.timezone import now, timedelta
from .models import OTP, User
from celery.utils.log import get_task_logger

logger = get_task_logger(__name__)

@shared_task
def delete_expired_otps():
    """
    Delete OTPs that are older than 5 minutes.
    
    Returns:
        str: A message indicating how many OTPs were deleted
    """
    from django.utils import timezone
    from datetime import timedelta
    
    try:
        # Get current time in UTC to ensure consistency
        current_time = timezone.now()
        expiration_time = current_time - timedelta(minutes=5)
        
        logger.info(f"[OTP Cleanup] Current time (UTC): {current_time}")
        logger.info(f"[OTP Cleanup] Deleting OTPs older than (UTC): {expiration_time}")
        
        # Find and delete expired OTPs
        expired_otps = OTP.objects.filter(created_at__lt=expiration_time)
        all_otps = OTP.objects.all()
        
        # Log all OTPs for debugging
        for otp in all_otps:
            logger.info(f"[OTP Cleanup] OTP {otp.otp} created at {otp.created_at} (UTC)")
        
        count = expired_otps.count()
        
        if count > 0:
            # Log details about the OTPs that will be deleted
            otp_details = [f"OTP {otp.otp} created at {otp.created_at} (UTC)" for otp in expired_otps[:5]]
            if count > 5:
                otp_details.append(f"... and {count - 5} more")
            logger.info(f"[OTP Cleanup] Deleting {count} expired OTP(s): {', '.join(otp_details)}")
            
            # Use iterator() to avoid loading all objects into memory
            expired_otps_iterator = expired_otps.iterator()
            deleted_count = 0
            
            for otp in expired_otps_iterator:
                otp.delete()
                deleted_count += 1
                
            logger.info(f"[OTP Cleanup] Successfully deleted {deleted_count} expired OTP(s).")
            return f"{deleted_count} expired OTP(s) deleted."
        else:
            logger.info("[OTP Cleanup] No expired OTPs found to delete.")
            return "No expired OTPs found to delete."
            
    except Exception as e:
        logger.error(f"[OTP Cleanup] Error deleting expired OTPs: {str(e)}", exc_info=True)
        return f"Error deleting expired OTPs: {str(e)}"

@shared_task
def recover_trust_scores_daily():
    """
    Celery task to recover trust scores for all users with negative scores.
    Increases negative trust scores by TRUST_SCORE_RECOVERY_RATE points daily until they reach 0.
    """
    try:
        from django.conf import settings
        
        # Get all users with negative trust scores
        users_to_recover = User.objects.filter(trust_score__lt=0)
        recovered_count = 0
        
        for user in users_to_recover:
            # Call the model method which handles the recovery logic
            if user.recover_trust_score_daily(recovery_rate=settings.TRUST_SCORE_RECOVERY_RATE):
                recovered_count += 1
        
        result = {
            'status': 'success',
            'users_processed': len(users_to_recover),
            'users_recovered': recovered_count,
            'timestamp': timezone.now().isoformat()
        }
        
        logger.info(
            f"Trust score recovery completed. "
            f"Processed: {len(users_to_recover)}, Recovered: {recovered_count}"
        )
        
        return result
        
    except Exception as e:
        logger.error(f"Error in recover_trust_scores_daily task: {str(e)}")
        raise
