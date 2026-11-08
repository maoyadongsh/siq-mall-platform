from django.urls import path

from .views import (
    RegionDirectoryAPIView,
    AddressDefaultAPIView,
    AddressDetailAPIView,
    AddressListCreateAPIView,
    PhoneBindAPIView,
    ProfileAPIView,
)

app_name = "users"

urlpatterns = [
    path("regions/", RegionDirectoryAPIView.as_view(), name="regions"),
    path("users/me/", ProfileAPIView.as_view(), name="profile"),
    path("users/me/phone/", PhoneBindAPIView.as_view(), name="phone-bind"),
    path("users/me/addresses/", AddressListCreateAPIView.as_view(), name="addresses"),
    path(
        "users/me/addresses/<int:address_id>/",
        AddressDetailAPIView.as_view(),
        name="address-detail",
    ),
    path(
        "users/me/addresses/<int:address_id>/default/",
        AddressDefaultAPIView.as_view(),
        name="address-default",
    ),
]
