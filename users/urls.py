from django.urls import path
from .views import (
    SendOTPView, VerifyOTPView, SignUpView, SignInView,
    SignOutView, RefreshTokenView, MeView,
    RequestPasswordResetView, ResetPasswordView, UserProfileUpdateView,
    ChangePasswordView, CheckPhoneNumberView, CheckStudentNumberView, TrustScoreView,
    AdminTrustScoreRecoveryView, StudentListCreateAPIView, StudentRetrieveUpdateDestroyAPIView
)


urlpatterns = [
    # Authentication endpoints
    path('signup/', SignUpView.as_view(), name='sign_up'),
    path('signin/', SignInView.as_view(), name='sign_in'),
    path('signout/', SignOutView.as_view(), name='sign_out'),
    path('refresh/', RefreshTokenView.as_view(), name='refresh_token'),
    path('me/', MeView.as_view(), name='me'),
    
    # Verification endpoints
    path('send-verification-code/', SendOTPView.as_view(), name='send_verification_code'),
    path('verify-code/', VerifyOTPView.as_view(), name='verify_code'),
    
    # Password management endpoints
    path('request-password-reset/', RequestPasswordResetView.as_view(), name='request_password_reset'),
    path('reset-password/', ResetPasswordView.as_view(), name='reset_password'),
    path('change-password/', ChangePasswordView.as_view(), name='change_password'),
    
    # Profile endpoints
    path('profile/update/', UserProfileUpdateView.as_view(), name='profile_update'),
    
    # Validation endpoints
    path('check-phone-number/', CheckPhoneNumberView.as_view(), name='check_phone_number'),
    path('check-student-number/', CheckStudentNumberView.as_view(), name='check_student_number'),
    
    # Trust score endpoints
    path('trust-score/', TrustScoreView.as_view(), name='trust_score'),
    path('trust-score/recover/', AdminTrustScoreRecoveryView.as_view(), name='admin_trust_score_recover'),
    
    # Student management endpoints
    path('students/', StudentListCreateAPIView.as_view(), name='student-list'),
    path('students/<int:pk>/', StudentRetrieveUpdateDestroyAPIView.as_view(), name='student-detail'),
]
