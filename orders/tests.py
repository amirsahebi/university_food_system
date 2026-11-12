from django.test import TestCase
from django.utils import timezone
from datetime import time, timedelta
from rest_framework.test import APIClient
from rest_framework import status
from django.urls import reverse

from users.models import User
from food.models import Food, FoodCategory
from menu.models import DailyMenu, DailyMenuItem, TimeSlot
from core.models import VoucherType
from orders.models import Reservation
from orders.serializers import CreateReservationSerializer
from rest_framework.exceptions import ValidationError


class TrustScoreAndLoyaltyTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()

        # Create student user
        self.student = User.objects.create_user(
            phone_number='09120000001',
            first_name='Ali',
            last_name='Rezaei',
            role='student',
            student_number='99123456',
            password='testpass123',
            trust_score=10
        )

        # Create admin user
        self.admin = User.objects.create_superuser(
            phone_number='09120000002',
            first_name='Admin',
            last_name='User',
            role='admin',
            password='adminpass123'
        )

        # Create food category and food
        self.category = FoodCategory.objects.create(name='Traditional')
        self.voucher_type = VoucherType.objects.create(
            code='type_1',
            name='ژتون دولتی',
            discount_amount=20000,
            is_active=True
        )
        self.food = Food.objects.create(
            name='چلو جوجه کباب',
            price=100000,
            category=self.category,
            supports_extra_voucher=True
        )
        self.food.allowed_vouchers.add(self.voucher_type)

        # Create menu and time slots
        today = timezone.localdate()
        self.daily_menu = DailyMenu.objects.create(
            date=today,
            meal_type='lunch'
        )
        self.menu_item = DailyMenuItem.objects.create(
            daily_menu=self.daily_menu,
            food=self.food,
            start_time=time(12, 0),
            end_time=time(14, 0),
            time_slot_count=2,
            time_slot_capacity=50,
            daily_capacity=100
        )
        self.time_slot = TimeSlot.objects.create(
            daily_menu_item=self.menu_item,
            start_time=time(12, 0),
            end_time=time(13, 0),
            capacity=50
        )

    def _create_reservation(self, student, price, original_price=None, has_voucher=False, voucher_type=None, has_extra_voucher=False):
        orig_price = original_price if original_price is not None else price
        return Reservation.objects.create(
            student=student,
            food=self.food,
            time_slot=self.time_slot,
            reserved_date=self.daily_menu.date,
            meal_type='lunch',
            status='ready_to_pickup',
            price=price,
            original_price=orig_price,
            has_voucher=has_voucher,
            voucher_type=voucher_type,
            has_extra_voucher=has_extra_voucher
        )

    def test_cumulative_spending_awards_points(self):
        """
        Verify that spending accumulates across multiple orders,
        and exactly +1 trust score is awarded for every 100,000 Tomans of cumulative payments.
        """
        self.assertEqual(self.student.trust_score, 10)
        self.assertEqual(self.student.total_spent, 0)
        self.assertEqual(self.student.loyalty_points_awarded, 0)

        # Order 1: 40,000 Tomans
        order1 = self._create_reservation(self.student, price=40000)
        order1.status = 'picked_up'
        order1.save()

        self.student.refresh_from_db()
        self.assertEqual(self.student.total_spent, 40000)
        self.assertEqual(self.student.loyalty_points_awarded, 0)
        self.assertEqual(self.student.trust_score, 10, "Score should not increase yet (spent 40k < 100k)")

        # Order 2: 70,000 Tomans -> Total = 110,000 Tomans (crosses 100k)
        order2 = self._create_reservation(self.student, price=70000)
        order2.status = 'picked_up'
        order2.save()

        self.student.refresh_from_db()
        self.assertEqual(self.student.total_spent, 110000)
        self.assertEqual(self.student.loyalty_points_awarded, 1)
        self.assertEqual(self.student.trust_score, 11, "Score should increase by +1 upon crossing 100k")

        # Order 3: 150,000 Tomans -> Total = 260,000 Tomans (crosses 200k)
        order3 = self._create_reservation(self.student, price=150000)
        order3.status = 'picked_up'
        order3.save()

        self.student.refresh_from_db()
        self.assertEqual(self.student.total_spent, 260000)
        self.assertEqual(self.student.loyalty_points_awarded, 2)
        self.assertEqual(self.student.trust_score, 12, "Score should increase by +1 upon crossing 200k")

    def test_free_order_does_not_award_points(self):
        """
        An order with price=0 (e.g., 100% voucher discount) must not award loyalty points.
        """
        order = self._create_reservation(self.student, price=0, has_voucher=True, voucher_type=self.voucher_type)
        order.status = 'picked_up'
        order.save()

        self.student.refresh_from_db()
        self.assertEqual(self.student.total_spent, 0)
        self.assertEqual(self.student.loyalty_points_awarded, 0)
        self.assertEqual(self.student.trust_score, 10)

    def test_penalty_for_not_picked_up_with_voucher(self):
        """
        Failing to pick up an order with a voucher must incur -10 penalty.
        With extra voucher, penalty must be -20.
        """
        # Regular voucher penalty
        order1 = self._create_reservation(
            self.student, price=80000, has_voucher=True, voucher_type=self.voucher_type
        )
        order1.status = 'not_picked_up'
        order1.save()

        self.student.refresh_from_db()
        self.assertEqual(self.student.trust_score, 0, "Score should drop by 10 (from 10 to 0)")

        # Extra voucher penalty (-20 total)
        order2 = self._create_reservation(
            self.student, price=60000, has_voucher=True, voucher_type=self.voucher_type, has_extra_voucher=True
        )
        order2.status = 'not_picked_up'
        order2.save()

        self.student.refresh_from_db()
        self.assertEqual(self.student.trust_score, -20, "Score should drop by 20 (from 0 to -20)")

    def test_negative_trust_score_blocks_voucher_orders(self):
        """
        When student trust score is negative, creating an order with a voucher must be rejected.
        """
        self.student.trust_score = -5
        self.student.save()

        serializer = CreateReservationSerializer(
            data={
                'food': self.food.id,
                'time_slot': self.time_slot.id,
                'reserved_date': self.daily_menu.date,
                'meal_type': 'lunch',
                'has_voucher': True,
                'voucher_type': self.voucher_type.id
            },
            context={'request': type('Req', (), {'user': self.student})()}
        )
        with self.assertRaises(ValidationError):
            serializer.is_valid(raise_exception=True)

    def test_negative_trust_score_allows_full_price_orders(self):
        """
        When student trust score is negative, full-price orders (without voucher) MUST be allowed.
        """
        self.student.trust_score = -5
        self.student.save()

        serializer = CreateReservationSerializer(
            data={
                'food': self.food.id,
                'time_slot': self.time_slot.id,
                'reserved_date': self.daily_menu.date,
                'meal_type': 'lunch',
                'has_voucher': False,
                'voucher_type': None
            },
            context={'request': type('Req', (), {'user': self.student})()}
        )
        self.assertTrue(serializer.is_valid(), f"Serializer errors: {serializer.errors}")

    def test_admin_reset_negative_trust_score(self):
        """
        Admin endpoint `/auth/trust-score/recover/` resets negative trust score to 0.
        """
        self.student.trust_score = -8
        self.student.save()

        self.client.force_authenticate(user=self.admin)
        url = reverse('admin_trust_score_recover')
        response = self.client.post(url, {'student_id': self.student.id}, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.student.refresh_from_db()
        self.assertEqual(self.student.trust_score, 0, "Trust score should be reset to 0 by admin")

    def test_no_auto_daily_recovery(self):
        """
        Automatic daily recovery must be inactive: negative score stays negative.
        """
        self.student.trust_score = -6
        self.student.save()

        updated = self.student.recover_trust_score_daily()
        self.assertFalse(updated)

        self.student.refresh_from_db()
        self.assertEqual(self.student.trust_score, -6, "Score must remain negative without auto-recovery")
