from django.urls import path
from . import api

urlpatterns = [
    path("ops/order-activities/", api.ActivityFeed.as_view()),
    path("orders/", api.BuyerList.as_view()),
    path("orders/by-intent/<uuid:intent>/", api.Intent.as_view()),
    path("orders/<uuid:no>/", api.Detail.as_view()),
    path("orders/<uuid:no>/cancel/", api.CancelOrder.as_view()),
    path("orders/<uuid:no>/receive/", api.Receive.as_view()),
    path("payments/", api.Payments.as_view()),
    path("payments/<uuid:no>/", api.Attempt.as_view()),
    path("payments/<uuid:no>/simulate/", api.Simulate.as_view()),
    path("ops/orders/", api.OpsList.as_view()),
    path("ops/orders/<uuid:no>/", api.OpsDetail.as_view()),
    path("ops/orders/<uuid:no>/ship/", api.Shipment.as_view()),
    path("operations/<str:operation>/<uuid:token>/", api.Lookup.as_view()),
]
