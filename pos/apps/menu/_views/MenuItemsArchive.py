import base64
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from pos.apps.menu.models import MasterMenuItem
from pos.utils.logger import POSLogger

class MenuItemsArchive(APIView):

    def get(self, request):
        if not getattr(request.user, "is_super_admin", False):
            return Response({'error': 'Only super admin can view archived items'}, status=403)
        
        archived_items = MasterMenuItem.objects.filter(is_active=False)
        data = []

        for item in archived_items:
            # Handle image as base64
            image_base64 = None
            if item.image:
                try:
                    image_base64 = base64.b64encode(bytes(item.image)).decode('utf-8')
                except Exception as e:
                    POSLogger.error(f"Error encoding image for item {item.id}: {e}")

            data.append({
                'id': item.id,
                'name': item.name,
                'price': float(item.price),
                'description': item.description,
                'category_id': item.category.id,
                'category_name': item.category.name,
                'image': image_base64,
                'is_active': item.is_active,
            })

        return Response({
            "status": "success",
            "message": "Archived menu items retrieved successfully",
            "data": data,
            "status_code": 200
        })


class RestoreMenuItem(APIView):

    def post(self, request, item_id):
        if not getattr(request.user, "is_super_admin", False):
            return Response({'error': 'Only super admin can restore items'}, status=403)

        try:
            item = MasterMenuItem.objects.get(id=item_id, is_active=False)
            item.is_active = True
            item.save(update_fields=["is_active"])

            return Response({
                "status": "success",
                "message": f"Menu item '{item.name}' restored successfully",
                "status_code": 200
            }, status=status.HTTP_200_OK)

        except MasterMenuItem.DoesNotExist:
            return Response({
                "status": "error",
                "message": "Archived menu item not found",
                "status_code": 404
            }, status=status.HTTP_404_NOT_FOUND)

        except Exception as e:
            POSLogger.error(f"Error restoring menu item {item_id}: {e}")
            return Response({
                "status": "error",
                "message": "Failed to restore item",
                "status_code": 500
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
