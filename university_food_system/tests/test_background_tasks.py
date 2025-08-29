from datetime import datetime, timedelta
from django.test import TestCase
from django.utils import timezone
from unittest.mock import patch, MagicMock
from django.contrib.auth import get_user_model
from orders.models import Reservation
from food.models import Food, FoodCategory
from menu.models import DailyMenu, DailyMenuItem, TimeSlot
from university_food_system.tasks.background_tasks import cancel_pending_payment_reservations

User = get_user_model()

class BackgroundTasksTestCase(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Set up test data once for all test methods
        cls.user = get_user_model().objects.create_user(
            phone_number='09123456789',
            password='testpass123',
            email='test@example.com',
            role='student'
        )
        
        # Create test food category
        cls.category = FoodCategory.objects.create(
            name='Test Category',
            description='Test Description'
        )
        
        # Create test food
        cls.food = Food.objects.create(
            name='Test Food',
            description='Test Description',
            price=10000,
            category=cls.category,
            supports_extra_voucher=False
        )
        
        # Create test daily menu
        cls.daily_menu = DailyMenu.objects.create(
            date=timezone.now().date(),
            meal_type='lunch'
        )
        
        # Create test daily menu item
        cls.daily_menu_item = DailyMenuItem.objects.create(
            daily_menu=cls.daily_menu,
            food=cls.food,
            start_time=timezone.now().time(),
            end_time=(timezone.now() + timezone.timedelta(hours=1)).time(),
            time_slot_count=3,
            time_slot_capacity=10,
            daily_capacity=30,
            is_available=True
        )
        
        # Create a time slot for the reservation
        cls.time_slot = TimeSlot.objects.create(
            daily_menu_item=cls.daily_menu_item,
            start_time='12:00:00',
            end_time='13:00:00',
            capacity=100,
            is_available=True
        )

    def setUp(self):
        # Set a fixed current time for the test
        self.now = timezone.make_aware(datetime(2025, 1, 1, 12, 0, 0))
        
        # Set up timestamps relative to the mocked current time
        current_time = self.now
        expiration_time = current_time - timezone.timedelta(minutes=10)
        
        # Create a pending payment reservation that's older than 10 minutes (11 minutes old)
        pending_created_at = current_time - timezone.timedelta(minutes=11)
        self.pending_reservation = Reservation.objects.create(
            student=self.user,
            food=self.food,
            time_slot=self.time_slot,
            meal_type='lunch',
            reserved_date=current_time.date(),
            has_voucher=False,
            has_extra_voucher=False,
            price=10000,  # Example price
            status='pending_payment',
        )
        # Update created_at after creation to bypass auto_now_add
        Reservation.objects.filter(pk=self.pending_reservation.pk).update(created_at=pending_created_at)
        self.pending_reservation.refresh_from_db()
        
        # Create a recent pending payment reservation that shouldn't be cancelled (5 minutes old)
        recent_created_at = current_time - timezone.timedelta(minutes=5)
        self.recent_reservation = Reservation.objects.create(
            student=self.user,
            food=self.food,
            time_slot=self.time_slot,
            meal_type='lunch',
            reserved_date=current_time.date(),
            has_voucher=False,
            has_extra_voucher=False,
            price=10000,  # Example price
            status='pending_payment',
        )
        # Update created_at after creation to bypass auto_now_add
        Reservation.objects.filter(pk=self.recent_reservation.pk).update(created_at=recent_created_at)
        self.recent_reservation.refresh_from_db()
        
        # Log the timestamps for debugging
        print(f"Pending reservation created at: {self.pending_reservation.created_at} (should be before {expiration_time})")
        print(f"Recent reservation created at: {self.recent_reservation.created_at} (should be after {expiration_time})")

    @patch('django.utils.timezone.now')
    def test_cancel_pending_payment_reservations(self, mock_now):
        """Test that pending payment reservations older than 10 minutes are cancelled."""
        # Set the fixed time for the test
        mock_now.return_value = self.now
        
        print("\n" + "="*80)
        print("TEST: Starting pending payment cancellation test")
        print(f"Current time (test): {self.now}")
        
        # Calculate the expiration time (10 minutes before now)
        expiration_time = self.now - timedelta(minutes=10)
        print(f"Expiration time: {expiration_time} (reservations older than this should be cancelled)")
        
        # Print the created_at times for debugging
        print(f"Pending reservation created at: {self.pending_reservation.created_at} (should be before {expiration_time})")
        print(f"Recent reservation created at: {self.recent_reservation.created_at} (should be after {expiration_time})")
        
        # Verify the test data is set up correctly
        self.assertLess(self.pending_reservation.created_at, expiration_time,
                       f"Pending reservation should be older than {expiration_time} but is {self.pending_reservation.created_at}")
        
        self.assertGreater(self.recent_reservation.created_at, expiration_time,
                          f"Recent reservation should be newer than {expiration_time} but is {self.recent_reservation.created_at}")
        
        # Call the task
        with patch('university_food_system.tasks.background_tasks.timezone.now', return_value=self.now):
            result = cancel_pending_payment_reservations()
        
        # Verify the task completed successfully
        self.assertEqual(result, '1 pending payment reservations cancelled.')
        
        # Refresh the reservations from the database
        self.pending_reservation.refresh_from_db()
        self.recent_reservation.refresh_from_db()
        
        # Log the status of the reservations after the task
        print(f"\nAfter task execution:")
        print(f"- Pending reservation status: {self.pending_reservation.status}")
        print(f"- Recent reservation status: {self.recent_reservation.status}")
        
        # Verify the old pending payment reservation was cancelled
        self.assertEqual(self.pending_reservation.status, 'cancelled',
                        f"Expected status 'cancelled' but got '{self.pending_reservation.status}'")
        
        # Verify the recent pending payment reservation was not cancelled
        self.assertEqual(self.recent_reservation.status, 'pending_payment',
                        f"Expected status 'pending_payment' but got '{self.recent_reservation.status}'")
        
        print("Test completed successfully!")
        print("="*80)
