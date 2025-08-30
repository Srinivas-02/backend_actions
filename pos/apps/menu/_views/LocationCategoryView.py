from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from pos.apps.menu.models import LocationMenuCategory, MasterMenuCategory
from pos.apps.locations.models import LocationModel
from django.shortcuts import get_object_or_404

class LocationCategoryView(APIView):
    """
    Super admin: CRUD location category assignments (assign/unassign).
    Franchise admin: Read-only view for their own locations.
    """

    def get(self, request, pk=None):
        if pk:
            try:
                location_category = LocationMenuCategory.objects.select_related('category', 'location').get(pk=pk)
                if getattr(request.user, 'is_super_admin', False) or (
                    getattr(request.user, 'is_franchise_admin', False) and
                    location_category.location in request.user.locations.all()
                ):
                    data = {
                        'id': location_category.id,
                        'category_id': location_category.category.id,
                        'category_name': location_category.category.name,
                        'location_id': location_category.location.id,
                        'location_name': location_category.location.name,
                        'is_available': location_category.is_available
                    }
                    return Response(data)
                else:
                    return Response({'error': 'Not allowed'}, status=status.HTTP_403_FORBIDDEN)
            except LocationMenuCategory.DoesNotExist:
                return Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)
        else:
            if getattr(request.user, 'is_super_admin', False):
                items = LocationMenuCategory.objects.select_related('category', 'location').filter(
                    category__is_active=True
                )
            elif getattr(request.user, 'is_franchise_admin', False):
                items = LocationMenuCategory.objects.select_related('category', 'location').filter(
                    location__in=request.user.locations.all(),
                    category__is_active=True
                )
            else:
                return Response({'error': 'Not allowed'}, status=status.HTTP_403_FORBIDDEN)

            data = []
            for item in items:
                data.append({
                    'id': item.id,
                    'category_id': item.category.id,
                    'category_name': item.category.name,
                    'location_id': item.location.id,
                    'location_name': item.location.name,
                    'is_available': item.is_available
                })
            return Response({'location_categories': data})

    def post(self, request):
        if not (getattr(request.user, 'is_super_admin', False) or getattr(request.user, 'is_franchise_admin', False)):
            return Response({'error': 'Not allowed'}, status=status.HTTP_403_FORBIDDEN)
        try:
            category_id = request.data.get('category_id')
            location_id = request.data.get('location_id')
            is_available = request.data.get('is_available', True)

            if not category_id or not location_id:
                return Response({'error': 'category_id and location_id are required'}, status=400)

            category = get_object_or_404(MasterMenuCategory, pk=category_id)
            location = get_object_or_404(LocationModel, pk=location_id)

            location_category, created = LocationMenuCategory.objects.get_or_create(
                category=category,
                location=location,
                defaults={'is_available': is_available}
            )
            if not created:
                location_category.is_available = is_available
                location_category.save()

            data = {
                'id': location_category.id,
                'category_id': location_category.category.id,
                'category_name': location_category.category.name,
                'location_id': location_category.location.id,
                'location_name': location_category.location.name,
                'is_available': location_category.is_available
            }
            return Response(data, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    def patch(self, request, pk=None):
        if not (getattr(request.user, 'is_super_admin', False) or getattr(request.user, 'is_franchise_admin', False)):
            return Response({'error': 'Not allowed'}, status=status.HTTP_403_FORBIDDEN)
        try:
            location_category_id = pk or request.data.get("id")
            if not location_category_id:
                return Response({'error': 'Assignment ID required'}, status=status.HTTP_400_BAD_REQUEST)
            location_category = get_object_or_404(LocationMenuCategory, id=location_category_id)
            if 'is_available' in request.data:
                location_category.is_available = request.data['is_available']
            location_category.save()
            data = {
                'id': location_category.id,
                'category_id': location_category.category.id,
                'category_name': location_category.category.name,
                'location_id': location_category.location.id,
                'location_name': location_category.location.name,
                'is_available': location_category.is_available
            }
            return Response(data, status=status.HTTP_200_OK)
        except LocationMenuCategory.DoesNotExist:
            return Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk=None):
        if not getattr(request.user, 'is_super_admin', False):
            return Response({'error': 'Not allowed'}, status=status.HTTP_403_FORBIDDEN)
        
        location_category_id = pk or request.data.get("id")
        if not location_category_id:
            return Response({'error': 'Assignment ID required'}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            location_category = LocationMenuCategory.objects.get(id=location_category_id,is_assigned=True)
        except LocationMenuCategory.DoesNotExist:
            return Response({'error': 'Category not found or already unassigned'}, status=status.HTTP_404_NOT_FOUND)
        
        location_category.is_assigned = False
        location_category.is_available = False
        location_category.save(update_fields=['is_assigned', 'is_available'])

        return Response({'status': 'success', 'message': f'Location category {location_category.category.name} unassigned successfully.'},status=status.HTTP_200_OK)

