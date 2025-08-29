import requests
from django.conf import settings
from core.logging_utils import get_logger

logger = get_logger(__name__)

ZARINPAL_REQUEST_URL = settings.ZARINPAL_REQUEST_URL
ZARINPAL_VERIFY_URL = settings.ZARINPAL_VERIFY_URL
ZARINPAL_INQUIRY_URL = settings.ZARINPAL_INQUIRY_URL
ZARINPAL_STARTPAY_URL = settings.ZARINPAL_STARTPAY_URL
MERCHANT_ID = settings.ZARINPAL_MERCHANT_ID
ZARINPAL_REVERSE_URL = settings.ZARINPAL_REVERSE_URL

def request_payment(amount, callback_url, user):
    """Send payment request to ZarinPal."""
    logger.info(f"Initiating payment request for user {user.id} amount {amount}")
    
    data = {
        "merchant_id": MERCHANT_ID,
        "amount": float(amount * 10),  # Convert Decimal to float
        "callback_url": callback_url,
        "description": f"Payment by {user.phone_number}",
        "metadata": {
            "mobile": user.phone_number,
            "email": user.email or "",
        }
    }
    logger.debug(f"Payment request data: {data}")
    
    try:
        response = requests.post(ZARINPAL_REQUEST_URL, json=data, timeout=10)
        response.raise_for_status()
        logger.debug(f"Payment request response: {response.text}")
        return response.json()
    except requests.RequestException as e:
        logger.error(f"Payment request failed: {str(e)}")
        raise

def inquire_payment(authority):
    """
    Inquire payment status from ZarinPal.
    
    Args:
        authority: The payment authority code from ZarinPal
        
    Returns:
        dict: Payment inquiry result with status, code, and message
        
    Raises:
        Exception: If inquiry fails
    """
    logger.info(f"Inquiring payment status for authority: {authority}")
    
    data = {
        "merchant_id": MERCHANT_ID,
        "authority": authority
    }
    
    headers = {
        'Content-Type': 'application/json',
        'Accept': 'application/json'
    }
    
    try:
        response = requests.post(
            ZARINPAL_INQUIRY_URL,
            json=data,
            headers=headers,
            timeout=10
        )
        response.raise_for_status()
        
        result = response.json()
        logger.debug(f"Payment inquiry response: {result}")
        
        # Handle successful response
        if 'data' in result and result.get('data', {}).get('code') == 100:
            return {
                'status': result['data'].get('status'),
                'code': result['data'].get('code'),
                'message': result['data'].get('message'),
                'success': True
            }
        
        # Handle error response
        error_message = result.get('message', 'Unknown error')
        error_code = None
        
        # Extract error code if available
        if 'errors' in result and isinstance(result['errors'], dict):
            for field_errors in result['errors'].values():
                if isinstance(field_errors, list) and len(field_errors) > 1 and isinstance(field_errors[1], (int, str)):
                    error_code = str(field_errors[1])
                    break
        
        logger.warning(f"Payment inquiry failed: {error_message} (Code: {error_code})")
        return {
            'status': None,
            'code': error_code or -1,
            'message': error_message,
            'success': False
        }
        
    except requests.RequestException as e:
        error_msg = f"Payment inquiry request failed: {str(e)}"
        logger.error(error_msg)
        return {
            'status': None,
            'code': -1,
            'message': error_msg,
            'success': False
        }

def reverse_payment(authority):
    """
    Reverse a payment through ZarinPal's API.
    
    Args:
        authority: The payment authority code from ZarinPal
        
    Returns:
        dict: Reversal result with success status and details
    """
    logger.info(f"Attempting to reverse payment with authority: {authority}")
    
    data = {
        "merchant_id": MERCHANT_ID,
        "authority": authority
    }
    
    headers = {
        'Content-Type': 'application/json',
        'Accept': 'application/json'
    }
    
    try:
        response = requests.post(
            ZARINPAL_REVERSE_URL,
            json=data,
            headers=headers,
            timeout=10
        )
        response.raise_for_status()
        
        result = response.json()
        logger.debug(f"Payment reversal response: {result}")
        
        # Handle successful response
        if 'data' in result and result.get('data', {}).get('code') == 100:
            return {
                'success': True,
                'code': 100,
                'message': result['data'].get('message', 'Payment reversed successfully')
            }
        
        # Handle error response
        error_message = result.get('message', 'Unknown error')
        error_code = result.get('code', -1)
        
        logger.warning(f"Payment reversal failed: {error_message} (Code: {error_code})")
        return {
            'success': False,
            'code': error_code,
            'message': error_message
        }
        
    except requests.RequestException as e:
        error_msg = f"Payment reversal request failed: {str(e)}"
        logger.error(error_msg)
        return {
            'success': False,
            'code': -1,
            'message': error_msg
        }

def check_and_reverse_failed_payment(payment):
    """
    Check if a failed payment should be reversed and process the reversal if needed.
    
    Args:
        payment: Payment instance to check
        
    Returns:
        bool: True if payment was reversed, False otherwise
    """
    from django.utils import timezone
    from datetime import timedelta
    
    logger.info(f"[DEBUG] Starting check_and_reverse_failed_payment for payment {payment.id} with status {payment.status}")
    
    # Skip if not a failed payment
    if payment.status != 'failed':
        logger.info(f"[DEBUG] Payment {payment.id} is not in failed status, skipping")
        return False
        
    # Only process payments that are older than 30 minutes
    if payment.updated_at > timezone.now() - timedelta(minutes=30):
        logger.info(f"[DEBUG] Payment {payment.id} is less than 30 minutes old, skipping")
        return False
        
    # Skip if we've already tried to reverse this payment
    if payment.failure_details and payment.failure_details.get('reversal_attempted', False):
        logger.info(f"[DEBUG] Payment {payment.id} already has reversal_attempted=True, skipping")
        return False
    
    # Initialize failure_details if not exists
    if not hasattr(payment, 'failure_details'):
        payment.failure_details = {}
    
    try:
        logger.info(f"[DEBUG] Checking payment {payment.id} with ZarinPal, authority: {payment.authority}")
        # Check payment status with ZarinPal
        inquiry_result = inquire_payment(payment.authority)
        logger.info(f"[DEBUG] Payment {payment.id} inquiry result: {inquiry_result}")
        
        # If payment is marked as PAID or VERIFIED in ZarinPal but failed in our system, reverse it
        if inquiry_result.get('success') and inquiry_result.get('status') in ['PAID', 'VERIFIED']:
            logger.info(
                f"Found successful payment for failed payment {payment.id}. "
                f"Status: {inquiry_result.get('status')}. Attempting reversal..."
            )
            
            # Record that we're attempting a reversal
            payment.failure_details['reversal_attempted'] = True
            payment.failure_details['reversal_attempted_at'] = timezone.now().isoformat()
            payment.save(update_fields=['failure_details'])
            
            # Try to reverse the payment through ZarinPal
            logger.info(f"[DEBUG] Attempting to reverse payment {payment.id} with authority {payment.authority}")
            reversal_result = reverse_payment(payment.authority)
            logger.info(f"[DEBUG] Payment {payment.id} reversal result: {reversal_result}")
            
            if reversal_result.get('success'):
                logger.info(f"Successfully reversed payment {payment.id} via ZarinPal")
                
                # Mark as reversed in our system
                if hasattr(payment, 'mark_as_reversed'):
                    logger.info(f"[DEBUG] Calling mark_as_reversed for payment {payment.id}")
                    payment.mark_as_reversed()
                else:
                    # If mark_as_reversed is not available, update status directly
                    payment.status = 'reversed'
                    logger.info(f"[DEBUG] Updated payment {payment.id} status to 'reversed'")
                
                # Update failure details and save
                payment.failure_details['reversed'] = True
                payment.failure_details['reversed_at'] = timezone.now().isoformat()
                payment.save(update_fields=['status', 'failure_details', 'updated_at'])
                logger.info(f"[DEBUG] Successfully updated payment {payment.id} as reversed")
                return True
            else:
                error_msg = f"Failed to reverse payment {payment.id} via ZarinPal: {reversal_result.get('message')} (Code: {reversal_result.get('code')})"
                logger.error(error_msg)
                payment.failure_details['reversal_error'] = {
                    'code': reversal_result.get('code'),
                    'message': reversal_result.get('message'),
                    'timestamp': timezone.now().isoformat()
                }
                payment.save(update_fields=['failure_details'])
                logger.info(f"[DEBUG] Saved reversal error for payment {payment.id}")
                return False
        else:
            logger.info(f"[DEBUG] Payment {payment.id} not marked as PAID/VERIFIED in ZarinPal, no reversal needed")
            return False
                
    except Exception as e:
        error_msg = f"Error processing payment {payment.id} for reversal: {str(e)}"
        logger.error(error_msg, exc_info=True)
        payment.failure_details['reversal_error'] = {
            'error': str(e),
            'timestamp': timezone.now().isoformat()
        }
        payment.save(update_fields=['failure_details'])
        logger.info(f"[DEBUG] Saved exception in reversal for payment {payment.id}")
    
    return False

def verify_payment(amount, authority, max_retries=3):
    """
    Verify payment with ZarinPal with retry logic and idempotency.
    
    Args:
        amount: The payment amount
        authority: The payment authority code from ZarinPal
        max_retries: Maximum number of retry attempts
        
    Returns:
        dict: Payment verification result
        
    Raises:
        Exception: If verification fails after all retries
    """
    logger.info(f"Verifying payment with authority {authority} amount {amount}")
    
    data = {
        "merchant_id": MERCHANT_ID,
        "amount": float(amount * 10),  # Convert Decimal to float
        "authority": authority
    }
    
    last_exception = None
    
    for attempt in range(max_retries):
        try:
            logger.debug(f"Payment verification attempt {attempt + 1}/{max_retries}")
            logger.debug(f"Payment verification data: {data}")
            
            response = requests.post(ZARINPAL_VERIFY_URL, json=data, timeout=10)
            
            # Handle 404 specifically - might be a temporary issue
            if response.status_code == 404:
                logger.warning(f"Payment verification endpoint not found (404) for authority {authority}")
                if attempt < max_retries - 1:
                    wait_time = (2 ** attempt) + 1  # Exponential backoff
                    logger.info(f"Retrying in {wait_time} seconds...")
                    import time
                    time.sleep(wait_time)
                    continue
                else:
                    raise Exception("Payment verification endpoint not available after multiple attempts")
            
            # Handle 401 Unauthorized specifically
            if response.status_code == 401:
                error_msg = "ZarinPal API credentials are invalid"
                logger.error(error_msg)
                raise Exception("Invalid ZarinPal API credentials. Please check your configuration.")
                
            response.raise_for_status()
            logger.debug(f"Payment verification response: {response.text}")
            
            result = response.json()
            
            # Check ZarinPal's error code
            if "data" not in result or "code" not in result["data"]:
                error_msg = f"Invalid response format from ZarinPal: {result}"
                logger.error(error_msg)
                raise Exception("Invalid response format from ZarinPal")
                
            if result["data"]["code"] not in [100, 101]:
                error_msg = f"ZarinPal verification failed with code: {result['data']['code']}"
                logger.error(error_msg)
                
                # If it's a known error that won't change with retries, fail fast
                if result["data"]["code"] in [51, 54]:  # Payment already verified or already reversed
                    logger.info("Payment already processed, returning existing status")
                
                # For other errors, retry if we have attempts left
                if attempt < max_retries - 1 and result["data"]["code"] not in [51, 54]:
                    wait_time = (2 ** attempt) + 1
                    logger.info(f"Retrying in {wait_time} seconds...")
                    import time
                    time.sleep(wait_time)
                    continue
                    
                raise Exception(f"Payment verification failed with code: {result['data']['code']}")
                
            return result
            
        except requests.RequestException as e:
            last_exception = e
            logger.warning(f"Payment verification attempt {attempt + 1} failed: {str(e)}")
            if attempt < max_retries - 1:
                wait_time = (2 ** attempt) + 1
                logger.info(f"Retrying in {wait_time} seconds...")
                import time
                time.sleep(wait_time)
            continue
    
    # If we get here, all retries failed
    error_msg = f"Payment verification failed after {max_retries} attempts"
    logger.error(f"{error_msg}: {str(last_exception) if last_exception else 'Unknown error'}")
    raise Exception(f"{error_msg}. Last error: {str(last_exception)}")
