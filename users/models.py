from datetime import date, timedelta

from django.contrib.auth.models import User
from django.contrib.sessions.models import Session
from django.core.urlresolvers import reverse
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from django.utils.translation import ugettext_lazy as _

from tools.utils import send_email


class Profile(User):
    """ User profiles """
    PLAN_BUSINESS = 2
    PLAN_FREE = 1
    PLAN_SMALL_BUSINESS = 3
    PLAN_NAMES = {PLAN_FREE: _('free plan'), PLAN_BUSINESS: _('business plan'),
                  PLAN_SMALL_BUSINESS: _("small business plan")}
    PLAN_CHOICES = {PLAN_FREE: _('Free'), PLAN_BUSINESS: _('Business'),
                    PLAN_SMALL_BUSINESS: _('Small business')}
    user = models.OneToOneField(User, parent_link=True)

    gender = models.CharField(max_length=1, null=True, blank=True)
    dob = models.DateField(verbose_name='Date of birthday', null=True, blank=True)

    activation_key = models.CharField(max_length=40, null=True, blank=True)

    provider = models.CharField(max_length=200, null=True, blank=True)
    uid = models.CharField(max_length=200, null=True, blank=True)

    session = models.ForeignKey(Session, blank=True, null=True)  # session for anonymous users
    last_seen_on = models.DateTimeField(default=timezone.now)

    plan = models.IntegerField(default=PLAN_FREE)
    plan_expiry = models.DateField(null=True, blank=True)
    subscription = models.BooleanField(default=False)

    syncs_left = models.IntegerField(default=30)

    def __unicode__(self):
        return self.email

    def plan_name(self):
        """get translated plan name"""
        return self.PLAN_NAMES[self.plan]

    def is_guest(self):
        return bool(self.session)

    def is_paid(self):
        """returns whether user is using paid plan or not"""
        return self.plan != Profile.PLAN_FREE

    def is_update_allowed(self):
        """return whether user is allowed to perform an update"""
        return self.is_paid() or self.syncs_left

    @property
    def next_payment_dates(self):
        """
        :rtype: tuple
        :returns: tuple of dates for the next payment start and end (+1 month)
        """
        if self.is_paid():
            return self.plan_expiry, self.plan_expiry + timedelta(days=30)
        else:
            return date.today(), date.today() + timedelta(days=30)

    def new_plan_expiry(self, amount_paid):
        """
        :returns: new plan_expiry by 31 day from last expiry date
        """
        if self.plan == self.PLAN_BUSINESS:
            days = amount_paid * 2
            if days > 36:
                days += days / 31 * 7
        elif self.plan == self.PLAN_SMALL_BUSINESS:
            days = amount_paid * 6
        if self.plan_expiry:
            plan_expiry = self.plan_expiry + timedelta(days=days)
        else:
            plan_expiry = date.today() + timedelta(days=days)
        return plan_expiry

    @property
    def sync_abs_width(self):
        """Get absolute width in pixels for battery indicator"""
        return self.syncs_left * 150 / 30

    def save(self, *args, **kwargs):
        self.username = self.email
        if self.session:
            self.username = self.session.session_key[:30]
        if not self.first_name:
            self.first_name = 'None'
        if not self.last_name:
            self.last_name = 'None'
        result = super(Profile, self).save(*args, **kwargs)
        return result

    def get_register_redirect(self):
        """
        Return correct redirect url after registration,
        depending on whether user chosen business plan or not
        """
        if self.plan != Profile.PLAN_FREE:
            self.plan = Profile.PLAN_FREE
            self.save()
            return reverse('payment')
        else:
            return reverse('main')


@receiver(post_save, sender=Profile)
def send_registration_email(sender, instance, created, **kwargs):
    """
    Send email on registration
    :type instance: Profile
    """
    if created and not instance.is_guest():
        send_email.delay('mail/feedback', {'message': str(instance.provider), 'email':instance.email}, "User registration")
