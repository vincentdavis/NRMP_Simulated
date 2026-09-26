"""URL configuration for NRMP_Simulated project."""

from django.conf import settings
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("nrmps.urls")),
]

# Development-only tools. They are installed only with the dev dependency group and are not in INSTALLED_APPS when
# DEBUG is off, so they must not be imported unconditionally.
if settings.DEBUG and "debug_toolbar" in settings.INSTALLED_APPS:
    from debug_toolbar.toolbar import debug_toolbar_urls

    urlpatterns += debug_toolbar_urls()

if settings.DEBUG and "django_browser_reload" in settings.INSTALLED_APPS:
    urlpatterns += [path("__reload__/", include("django_browser_reload.urls"))]
