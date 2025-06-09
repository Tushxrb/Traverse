from django.urls import path
from main import views
from django.contrib.auth.views import LogoutView

urlpatterns = [
    path('', views.index, name='index'),

    # Employee URLs
    path('employee_login/', views.employee_login, name='employee_login'),
    path('reset_password/', views.reset_password, name='reset_password'),
    path('verify_otp/', views.verify_otp, name='verify_otp'),
    path('verify_otp_check/', views.verify_otp_check, name='verify_otp_check'),

    # Admin URLs
    path('admin_login/', views.admin_login, name='admin_login'),
    path('admin_dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('delete-user/<int:user_id>/', views.delete_user, name='delete_user'),
    path('admin-dashboard/update/', views.update_users, name='update_users'),

    # Logout
    path('admin_logout/', views.admin_logout, name='admin_logout'),
    path('employee_logout/', views.employee_logout, name='employee_logout'),

    path('dashboard/', views.dashboard, name='dashboard'),
]
