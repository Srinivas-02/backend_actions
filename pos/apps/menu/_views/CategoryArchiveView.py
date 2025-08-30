from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from pos.apps.menu.models import MasterMenuCategory
from pos.utils.logger import POSLogger

class CategoryArchiveView(APIView):

    def get(self,request):
        if not getattr(request.user, "is_super_admin", False):
            return Response({'error': 'Only super admin can view archived items'}, status=403)

        archived_items = MasterMenuCategory.objects.filter(is_active=False)
        data = []
        for item in archived_items:
            data.append({
                'id': item.id,
                'name': item.name,
                'description': item.description,
                'image': item.image.decode('utf-8') if item.image else None,
                'is_active': item.is_active,
            })
        return Response({
            "status": "success",
            "message": "Archived menu categories retrieved successfully",
            "data": data,
            "status_code": 200
        })
