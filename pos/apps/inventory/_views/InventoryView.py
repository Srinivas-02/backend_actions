import traceback
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from pos.apps.inventory.models import DailyInventory, LocationIngredient, LocationModel, PurchaseEntry
from django.shortcuts import get_object_or_404
from django.db.models import Sum
from datetime import timedelta, date
from decimal import Decimal, ROUND_HALF_UP
from pos.utils.logger import POSLogger
from django.db import transaction



def round_qty(val, places=2):
    try:
        return float(Decimal(str(val)).quantize(Decimal('1.' + '0'*places), rounding=ROUND_HALF_UP))
    except Exception:
        return val


class InventoryView(APIView):
    def get(self, request):
        query_date = request.GET.get("date")
        location_id = request.GET.get("location_id")

        if not query_date:
            return Response({"error": "Date is required"}, status=status.HTTP_400_BAD_REQUEST)
        
        # check if location exists or not
        if location_id:
            if not LocationModel.objects.filter(id=location_id).exists():
                return Response({"error": "Location not found"}, status=status.HTTP_404_NOT_FOUND)


        # Filter out inactive master ingredients
        queryset = (
                DailyInventory.objects
                .select_related("location_ingredient__master_ingredient", "location")
                .filter(date=query_date, location_ingredient__master_ingredient__is_active=True)
                .order_by("location_ingredient__master_ingredient__name")
            )
        if location_id is not None:
            queryset = queryset.filter(location_id=location_id)

        data = []
        for entry in queryset:
            if entry.location_ingredient:
                master = entry.location_ingredient.master_ingredient
                data.append({
                    "id": entry.id,
                    "date": entry.date,  
                    "ingredient_id": entry.location_ingredient.id,
                    "ingredient_name": master.name,
                    "ingredient_unit": master.unit,
                    "location_id": entry.location.id,
                    "location_name": entry.location.name,
                    "is_composite": master.is_composite,
                    "opening_stock": round_qty(entry.opening_stock),
                    "used_qty": round_qty(entry.used_qty),
                    "prepared_qty": round_qty(entry.prepared_qty),
                    "closing_stock": round_qty(entry.closing_stock),
                    "raw_equiv": {k: round_qty(v) for k, v in entry.raw_equiv.items()} if entry.raw_equiv else None,
                })

        return Response({"status": "success", "data": data}, status=200)

    def post(self, request):
        data = request.data
        try:
            location_ingredient = get_object_or_404(LocationIngredient, id=data.get("ingredient_id"))
            location = get_object_or_404(LocationModel, id=data.get("location_id"))
            report_date = data.get("date")
            opening_stock = float(data.get("opening_stock", 0))

            used_qty = float(data.get("used_qty", 0))
            prepared_qty = float(data.get("prepared_qty", 0)) if location_ingredient.master_ingredient.is_composite else 0.0

            
            closing_stock = opening_stock  + prepared_qty - used_qty

            raw_equiv = None
            if location_ingredient.master_ingredient.is_composite and prepared_qty > 0:
                recipe = location_ingredient.master_ingredient.recipe_ratios or {}
                recipe_yield = location_ingredient.master_ingredient.recipe_yield or 1
                scale = prepared_qty / recipe_yield
                raw_equiv = {}

                for raw_id_str, ratio in recipe.items():
                    raw_id = int(raw_id_str)
                    qty_used = round(ratio * prepared_qty, 3)
                    raw_equiv[str(raw_id)] = qty_used

                    raw_row = DailyInventory.objects.filter(
                        date=report_date,
                        location_ingredient__master_ingredient_id=raw_id,
                        location=location
                    ).first()

                    if raw_row:
                        raw_row.used_qty += qty_used
                        raw_row.closing_stock = raw_row.opening_stock  - raw_row.used_qty
                        raw_row.save()
                    else:
                        return Response({
                            "status": "error",
                            "message": f"Inventory for raw ingredient ID {raw_id} not found for the day. Please add it first."
                        }, status=400)

            inventory = DailyInventory.objects.create(
                date=report_date,
                location_ingredient=location_ingredient,
                location=location,
                opening_stock=opening_stock,
                used_qty=used_qty,
                prepared_qty=prepared_qty,
                closing_stock=closing_stock,
                raw_equiv=raw_equiv 

            )

            # Handle the response data safely
            if inventory.location_ingredient:
                response_data = {
                    "date": inventory.date,
                    "id": inventory.id,
                    "ingredient_id": inventory.location_ingredient.id,
                    "ingredient_name": inventory.location_ingredient.master_ingredient.name,
                    "location_id": inventory.location.id,
                    "location_name": inventory.location.name,
                    "is_composite": inventory.location_ingredient.master_ingredient.is_composite,
                    "opening_stock": round_qty(inventory.opening_stock),
                    "used_qty": round_qty(inventory.used_qty),
                    "prepared_qty": round_qty(inventory.prepared_qty),
                    "closing_stock": round_qty(inventory.closing_stock),
                    "raw_equiv": {k: round_qty(v) for k, v in inventory.raw_equiv.items()} if inventory.raw_equiv else None
                }
            elif inventory.ingredient:
                # Fallback to legacy ingredient field
                response_data = {
                    "date": inventory.date,
                    "id": inventory.id,
                    "ingredient_id": inventory.ingredient.id,
                    "ingredient_name": inventory.ingredient.name,
                    "location_id": inventory.location.id,
                    "location_name": inventory.location.name,
                    "is_composite": inventory.ingredient.is_composite,
                    "opening_stock": round_qty(inventory.opening_stock),
                    "used_qty": round_qty(inventory.used_qty),
                    "prepared_qty": round_qty(inventory.prepared_qty),
                    "closing_stock": round_qty(inventory.closing_stock),
                    "raw_equiv": {k: round_qty(v) for k, v in inventory.raw_equiv.items()} if inventory.raw_equiv else None
                }
            else:
                return Response({
                    "status": "error", 
                    "message": "Inventory item has no ingredient reference"
                }, status=400)

            return Response({
                "status": "success",
                "data": response_data
            }, status=status.HTTP_201_CREATED)

        except Exception as e:
            return Response({"status": "error", "message": str(e)}, status=400)

    def patch(self, request):
        import traceback
        logger = POSLogger(__name__)
        logger.info("Updating inventory entry")
        logger.info(f"Request data: {request.data}")
        data = request.data
        try:
            inventory = get_object_or_404(DailyInventory, id=data.get("id"))
            location_ingredient = inventory.location_ingredient
            location = inventory.location
            report_date = inventory.date

            # Save previous prepared_qty for "undo" logic
            previous_prepared_qty = inventory.prepared_qty if location_ingredient.master_ingredient.is_composite else 0.0


            opening_stock = float(data.get("opening_stock", inventory.opening_stock))
            used_qty = float(data.get("used_qty", inventory.used_qty))
            # Handle None for prepared_qty
            prepared_qty_val = data.get("prepared_qty", previous_prepared_qty)
            if prepared_qty_val is None:
                prepared_qty_val = previous_prepared_qty
            prepared_qty = float(prepared_qty_val) if location_ingredient.master_ingredient.is_composite else 0.0

            inventory.opening_stock = opening_stock
            inventory.used_qty = used_qty
            inventory.prepared_qty = prepared_qty if location_ingredient.master_ingredient.is_composite else 0.0

            inventory.closing_stock = inventory.opening_stock + inventory.prepared_qty - inventory.used_qty

            # After calculating prepared_qty, before any database updates:

            if location_ingredient.master_ingredient.is_composite:
                recipe = location_ingredient.master_ingredient.recipe_ratios or {}
                recipe_yield = location_ingredient.master_ingredient.recipe_yield or 1
                
                # validate all ingredients
                validation_data = {}  
                
                for raw_id_str, ratio in recipe.items():
                    raw_id = int(raw_id_str)
                    previous_qty_used = round(ratio * previous_prepared_qty, 3)
                    new_qty_used = round(ratio * prepared_qty, 3)

                    raw_row = DailyInventory.objects.filter(
                        date=report_date,
                        location_ingredient__master_ingredient_id=raw_id,  
                        location=location
                    ).first()

                    if raw_row:
                        # Check if stock is enough using closing stock
                        available_qty = raw_row.closing_stock + previous_qty_used
                        if new_qty_used > available_qty:
                            return Response({
                                "status": "error",
                                "message": f"Not enough stock of {raw_row.location_ingredient.master_ingredient.name}. "
                                        f"Available: {available_qty}, Required: {new_qty_used}."
                            }, status=400)
                        
                        validation_data[raw_id] = {
                            'raw_row': raw_row,
                            'previous_qty_used': previous_qty_used,
                            'new_qty_used': new_qty_used
                        }
                    else:
                        if new_qty_used > 0:
                            return Response({
                                "status": "error",
                                "message": f"No stock record found for raw ingredient id {raw_id}. "
                                        f"Cannot prepare this composite item."
                            }, status=400)
                        
                        validation_data[raw_id] = {
                            'raw_row': None,
                            'previous_qty_used': previous_qty_used,
                            'new_qty_used': new_qty_used
                        }

                # now update
                with transaction.atomic():
                    raw_equiv = {}
                    
                    for raw_id, data in validation_data.items():
                        raw_row = data['raw_row']
                        previous_qty_used = data['previous_qty_used']
                        new_qty_used = data['new_qty_used']
                        
                        if raw_row:
                            # Update existing row
                            raw_row.used_qty = raw_row.used_qty - previous_qty_used + new_qty_used
                            raw_row.closing_stock = raw_row.opening_stock - raw_row.used_qty
                            raw_row.save()
                        else:
                            # Create new row if needed (only if new_qty_used > 0)
                            if new_qty_used > 0:
                                raw_location_ingredient = LocationIngredient.objects.filter(
                                    location=location, master_ingredient_id=raw_id
                                ).first()
                                if not raw_location_ingredient:
                                    logger.error(f"No LocationIngredient found for raw ingredient ID {raw_id}")
                                    return Response({
                                        "status": "error",
                                        "message": f"No LocationIngredient found for raw ingredient ID {raw_id}."
                                    }, status=400)
                                
                                DailyInventory.objects.create(
                                    date=report_date,
                                    location_ingredient=raw_location_ingredient,
                                    location=location,
                                    opening_stock=0.0,
                                    used_qty=new_qty_used,
                                    prepared_qty=0.0,
                                    closing_stock=0.0 - new_qty_used,
                                    raw_equiv=None
                                )
                        
                        raw_equiv[str(raw_id)] = new_qty_used

                    inventory.raw_equiv = raw_equiv # If not composite, ensure raw_equiv is None
            elif hasattr(inventory, 'raw_equiv'):
                inventory.raw_equiv = None

            inventory.save()

            # Always round raw_equiv values in response for consistency
            raw_equiv_rounded = {k: round_qty(v) for k, v in inventory.raw_equiv.items()} if inventory.raw_equiv else None

            return Response({
                "status": "success",
                "data": {
                    "id": inventory.id,
                    "date": inventory.date,
                    "ingredient_id": location_ingredient.id,
                    "ingredient_name": location_ingredient.master_ingredient.name,
                    "location_id": location.id,
                    "location_name": location.name,
                    "is_composite": location_ingredient.master_ingredient.is_composite,
                    "opening_stock": round_qty(inventory.opening_stock),
                    "prepared_qty": round_qty(inventory.prepared_qty) if location_ingredient.master_ingredient.is_composite else None,
                    "used_qty": round_qty(inventory.used_qty),
                    "closing_stock": round_qty(inventory.closing_stock),
                    "raw_equiv": raw_equiv_rounded
                }
            }, status=200)

        except Exception as e:
            tb = traceback.format_exc()
            logger.error(f"Exception in PATCH /inventory/daily-report/: {str(e)}\n{tb}")
            return Response({"status": "error", "message": str(e), "trace": tb}, status=400)

    def delete(self, request):
        inventory_id = request.data.get("id")
        if not inventory_id:
            return Response({"status": "error", "message": "id is required"}, status=400)

        try:
            inventory = get_object_or_404(DailyInventory, id=inventory_id)
            inventory.delete()
            return Response({"status": "success", "message": "Inventory entry deleted"}, status=200)
        except Exception as e:
            return Response({"status": "error", "message": str(e)}, status=400)
