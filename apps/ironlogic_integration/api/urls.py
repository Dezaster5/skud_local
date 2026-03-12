from django.urls import path

from apps.ironlogic_integration.api.views import IronLogicWebJsonAPIView

urlpatterns = [
    path("webjson/", IronLogicWebJsonAPIView.as_view(), name="ironlogic-webjson"),
]

