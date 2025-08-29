import json
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase, APIClient

from payments.models import Payment
from orders.models import Reservation
from food.models import Food
from menu.models import DailyMenu, DailyMenuItem, TimeSlot
from django.utils import timezone


class PaymentsViewsTestCase(APITestCase):
    def setUp(self):
        self.client = APIClient()
        User = get_user_model()
        # Create users
        self.user = User.objects.create_user(
            phone_number="09120000001", password="pass1234", role="student",
            first_name="A", last_name="B"
        )
        self.admin = User.objects.create_user(
            phone_number="09120000002", password="pass1234", role="admin",
            first_name="Admin", last_name="User", is_staff=True, is_superuser=True
        )

        # Common menu/food setup
        self.food = Food.objects.create(name="Kebab", price=Decimal("100000.00"))
        self.daily_menu = DailyMenu.objects.create(date=timezone.now().date(), meal_type="lunch")
        self.dmi = DailyMenuItem.objects.create(
            daily_menu=self.daily_menu,
            food=self.food,
            start_time=timezone.now().time(),
            end_time=(timezone.now() + timezone.timedelta(hours=1)).time(),
            time_slot_count=1,
            time_slot_capacity=10,
            daily_capacity=100,
        )
        self.time_slot = TimeSlot.objects.create(
            daily_menu_item=self.dmi,
            start_time=self.dmi.start_time,
            end_time=self.dmi.end_time,
            capacity=10,
        )

    def _create_reservation(self, price=Decimal("100000.00")):
        # Adjust food price for this reservation scenario
        self.food.price = Decimal(price)
        self.food.save()
        return Reservation.objects.create(
            student=self.user,
            food=self.food,
            time_slot=self.time_slot,
            meal_type="lunch",
            reserved_date=self.daily_menu.date,
            has_voucher=False,
            has_extra_voucher=False,
            price=Decimal(price),
            original_price=Decimal(price),
            status="pending_payment",
        )

    def test_payment_start_redirects(self):
        authority = "A123"
        url = reverse("payments:payment_start", args=[authority])
        resp = self.client.get(url)
        self.assertIn(resp.status_code, (301, 302))
        self.assertTrue(resp.headers.get("Location", "").endswith(authority))

    @patch("payments.views.request_payment")
    def test_payment_request_success_creates_payment(self, mock_request_payment):
        reservation = self._create_reservation(price=Decimal("50000.00"))
        mock_request_payment.return_value = {"data": {"code": 100, "authority": "AUTH123"}}

        self.client.force_authenticate(self.user)
        url = reverse("payments:payment-request")
        payload = {"callback_url": "https://example.com/callback", "reservation_id": reservation.id}
        resp = self.client.post(url, data=payload, format="json")

        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertIn("redirect_url", resp.data)
        self.assertTrue(Payment.objects.filter(authority="AUTH123", user=self.user, reservation_id=reservation.id).exists())

    def test_payment_request_free_reservation_sets_waiting(self):
        reservation = self._create_reservation(price=Decimal("0.00"))

        self.client.force_authenticate(self.user)
        url = reverse("payments:payment-request")
        payload = {"callback_url": "https://example.com/callback", "reservation_id": reservation.id}
        resp = self.client.post(url, data=payload, format="json")

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        reservation.refresh_from_db()
        self.assertEqual(reservation.status, "waiting")
        self.assertEqual(resp.data.get("status"), "waiting")

    def test_payment_request_reservation_not_found(self):
        self.client.force_authenticate(self.user)
        url = reverse("payments:payment-request")
        payload = {"callback_url": "https://example.com/callback", "reservation_id": 999999}
        resp = self.client.post(url, data=payload, format="json")
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    @patch("payments.views.verify_payment")
    def test_payment_verify_success(self, mock_verify):
        reservation = self._create_reservation(price=Decimal("50000.00"))
        payment = Payment.objects.create(
            user=self.user, reservation=reservation, amount=50000, authority="AUTH_OK", status="pending"
        )
        mock_verify.return_value = {"data": {"code": 100, "ref_id": "REF123"}}

        self.client.force_authenticate(self.user)
        url = reverse("payments:payment-verify") + "?Authority=AUTH_OK&Status=OK"
        resp = self.client.get(url)

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        payment.refresh_from_db(); reservation.refresh_from_db()
        self.assertEqual(payment.status, "paid")
        self.assertEqual(payment.ref_id, "REF123")
        self.assertEqual(reservation.status, "waiting")
        self.assertTrue(resp.data.get("success"))

    @patch("payments.views.verify_payment")
    def test_payment_verify_already_paid_idempotent(self, mock_verify):
        reservation = self._create_reservation(price=Decimal("50000.00"))
        payment = Payment.objects.create(
            user=self.user, reservation=reservation, amount=50000, authority="AUTH_PAID", status="paid", ref_id="R1"
        )
        # verify should not even be called due to early return
        mock_verify.return_value = {"data": {"code": 100, "ref_id": "REF123"}}

        self.client.force_authenticate(self.user)
        url = reverse("payments:payment-verify") + "?Authority=AUTH_PAID&Status=OK"
        resp = self.client.get(url)

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data.get("status"), "paid")
        payment.refresh_from_db()
        self.assertEqual(payment.ref_id, "R1")  # unchanged

    @patch("payments.views.verify_payment")
    def test_payment_verify_failure_marks_failed_and_cancels(self, mock_verify):
        reservation = self._create_reservation(price=Decimal("50000.00"))
        payment = Payment.objects.create(
            user=self.user, reservation=reservation, amount=50000, authority="AUTH_FAIL", status="pending"
        )
        mock_verify.return_value = {"data": {"code": 102}}

        self.client.force_authenticate(self.user)
        url = reverse("payments:payment-verify") + "?Authority=AUTH_FAIL&Status=OK"
        resp = self.client.get(url)

        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        payment.refresh_from_db(); reservation.refresh_from_db()
        self.assertEqual(payment.status, "failed")
        self.assertEqual(reservation.status, "cancelled")

    def test_payment_verify_payment_not_found(self):
        self.client.force_authenticate(self.user)
        url = reverse("payments:payment-verify") + "?Authority=AUTH_NONE&Status=OK"
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_payment_history_lists_and_filters(self):
        # Create payments for user
        reservation = self._create_reservation(price=Decimal("50000.00"))
        Payment.objects.create(user=self.user, reservation=reservation, amount=50000, authority="A1", status="paid")
        Payment.objects.create(user=self.user, reservation=reservation, amount=50000, authority="A2", status="failed")

        self.client.force_authenticate(self.user)
        url = reverse("payments:payment-history")
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(resp.data.get("count", 0), 2)

        # Filter by status
        resp2 = self.client.get(url + "?status=paid")
        self.assertEqual(resp2.status_code, status.HTTP_200_OK)
        for item in resp2.data.get("results", []):
            self.assertEqual(item["status"], "paid")

    def test_admin_payment_list_requires_admin(self):
        url = reverse("payments:admin-payment-list")
        # Non-admin
        self.client.force_authenticate(self.user)
        resp = self.client.get(url)
        self.assertIn(resp.status_code, (status.HTTP_403_FORBIDDEN, status.HTTP_401_UNAUTHORIZED))
        # Admin
        self.client.force_authenticate(self.admin)
        resp2 = self.client.get(url)
        self.assertEqual(resp2.status_code, status.HTTP_200_OK)

    def test_admin_payment_delete_only_pending(self):
        reservation = self._create_reservation(price=Decimal("50000.00"))
        pending = Payment.objects.create(user=self.user, reservation=reservation, amount=50000, authority="DP", status="pending")
        paid = Payment.objects.create(user=self.user, reservation=reservation, amount=50000, authority="DX", status="paid")

        self.client.force_authenticate(self.admin)
        # Delete paid -> 400
        url_paid = reverse("payments:admin-payment-detail", args=[paid.id])
        resp_paid = self.client.delete(url_paid)
        self.assertEqual(resp_paid.status_code, status.HTTP_400_BAD_REQUEST)
        # Delete pending -> 204
        url_pending = reverse("payments:admin-payment-detail", args=[pending.id])
        resp_pending = self.client.delete(url_pending)
        self.assertEqual(resp_pending.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Payment.objects.filter(id=pending.id).exists())

    @patch("payments.views.inquire_payment")
    @patch("payments.utils.check_and_reverse_failed_payment")
    def test_payment_inquiry_with_reversal(self, mock_check_reverse, mock_inquire):
        reservation = self._create_reservation(price=Decimal("50000.00"))
        payment = Payment.objects.create(user=self.user, reservation=reservation, amount=50000, authority="AUTHQ", status="failed")

        mock_inquire.return_value = {"success": True, "status": "PAID", "code": 100, "message": "OK"}
        mock_check_reverse.return_value = True

        self.client.force_authenticate(self.admin)
        url = reverse("payments:admin-payment-inquiry", args=[payment.authority])
        resp = self.client.get(url)

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(resp.data.get("success"))
        self.assertTrue(resp.data.get("reversed"))

    @patch("payments.views.inquire_payment")
    def test_payment_inquiry_without_payment_in_db(self, mock_inquire):
        mock_inquire.return_value = {"success": True, "status": "PAID", "code": 100, "message": "OK"}
        self.client.force_authenticate(self.admin)
        url = reverse("payments:admin-payment-inquiry", args=["NOAUTH"])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(resp.data.get("success"))
