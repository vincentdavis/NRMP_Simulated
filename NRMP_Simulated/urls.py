"""URL configuration for NRMP_Simulated project."""

from debug_toolbar.toolbar import debug_toolbar_urls
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("nrmps.urls")),
] + debug_toolbar_urls()
