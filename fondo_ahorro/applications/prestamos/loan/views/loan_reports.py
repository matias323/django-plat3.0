# views/loan_reports.py

from django.contrib.auth.decorators import login_required
from django.shortcuts import render


@login_required
def loan_reports(request):
    return render(request, "loan/reports/loan_reports.html")