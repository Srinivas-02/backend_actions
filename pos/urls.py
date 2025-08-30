"""
URL configuration for pos_backend project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path,include
from pos.health_view import health_check
urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('pos.apps.accounts.urls')),
    path('locations/', include('pos.apps.locations.urls')),
    path('menu/', include('pos.apps.menu.urls')),
    path('health/', health_check, name='health_check'),
    path('orders/', include('pos.apps.orders.urls')),
    path('inventory/', include('pos.apps.inventory.urls')),
    path('dashboard/', include('pos.apps.dashboard.urls')),

]
