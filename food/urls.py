from django.urls import path
from .views import FoodListCreateView, FoodDetailView

urlpatterns = [
    path('', FoodListCreateView.as_view(), name='food_list'),  # GET and POST
    path('<int:id>/', FoodDetailView.as_view(), name='food_detail'),  # PUT and DELETE
]
