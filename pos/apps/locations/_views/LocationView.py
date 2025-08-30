from django.http import JsonResponse
from rest_framework.views import APIView
import json
from django.core.exceptions import ObjectDoesNotExist
from pos.utils.permissions import IsSuperAdmin
from pos.utils.logger import POSLogger
from rest_framework.response import Response
from rest_framework import status
from django.views.decorators.http import require_GET
from pos.apps.accounts.models import User


from pos.apps.locations.models import LocationModel

logger = POSLogger(__name__)

@require_GET
def get_location_names(request):
    try:
        locations = LocationModel.objects.values('name','id')
        logger.info("All location names accessed")
        return JsonResponse(list(locations), safe=False)
    except Exception as e:
        logger.error(f"Error retrieving location names: {str(e)}")
        return JsonResponse({'error': 'Error retrieving locations'}, status=500)




class LocationView(APIView):
    """
    Single endpoint for all operations:
    - GET: All locations (default) or specific location (?id=)
    - POST: Create location
    - PATCH: Update location
    - DELETE: Delete location
    
    Protected: Only super admins can access this view
    """
    
    def get(self, request):
        """Get all locations or specific one if ID provided"""
        location_id = request.GET.get('id')

        user = request.user
        if not (request.user.is_super_admin or request.user.is_franchise_admin):
            return Response({'error': 'not authorized'})
        if location_id:
                if request.user.is_franchise_admin:
                    if not request.user.has_location_access(location_id):
                        logger.warning(f"Franchise admin {request.user.email} attempted to access unauthorized location {location_id}")
                        return JsonResponse({'error': 'You do not have access to this location'}, status=403)
                try:
                    location = LocationModel.objects.get(id=location_id)
                    logger.info(f"Location {location.id} details accessed by {user.email}")
                    return JsonResponse({
                        'id': location.id,
                        'name': location.name,
                        'address': location.address,
                        'city': location.city,
                        'state': location.state,
                        'phone': location.phone,
                    })
                except ObjectDoesNotExist:
                    logger.warning(f"Attempt to access non-existent location {location_id}")
                    return JsonResponse({'error': 'Location not found'}, status=404)
        # Super Admin: all locations
        if user.is_super_admin:
            
                locations = list(LocationModel.objects.values(
                    'id', 'name', 'city', 'state', 'address', 'phone',
                ))
                return JsonResponse(locations, safe=False)
        # Franchise Admin: only their locations
        elif user.is_franchise_admin:
                locations = list(user.locations.values(
                    'id', 'name', 'city', 'state', 'address', 'phone',
                ))
                return JsonResponse(locations, safe=False)
        # Staff: deny access
        elif user.is_staff_member:
            return JsonResponse({'error': 'fuck off'}, status=403)
        # Default: deny access
        else:
            return JsonResponse({'error': 'Not authorized'}, status=403)

    def post(self, request):
        """Create new location with optional fields"""
        if not request.user.is_super_admin:
            return Response({"error":"not allowed"})
        try:
            data = json.loads(request.body)
            
            # Create with any provided fields
            location = LocationModel.objects.create(
                name=data.get('name', ''),
                address=data.get('address', ''),
                city=data.get('city', ''),
                state=data.get('state', ''),
                password=data.get('password', ''),
                phone = data.get('phone', None)
            )
            logger.info(f"New location '{location.name}' created by {request.user.email}")
            return JsonResponse({'id': location.id, 'status': 'created'}, status=201)
        except json.JSONDecodeError:
            logger.error(f"Invalid JSON in location creation request")
            return JsonResponse({'error': 'Invalid JSON'}, status=400)
        except Exception as e:
            logger.error(f"Error creating location: {str(e)}")
            return JsonResponse({'error': str(e)}, status=400)

    def patch(self, request):
        """Update location with only provided fields"""

        if not request.user.is_super_admin :
            return Response({"error":"not allowed"})
        
        try:
            data = json.loads(request.body)
            
            if 'id' not in data:
                logger.warning("Attempt to update location without providing ID")
                return JsonResponse({'error': 'Location ID required'}, status=400)

            try:
                location = LocationModel.objects.get(id=data['id'])
                
                # Update only provided fields
                if 'name' in data:
                    location.name = data['name']
                if 'address' in data:
                    location.address = data['address']
                if 'city' in data:
                    location.city = data['city']
                if 'state' in data:
                    location.state = data['state']
                if 'phone' in data:
                    location.phone = data['phone']
                
                location.save()
                logger.info(f"Location '{location.name}' updated by {request.user.email}")
                return JsonResponse({'status': 'updated'})
            except ObjectDoesNotExist:
                logger.warning(f"Attempt to update non-existent location {data['id']}")
                return JsonResponse({'error': 'Location not found'}, status=404)
                
        except json.JSONDecodeError:
            logger.error("Invalid JSON in location update request")
            return JsonResponse({'error': 'Invalid JSON'}, status=400)

    def delete(self, request):
        """
        Delete locations:
        - If ID is provided: delete specific location
        - If no ID: delete all locations
        """
        if not request.user.is_super_admin:
            return Response({"error":"not allowed"})
        
        location_id = request.GET.get('id')
        
        if location_id:
            # Delete specific location
            try:
                location = LocationModel.objects.get(id=location_id)
                location_name = location.name
                location.delete()
                logger.info(f"Location '{location_name}' deleted by {request.user.email}")
                return JsonResponse({'status': f'Location {location_id} deleted'})
            except ObjectDoesNotExist:
                logger.warning(f"Attempt to delete non-existent location {location_id}")
                return JsonResponse({'error': 'Location not found'}, status=404)
        else:
            # Delete all locations
            count, _ = LocationModel.objects.all().delete()
            logger.warning(f"All locations ({count}) deleted by {request.user.email}")
            return JsonResponse({'status': f'All locations deleted', 'count': count})