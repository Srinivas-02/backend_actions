from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from pos.apps.inventory.models import PurchaseList, PurchaseListItem
from pos.apps.inventory.models import PurchaseEntry, DailyInventory
from django.db import transaction
from django.utils import timezone
from pos.utils.logger import POSLogger

logger = POSLogger(__name__)

class ConfirmPurchaseListView(APIView):
    def post(self, request, pk):
        try:
            purchase_list = PurchaseList.objects.get(id=pk)
        except PurchaseList.DoesNotExist:
            return Response({"error": "Purchase list not found"}, status=404)

        if purchase_list.status != 'draft':
            return Response({"error": "Only draft lists can be confirmed"}, status=400)

        with transaction.atomic():
            purchase_list.status = 'confirmed'
            purchase_list.save()

            #  create or update PurchaseEntry for each item
            for item in purchase_list.items.all():
                # Skip items without ingredient reference
                if not item.location_ingredient and not item.ingredient:
                    continue
                
                # Use location_ingredient if available, otherwise fall back to legacy ingredient
                location_ingredient = item.location_ingredient
                ingredient_name = ""
                
                if location_ingredient:
                    ingredient_name = location_ingredient.master_ingredient.name
                elif item.ingredient:
                    # Handle legacy data - you might need to create LocationIngredient or skip
                    continue  # For now, skip legacy items in purchase confirmation
                
                purchase_entry, created = PurchaseEntry.objects.get_or_create(
                    date=purchase_list.date,
                    location_ingredient = location_ingredient,
                    location = purchase_list.location,
                    defaults={
                        'quantity' : item.quantity,
                        'added_by': 'system'  # Adding default value for required field
                    }
                )

                if not created:
                    purchase_entry.quantity += item.quantity
                    logger.info(f"\n\n quantity for {ingredient_name} is updated with quantity {item.quantity}")
                    purchase_entry.save()

                # update daily inventory report purchase quantity
                try:
                    daily_inv = DailyInventory.objects.get(
                        date = purchase_list.date,
                        location_ingredient = location_ingredient,
                        location = purchase_list.location
                    )
                    daily_inv.opening_stock += item.quantity
                    daily_inv.closing_stock += item.quantity 

                    daily_inv.save()
                except DailyInventory.DoesNotExist:
                    return Response(
                        {"error" : f"DailyInventory report not found for {ingredient_name} on {purchase_list.date}"}
                    )
                

        return Response({"message": "Purchase list confirmed and entries recorded"}, status=200)
