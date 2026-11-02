from django.urls import path
from .views import RoleListView, RoleCreateView, RoleUpdateView

app_name = 'role'  

urlpatterns = [
    path('roles/', RoleListView.as_view(), name='role_list'),
    path('roles/nuevo/', RoleCreateView.as_view(), name='role_create'),
    path('roles/editar/<int:pk>/', RoleUpdateView.as_view(), name='role_update'), 
]