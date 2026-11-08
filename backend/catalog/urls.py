from django.urls import path
from .views import ManageProducts, Publication, PublicDetail, PublicProducts

urlpatterns = [
    path("products/", PublicProducts.as_view()),
    path("products/<int:pk>/", PublicDetail.as_view()),
    path("ops/products/", ManageProducts.as_view()),
    path("ops/products/<int:pk>/publish/", Publication.as_view()),
    path("ops/products/<int:pk>/unpublish/", Publication.as_view(publish=False)),
]
