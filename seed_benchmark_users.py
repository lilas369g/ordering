import os
import sys
import django

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.contrib.auth import get_user_model
from apps.customers.models import CustomerProfile, AccountSource

User = get_user_model()

PASSWORD = 'Test@1234'

for i in range(1, 11):
    phone = f'091100000{i}'
    user, created = User.objects.get_or_create(
        phone_number=phone,
        defaults={
            'user_type': 'customer',
            'is_active': True,
            'is_phone_verified': True,
        },
    )
    if created:
        user.set_password(PASSWORD)
        user.save()
        CustomerProfile.objects.get_or_create(
            user=user,
            defaults={'account_source': AccountSource.ADMIN_CREATED},
        )
        print(f'Created: {phone}')
    else:
        print(f'Already exists: {phone}')

from apps.catalog.models import Product
if not Product.objects.exists():
    from django.core.management import call_command
    print('No products found — seeding demo store...')
    call_command('seed_demo_store')

print('Done.')
