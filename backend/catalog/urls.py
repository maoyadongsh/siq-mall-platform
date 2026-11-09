from django.urls import path
from .views import ManageProducts, Publication, PublicDetail, PublicProducts

from .ops import Upload, ProductMaintenance, VariantMaintenance, StockHistory
from .category_api import ManageDetail, ManageTree, PublicTree

urlpatterns = [
    path("categories/tree/", PublicTree.as_view()),
    path("ops/categories/", ManageTree.as_view()),
    path("ops/categories/<int:pk>/", ManageDetail.as_view()),
    path("ops/media/", Upload.as_view()),
    path("ops/products/<int:pk>/", ProductMaintenance.as_view()),
    path("ops/skus/<int:pk>/", VariantMaintenance.as_view()),
    path("ops/skus/<int:pk>/stock-adjustments/", StockHistory.as_view()),
    path("products/", PublicProducts.as_view()),
    path("products/<int:pk>/", PublicDetail.as_view()),
    path("ops/products/", ManageProducts.as_view()),
    path("ops/products/<int:pk>/publish/", Publication.as_view()),
    path("ops/products/<int:pk>/unpublish/", Publication.as_view(publish=False)),
]
