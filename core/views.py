from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from university_food_system.permissions import IsAdminOrReadOnly
from .models import Voucher
from .serializers import VoucherSerializer
from django.core.exceptions import ValidationError


class VoucherPriceView(APIView):
    permission_classes = [IsAuthenticated, IsAdminOrReadOnly]

    def get(self, request):
        """Retrieve the current voucher price."""
        try:
            voucher = Voucher.objects.first()
            if not voucher:
                return Response({"error": "Voucher price not set"}, status=status.HTTP_404_NOT_FOUND)
            serializer = VoucherSerializer(voucher)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


    def put(self, request):
        """Update the voucher price. Only accessible by admins."""     
        voucher, _ = Voucher.objects.get_or_create()
        serializer = VoucherSerializer(voucher, data=request.data, partial=True)
        if serializer.is_valid():
            try:
                serializer.save()  # Will trigger the `clean()` method
                return Response(serializer.data, status=status.HTTP_200_OK)
            except ValidationError as e:
                return Response({"error": str(e.message)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)