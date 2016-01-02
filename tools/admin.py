from django.contrib import admin
from django.contrib.sessions.models import Session
from tools.models import MemberRus, ShopLinkRus

class SessionAdmin(admin.ModelAdmin):
    list_display = ('decoded_session_data', 'expire_date')

    def decoded_session_data(self, obj):
        return str(obj.get_decoded())
    decoded_session_data.short_description = 'Data'

class ShopLinkRusAdmin(admin.ModelAdmin):
    list_display = ('link', 'member', 'messages', 'home_page')

    def messages(self, obj):
        return '%d' % obj.member.messages
    messages.short_description = 'Message count'

    def home_page(self, obj):
        return '%s' % obj.member.home_page
    home_page.short_description = 'Home page'

admin.site.register(MemberRus)
admin.site.register(ShopLinkRus, ShopLinkRusAdmin)
admin.site.register(Session, SessionAdmin)
