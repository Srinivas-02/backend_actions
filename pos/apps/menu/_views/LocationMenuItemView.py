import base64
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from pos.apps.menu.models import LocationMenuItem, MasterMenuItem
from pos.apps.locations.models import LocationModel
from django.shortcuts import get_object_or_404
from pos.apps.utils import ensure_can_access_location
from pos.utils.logger import POSLogger



class LocationMenuItemView(APIView):
    """
    Super Admin:
        Bulk assign menu items to a location (POST)
        Bulk update availability (PATCH)
        Unassign (DELETE)
        Read any assignment (GET)
    Franchise Admin:
        Read assignment rows for their own locations only (GET)
    """


    def encode_image_to_data_url(self, raw_bytes):
        if not raw_bytes:
            return None
        base64_string = base64.b64encode(raw_bytes).decode('utf-8')
        return f"data:image/jpeg;base64,{base64_string}"
    
    def get(self, request, pk=None):
        """List assigned/unassigned menu items for a location or get a single assignment row."""

        if pk:
            try:
                location_menu_item = LocationMenuItem.objects.select_related(
                    'menu_item', 'location'
                ).get(pk=pk)
            except LocationMenuItem.DoesNotExist:
                return Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)

            if not ensure_can_access_location(request.user, location_menu_item.location_id):
                return Response({'error': 'Not allowed'}, status=status.HTTP_403_FORBIDDEN)

            data = {
                'id': location_menu_item.id,
                'menu_item_id': location_menu_item.menu_item.id,
                'menu_item_name': location_menu_item.menu_item.name,
                'menu_item_price': float(location_menu_item.price) if location_menu_item.price is not None else float(location_menu_item.menu_item.price),
                'menu_item_description': location_menu_item.menu_item.description,
                'menu_item_category': location_menu_item.menu_item.category.id,
                'menu_item_category_name': location_menu_item.menu_item.category.name,
                'menu_item_image': self.encode_image_to_data_url(location_menu_item.menu_item.image),
                'location_id': location_menu_item.location.id,
                'location_name': location_menu_item.location.name,
                'is_assigned': location_menu_item.is_assigned,
                'is_available': location_menu_item.is_available
            }
            return Response(data)

        location_id = request.query_params.get('location_id')
        assigned_param = request.query_params.get('assigned')  # "true" / "false" optional

        if not location_id:
            return Response({'error': 'location_id is required'}, status=status.HTTP_400_BAD_REQUEST)

        if not ensure_can_access_location(request.user, location_id):
            return Response({'error': 'Not allowed'}, status=status.HTTP_403_FORBIDDEN)

        queryset = LocationMenuItem.objects.select_related('menu_item', 'location').filter(
            location_id=location_id,
            menu_item__is_active=True
        )

        # Assigned filter (default = true)
        if assigned_param is None or assigned_param.lower() == 'true':
            queryset = queryset.filter(is_assigned=True)
        elif assigned_param.lower() == 'false':
            queryset = queryset.filter(is_assigned=False)

        data = []
        for item in queryset:
            data.append({
                'id': item.id,
                'menu_item_id': item.menu_item.id,
                'menu_item_name': item.menu_item.name,
                'menu_item_price': float(item.price) if item.price is not None else float(item.menu_item.price),
                'menu_item_description': item.menu_item.description,
                'menu_item_category': item.menu_item.category.id,
                'menu_item_category_name': item.menu_item.category.name,
                'menu_item_image': self.encode_image_to_data_url(item.menu_item.image),
                'location_id': item.location.id,
                'location_name': item.location.name,
                'is_assigned': item.is_assigned,
                'is_available': item.is_available
            })

        return Response({'location_menu_items': data})

    def post(self, request):
        """Bulk assign menu items to a location or reassign if previously unassigned."""
        if not (getattr(request.user, 'is_super_admin', False) or getattr(request.user, 'is_franchise_admin', False)):
            return Response({'error': 'only super admin or franchise admin allowed'}, status=status.HTTP_403_FORBIDDEN)

        location_id = request.data.get('location_id')
        menu_items_payload = request.data.get('menu_items', [])

        if not location_id or not menu_items_payload:
            return Response({'error': 'location_id and menu_items are required'}, status=400)

        location = get_object_or_404(LocationModel, pk=location_id)
        results = []

        for menu_item_object in menu_items_payload:
            master_menu_item_id = menu_item_object.get('id')
            franchise_price = menu_item_object.get('franchise_price')
            is_available = bool(menu_item_object.get('is_available', True))
            if master_menu_item_id is None:
                continue

            master_menu_item = get_object_or_404(MasterMenuItem, pk=master_menu_item_id, is_active=True)

            location_menu_item, created = LocationMenuItem.objects.get_or_create(
                menu_item=master_menu_item,
                location=location,
                defaults={
                    'price': franchise_price,
                    'is_assigned': True,
                    'is_available': is_available
                }
            )
            if not created:
                location_menu_item.is_assigned = True
                location_menu_item.is_available = is_available
                if franchise_price is not None:
                    location_menu_item.price = franchise_price
                location_menu_item.save(update_fields=['is_assigned', 'is_available', 'price'])

            results.append({
                'id': location_menu_item.id,
                'menu_item_id': location_menu_item.menu_item.id,
                'menu_item_name': location_menu_item.menu_item.name,
                'menu_item_price': float(location_menu_item.price) if location_menu_item.price is not None else float(location_menu_item.menu_item.price),
                'location_id': location_menu_item.location.id,
                'location_name': location_menu_item.location.name,
                'is_assigned': location_menu_item.is_assigned,
                'is_available': location_menu_item.is_available
            })

        return Response({'status': 'success', 'data': results}, status=status.HTTP_201_CREATED)


    def patch(self, request, pk=None):
        """Toggle availability for assigned menu items, or update price """
        
        if pk:
            try:
                if not (getattr(request.user, 'is_super_admin', False) or getattr(request.user, 'is_franchise_admin', False)):
                    return Response({'error': 'only super admin or franchise admin allowed'}, status=status.HTTP_403_FORBIDDEN)        
                location_menu_item = LocationMenuItem.objects.get(pk=pk, is_assigned=True)
            except LocationMenuItem.DoesNotExist:
                return Response({'error': 'Location menu item not found or not assigned'}, status=status.HTTP_404_NOT_FOUND)
            
            updated_price = request.data.get('franchise_price')
            is_available = request.data.get('is_available')

            if updated_price is not None:
                location_menu_item.price = updated_price

            if is_available is not None:
                location_menu_item.is_available = is_available

            data = {
                'id': location_menu_item.id,
                'menu_item_id': location_menu_item.menu_item.id,
                'menu_item_name': location_menu_item.menu_item.name,
                'menu_item_price': float(location_menu_item.price) if location_menu_item.price is not None else float(location_menu_item.menu_item.price),
                'location_id': location_menu_item.location.id,
                'location_name': location_menu_item.location.name,
                'is_assigned': location_menu_item.is_assigned,
                'is_available': location_menu_item.is_available
            }

            location_menu_item.save(update_fields=['price', 'is_available'])

            return Response({'status': 'success', 'data': data}, status=status.HTTP_200_OK)

        menu_items_payload = request.data.get('menu_items', [])
        if not menu_items_payload:
            return Response({'error': 'menu_items are required'}, status=status.HTTP_400_BAD_REQUEST)

        updated = []
        for menu_item_object in menu_items_payload:
            location_menu_item_id = menu_item_object.get('id')
            is_available = menu_item_object.get('is_available')
            if location_menu_item_id is None or is_available is None:
                continue
            try:
                location_menu_item = LocationMenuItem.objects.get(id=location_menu_item_id, is_assigned=True)
            except LocationMenuItem.DoesNotExist:
                continue
            if location_menu_item.is_available != is_available:
                location_menu_item.is_available = is_available
                location_menu_item.save(update_fields=['is_available'])

            updated.append({
                'id': location_menu_item.id,
                'menu_item_id': location_menu_item.menu_item.id,
                'menu_item_name': location_menu_item.menu_item.name,
                'location_id': location_menu_item.location.id,
                'location_name': location_menu_item.location.name,
                'is_available': location_menu_item.is_available,
                'is_assigned': location_menu_item.is_assigned
            })

        return Response({'status': 'success', 'data': updated}, status=status.HTTP_200_OK)


    def delete(self, request, pk=None):
        """Unassign a menu item from a location without deleting the row."""
        if not (getattr(request.user, 'is_super_admin', False) or getattr(request.user, 'is_franchise_admin', False)):
            return Response({'error': 'only super admin or franchise admin allowed'}, status=status.HTTP_403_FORBIDDEN)

        location_menu_item_id = pk or request.data.get('id')
        if not location_menu_item_id:
            return Response({'error': 'Assignment ID required'}, status=400)

        try:
            location_menu_item = LocationMenuItem.objects.get(id=location_menu_item_id, is_assigned=True)
        except LocationMenuItem.DoesNotExist:
            return Response({'error': 'Menu item not found or already unassigned'}, status=status.HTTP_404_NOT_FOUND)

        location_menu_item.is_assigned = False
        location_menu_item.is_available = False
        location_menu_item.save(update_fields=['is_assigned', 'is_available'])

        return Response({'status': 'success', 'message': f"Menu item '{location_menu_item.menu_item.name}' unassigned successfully"}, status=status.HTTP_200_OK)
