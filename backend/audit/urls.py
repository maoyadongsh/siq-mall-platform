from django.urls import path

from .api import AuditList, Dashboard

urlpatterns = [
    path("ops/dashboard/", Dashboard.as_view()),
    path("ops/audits/", AuditList.as_view()),
]
