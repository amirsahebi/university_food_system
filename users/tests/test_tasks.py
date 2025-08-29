from datetime import timedelta
from unittest.mock import patch, MagicMock, call
from django.test import TestCase, override_settings
from django.utils import timezone
from django.conf import settings
from django.contrib.auth import get_user_model
from freezegun import freeze_time
from users.models import OTP
from users.tasks import delete_expired_otps, recover_trust_scores_daily

User = get_user_model()

class UserTasksTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            phone_number='09123456789',
            first_name='Test',
            last_name='User',
            role='student',
            student_number='12345',
            password='testpass123',
            trust_score=80
        )
        self.otp = OTP.objects.create(
            phone_number='09123456789',
            otp='123456',
            created_at=timezone.now() - timedelta(minutes=31)  # Already expired
        )

    @freeze_time("2025-01-01 12:00:00+00:00")
    def test_delete_expired_otps(self):
        from django.utils import timezone
        from datetime import datetime, timedelta, timezone as tz
        
        # Get the current time (frozen by freezegun)
        current_time = timezone.now()
        expiration_time = current_time - timedelta(minutes=5)
        
        print(f"\n{'='*80}")
        print(f"TEST: Starting OTP deletion test")
        print(f"Current time (test): {current_time}")
        print(f"Expiration time: {expiration_time} (OTPs older than this should be deleted)")
        
        # Create an OTP that's 10 minutes old (should be deleted)
        expired_time = current_time - timedelta(minutes=10)
        with freeze_time(expired_time):
            expired_otp = OTP.objects.create(
                phone_number='09123456789',
                otp='123456'
            )
            print(f"Created expired OTP at {expired_otp.created_at} (should be before {expiration_time})")
        
        # Create a non-expired OTP (1 minute old)
        valid_time = current_time - timedelta(minutes=1)
        with freeze_time(valid_time):
            valid_otp = OTP.objects.create(
                phone_number='09123456789',
                otp='654321'
            )
            print(f"Created valid OTP at {valid_otp.created_at} (should be after {expiration_time})")
        
        # Verify both OTPs exist initially
        self.assertTrue(
            OTP.objects.filter(otp='123456', created_at=expired_time).exists(),
            "Expired OTP should exist before deletion"
        )
        self.assertTrue(
            OTP.objects.filter(otp='654321', created_at=valid_time).exists(),
            "Valid OTP should exist before deletion"
        )
        
        # Print all OTPs in database before deletion
        all_otps_before = OTP.objects.all()
        print("\nOTPs in database before deletion:")
        for otp in all_otps_before:
            print(f"- OTP {otp.otp} created at {otp.created_at}")
        
        # Run the task with the frozen time
        print("\nRunning delete_expired_otps task...")
        result = delete_expired_otps()
        print(f"Task result: {result}")
        
        # Print all OTPs in database after deletion
        all_otps_after = OTP.objects.all()
        print("\nOTPs in database after deletion:")
        for otp in all_otps_after:
            print(f"- OTP {otp.otp} created at {otp.created_at}")
        
        # Check that expired OTP was deleted
        self.assertFalse(
            OTP.objects.filter(otp='123456', created_at=expired_time).exists(),
            "Expired OTP should have been deleted"
        )
        
        # Check that valid OTP still exists
        self.assertTrue(
            OTP.objects.filter(otp='654321', created_at=valid_time).exists(),
            "Valid OTP should still exist"
        )
        
        # Check the task result
        self.assertEqual(
            result, 
            "1 expired OTP(s) deleted.",
            "Task should report 1 OTP was deleted"
        )
        
        print("\nTest completed successfully!")
        print(f"{'='*80}\n")

    @override_settings(TRUST_SCORE_RECOVERY_RATE=2)
    @patch('users.models.User.recover_trust_score_daily')
    def test_recover_trust_scores_daily(self, mock_recover):
        # Create test users with different trust scores
        user1 = User.objects.create_user(
            phone_number='09121111111',
            first_name='User1',
            last_name='Test',
            role='student',
            student_number='11111',
            password='testpass123',
            trust_score=-3
        )
        
        User.objects.create_user(
            phone_number='09122222222',
            first_name='User2',
            last_name='Test',
            role='student',
            student_number='22222',
            password='testpass123',
            trust_score=5  # Positive score, should be skipped
        )
        
        # Set up mock return values
        mock_recover.return_value = True
        
        # Run the task
        result = recover_trust_scores_daily()
        
        # Check the task result
        self.assertEqual(result['status'], 'success')
        self.assertEqual(result['users_processed'], 1)  # Only user1 should be processed
        self.assertEqual(result['users_recovered'], 1)  # Only user1 should be recovered
        
        # Verify the method was called with the correct recovery rate
        mock_recover.assert_called_once_with(recovery_rate=2)
