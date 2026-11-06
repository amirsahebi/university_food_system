from rest_framework.views import APIView
from rest_framework.generics import ListCreateAPIView, RetrieveUpdateDestroyAPIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from university_food_system.permissions import IsAdminOrReadOnly
from .models import Voucher, VoucherType
from .serializers import VoucherSerializer, VoucherTypeSerializer
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


class VoucherTypeListCreateView(ListCreateAPIView):
    """
    GET: List all voucher types (available to all authenticated users).
    POST: Create a new voucher type (admin only).
    """
    permission_classes = [IsAuthenticated, IsAdminOrReadOnly]
    queryset = VoucherType.objects.all()
    serializer_class = VoucherTypeSerializer


class VoucherTypeDetailView(RetrieveUpdateDestroyAPIView):
    """
    GET: Retrieve a voucher type.
    PUT/PATCH: Update a voucher type (admin only).
    DELETE: Delete a voucher type (admin only).
    """
    permission_classes = [IsAuthenticated, IsAdminOrReadOnly]
    queryset = VoucherType.objects.all()
    serializer_class = VoucherTypeSerializer
