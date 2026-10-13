from django.contrib import admin

# Register your models here.
from .models import (Deposit, DepositApplication, ProcessType)

admin.site.register(Deposit)
admin.site.register(DepositApplication)
admin.site.register(ProcessType)