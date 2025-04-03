from django.urls import path
from .views import (
    TemplateMenuView,
    TemplateMenuDetailView,
    DailyMenuView,
    DailyMenuItemView,
    ToggleDailyMenuItemAvailabilityView,
    UseTemplateForDailyView,
)

urlpatterns = [
    path('template/', TemplateMenuView.as_view(), name='template_menu'),
    path('template/<int:id>/', TemplateMenuDetailView.as_view(), name='template_menu_detail'),
    path('daily/', DailyMenuView.as_view(), name='daily_menu'),
    path('daily/<int:pk>/', DailyMenuItemView.as_view(), name='daily_menu_item'),
    path('daily/<int:id>/availability/', ToggleDailyMenuItemAvailabilityView.as_view(), name='toggle_daily_menu_item'),
    path('use-template/', UseTemplateForDailyView.as_view(), name='use_template_for_daily'),
]
