from django.contrib import admin

from .models.person import (
    Person, 
    PersonType, 
    PersonContactType, 
    PersonContact, 
    PersonAddress,
)
from .models.user import  User, UserPermission
from .models.session import Session

from .models import Document, DocumentType
from .models import Observation
from .models import Request
from .models.location import Region, Commune

from .models import (
    Employee,
    EmployeeGrade,
    EmployeeContractType,
    EmployeeSalaryType,
    EmployeeQualificationType,
)

from .models import (
    Partner,
    PartnerContributionType,
    PartnerVoluntaryDiscount,
    PartnerBalance,
    PartnerReentry,
    PartnerMovementType,
    PartnerMovement,
)

# USER
admin.site.register(Person)
admin.site.register(PersonType)
admin.site.register(PersonContactType)
admin.site.register(PersonContact)
admin.site.register(PersonAddress)
admin.site.register(User)
admin.site.register(UserPermission)
admin.site.register(Session)

# INFO
admin.site.register(Document)
admin.site.register(DocumentType)
admin.site.register(Observation)

# REQUESTS
admin.site.register(Request)

# EMPLOYEE
admin.site.register(Employee)
admin.site.register(EmployeeGrade)
admin.site.register(EmployeeContractType)
admin.site.register(EmployeeSalaryType)
admin.site.register(EmployeeQualificationType)

# PARTNER
admin.site.register(Partner)
admin.site.register(PartnerContributionType)
admin.site.register(PartnerVoluntaryDiscount)
admin.site.register(PartnerBalance)
admin.site.register(PartnerReentry)
admin.site.register(PartnerMovementType)
admin.site.register(PartnerMovement)

# LOCATION
admin.site.register(Region)
admin.site.register(Commune)

# @admin.register(Person)
# class PersonAdmin(admin.ModelAdmin):
#     list_display = ('get_rut', 'first_name', 'last_name_1', 'last_name_2', 'birth_date')
#     search_fields = ('rut', 'first_name', 'last_name_1')
#     list_filter = ('birth_date',)