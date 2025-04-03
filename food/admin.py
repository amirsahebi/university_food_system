from django.contrib import admin
from .models import Food

@admin.register(Food)
class FoodAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'price', 'created_at', 'updated_at']
    search_fields = ['name']
    list_filter = ['created_at']
