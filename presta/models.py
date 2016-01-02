import base64
from django.conf import settings
from django.core.urlresolvers import reverse
from django.db import models
from django.db.models import F
from django.utils.translation import ugettext_lazy as _

from users.models import Profile


class UserActivity(models.Model):
    domain = models.CharField(max_length=255)
    date = models.DateTimeField(auto_now_add=True, db_index=True)
    action = models.CharField(max_length=255)
    data = models.TextField()
    errors = models.TextField()

    class Meta:
        ordering = ['-date']

    def success_status(self):
        return self.errors == 'None' or not self.errors
    success_status.short_description = 'Status'
    success_status.boolean = True

    def __unicode__(self):
        return self.domain


class UpdateStatus(models.Model):
    domain = models.CharField(max_length=255, verbose_name=_("Shop URL"), unique=True)
    update_status = models.CharField(max_length=255)

    def __unicode__(self):
        return self.domain + ': ' + self.update_status


class Shop(models.Model):
    INVERVALS = ((60, _('Every hour')), (60*24, _('Every day')), (60*24*7, _('Every week')))
    SYNC_TYPE = (
        ('REFERENCE', _('Based on Reference')),
        ('SUPPLIER_REFERENCE', _('Based on Supplier Reference')),
        ('EAN13', _('Based on EAN13')),
#        ('PRESTA_ID', _('Based on Prestashop ID')),
        ('ID', _('Internal ID (Deprecated)')),
    )
    VERSION = (
        ('1.3', 'Prestashop 1.3'),
        ('1.4', 'Prestashop 1.4'),
    )
    STATUS = [(a, a) for a in ['red', 'yellow', 'green']]
    user = models.ForeignKey(Profile)
    title = models.CharField(max_length=1000)
    domain = models.CharField(max_length=255, verbose_name=_("Shop URL"))
    sync_type = models.CharField(max_length=100, choices=SYNC_TYPE, default='PRESTA_ID',
                                 verbose_name=_("Sync type"))
    version = models.CharField(max_length=3, choices=VERSION, default=0)
    key = models.CharField(max_length=255, verbose_name=_("Secret key"))
    status = models.CharField(max_length=10, choices=STATUS)
    error_status = models.CharField(max_length=255, null=True, blank=True)
    is_schedule_enabled = models.BooleanField(default=False)
    location = models.URLField(verbose_name=_("Update File URL"), null=True, blank=True)
    interval = models.IntegerField(choices=INVERVALS,
                                   verbose_name=_("Update interval"), default=INVERVALS[0][0])
    last_update_time = models.DateTimeField(auto_now_add=True)
    update_index = models.IntegerField(default=0)

    # Field to store temporary unsaved shops
    temp = models.BooleanField()

    class Meta:
        unique_together = ('user', 'domain')
        ordering = ('pk',)

    @property
    def actions(self):
        actions = [# ('update', {'url': reverse('shop_status', args=[self.id]), 'title':_("Update status")}),
                   ('add', {'url': reverse('add_data', args=[self.id]), 'title':_("Add products")}),
                   ('edit', {'url': reverse('shop_edit', args=[self.id]), 'title':_("Edit")}),
                   ('delete', {'url': reverse('shop_delete', args=[self.id]), 'title':_("Delete")})]
        return actions

    @property
    def api(self):
        from presta.utils.presta_api import PrestashopAPI
        if not hasattr(self, '_api'):
            self.api = PrestashopAPI.getAPI(self)
        return self._api

    @api.setter
    def api(self, api):
        if api.__version__ != self.version:
            self.version = api.__version__
            self.save()
        self._api = api

    @api.deleter
    def api(self):
        if hasattr(self, '_api'):
            del self._api

    def get_data(self, page=0, page_limit=settings.PAGINATION):
        from presta.utils.presta_api import build_id_list
        from presta.db_logging import whosdaddy, log_user_action
        data, error_dict = self.api.get_presta_data(page, page_limit)
        if not error_dict:
            data = build_id_list(data)
        else:
            log_user_action.delay(self.domain, whosdaddy(), str(data), str(error_dict))
        return data, error_dict

    def prepare_data_for_update(self, lines):
        """Retrieves all the data, then generates data list for update"""
        from presta.utils.presta_api import make_data_list
        data_full = []
        page = 0
        while not self.api.finished:
            data, error_dict = self.get_data(page, 1000)
            if error_dict:
                return {'result': 'error', 'response': error_dict}
            page += 1
            data_full.extend(data)
        result = make_data_list(data_full, self.sync_type, lines)
        return result

    def send_data_update_signal(self):
        """
        Method performed after any update to the shop data,
        Decrement user syncs counter for now
        """
        # TODO: django 1.5 update only one field
        if self.domain != settings.DEMO_SHOP['domain'] and not self.user.is_paid():
            Profile.objects.filter(id=self.user.id).update(syncs_left=F('syncs_left') - 1)

    @property
    def authheader(self):
        """ Get simple authentication header using shop key """
        base64string = base64.encodestring('%s:' % (self.key,))[:-1]
        authheader = "Basic %s" % base64string
        return authheader

    def is_demo(self):
        from django.conf import settings
        for k, v in settings.DEMO_SHOP.items():
            if k == 'sync_type':
                continue
            if not getattr(self, k) == v:
                return False
        return True

    def is_data_finished(self, data_len, page_num):
        """
        Tells if api finished retrieving the data (for pagination)
        :rtype: int
        """
        if data_len > settings.PAGINATION*page_num:
            next_page = 1
        else:
            next_page = int(not self.api.finished)
        return next_page

    def get_initial(self):
        """get initial data for the form"""
        return {'domain': self.domain, 'sync_type': self.sync_type, 'key': self.key}

    def get_normalized_title(self):
        title = self.domain
        if title.startswith('www.'):
            title = title[4:]
        return title.capitalize()

    def is_ok(self):
        return self.status == 'green'

    def set_alarm(self, error_msg=None):
        self.status = 'red'
        if error_msg:
            error_msg = _(error_msg)
        self.error_status = error_msg
        self.save()

    def set_ok(self):
        self.status = 'green'
        self.error_status = None
        self.save()

    def has_alarm(self, error_msg):
        if self.error_status:
            return self.error_status.startswith(error_msg)
        return False

    def save(self, *args, **kwargs):
        # Update title for temp shops
        if not self.title or self.temp:
            self.title = self.get_normalized_title()
        # Clear api
        del self.api
        super(Shop, self).save(*args, **kwargs)

    def __unicode__(self):
        return self.title


class UpdateSchedule(models.Model):
    INVERVALS = ((60, _('Every hour')), (60*24, _('Every day')), (60*24*7, _('Every week')))

    location = models.URLField(verbose_name=_("Update File URL"))
    interval = models.IntegerField(choices=INVERVALS,
                                   verbose_name=_("Update interval"), default=INVERVALS[0][0])
    shop = models.ForeignKey("Shop", related_name='schedules')

    def __unicode__(self):
        return self.shop.title
