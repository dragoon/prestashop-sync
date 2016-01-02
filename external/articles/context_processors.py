from django.core.urlresolvers import reverse
from django.utils import timezone
from django.utils.translation import get_language

from articles.models import Article

def article_count(request):
    """
    Calculate article count for current language to show on every page
    """
    # TODO: make this count a new articles for the each user
    language = get_language()
    user = request.user
    a_count = Article.objects.live(user=request.user).filter(language=language,
                publish_date__gte=user.last_seen_on).count()
    if request.path.startswith(reverse('articles_archive')) and a_count:
        user.last_seen_on = timezone.now()
        user.save()
    return {'article_count': a_count}
