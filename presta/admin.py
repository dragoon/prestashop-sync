from django.contrib import admin
from presta.models import UserActivity, Shop, UpdateSchedule, UpdateStatus
from users.admin import FilteredModelAdmin


class UserActivityAdmin(admin.ModelAdmin):
    list_display = ('domain', 'action', 'date', 'success_status')


class ShopAdmin(FilteredModelAdmin):
    list_display = ('domain', 'user', 'status', 'key', 'last_update_time')
    search_fields = ('domain',)

admin.site.register(UserActivity, UserActivityAdmin)
admin.site.register(Shop, ShopAdmin)
admin.site.register(UpdateSchedule)
admin.site.register(UpdateStatus)
