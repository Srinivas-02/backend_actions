# accounts/urls.py

from django.urls import path

from pos.apps.accounts._views.login import LocationLoginView, UserLoginView
from .views import (
    ChangePasswordView,
    FranchiseAdminView,
    LogoutView,
    StaffView,
    GoogleLoginView
)
from rest_framework_simplejwt.views import TokenVerifyView
from pos.apps.accounts._views.token_refresh import CustomTokenRefreshView

urlpatterns = [
    path('login-location/', LocationLoginView.as_view(), name='login'),
    path('login/', UserLoginView.as_view(), name='login'),
    path('google/login/',GoogleLoginView.as_view(), name='google_login'),
    path('change-password/', ChangePasswordView.as_view()),
    path('franchise-admin/', FranchiseAdminView.as_view()),
    path('staff/', StaffView.as_view()),
    path('logout/', LogoutView.as_view()),
    path('token/refresh/', CustomTokenRefreshView.as_view(), name='token_refresh'),
    path('token/verify/', TokenVerifyView.as_view(), name='token_verify'),
]
