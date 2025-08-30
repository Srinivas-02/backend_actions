from django.shortcuts import render

# Create your views here.
from ._views.MasterIngredientView import MasterIngredientView
from ._views.InventoryView import InventoryView
from ._views.generate_inventory_report import generate_inventory_report
from ._views.PurchaseEntryView import PurchaseEntryView
from ._views.PurchaseListView import PurchaseListView
from ._views.ConfirmPurchaseListView import ConfirmPurchaseListView
from ._views.LocationIngredientView import LocationIngredientView
from ._views.IngredientsArchiveView import IngredientsArchiveView