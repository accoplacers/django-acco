from django.contrib.sitemaps import Sitemap
from django.urls import reverse
from .models import JobOpening

class StaticViewSitemap(Sitemap):
    priority = 1.0
    changefreq = 'daily'

    def items(self):
        return ['registration_view']

    def location(self, item):
        return reverse(item)

class JobSitemap(Sitemap):
    priority = 0.8
    changefreq = 'weekly'

    def items(self):
        return JobOpening.objects.filter(is_active=True).order_by('-created_at')

    def lastmod(self, obj):
        return obj.created_at
