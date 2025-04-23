import requests
from django.conf import settings
from core.logging_utils import get_logger

logger = get_logger(__name__)

ZARINPAL_REQUEST_URL = settings.ZARINPAL_REQUEST_URL
ZARINPAL_VERIFY_URL = settings.ZARINPAL_VERIFY_URL
ZARINPAL_STARTPAY_URL = settings.ZARINPAL_STARTPAY_URL
MERCHANT_ID = settings.ZARINPAL_MERCHANT_ID

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

def verify_payment(amount, authority):
    """Verify payment with ZarinPal."""
    logger.info(f"Verifying payment with authority {authority} amount {amount}")
    
    data = {
        "merchant_id": MERCHANT_ID,
        "amount": float(amount * 10),  # Convert Decimal to float
        "authority": authority
    }
    logger.debug(f"Payment verification data: {data}")
    
    try:
        response = requests.post(ZARINPAL_VERIFY_URL, json=data, timeout=10)
        
        # Handle 401 Unauthorized specifically
        if response.status_code == 401:
            logger.error("ZarinPal API credentials are invalid")
            raise Exception("Invalid ZarinPal API credentials. Please check your configuration.")
            
        response.raise_for_status()
        logger.debug(f"Payment verification response: {response.text}")
        
        result = response.json()
        
        # Check ZarinPal's error code
        if "data" not in result or "code" not in result["data"]:
            logger.error(f"Invalid response format from ZarinPal: {result}")
            raise Exception("Invalid response format from ZarinPal")
            
        if result["data"]["code"] not in [100, 101]:
            logger.error(f"ZarinPal verification failed with code: {result['data']['code']}")
            raise Exception(f"Payment verification failed with code: {result['data']['code']}")
            
        return result
        
    except requests.RequestException as e:
        logger.error(f"Payment verification failed: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"Payment verification failed with error: {str(e)}")
        raise
