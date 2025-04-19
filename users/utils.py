import os
import requests
import json
import logging
from django.conf import settings

logger = logging.getLogger(__name__)

class SMSService:
    """
    A utility class for sending SMS messages using configurable SMS providers.
    Supports environment-based configuration and flexible SMS sending.
    """
    
    @staticmethod
    def send_otp(phone_number: str, otp_code: str) -> dict:
        """
        Send OTP via SMS using configured SMS service.
        
        Args:
            phone_number (str): Recipient's phone number
            otp_code (str): One-time password to send
        
        Returns:
            dict: Response from SMS service with status and details
        """
        try:
            url = os.getenv('SMS_API_URL', 'https://api.sms.ir/v1/send/verify')
            headers = {
                'Content-Type': 'application/json',
                'Accept': 'text/plain',
                'x-api-key': os.getenv('SMS_API_KEY')
            }

            data = {
                "mobile": phone_number,
                "templateId": os.getenv('SMS_TEMPLATE_ID', 123456),
                "parameters": [{"name": "Code", "value": otp_code}]
            }

            response = requests.post(url, headers=headers, data=json.dumps(data))
            
            # Log the response for debugging
            logger.info(f"SMS sending response: {response.text}")
            
            # Check response status
            if response.status_code == 200:
                return {
                    "status": "success", 
                    "message": "OTP sent successfully",
                    "details": response.json()
                }
            else:
                logger.error(f"SMS sending failed: {response.text}")
                return {
                    "status": "error", 
                    "message": "Failed to send OTP",
                    "details": response.text
                }
        
        except Exception as e:
            logger.exception(f"Exception in sending SMS: {str(e)}")
            return {
                "status": "error", 
                "message": f"SMS sending exception: {str(e)}",
                "details": None
            }
    
    @staticmethod
    def validate_phone_number(phone_number: str) -> bool:
        """
        Validate Iranian phone number format.
        
        Args:
            phone_number (str): Phone number to validate
        
        Returns:
            bool: Whether the phone number is valid
        """
        import re
        return bool(re.match(r'^(?:\+98|0)?9\d{9}$', phone_number))

    @staticmethod
    def send_notification(phone_number: str, name: str, delivery_code: str) -> dict:
        """
        Send a general notification message via SMS.
        
        Args:
            phone_number (str): Recipient's phone number
            message (str): The message to send
        
        Returns:
            dict: Response from SMS service with status and details
        """
        try:
            # You may need to adjust this depending on your SMS provider's API for regular messages
            url = os.getenv('SMS_API_URL', 'https://api.sms.ir/v1/send/verify')
            headers = {
                'Content-Type': 'application/json',
                'Accept': 'text/plain',
                'x-api-key': os.getenv('SMS_API_KEY')
            }

            data = {
                "mobile": phone_number,
                "templateId": os.getenv('RESERVATION_READY_TEMPLATE_ID', 849510),
                "parameters": [{"name": "name", "value": name},
                               {"name": "delivery_code", "value": delivery_code}]
            }

            response = requests.post(url, headers=headers, data=json.dumps(data))
            
            # Log the response for debugging
            logger.info(f"Notification SMS response: {response.text}")
            
            # Check response status
            if response.status_code == 200:
                return {
                    "status": "success", 
                    "message": "Notification sent successfully",
                    "details": response.json()
                }
            else:
                logger.error(f"Notification SMS failed: {response.text}")
                return {
                    "status": "error", 
                    "message": "Failed to send notification",
                    "details": response.text
                }
        
        except Exception as e:
            logger.exception(f"Exception in sending notification SMS: {str(e)}")
            return {
                "status": "error", 
                "message": f"Notification sending exception: {str(e)}",
                "details": None
            }
