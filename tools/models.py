from django.db import models

class ShopLink(models.Model):
    link = models.URLField()
    last_update = models.DateTimeField(auto_now=True)
    member = models.ForeignKey('Member')

    def __unicode__(self):
        return self.link

class ShopLinkRus(models.Model):
    link = models.URLField()
    last_update = models.DateTimeField(auto_now=True)
    member = models.ForeignKey('MemberRus')

    def __unicode__(self):
        return self.link

class Member(models.Model):
    link = models.URLField(unique=True)
    page_number = models.IntegerField()

    def __unicode__(self):
        return self.link

class MemberRus(models.Model):
    title = models.CharField(max_length=255)
    messages = models.IntegerField()
    home_page = models.CharField(max_length=255, null=True, blank=True)
    page_number = models.IntegerField()

    def __unicode__(self):
        return self.title
