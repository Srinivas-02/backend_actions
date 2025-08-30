from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from pos.apps.menu.models import MasterMenuItem

class MasterMenuItemLocationsView(APIView):
    def get(self, request, menu_item_id):
        if not getattr(request.user, 'is_super_admin', False):
            return Response({'error': 'Only super admin allowed'}, status=status.HTTP_403_FORBIDDEN)

        menu_item = MasterMenuItem.objects.prefetch_related('location_items__location').get(pk=menu_item_id)
        locations = [
            {
                "location_id": li.location.id,
                "location_name": li.location.name,
                "price": float(li.price) if li.price is not None else float(menu_item.price),
                "is_available": li.is_available
            }
            for li in menu_item.location_items.all()
        ]
        return Response({
            "status": "success",
            "message": "Locations for menu item retrieved successfully",
            "menu_item_id": menu_item.id,
            "menu_item_name": menu_item.name,
            "locations": locations
        })
