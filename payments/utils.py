import requests
from django.conf import settings

ZARINPAL_REQUEST_URL = settings.ZARINPAL_REQUEST_URL
ZARINPAL_VERIFY_URL = settings.ZARINPAL_VERIFY_URL
ZARINPAL_STARTPAY_URL = settings.ZARINPAL_STARTPAY_URL
MERCHANT_ID = settings.ZARINPAL_MERCHANT_ID

def request_payment(amount, callback_url, user):
    """Send payment request to ZarinPal."""
    print(f"Using merchant ID: {MERCHANT_ID}")  # Debug print
    data = {
        "merchant_id": MERCHANT_ID,
        "amount": amount,
        "callback_url": callback_url,
        "description": f"Payment by {user.phone_number}",
        "metadata": {
            "mobile": user.phone_number,
            "email": user.email or "",
        }
    }
    print(f"Request data: {data}")  # Debug print
    response = requests.post(ZARINPAL_REQUEST_URL, json=data)
    return response.json()

def verify_payment(amount, authority):
    """Verify payment with ZarinPal."""
    data = {
        "merchant_id": MERCHANT_ID,
        "amount": amount,
        "authority": authority
    }
    response = requests.post(ZARINPAL_VERIFY_URL, json=data)
    
    return response.json()
