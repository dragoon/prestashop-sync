from django.conf import settings
from django.contrib import admin
from django.db.models.fields.related import ForeignKey

from users.models import Profile


class FilteredModelAdmin(admin.ModelAdmin):
    list_display = ['email', 'plan', 'plan_expiry', 'syncs_left', 'provider']
    search_fields = ('email',)

    def queryset(self, request):
        qs = super(FilteredModelAdmin, self).queryset(request)
        field = get_related_to(self.model, Profile)
        if field:
            field = '__'.join(field)
            qs = qs.exclude(**{field: settings.GUEST_EMAIL})
        return qs


def get_related_to(model_class, target_model):
    related = []
    if model_class == target_model:
        return ['email']
    for field in model_class._meta.fields:
        if isinstance(field, ForeignKey):
            if field.rel.to == target_model:
                related = [field.name, 'email']
            else:
                related.extend(get_related_to(field.rel.to, target_model))
    return related

admin.site.register(Profile, FilteredModelAdmin)
