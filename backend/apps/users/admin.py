from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from .models import User


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    model = User
    list_display = ('id', 'phone_number', 'user_type', 'is_phone_verified', 'is_staff', 'is_active')
    ordering = ('id',)
    fieldsets = (
        (None, {'fields': ('phone_number', 'password')}),
        ('Personal info', {'fields': ('first_name', 'last_name', 'email')}),
        ('Permissions', {'fields': ('user_type', 'is_phone_verified', 'is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Important dates', {'fields': ('last_login',)}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('phone_number', 'user_type', 'password1', 'password2', 'is_staff', 'is_active'),
        }),
    )
    search_fields = ('phone_number', 'first_name', 'last_name')
