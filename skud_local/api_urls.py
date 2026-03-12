from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.access.views import AccessPointViewSet, AccessPolicyViewSet
from apps.controllers.views import ControllerTaskViewSet, ControllerViewSet
from apps.events.views import AccessEventViewSet
from apps.ironlogic_integration.api.urls import urlpatterns as ironlogic_urlpatterns
from apps.people.views import PersonViewSet
from apps.wristbands.views import WristbandViewSet

# Keep device-protocol endpoints isolated from the internal REST API.
router = DefaultRouter()
router.register("people", PersonViewSet, basename="person")
router.register("wristbands", WristbandViewSet, basename="wristband")
router.register("controllers", ControllerViewSet, basename="controller")
router.register("access-points", AccessPointViewSet, basename="access-point")
router.register("access-policies", AccessPolicyViewSet, basename="access-policy")
router.register("access-events", AccessEventViewSet, basename="access-event")
router.register("controller-tasks", ControllerTaskViewSet, basename="controller-task")

urlpatterns = [
    path("auth/", include("rest_framework.urls")),
    path("ironlogic/", include((ironlogic_urlpatterns, "ironlogic"), namespace="ironlogic")),
    path("", include(router.urls)),
]
