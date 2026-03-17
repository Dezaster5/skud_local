from django.contrib import admin
from django.urls import include, path

from apps.fondvision_integration.views import FondvisionMCardSeaView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("health/", include("apps.core.api.urls")),
    path("qa/mcardsea.php", FondvisionMCardSeaView.as_view(), name="fondvision-mcardsea"),
    path("api/", include("skud_local.api_urls")),
]
