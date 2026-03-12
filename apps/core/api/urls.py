from django.urls import path

from apps.core.api.views import live_health_view, ready_health_view

urlpatterns = [
    path("live", live_health_view, name="health-live"),
    path("ready", ready_health_view, name="health-ready"),
]

