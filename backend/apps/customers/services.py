from django.contrib.auth import get_user_model
from rest_framework_simplejwt.tokens import RefreshToken

User = get_user_model()


def login_customer(phone_number: str, password: str) -> dict:
    try:
        user = User.objects.get(phone_number=phone_number, user_type='customer')
    except User.DoesNotExist:
        raise ValueError("رقم الهاتف أو كلمة المرور غير صحيحة")

    if not user.check_password(password):
        raise ValueError("رقم الهاتف أو كلمة المرور غير صحيحة")

    if not user.is_active:
        raise ValueError("هذا الحساب معطل")

    refresh = RefreshToken.for_user(user)
    return {
        "access": str(refresh.access_token),
        "refresh": str(refresh),
        "user_type": user.user_type,
        "is_phone_verified": user.is_phone_verified,
    }
