from django.urls import path

from .views import AddToCartApiView, CartDetailView, UpdateCartItemApiView, add_to_cart_page, cart_page, update_cart_item_page

app_name = "cart"

urlpatterns = [
    path("", CartDetailView.as_view(), name="detail"),
    path("add/", AddToCartApiView.as_view(), name="add-api"),
    path("items/<int:item_id>/", UpdateCartItemApiView.as_view(), name="item-update-api"),
    path("page/", cart_page, name="cart-page"),
    path("page/add/", add_to_cart_page, name="cart-page-add"),
    path("page/items/<int:item_id>/", update_cart_item_page, name="cart-page-item-update"),
]
