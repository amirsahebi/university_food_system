import json
from decimal import Decimal
from datetime import datetime, time, timedelta
import pytz

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase, APIClient
from django.utils import timezone

from payments.models import Payment, Wallet, WalletTransaction
from orders.models import Reservation
from food.models import Food
from menu.models import DailyMenu, DailyMenuItem, TimeSlot

IRAN_TZ = pytz.timezone("Asia/Tehran")


class WalletSystemTestCase(APITestCase):
    def setUp(self):
        self.client = APIClient()
        User = get_user_model()
        self.user = User.objects.create_user(
            phone_number="09121112233", password="testpassword123", role="student",
            first_name="Ali", last_name="Rezaei", student_number="99123456"
        )
        self.client.force_authenticate(user=self.user)

        self.food = Food.objects.create(name="زرشک پلو با مرغ", price=Decimal("50000.00"))
        
        # Tomorrow's menu
        tomorrow = timezone.now().astimezone(IRAN_TZ).date() + timedelta(days=1)
        self.tomorrow_menu = DailyMenu.objects.create(date=tomorrow, meal_type="lunch")
        self.tomorrow_dmi = DailyMenuItem.objects.create(
            daily_menu=self.tomorrow_menu,
            food=self.food,
            start_time=time(12, 0),
            end_time=time(14, 0),
            time_slot_count=2,
            time_slot_capacity=10,
            daily_capacity=20,
        )
        self.tomorrow_slot = TimeSlot.objects.create(
            daily_menu_item=self.tomorrow_dmi,
            start_time=time(12, 0),
            end_time=time(13, 0),
            capacity=10,
        )

        # Today's menu
        today = timezone.now().astimezone(IRAN_TZ).date()
        self.today_menu = DailyMenu.objects.create(date=today, meal_type="lunch")

    def test_wallet_creation_and_deposit_withdraw(self):
        wallet = Wallet.get_or_create_wallet(self.user)
        self.assertEqual(wallet.balance, 0)

        # Test deposit
        tx1 = wallet.deposit(100000, transaction_type=WalletTransaction.TYPE_DEPOSIT, description="شارژ تستی")
        self.assertEqual(wallet.balance, 100000)
        self.assertEqual(tx1.amount, 100000)
        self.assertEqual(tx1.balance_after, 100000)

        # Test withdraw
        tx2 = wallet.withdraw(30000, transaction_type=WalletTransaction.TYPE_ORDER_PAYMENT, description="خرید تستی")
        self.assertEqual(wallet.balance, 70000)
        self.assertEqual(tx2.amount, -30000)
        self.assertEqual(tx2.balance_after, 70000)

        # Test overdraft prevention
        with self.assertRaises(ValueError):
            wallet.withdraw(100000)
        self.assertEqual(wallet.balance, 70000)

    def test_get_my_wallet_api(self):
        wallet = Wallet.get_or_create_wallet(self.user)
        wallet.deposit(50000, description="شارژ اولیه")

        url = reverse("payments:my-wallet")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["balance"], 50000)
        self.assertEqual(len(response.data["transactions"]), 1)

    def test_pay_order_with_wallet_success(self):
        wallet = Wallet.get_or_create_wallet(self.user)
        wallet.deposit(100000, description="شارژ برای خرید")

        reservation = Reservation.objects.create(
            student=self.user,
            food=self.food,
            time_slot=self.tomorrow_slot,
            meal_type="lunch",
            reserved_date=self.tomorrow_menu.date,
            price=Decimal("50000.00"),
            status="pending_payment"
        )

        url = reverse("payments:wallet-pay-order")
        response = self.client.post(url, {"reservation_id": reservation.id})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["success"])

        reservation.refresh_from_db()
        self.assertEqual(reservation.status, "waiting")

        wallet.refresh_from_db()
        self.assertEqual(wallet.balance, 50000)

        # Check payment record created
        payment = Payment.objects.filter(reservation=reservation, status="paid").first()
        self.assertIsNotNone(payment)
        self.assertEqual(payment.amount, 50000)

    def test_pay_order_with_wallet_insufficient_funds(self):
        wallet = Wallet.get_or_create_wallet(self.user)
        wallet.deposit(20000)

        reservation = Reservation.objects.create(
            student=self.user,
            food=self.food,
            time_slot=self.tomorrow_slot,
            meal_type="lunch",
            reserved_date=self.tomorrow_menu.date,
            price=Decimal("50000.00"),
            status="pending_payment"
        )

        url = reverse("payments:wallet-pay-order")
        response = self.client.post(url, {"reservation_id": reservation.id})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("موجودی کیف پول شما کافی نیست", response.data["error"])
        self.assertEqual(response.data["shortage"], 30000)

    def test_cancel_future_order_refunds_wallet_and_restores_capacity(self):
        wallet = Wallet.get_or_create_wallet(self.user)
        self.assertEqual(wallet.balance, 0)

        initial_slot_capacity = self.tomorrow_slot.capacity
        initial_daily_capacity = self.tomorrow_dmi.daily_capacity

        reservation = Reservation.objects.create(
            student=self.user,
            food=self.food,
            time_slot=self.tomorrow_slot,
            meal_type="lunch",
            reserved_date=self.tomorrow_menu.date,
            price=Decimal("50000.00"),
            original_price=Decimal("50000.00"),
            status="waiting"
        )

        url = reverse("cancel_order", kwargs={"id": reservation.id})
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["success"])
        self.assertEqual(response.data["refunded_amount"], 50000)

        # Verify wallet balance
        wallet.refresh_from_db()
        self.assertEqual(wallet.balance, 50000)

        # Verify refund transaction
        tx = WalletTransaction.objects.filter(wallet=wallet, transaction_type=WalletTransaction.TYPE_ORDER_REFUND).first()
        self.assertIsNotNone(tx)
        self.assertEqual(tx.amount, 50000)

        # Verify reservation status
        reservation.refresh_from_db()
        self.assertEqual(reservation.status, "cancelled")

        # Verify capacity restored
        self.tomorrow_slot.refresh_from_db()
        self.tomorrow_dmi.refresh_from_db()
        self.assertEqual(self.tomorrow_slot.capacity, initial_slot_capacity)
        self.assertEqual(self.tomorrow_dmi.daily_capacity, initial_daily_capacity)

    def test_cancel_today_order_after_earliest_food_start_time_blocked(self):
        # Create a food whose earliest start_time has already passed
        iran_now = timezone.now().astimezone(IRAN_TZ)
        past_time = (iran_now - timedelta(minutes=30)).time()
        
        today_dmi = DailyMenuItem.objects.create(
            daily_menu=self.today_menu,
            food=self.food,
            start_time=past_time,
            end_time=(iran_now + timedelta(hours=2)).time(),
            time_slot_count=1,
            time_slot_capacity=10,
            daily_capacity=10,
        )
        today_slot = TimeSlot.objects.create(
            daily_menu_item=today_dmi,
            start_time=past_time,
            end_time=(iran_now + timedelta(hours=2)).time(),
            capacity=10,
        )

        reservation = Reservation.objects.create(
            student=self.user,
            food=self.food,
            time_slot=today_slot,
            meal_type="lunch",
            reserved_date=self.today_menu.date,
            price=Decimal("40000.00"),
            status="waiting"
        )

        url = reverse("cancel_order", kwargs={"id": reservation.id})
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("فرآیند توزیع این غذا در سلف", response.data["error"])

    def test_cancel_today_order_before_earliest_food_start_time_allowed(self):
        # Create a food whose earliest start_time is in the future today
        iran_now = timezone.now().astimezone(IRAN_TZ)
        future_start = (iran_now + timedelta(hours=2)).time()
        future_end = (iran_now + timedelta(hours=3)).time()

        today_dmi = DailyMenuItem.objects.create(
            daily_menu=self.today_menu,
            food=self.food,
            start_time=future_start,
            end_time=future_end,
            time_slot_count=1,
            time_slot_capacity=10,
            daily_capacity=10,
        )
        today_slot = TimeSlot.objects.create(
            daily_menu_item=today_dmi,
            start_time=future_start,
            end_time=future_end,
            capacity=10,
        )

        wallet = Wallet.get_or_create_wallet(self.user)
        reservation = Reservation.objects.create(
            student=self.user,
            food=self.food,
            time_slot=today_slot,
            meal_type="lunch",
            reserved_date=self.today_menu.date,
            price=Decimal("50000.00"),
            original_price=Decimal("50000.00"),
            status="waiting"
        )

        url = reverse("cancel_order", kwargs={"id": reservation.id})
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["success"])

        wallet.refresh_from_db()
        self.assertEqual(wallet.balance, 50000)
