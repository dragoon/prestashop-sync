from django.conf.urls import *
from django.conf import settings
from articles import views
from articles.feeds import TagFeed, LatestEntries

tag_rss = TagFeed()
latest_rss = LatestEntries()

urlpatterns = patterns('',
    (r'^(?P<year>\d{4})/(?P<month>.{3})/(?P<day>\d{1,2})/(?P<slug>.*)/$', views.redirect_to_article),
    url(r'^(?P<year>\d{4})/(?P<month>\d{1,2})/page/(?P<page>\d+)/$', views.display_blog_page, name='articles_in_month_page'),
    url(r'^(?P<year>\d{4})/(?P<month>\d{1,2})/$', views.display_blog_page, name='articles_in_month'),
)

LANGUAGE_LIST = map((lambda x: x[0]), settings.LANGUAGES)

urlpatterns += patterns('',
    url(r'^$', views.display_blog_page, name='articles_archive'),
    url(r'^page/(?P<page>\d+)/$', views.display_blog_page, name='articles_archive_page'),

    url(r'^tag/(?P<tag>.*)/page/(?P<page>\d+)/$', views.display_blog_page, name='articles_display_tag_page'),
    url(r'^tag/(?P<tag>.*)/$', views.display_blog_page, name='articles_display_tag'),

    url(r"^lang/(?P<language>.*)/page/(?P<page>\d+)/$", views.display_blog_page, name='articles_by_language'),
    url(r"^lang/(?P<language>.*)/$", views.display_blog_page, name='articles_by_language'),

    url(r'^author/(?P<username>.*)/page/(?P<page>\d+)/$', views.display_blog_page, name='articles_by_author_page'),
    url(r'^author/(?P<username>.*)/$', views.display_blog_page, name='articles_by_author'),

    url(r'^(?P<year>\d{4})/(?P<language>[a-z\-]{5})/(?P<slug>.*)/$', views.display_article, name='articles_display_article'),
    url(r'^(?P<year>\d{4})/(?P<language>[a-z]{2})/(?P<slug>.*)/$', views.display_article, name='articles_display_article'),

    # AJAX
    url(r'^ajax/tag/autocomplete/$', views.ajax_tag_autocomplete, name='articles_tag_autocomplete'),

    # RSS
    url(r'^feeds/latest\.rss$', latest_rss, name='articles_rss_feed_latest'),
    url(r'^feeds/latest/$', latest_rss),
    url(r'^feeds/tag/(?P<slug>[\w_-]+)\.rss$', tag_rss, name='articles_rss_feed_tag'),
    url(r'^feeds/tag/(?P<slug>[\w_-]+)/$', tag_rss),

)
