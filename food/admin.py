from django.contrib import admin
from .models import Food, FoodCategory

@admin.register(Food)
class FoodAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'price', 'created_at', 'updated_at']
    search_fields = ['name']
    list_filter = ['created_at']

@admin.register(FoodCategory)
class FoodCategoryAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'created_at', 'updated_at']
    search_fields = ['name']
    list_filter = ['created_at']

