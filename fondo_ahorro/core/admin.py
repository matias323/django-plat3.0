from django.contrib import admin

from .models.person import Person, PersonType
from .models.user import  User


admin.site.register(Person)
admin.site.register(PersonType)
admin.site.register(User)


# @admin.register(Person)
# class PersonAdmin(admin.ModelAdmin):
#     list_display = ('get_rut', 'first_name', 'last_name_1', 'last_name_2', 'birth_date')
#     search_fields = ('rut', 'first_name', 'last_name_1')
#     list_filter = ('birth_date',)