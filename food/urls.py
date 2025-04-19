from django.urls import path
from .views import FoodListCreateView, FoodDetailView, FoodCategoryListCreateView, FoodCategoryDetailView

urlpatterns = [
    # Food endpoints
    path('', FoodListCreateView.as_view(), name='food_list'),  # GET and POST
    path('<int:id>/', FoodDetailView.as_view(), name='food_detail'),  # PUT and DELETE
    
    # Food Category endpoints
    path('categories/', FoodCategoryListCreateView.as_view(), name='food_category_list'),
    path('categories/<int:id>/', FoodCategoryDetailView.as_view(), name='food_category_detail'),
]
