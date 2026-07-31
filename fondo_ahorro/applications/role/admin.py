from django.contrib import admin

# Register your models here.

from .models import Role, Permission, RoleApp, RoleUser

admin.site.register(Role)
admin.site.register(Permission)
admin.site.register(RoleApp)
admin.site.register(RoleUser)
