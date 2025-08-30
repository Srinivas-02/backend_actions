from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from pos.apps.menu.models import CategoryModel
from pos.apps.accounts.models import User
from pos.apps.locations.models import LocationModel
from django.shortcuts import get_object_or_404
from pos.utils.logger import POSLogger

logger = POSLogger(__name__)

class CategoryView(APIView):
    def get(self, request):
        """Get all categories"""
        logger.info(f"hi this is the test code \n\n\n")
        if not request.user.is_super_admin and not request.user.is_franchise_admin :
            return Response({'error': 'not allowed'})

        location_id = request.query_params.get('location_id')
        if location_id:
            categories = CategoryModel.objects.filter(location__id = location_id)
            if not categories:
                return Response({'error': 'no categories for the given location'})

            data = [ {
                "id": category.id,
                "name": category.name,
                "location_id" : category.location.id,
                "display_order": category.display_order,
            } for category in categories]
            return Response({ "categories": data})
        if request.user.is_super_admin:
            categories = CategoryModel.objects.all().order_by('display_order')
            data = [{
                'id': category.id,
                'name': category.name,
                'location_id': category.location.id,
                'display_order': category.display_order
            } for category in categories]
            
            logger.info(f"Returning categories: {data}")  # ✅ Log added here
            return Response({'categories': data})
        
        elif request.user.is_franchise_admin or request.user.is_staff_member:
            requester = get_object_or_404(User, id=request.user.id)
            categories = CategoryModel.objects.filter(location__in=requester.locations.all()).order_by('display_order')
            data = [{
                'id': category.id,
                'name': category.name,
                'location_id': category.location.id,
                'display_order': category.display_order
            } for category in categories]

            logger.info(f"Returning categories: {data}")  # ✅ Log added here
            return Response({'categories': data})
        
        else:
            logger.warning(f"Unauthorized user {request.user.email} tried to access categories")  # Optional
            return Response({'error': 'not allowed'})

        


    def post(self, request):
        """Create a new category"""
        try:
            requested_location = LocationModel.objects.get(id=request.data.get('location_id'))
            if request.user.is_super_admin:
                category = CategoryModel.objects.create(
                    name=request.data.get('name'),
                    display_order=request.data.get('display_order', 0),
                    location=requested_location
                )
                return Response({
                    'status': 'success',
                    'id': category.id,
                    'name': category.name
                }, status=status.HTTP_201_CREATED)
            elif request.user.is_franchise_admin:
                admin = get_object_or_404(User, id = request.user.id, is_franchise_admin = True)
                locations = list(admin.locations.values('id','name'))
                logger.info(f"\n\n the requested id is {requested_location} \n\n and the access to admin are {locations} \n\n")
                if requested_location.id not in [loc['id'] for loc in locations]:
                    return Response({'error': 'Did not have access for that location'})

                category = CategoryModel.objects.create(
                    name=request.data.get('name'),
                    display_order = request.data.get('display_order', 0),
                    location= requested_location
                )
                return Response({
                    'status': 'success',
                    'id': category.id,
                    'name': category.name
                }, status=status.HTTP_201_CREATED)
            else:
                return Response({'error': 'not allowed '})
        except Exception as e:
            return Response(
                {'status': 'error', 'message': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    def patch(self, request):
        """Update an existing category"""
        logger.info("Category update request received")
        
        if 'id' not in request.data:
            logger.warning("Attempt to update category without providing ID")
            return Response({'error': 'Category ID required'}, status=status.HTTP_400_BAD_REQUEST)
            
        try:
            category = get_object_or_404(CategoryModel, id=request.data['id'])
            
            if request.user.is_super_admin:
                # Super admin can update freely
                pass
            elif request.user.is_franchise_admin:
                # Franchise admin can only update categories in their locations
                admin = get_object_or_404(User, id=request.user.id, is_franchise_admin=True)
                admin_locations = set(admin.locations.values_list('id', flat=True))
                if category.location.id not in admin_locations:
                    logger.warning(f"{request.user.email} unauthorized to update this category")
                    return Response({'error': 'Unauthorized to update this category'}, 
                                   status=status.HTTP_403_FORBIDDEN)
            else:
                return Response({'error': 'Not allowed'}, status=status.HTTP_403_FORBIDDEN)
            
            # Update fields
            if 'name' in request.data:
                category.name = request.data['name']
            if 'display_order' in request.data:
                category.display_order = request.data['display_order']
            if 'location_id' in request.data:
                new_location = get_object_or_404(LocationModel, id=request.data['location_id'])
                
                if request.user.is_franchise_admin:
                    admin_locations = set(request.user.locations.values_list('id', flat=True))
                    if new_location.id not in admin_locations:
                        return Response({'error': 'Cannot assign unauthorized location'}, 
                                       status=status.HTTP_403_FORBIDDEN)
                
                category.location = new_location
            
            category.save()
            logger.info(f"Category {category.name} updated by {request.user.email}")
            
            return Response({
                'status': 'success',
                'message': 'Category updated',
                'category': {
                    'id': category.id,
                    'name': category.name,
                    'location_id': category.location.id,
                    'display_order': category.display_order
                }
            })
            
        except Exception as e:
            logger.error(f"Error updating category: {str(e)}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_404_NOT_FOUND
            )
    
    def delete(self, request):
        """Permanently delete category from database"""
        logger.info("Category delete request received")
        logger.info(f"Request query params: {request.query_params}")
        logger.info(f"User: {request.user.email}, Method: {request.method}")
        
        if 'id' not in request.query_params:
            logger.warning("Attempt to delete category without providing ID")
            return Response({'error': 'Specify ?id=<category_id>'}, status=status.HTTP_400_BAD_REQUEST)
            
        try:
            category = get_object_or_404(CategoryModel, id=request.query_params['id'])
            
            if request.user.is_super_admin:
                pass  # Full access
            elif request.user.is_franchise_admin:
                admin = get_object_or_404(User, id=request.user.id, is_franchise_admin=True)
                admin_locations = set(admin.locations.values_list('id', flat=True))
                if category.location.id not in admin_locations:
                    logger.warning(f"{request.user.email} unauthorized to delete this category")
                    return Response({'error': 'Unauthorized to delete this category'}, 
                                  status=status.HTTP_403_FORBIDDEN)
            else:
                return Response({'error': 'Not allowed'}, status=status.HTTP_403_FORBIDDEN)
            
            category_name = category.name
            category.delete()
            logger.warning(f"Category {category_name} deleted by {request.user.email}")
            
            return Response({'message': 'Category permanently deleted'}, status=status.HTTP_204_NO_CONTENT)
            
        except Exception as e:
            logger.error(f"Error deleting category: {str(e)}")
            return Response({'error': str(e)}, status=status.HTTP_404_NOT_FOUND)