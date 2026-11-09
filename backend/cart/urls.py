from django.urls import path
from .api import Checkout, Detail, Items, Merge

urlpatterns = [
    path("carts/items/", Items.as_view()),
    path("carts/items/<int:pk>/", Detail.as_view()),
    path("carts/merge/", Merge.as_view()),
    path("checkout/quote/", Checkout.as_view()),
]
