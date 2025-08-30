from django.urls import path

from pos.apps.menu._views.CategoryArchiveView import CategoryArchiveView
from pos.apps.menu._views.MenuItemsArchive import RestoreMenuItem
from .views import MenuItemsView, CategoryView,MasterMenuItemView, MasterMenuCategoryView,LocationMenuItemView, LocationCategoryView, MasterMenuItemLocationsView,MenuItemsArchive

urlpatterns = [
    path('menu-items/', MenuItemsView.as_view()),
    path('categories/', CategoryView.as_view()),
    path('master-menu-items/', MasterMenuItemView.as_view()),  
    path('master-menu-items/<int:pk>/', MasterMenuItemView.as_view()),  
    path('master-menu-categories/', MasterMenuCategoryView.as_view()),
    path('master-menu-categories/<int:pk>/', MasterMenuCategoryView.as_view()),  
    path('location-menu-items/', LocationMenuItemView.as_view()),  # assigning menu items to locations
    path('location-menu-items/<int:pk>/', LocationMenuItemView.as_view()), 
    path('location-categories/', LocationCategoryView.as_view()),  # assigning categories to locations
    path('location-categories/<int:pk>/', LocationCategoryView.as_view()), 

    path('master-menu-item-locations/<int:menu_item_id>/', MasterMenuItemLocationsView.as_view()),  # Get locations for a master menu item
    path('archived-menu-items/', MenuItemsArchive.as_view()),  
    path('restore-menu-item/<int:item_id>/', RestoreMenuItem.as_view()),
    path('archived-categories/', CategoryArchiveView.as_view()),  
]