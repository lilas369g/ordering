from django.urls import path

from apps.cart.views import add_to_cart_page, cart_page, update_cart_item_page
from apps.catalog.views import storefront_product_list

app_name = "storefront"

urlpatterns = [
    path("", storefront_product_list, name="product-list"),
    path("cart/", cart_page, name="cart-page"),
    path("cart/add/", add_to_cart_page, name="add-to-cart"),
    path("cart/items/<int:item_id>/", update_cart_item_page, name="update-cart-item"),
]
