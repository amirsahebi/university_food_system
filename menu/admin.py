from django.contrib import admin
from .models import TemplateMenu, TemplateMenuItem, DailyMenu, DailyMenuItem, TimeSlot

admin.site.register(TemplateMenu)
admin.site.register(TemplateMenuItem)
admin.site.register(DailyMenu)
admin.site.register(DailyMenuItem)
admin.site.register(TimeSlot)
