"""
URL configuration for acco project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.conf.urls.static import static
from django.conf import settings
from django.views.static import serve
from django.contrib.sitemaps.views import sitemap
from base.sitemaps import StaticViewSitemap, JobSitemap
from django.views.generic import TemplateView

sitemaps = {
    'static': StaticViewSitemap,
    'jobs': JobSitemap,
}

urlpatterns = [
    path('favicon.ico', serve, {
        'document_root': settings.BASE_DIR / 'base' / 'static' / 'base' / 'img',
        'path': 'favicon.ico',
    }, name='favicon'),
    path('robots.txt', TemplateView.as_view(template_name="base/robots.txt", content_type="text/plain"), name='robots'),
    path('llms.txt', TemplateView.as_view(template_name="base/llms.txt", content_type="text/plain"), name='llms'),
    path('sitemap.xml', sitemap, {'sitemaps': sitemaps}, name='django.contrib.sitemaps.views.sitemap'),
    # Admin Hardening: Use dynamic path from environment variables
    path(settings.ADMIN_URL, admin.site.urls),
    path("", include("base.urls")),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

handler404 = 'base.views.custom_404'
handler500 = 'base.views.custom_500'

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.BASE_DIR / "base" / "static")