from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenRefreshView
from django.core.cache import cache
from django.utils.timezone import now, timedelta
from kavenegar import KavenegarAPI
from .models import User, OTP
from .serializers import UserSerializer,UserProfileUpdateSerializer
import re
from django.contrib.auth import authenticate
from sms_ir import SmsIr
import requests
import json


class SendOTPView(APIView):
    """Send an OTP to the user's phone number."""
    def post(self, request):
        phone_number = request.data.get('phone_number')

        if not phone_number:
            return Response({"error": "Phone number is required"}, status=status.HTTP_400_BAD_REQUEST)

        # Validate phone number format
        if not re.match(r'^(?:\+98|0)?9\d{9}$', phone_number):
            return Response({"error": "Invalid phone number format"}, status=status.HTTP_400_BAD_REQUEST)

        # Rate limit: Check cache
        cache_key = f"otp_limit:{phone_number}"
        if cache.get(cache_key):
            return Response(
                {"error": "Too many requests. Please wait before requesting another OTP."},
                status=status.HTTP_429_TOO_MANY_REQUESTS
            )

        # **Delete any existing OTP for this phone number**
        OTP.objects.filter(phone_number=phone_number).delete()

        # Generate OTP
        otp_code = OTP.generate_otp()
        OTP.objects.create(phone_number=phone_number, otp=otp_code)

        # Send OTP via SMS
        try:
            url = "https://api.sms.ir/v1/send/verify"
            headers = {
                'Content-Type': 'application/json',
                'Accept': 'text/plain',
                'x-api-key': 'AvlnbwJn9oPDn9BCcbsyacENDj4qkeUnOJkf3zCIvIGIyJeS'
            }

            data = {
                "mobile": phone_number,
                "templateId": 123456,
                "parameters": [{"name": "Code", "value": otp_code}]
            }

            response = requests.post(url, headers=headers, data=json.dumps(data))
            print(otp_code)  # For debugging (remove in production)
            
        except Exception as e:
            return Response({"error": f"Failed to send OTP: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # **Set cache to enforce rate limit (5 min = 300 seconds)**
        cache.set(cache_key, True, timeout=300)

        return Response({"message": "OTP sent successfully"})



class VerifyOTPView(APIView):
    """Verify the OTP sent to the user's phone."""
    def post(self, request):
        phone_number = request.data.get('phone_number')
        otp_code = request.data.get('code')

        if not phone_number or not otp_code:
            return Response({"error": "Phone number and OTP are required"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            print(phone_number)
            print(otp_code)
            print(type(phone_number))
            print(type(otp_code))
            otp_entry = OTP.objects.get(phone_number=phone_number, otp=otp_code)
            print(otp_entry)
            if otp_entry.is_valid():
                # # Delete the OTP after successful verification
                # otp_entry.delete()
                return Response({"verified": True}, status=status.HTTP_200_OK)
            return Response({"error": "OTP expired"}, status=status.HTTP_400_BAD_REQUEST)
        except OTP.DoesNotExist:
            return Response({"error": "Invalid OTP"}, status=status.HTTP_400_BAD_REQUEST)


class SignUpView(APIView):
    """Sign up a new student after OTP verification."""
    def post(self, request):
        phone_number = request.data.get('phone_number')
        first_name = request.data.get('first_name')
        last_name = request.data.get('last_name')
        student_number = request.data.get('student_number')
        password = request.data.get('password')

        # Ensure OTP verification exists
        verified = OTP.objects.filter(
            phone_number=phone_number, created_at__gte=now() - timedelta(minutes=5)
        ).exists()

        if not verified:
            return Response({"error": "OTP verification required"}, status=status.HTTP_400_BAD_REQUEST)

        # Check if user already exists
        if User.objects.filter(phone_number=phone_number).exists():
            return Response({"error": "User already exists"}, status=status.HTTP_400_BAD_REQUEST)

        # Create user
        user = User.objects.create_user(phone_number=phone_number, first_name=first_name, last_name=last_name, password=password, student_number=student_number, role='student')
        return Response({"message": "Student registered successfully", "phone_number": user.phone_number}, status=status.HTTP_201_CREATED)


class SignInView(APIView):
    """Sign in a user and return JWT tokens."""
    def post(self, request):
        phone_number = request.data.get('phone_number')
        password = request.data.get('password')

        user = authenticate(phone_number=phone_number, password=password)
        print(user)
        if not user:

            return Response({"error": "Invalid credentials"}, status=status.HTTP_401_UNAUTHORIZED)

        # Generate JWT tokens
        refresh = RefreshToken.for_user(user)
        return Response({
            "access_token": str(refresh.access_token),
            "refresh_token": str(refresh),
            "user": {
                "id": user.id,
                "phone_number": user.phone_number,
                "role": user.role
            }
        })


class SignOutView(APIView):
    """Log out by blacklisting the refresh token."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        refresh_token = request.data.get("refresh_token")
        if not refresh_token:
            return Response({"error": "Refresh token is required"}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            token = RefreshToken(refresh_token)
            token.blacklist()
            return Response({"message": "Logged out successfully"}, status=status.HTTP_205_RESET_CONTENT)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class RefreshTokenView(TokenRefreshView):
    """Refresh JWT tokens."""
    pass


class MeView(APIView):
    """Retrieve details of the current user."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        serializer = UserSerializer(user, context={'request': request})
        return Response(serializer.data)


class RequestPasswordResetView(APIView):
    """Send an OTP for password reset with rate limiting."""
    def post(self, request):
        phone_number = request.data.get('phone_number')

        if not phone_number:
            return Response({"error": "Phone number is required"}, status=status.HTTP_400_BAD_REQUEST)

        # Check if user exists
        if not User.objects.filter(phone_number=phone_number).exists():
            return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)

        # **Rate limit: Allow request only once every 5 minutes**
        cache_key = f"reset_password_limit:{phone_number}"
        if cache.get(cache_key):
            return Response({"error": "Too many requests. Please wait before requesting another OTP."},
                            status=status.HTTP_429_TOO_MANY_REQUESTS)

        # Generate OTP and send it
        otp_code = OTP.generate_otp()
        OTP.objects.create(phone_number=phone_number, otp=otp_code)

        # Send OTP via SMS
        try:
            url = "https://api.sms.ir/v1/send/verify"
            headers = {
                'Content-Type': 'application/json',
                'Accept': 'text/plain',
                'x-api-key': 'AvlnbwJn9oPDn9BCcbsyacENDj4qkeUnOJkf3zCIvIGIyJeS'
            }

            data = {
                "mobile": phone_number,
                "templateId": 123456,
                "parameters": [{"name": "Code", "value": otp_code}]
            }

            response = requests.post(url, headers=headers, data=json.dumps(data))

        except Exception as e:
            return Response({"error": f"Failed to send OTP: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # **Set cache to enforce rate limit (5 min = 300 seconds)**
        cache.set(cache_key, True, timeout=300)

        return Response({"message": "Password reset OTP sent successfully"})
    """Send an OTP for password reset."""
    def post(self, request):
        phone_number = request.data.get('phone_number')

        if not phone_number:
            return Response({"error": "Phone number is required"}, status=status.HTTP_400_BAD_REQUEST)

        # Check if user exists
        if not User.objects.filter(phone_number=phone_number).exists():
            return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)

        # Generate OTP and send it
        otp_code = OTP.generate_otp()
        OTP.objects.create(phone_number=phone_number, otp=otp_code)

        # Send OTP via SMS
        try:
            url = "https://api.sms.ir/v1/send/verify"
            headers = {
                'Content-Type': 'application/json',
                'Accept': 'text/plain',
                'x-api-key': 'AvlnbwJn9oPDn9BCcbsyacENDj4qkeUnOJkf3zCIvIGIyJeS'
            }

            # Define the request body
            data = {
                "mobile": phone_number,
                "templateId": 123456,
                "parameters": [
                    {
                        "name": "Code",
                        "value": otp_code
                    }
                ]
            }

            # Send the POST request
            response = requests.post(url, headers=headers, data=json.dumps(data))
            print(response)
            print(otp_code)
        except Exception as e:
            return Response({"error": f"Failed to send OTP: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response({"message": "Password reset OTP sent successfully"})


class ResetPasswordView(APIView):
    """Reset password using OTP."""
    def post(self, request):
        phone_number = request.data.get('phone_number')
        otp_code = request.data.get('otp')
        new_password = request.data.get('new_password')

        if not phone_number or not otp_code or not new_password:
            return Response({"error": "Phone number, OTP, and new password are required"},
                            status=status.HTTP_400_BAD_REQUEST)

        # Verify OTP
        try:
            otp_entry = OTP.objects.get(phone_number=phone_number, otp=otp_code)
            if otp_entry.is_valid():
                # Reset password
                try:
                    user = User.objects.get(phone_number=phone_number)
                    user.set_password(new_password)
                    user.save()

                    # Delete OTP after successful use
                    otp_entry.delete()

                    return Response({"message": "Password reset successfully"})
                except User.DoesNotExist:
                    return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)
            return Response({"error": "OTP expired"}, status=status.HTTP_400_BAD_REQUEST)
        except OTP.DoesNotExist:
            return Response({"error": "Invalid OTP"}, status=status.HTTP_400_BAD_REQUEST)

class UserProfileUpdateView(APIView):
    permission_classes = [IsAuthenticated]

    def put(self, request):
        user = request.user
        serializer = UserProfileUpdateSerializer(user, data=request.data, partial=True)
        print(request.data)
        if serializer.is_valid():
            serializer.save()
            return Response({"message": "Profile updated successfully"}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    

class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        current_password = request.data.get('currentPassword')
        new_password = request.data.get('newPassword')

        if not current_password or not new_password:
            print({"error": "Current password and new password are required"})
            return Response({"error": "Current password and new password are required"},
                            status=status.HTTP_400_BAD_REQUEST)

        if not user.check_password(current_password):
            print({"error": "Current password is incorrect"})
            return Response({"error": "Current password is incorrect"},
                            status=status.HTTP_400_BAD_REQUEST)

        user.set_password(new_password)
        user.save()
        return Response({"message": "Password changed successfully"}, status=status.HTTP_200_OK)
    

class CheckPhoneNumberView(APIView):
    """Check if a phone number is registered in the system."""
    def post(self, request):
        phone_number = request.data.get('phone_number')

        if not phone_number:
            return Response({"error": "Phone number is required"}, status=status.HTTP_400_BAD_REQUEST)

        # Validate phone number format
        if not re.match(r'^(?:\+98|0)?9\d{9}$', phone_number):
            return Response({"error": "Invalid phone number format"}, status=status.HTTP_400_BAD_REQUEST)

        # Check if phone number exists
        exists = User.objects.filter(phone_number=phone_number).exists()

        return Response({"exists": exists}, status=status.HTTP_200_OK)
    
class CheckStudentNumberView(APIView):
    """Check if a student number is registered in the system."""
    def post(self, request):
        student_number = request.data.get('student_number')

        if not student_number:
            return Response({"error": "Student number is required"}, status=status.HTTP_400_BAD_REQUEST)

        # Ensure student number is numeric and has a valid length
        if not student_number.isdigit() or len(student_number) < 5:
            return Response({"error": "Invalid student number format"}, status=status.HTTP_400_BAD_REQUEST)

        # Check if the student number exists
        exists = User.objects.filter(student_number=student_number).exists()

        return Response({"exists": exists}, status=status.HTTP_200_OK)
