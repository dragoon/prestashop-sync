import urllib2
import time
from celery.task import task

from django.core import mail
from django.conf import settings
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
from django.core.mail import EmailMultiAlternatives
from django.utils.html import strip_tags
from django.db.models.aggregates import Max

from django.template import Context, TemplateDoesNotExist, loader
from lxml.html import document_fromstring
from tools.models import Member, MemberRus, ShopLink, ShopLinkRus

@task
def send_email(template, context, subject, email=settings.ADMIN_MAILS):
    try:
        t = loader.get_template(template)
        content = t.render(Context(context))
    except TemplateDoesNotExist:
        pass
    else:
        if not settings.DEBUG:
            mail.send_mail(subject, content, "Prestashop-Sync <no-reply@prestashop-sync.com>", email)
        else:
            print subject
            print content


@task
def send_html_email(template, context, subject, email=settings.ADMIN_MAILS):
    # TODO: django 1.6? has argument to send HTML mail
    try:
        t = loader.get_template(template)
        content = t.render(Context(context))
    except TemplateDoesNotExist:
        pass
    else:
        text_content = strip_tags(content)
        if not settings.DEBUG:
            msg = EmailMultiAlternatives(subject, text_content, "Prestashop-Sync <no-reply@prestashop-sync.com>", email)
            msg.attach_alternative(content, "text/html")
            msg.send()
        else:
            print subject
            print text_content


def print_timing(func):
    """ Decorator to print function execution time
    """
    if settings.DEBUG:
        def wrapper(*arg, **kwargs):
            time1 = time.clock()
            result = func(*arg, **kwargs)
            time2 = time.clock()
            res = '%s took %0.3fms' % (func.func_name, (time2 - time1) * 1000.0)
            print res
            return result
        return wrapper
    else:
        return func


def get_pagination(objects, page):
    paginator = Paginator(objects, settings.PAGINATION)
    try:
        page_objects = paginator.page(page)
    except PageNotAnInteger:
        # If page is not an integer, deliver first page.
        page_objects = paginator.page(1)
    except EmptyPage:
        # If page is out of range (e.g. 9999), deliver last page of results.
        page_objects = paginator.page(paginator.num_pages)
    return page_objects


def search_shops_on_forum(force=False):
    # Get member pages
    step = 500
    last_page = page_number = (Member.objects.aggregate(Max('page_number')) and not force) or 1
    page_url = 'http://www.prestashop.com/forums/members/page__sort_key__members_display_name__sort_order__asc__max_results__%d__st__%d' % (step, (last_page-1)*step)
    while page_url:
        page = document_fromstring(urllib2.urlopen(page_url).read())
        for member in page.cssselect('ul.members li h3.bar a:first'):
            # member url
            Member.objects.get_or_create(link=member.get('href'), defaults={'page_number':page_number})
        page_url = page.cssselect('ul.pagination.left li.next a').get('href')
        page_number+=1

    for member in Member.objects.filter(page_number__gte=last_page):
        member_page = document_fromstring(urllib2.urlopen(member.link).read())
        for link in member_page.cssselect('div.general_box div.signature a'):
            ShopLink.objects.get_or_create(link=link.get('href'), member=member)


def search_shops_on_rus_forum(force=False):
    last_page = (MemberRus.objects.aggregate(Max('page_number')) and not force) or 1

    for i in range(last_page, 4219):
        page_url = 'http://prestadev.ru/forum/profile.php?u='+str(i)
        page = document_fromstring(urllib2.urlopen(page_url).read())
        messages = 0
        try:
            messages = int(page.cssselect('div.wttborder td strong')[2].text.strip())
        except:
            pass
        try:
            params = {'title': page.cssselect('#profilename')[0].text.strip(),
                  'messages': messages,
                  'page_number': i,
                  'home_page':page.cssselect('div.wttborder td.row1')[4]}
        except IndexError:
            continue
        member = MemberRus.objects.get_or_create(**params)[0]
        for link in page.cssselect('div.wgborder td.row1 a'):
            ShopLinkRus.objects.get_or_create(link=link.get('href'), member=member)
