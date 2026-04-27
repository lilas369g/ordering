from decimal import Decimal
from threading import Barrier, Thread

from django.contrib.auth import get_user_model
from django.db import close_old_connections
from django.test import TransactionTestCase, skipUnlessDBFeature
from rest_framework import status
from rest_framework.test import APITestCase, APIClient

from apps.cart.models import Cart, CartItem, CartStatus
from apps.catalog.models import Brand, Category, Product, ProductVariant
from apps.inventory.models import InventoryRecord
from apps.users.models import UserType

from apps.orders.models import Order, OrderItem

User = get_user_model()


class CheckoutTestDataMixin:
    def create_customer(self, phone_number="0999000000"):
        user = User(
            phone_number=phone_number,
            first_name="Ahmad",
            user_type=UserType.CUSTOMER,
        )
        user.set_password("password123")
        user.save()
        return user

    def create_variant_with_stock(self, quantity_available=5, price=Decimal("10.00"), sku="SKU-1"):
        category = Category.objects.create(name="Shoes")
        brand = Brand.objects.create(name=f"Brand {sku}")
        product = Product.objects.create(
            name=f"Product {sku}",
            category=category,
            brand=brand,
            is_active=True,
        )
        variant = ProductVariant.objects.create(
            product=product,
            sku=sku,
            price=price,
            is_active=True,
        )
        InventoryRecord.objects.create(
            variant=variant,
            quantity_available=quantity_available,
        )
        return variant

    def create_cart_item(self, user, variant, quantity=1):
        cart = Cart.objects.create(customer=user, status=CartStatus.ACTIVE)
        return CartItem.objects.create(
            cart=cart,
            variant=variant,
            quantity=quantity,
            unit_price_snapshot=variant.price,
        )


class CheckoutApiTests(CheckoutTestDataMixin, APITestCase):
    checkout_payload = {
        "customer_name": "Ahmad Ali",
        "phone_number": "0999000000",
        "shipping_address": "Damascus, Main Street",
        "province": "Damascus",
    }

    def test_checkout_creates_order_decrements_stock_and_clears_cart(self):
        user = self.create_customer()
        variant = self.create_variant_with_stock(quantity_available=5, price=Decimal("12.50"))
        item = self.create_cart_item(user, variant, quantity=2)
        self.client.force_authenticate(user=user)

        response = self.client.post("/api/v1/orders/checkout/", self.checkout_payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["message"], "تم الطلب بنجاح")
        order = Order.objects.get(id=response.data["order_id"])
        self.assertEqual(order.status, "pending")
        self.assertEqual(order.customer_name, self.checkout_payload["customer_name"])
        self.assertEqual(order.phone_number, self.checkout_payload["phone_number"])
        self.assertEqual(order.total_amount, Decimal("25.00"))
        self.assertEqual(OrderItem.objects.get(order=order).unit_price, Decimal("12.50"))
        self.assertEqual(OrderItem.objects.get(order=order).quantity, 2)
        self.assertFalse(CartItem.objects.filter(cart=item.cart).exists())

        variant.inventory_record.refresh_from_db()
        item.cart.refresh_from_db()
        self.assertEqual(variant.inventory_record.quantity_available, 3)
        self.assertEqual(item.cart.status, CartStatus.ORDERED)

    def test_checkout_rejects_when_stock_is_not_enough(self):
        user = self.create_customer()
        variant = self.create_variant_with_stock(quantity_available=1)
        item = self.create_cart_item(user, variant, quantity=2)
        self.client.force_authenticate(user=user)

        response = self.client.post("/api/v1/orders/checkout/", self.checkout_payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("الكمية المتوفرة", response.data["detail"])
        self.assertEqual(Order.objects.count(), 0)
        self.assertTrue(CartItem.objects.filter(id=item.id).exists())
        variant.inventory_record.refresh_from_db()
        self.assertEqual(variant.inventory_record.quantity_available, 1)


@skipUnlessDBFeature("has_select_for_update")
class ConcurrentCheckoutTests(CheckoutTestDataMixin, TransactionTestCase):
    reset_sequences = True

    checkout_payload = {
        "customer_name": "Concurrent Customer",
        "phone_number": "0999111222",
        "shipping_address": "Damascus",
        "province": "Damascus",
    }

    def test_two_checkouts_for_one_stock_unit_create_one_order_only(self):
        variant = self.create_variant_with_stock(quantity_available=1, sku="SKU-CONFLICT")
        users = [
            self.create_customer(phone_number="0999000001"),
            self.create_customer(phone_number="0999000002"),
        ]
        for user in users:
            self.create_cart_item(user, variant, quantity=1)

        barrier = Barrier(2)
        results = []
        errors = []

        def post_checkout(user):
            close_old_connections()
            client = APIClient()
            client.force_authenticate(user=user)
            try:
                barrier.wait(timeout=5)
                response = client.post("/api/v1/orders/checkout/", self.checkout_payload, format="json")
                results.append(response.status_code)
            except Exception as exc:
                errors.append(exc)
            finally:
                close_old_connections()

        threads = [Thread(target=post_checkout, args=(user,)) for user in users]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=10)

        self.assertEqual(errors, [])
        self.assertEqual(results.count(status.HTTP_201_CREATED), 1)
        self.assertEqual(results.count(status.HTTP_400_BAD_REQUEST), 1)
        self.assertEqual(Order.objects.count(), 1)

        variant.inventory_record.refresh_from_db()
        self.assertEqual(variant.inventory_record.quantity_available, 0)
