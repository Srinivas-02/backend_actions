from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from pos.apps.menu.models import MasterMenuCategory
from pos.utils.logger import POSLogger

logger = POSLogger(__name__)

class MasterMenuCategoryView(APIView):
    def get(self, request, pk=None):
        """List all or retrieve a specific master category"""

        if not (getattr(request.user, "is_super_admin", False) or getattr(request.user, "is_franchise_admin", False)):
            return Response({'error': 'Not allowed'}, status=status.HTTP_403_FORBIDDEN)
        try:
            if pk:
                category = MasterMenuCategory.objects.get(pk=pk)
                data = {
                    "id": category.id,
                    "name": category.name,
                    "description": category.description,
                }
                return Response(data)
            else:
                categories = MasterMenuCategory.objects.filter(is_active=True)
                data = [{
                    "id": cat.id,
                    "name": cat.name,
                    "description": cat.description,
                } for cat in categories]
                return Response({"categories": data})
        except MasterMenuCategory.DoesNotExist:
            return Response({'error': 'Category not found'}, status=status.HTTP_404_NOT_FOUND)

    def post(self, request):
        """Create a master category (super admin only)"""

        if not getattr(request.user, "is_super_admin", False):
            return Response({'error': 'Not allowed'}, status=status.HTTP_403_FORBIDDEN)
        try:
            category = MasterMenuCategory.objects.create(
                name=request.data.get('name'),
                description=request.data.get('description', ''),
                image=request.FILES.get('image').read() if request.FILES.get('image') else None
            )
            return Response({
                'id': category.id,
                'name': category.name,
                'description': category.description
            }, status=status.HTTP_201_CREATED)
        except Exception as e:
            logger.error(f"Error creating master category: {str(e)}")
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    def put(self, request, pk=None):
        """Update a master category (super admin only)"""
        if not getattr(request.user, "is_super_admin", False):
            return Response({'error': 'Not allowed'}, status=status.HTTP_403_FORBIDDEN)
        if not pk:
            return Response({'error': 'ID required for update'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            category = MasterMenuCategory.objects.get(pk=pk)
            if 'name' in request.data:
                category.name = request.data['name']
            if 'description' in request.data:
                category.description = request.data['description']
            if request.FILES.get('image'):
                category.image = request.FILES['image'].read()
            category.save()
            return Response({
                'id': category.id,
                'name': category.name,
                'description': category.description
            }, status=status.HTTP_200_OK)
        except MasterMenuCategory.DoesNotExist:
            return Response({'error': 'Category not found'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Error updating master category: {str(e)}")
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk=None):
        """Delete a master category (super admin only)"""
        if not getattr(request.user, "is_super_admin", False):
            return Response({'error': 'Not allowed'}, status=status.HTTP_403_FORBIDDEN)
        if not pk:
            return Response({'error': 'ID required for delete'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            category = MasterMenuCategory.objects.get(pk=pk)
            category.is_active = False  # Soft delete
            category.save()
            return Response({'message': f'Category {category.name} is soft deleted'}, status=status.HTTP_200_OK)
        except MasterMenuCategory.DoesNotExist:
            return Response({'error': 'Category not found'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Error deleting master category: {str(e)}")
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
