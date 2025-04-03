from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.core.exceptions import ValidationError
from .models import Food
from .serializers import FoodSerializer
from university_food_system.permissions import IsAdminOrReadOnly


class FoodListCreateView(APIView):
    permission_classes = [IsAuthenticated, IsAdminOrReadOnly]

    def get(self, request):
        """List all foods"""
        foods = Food.objects.all()
        serializer = FoodSerializer(foods, many=True, context={'request': request})
        return Response(serializer.data)

    def post(self, request):
        """Create a new food item"""
        serializer = FoodSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            try:
                serializer.save()
                return Response(serializer.data, status=status.HTTP_201_CREATED)
            except ValidationError as e:
                return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class FoodDetailView(APIView):
    permission_classes = [IsAuthenticated, IsAdminOrReadOnly]

    def get_object(self, id):
        try:
            return Food.objects.get(id=id)
        except Food.DoesNotExist:
            return None

    def get(self, request, id):
        """Retrieve a food item"""
        food = self.get_object(id)
        if not food:
            return Response({"error": "Food not found"}, status=status.HTTP_404_NOT_FOUND)
        serializer = FoodSerializer(food, context={'request': request})
        return Response(serializer.data)

    def put(self, request, id):
        """Update a food item"""
        food = self.get_object(id)
        if not food:
            return Response({"error": "Food not found"}, status=status.HTTP_404_NOT_FOUND)
        serializer = FoodSerializer(food, data=request.data, context={'request': request})
        if serializer.is_valid():
            try:
                serializer.save()
                return Response(serializer.data)
            except ValidationError as e:
                return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def patch(self, request, id):
        """Partially update a food item"""
        food = self.get_object(id)
        if not food:
            return Response({"error": "Food not found"}, status=status.HTTP_404_NOT_FOUND)
        serializer = FoodSerializer(food, data=request.data, partial=True, context={'request': request})
        if serializer.is_valid():
            try:
                serializer.save()
                return Response(serializer.data)
            except ValidationError as e:
                return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, id):
        """Delete a food item"""
        food = self.get_object(id)
        if not food:
            return Response({"error": "Food not found"}, status=status.HTTP_404_NOT_FOUND)
        food.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
