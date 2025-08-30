from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from pos.apps.inventory.models import PurchaseEntry, LocationIngredient
from pos.apps.locations.models import LocationModel
from pos.utils.logger import POSLogger
from pos.apps.utils import ensure_can_access_location

logger = POSLogger(__name__)
class PurchaseEntryView(APIView):
    def get(self, request):
        date = request.query_params.get('date')
        location_id = request.query_params.get('location_id')


        if not date and not location_id:
            return Response({'status': 'error', 'message': 'Date and  location_id is required'}, status=400)

        if not ensure_can_access_location(request.user, location_id):
            return Response({"error": "You do not have permission to access this location"}, status=403)

        # if no date and location id, fetch all entries ( for testing purpose )
        entries = PurchaseEntry.objects.filter(date=date, location_id=location_id) if date and location_id else PurchaseEntry.objects.all()

        data = []
        for entry in entries:
            # Handle both new location_ingredient and legacy ingredient fields
            if entry.location_ingredient:
                data.append({
                    'id': entry.id,
                    'ingredient': entry.location_ingredient.master_ingredient.name,
                    'ingredient_id': entry.location_ingredient.id,
                    'ingredient_unit': entry.location_ingredient.master_ingredient.unit,
                    'quantity': entry.quantity,
                    'unit': entry.location_ingredient.master_ingredient.unit,
                    'date': entry.date,
                    'location': entry.location.name,
                    'location_id': entry.location.id,
                    'added_by': entry.added_by
                })

        return Response({'status': 'success', 'data': data}, status=200)

    def post(self, request):
        data = request.data
        try:
            date = data.get('date')
            print(f"\n\n date is {date} \n\n")

            
            location_ingredient = get_object_or_404(LocationIngredient, id=data['ingredient_id'])
            location = get_object_or_404(LocationModel, id=data['location_id'])

            if not ensure_can_access_location(request.user, location.id):
                return Response({"error": "You do not have permission to access this location"}, status=403)

            if not date or not location_ingredient or not location:
                return Response({'status': 'error', 'message': 'Date, ingredient_id, and location_id are required'}, status=400)

            purchase = PurchaseEntry.objects.create(
                date=date,
                location_ingredient=location_ingredient,
                quantity=data['quantity'],
                location=location,
                added_by=data.get('added_by', 'unknown')
            )

            if purchase.location_ingredient:
                response_data = {
                    "id": purchase.id,
                    'ingredient': purchase.location_ingredient.master_ingredient.name,
                    'ingredient_id': purchase.location_ingredient.id,
                    'ingredient_unit': purchase.location_ingredient.master_ingredient.unit,
                    'quantity': purchase.quantity,
                    'unit': purchase.location_ingredient.master_ingredient.unit,
                    'date': purchase.date,
                    'location': purchase.location.name,
                    'location_id': purchase.location.id,
                    'added_by': purchase.added_by
                }
            return Response(
                {
                    'status': 'success',
                    "data": response_data
                }
            )
        except Exception as e:
            return Response({'status': 'error', 'message': str(e)}, status=400)

    def patch(self, request):
        data = request.data
        entry_id = data.get('id')

        if not entry_id:
            return Response({'status': 'error', 'message': 'Entry ID is required'}, status=400)

        purchase = get_object_or_404(PurchaseEntry, id=entry_id)

        if not ensure_can_access_location(request.user, purchase.location.id):
            return Response({"error": "You do not have permission to access this location"}, status=403)

        if 'quantity' in data:
            purchase.quantity = data['quantity']
        if 'ingredient_id' in data:
            purchase.location_ingredient = get_object_or_404(LocationIngredient, id=data['ingredient_id'])
        if 'location_id' in data:
            purchase.location = get_object_or_404(LocationModel, id=data['location_id'])
        if 'added_by' in data:
            purchase.added_by = data['added_by']

        purchase.save()
        
        if purchase.location_ingredient:
            response_data = {
                "id": purchase.id,
                'ingredient': purchase.location_ingredient.master_ingredient.name,
                'ingredient_id': purchase.location_ingredient.id,
                'ingredient_unit': purchase.location_ingredient.master_ingredient.unit,
                'quantity': purchase.quantity,
                'unit': purchase.location_ingredient.master_ingredient.unit,
                'date': purchase.date,
                'location': purchase.location.name,
                'location_id': purchase.location.id,
                'added_by': purchase.added_by
            }
            
        return Response(
            {
                'status': 'success',
                "data": response_data
            }
        )

    def delete(self, request):
        entry_id = request.data.get('id')
        if not entry_id :
            return Response({'status': 'error', 'message': 'ID is required'}, status=400)

        purchase = get_object_or_404(PurchaseEntry, id=entry_id)

        if not ensure_can_access_location(request.user, purchase.location.id):
            return Response({"error": "You do not have permission to access this location"}, status=403)

        purchase.delete()
        return Response({'status': 'success', 'message': 'Entry deleted'}, status=200)
    