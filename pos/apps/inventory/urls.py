from django.urls import path

from pos.apps.inventory._views.IngredientsArchiveView import RestoreIngredientView
from .views import MasterIngredientView,InventoryView,PurchaseEntryView,PurchaseListView,ConfirmPurchaseListView,LocationIngredientView,IngredientsArchiveView
from .views import generate_inventory_report



urlpatterns = [
    path('daily-report/', InventoryView.as_view(), name='inventory'),
    path('generate-inventory-report/', generate_inventory_report, name='generate-inventory-report'),
    
    path('master-ingredients/', MasterIngredientView.as_view(), name='master-ingredient'),
    path('master-ingredients/<int:pk>/', MasterIngredientView.as_view()),
    path('location-ingredients/', LocationIngredientView.as_view(), name='location-ingredient'),
    path('location-ingredients/<int:pk>/', LocationIngredientView.as_view()),
    path('purchased-items/', PurchaseEntryView.as_view(), name='purchased-items'),
    path('purchase-list/', PurchaseListView.as_view(),name='purchase-list'),
    path('purchase-list/<int:pk>/',PurchaseListView.as_view()),
    path('purchase-list-confirm/<int:pk>/',ConfirmPurchaseListView.as_view()),

    path('archived-ingredients/', IngredientsArchiveView.as_view(), name='ingredients-archive'),
    path('restored-ingredients/<int:ingredient_id>/', RestoreIngredientView.as_view(), name='restore-ingredient'),
]