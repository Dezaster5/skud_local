from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("health/", include("apps.core.api.urls")),
    path("api/", include("skud_local.api_urls")),
]
