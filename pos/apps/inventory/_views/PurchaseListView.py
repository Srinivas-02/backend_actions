from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from pos.apps.inventory.models import PurchaseList, PurchaseListItem, LocationIngredient
from pos.apps.locations.models import LocationModel
from django.shortcuts import get_object_or_404
from django.utils.dateparse import parse_date
from django.utils import timezone
from pos.utils.logger import POSLogger
from pos.apps.utils import user_allowed_locations,ensure_can_access_location
logger = POSLogger(__name__)

class PurchaseListView(APIView):


    def get(self, request, pk=None):
        if pk is not None:
            purchase_list = get_object_or_404(PurchaseList, id=pk)

            if not ensure_can_access_location(request.user, purchase_list.location.id):
                return Response({"error": "You do not have permission to access this location"}, status=403)

            items_data = []
            for item in purchase_list.items.all():
                if item.location_ingredient:
                    items_data.append({
                        "id": item.id,
                        "ingredient_id": item.location_ingredient.id,
                        "ingredient_name": item.location_ingredient.master_ingredient.name,
                        "quantity": item.quantity,
                        "notes": item.notes,
                        "unit": item.location_ingredient.master_ingredient.unit
                    })

            data = {
                "id": purchase_list.id,
                "date": purchase_list.date,
                "location": purchase_list.location.name,
                "location_id": purchase_list.location.id,
                "created_by": purchase_list.created_by,
                "status": purchase_list.status,
                "notes": purchase_list.notes,
                "items": items_data
            }

            return Response(data, status=200)

        else:

            allowed_locations = user_allowed_locations(request.user)
            all_lists = PurchaseList.objects.filter(location__in=allowed_locations).order_by('-date', '-id')
            response_data = []

            for pl in all_lists:
                items_data = []
                for item in pl.items.all():
                    if item.location_ingredient:
                        items_data.append({
                            "id": item.id,
                            "ingredient_id": item.location_ingredient.id,
                            "ingredient_name": item.location_ingredient.master_ingredient.name,
                            "quantity": item.quantity,
                            "notes": item.notes,
                            "unit": item.location_ingredient.master_ingredient.unit
                        })

                response_data.append({
                    "id": pl.id,
                    "date": pl.date,
                    "location": pl.location.name,
                    "location_id": pl.location.id,
                    "status": pl.status,
                    "created_by": pl.created_by,
                    "notes": pl.notes,
                    "items": items_data  # Send full items data here
                })

            return Response(response_data, status=200)

    def post(self, request):

        data = request.data
        location_id = data.get('location_id')
        created_by = data.get('created_by')
        date_str = data.get('date')
        notes = data.get('notes', '')
        items = data.get('items', [])

        if not location_id or not created_by or not items:
            return Response({"error": "location_id, created_by, and items are required"}, status=400)


        date = parse_date(date_str) if date_str else timezone.now().date()
        if not date:
            return Response({"error": "Invalid date format. Use YYYY-MM-DD."}, status=400)

        location = get_object_or_404(LocationModel, id=location_id)

        if not ensure_can_access_location(request.user, location.id):
            return Response({"error": "You do not have permission to access this location"}, status=403)

        purchase_list = PurchaseList.objects.create(
            location=location,
            created_by=created_by,
            date=date,
            notes=notes
        )

        for item in items:
            location_ingredient = get_object_or_404(LocationIngredient, id=item.get('ingredient_id'))
            quantity = item.get('quantity')
            item_notes = item.get('notes', '')

            if quantity is None:
                continue

            PurchaseListItem.objects.create(
                purchase_list=purchase_list,
                location_ingredient=location_ingredient,
                quantity=quantity,
                notes=item_notes
            )

        # Prepare response inline
        items_data = []
        for item in purchase_list.items.all():
            if item.location_ingredient:
                items_data.append({
                    "id": item.id,
                    "ingredient_id": item.location_ingredient.id,
                    "ingredient_name": item.location_ingredient.master_ingredient.name,
                    "quantity": item.quantity,
                    "notes": item.notes,
                    "unit": item.location_ingredient.master_ingredient.unit
                })

        response_data = {
            "id": purchase_list.id,
            "date": purchase_list.date,
            "location": purchase_list.location.name,
            "location_id": purchase_list.location.id,
            "created_by": purchase_list.created_by,
            "status": purchase_list.status,
            "notes": purchase_list.notes,
            "items": items_data
        }

        return Response({
            "message": "Purchase list created",
            "data": response_data
        }, status=201)

    def put(self, request, pk=None):
        purchase_list = get_object_or_404(PurchaseList, id=pk)


        if not ensure_can_access_location(request.user, purchase_list.location.id):
            return Response({"error": "You do not have permission to access this location"}, status=403)
        data = request.data
        notes = data.get('notes', purchase_list.notes)
        items = data.get('items', [])

        purchase_list.notes = notes
        purchase_list.save()

        purchase_list.items.all().delete()

        for item in items:
            location_ingredient = get_object_or_404(LocationIngredient, id=item.get('ingredient_id'))
            quantity = item.get('quantity')
            item_notes = item.get('notes', '')

            if quantity is None:
                continue

            PurchaseListItem.objects.create(
                purchase_list=purchase_list,
                location_ingredient=location_ingredient,
                quantity=quantity,
                notes=item_notes
            )

        # Build response inline
        items_data = []
        for item in purchase_list.items.all():
            if item.location_ingredient:
                items_data.append({
                    "id": item.id,
                    "ingredient_id": item.location_ingredient.id,
                    "ingredient_name": item.location_ingredient.master_ingredient.name,
                    "quantity": item.quantity,
                    "notes": item.notes,
                    "unit": item.location_ingredient.master_ingredient.unit
                })

        response_data = {
            "id": purchase_list.id,
            "date": purchase_list.date,
            "location": purchase_list.location.name,
            "location_id": purchase_list.location.id,
            "created_by": purchase_list.created_by,
            "status": purchase_list.status,
            "notes": purchase_list.notes,
            "items": items_data
        }

        return Response({
            "message": "Purchase list updated",
            "data": response_data
        }, status=200)


    def delete(self, request, pk):
        purchase_list = get_object_or_404(PurchaseList, id=pk)

        if not ensure_can_access_location(request.user, purchase_list.location.id):
            return Response({"error": "You do not have permission to access this location"}, status=403)

        purchase_list.delete()
        return Response({
            "message": "Purchase list deleted",
        }, status=200)
