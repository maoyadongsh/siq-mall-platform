from django.urls import path
from . import api

urlpatterns = [
    path("coupons/", api.Templates.as_view()),
    path("coupons/<int:pk>/claim/", api.Claim.as_view()),
    path("users/me/coupons/", api.Wallet.as_view()),
    path("ops/coupons/", api.OpsTemplates.as_view()),
    path("ops/coupons/<int:pk>/", api.OpsDetail.as_view()),
    path("ops/coupons/<int:pk>/publish/", api.Lifecycle.as_view()),
    path(
        "ops/coupons/<int:pk>/stop-claiming/", api.Lifecycle.as_view(operation="stop")
    ),
]
