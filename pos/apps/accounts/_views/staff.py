from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from pos.apps.accounts.models import User
from pos.apps.locations.models import LocationModel
from pos.utils.logger import POSLogger

logger = POSLogger(__name__)

class StaffView(APIView):
    """
    Handles staff member operations:
    - POST: Create staff member
    - GET: List all staff members or get specific one
    - PATCH: Update staff member
    - DELETE: Delete staff member
    
    Protected: Only super admins and franchise admins can access this view
    """
    
    def post(self, request):
        """Create new staff member"""
        required_fields = ['email', 'password', 'first_name', 'last_name', 'location_ids']
        if missing := [f for f in required_fields if f not in request.data]:
            logger.warning(f"Attempt to create staff member with missing fields: {missing}")
            return Response(
                {'error': f'Missing fields: {", ".join(missing)}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Validate location IDs
        location_ids = request.data['location_ids']
        if not location_ids:
            logger.warning(f"Attempt to create staff member without assigning locations")
            return Response(
                {'error': 'At least one location must be assigned to a staff member'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Super admin can create staff for any location
        if request.user.is_super_admin:
            try:
                locations = LocationModel.objects.filter(id__in=location_ids)
                if len(locations) != len(location_ids):
                    return Response(
                        {'error': 'One or more location IDs are invalid'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                
                staff_member = User.objects.create_staff_user(
                    email=request.data['email'],
                    password=request.data['password'],
                    first_name=request.data['first_name'],
                    last_name=request.data['last_name'],
                    locations=locations
                )

                logger.info(f"Staff member {staff_member.email} created by super admin {request.user.email}")
                return Response({
                    'id': staff_member.id,
                    'email': staff_member.email,
                    'message': 'Staff member created successfully',
                    'locations': list(locations.values('id', 'name'))
                }, status=status.HTTP_201_CREATED)

            except Exception as e:
                logger.error(f"Error creating staff member: {str(e)}")
                return Response(
                    {'error': str(e)},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        # Franchise admin can create staff only for locations they have access to
        elif request.user.is_franchise_admin:
            admin = get_object_or_404(User, id=request.user.id, is_franchise_admin=True)
            admin_locations = list(admin.locations.values('id'))
            admin_location_ids = [loc['id'] for loc in admin_locations]
            
            # Check if all requested locations are in admin's accessible locations
            if not all(loc_id in admin_location_ids for loc_id in location_ids):
                logger.warning(f"Franchise admin {request.user.email} attempted to create staff with unauthorized locations")
                return Response(
                    {'error': 'You do not have access to all requested locations'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            try:
                locations = LocationModel.objects.filter(id__in=location_ids)
                
                staff_member = User.objects.create_staff_user(
                    email=request.data['email'],
                    password=request.data['password'],
                    first_name=request.data['first_name'],
                    last_name=request.data['last_name'],
                    locations=locations
                )

                logger.info(f"Staff member {staff_member.email} created by franchise admin {request.user.email}")
                return Response({
                    'id': staff_member.id,
                    'email': staff_member.email,
                    'message': 'Staff member created successfully',
                    'locations': list(locations.values('id', 'name'))
                }, status=status.HTTP_201_CREATED)

            except Exception as e:
                logger.error(f"Error creating staff member: {str(e)}")
                return Response(
                    {'error': str(e)},
                    status=status.HTTP_400_BAD_REQUEST
                )
        else:
            logger.warning(f"Unauthorized user {request.user.email} attempted to create staff member")
            return Response(
                {'error': 'Not authorized to create staff members'},
                status=status.HTTP_403_FORBIDDEN
            )

    def get(self, request):
        """Get all staff members or specific one"""
        staff_id = request.query_params.get('id')
        location_id = request.query_params.get('location_id')
        
        # Validate user has access to the location if location filter is applied
        if location_id:
            if not request.user.has_location_access(location_id):
                logger.warning(f"User {request.user.email} attempted to access staff for unauthorized location")
                return Response(
                    {'error': 'You do not have access to this location'},
                    status=status.HTTP_403_FORBIDDEN
                )
        
        # Get specific staff member by ID
        if staff_id:
            try:
                staff = get_object_or_404(User, id=staff_id, is_staff_member=True)
                
                # Check if user has access to view this staff member
                if request.user.is_franchise_admin:
                    admin_locations = request.user.locations.all()
                    staff_locations = staff.locations.all()
                    
                    # Check if there's an overlap in locations
                    if not any(loc in admin_locations for loc in staff_locations):
                        logger.warning(f"Franchise admin {request.user.email} attempted to access unauthorized staff {staff.email}")
                        return Response(
                            {'error': 'You do not have access to this staff member'},
                            status=status.HTTP_403_FORBIDDEN
                        )
                
                locations = list(staff.locations.values('id', 'name'))
                
                logger.info(f"Staff member {staff.email} details accessed by {request.user.email}")
                return Response({
                    'id': staff.id,
                    'email': staff.email,
                    'first_name': staff.first_name,
                    'last_name': staff.last_name,
                    'locations': locations
                })
            except Exception as e:
                logger.warning(f"Error retrieving staff member {staff_id}: {str(e)}")
                return Response({'error': str(e)}, status=status.HTTP_404_NOT_FOUND)
        
        # List all accessible staff members
        else:
            if request.user.is_super_admin:
                # Super admin can see all staff members, filter by location if provided
                staff_query = User.objects.filter(is_staff_member=True)
                
                if location_id:
                    staff_query = staff_query.filter(locations__id=location_id).distinct()
                
                staff_members = []
                for staff in staff_query:
                    locations = list(staff.locations.values('id', 'name'))
                    staff_data = {
                        'id': staff.id,
                        'email': staff.email,
                        'first_name': staff.first_name,
                        'last_name': staff.last_name,
                        'locations': locations
                    }
                    staff_members.append(staff_data)
                
                logger.info(f"All staff members list accessed by super admin {request.user.email}")
                return Response(staff_members)
            
            elif request.user.is_franchise_admin:
                # Franchise admin can only see staff members in their locations
                admin = get_object_or_404(User, id=request.user.id, is_franchise_admin=True)
                
                # Get all staff members that have access to any of the admin's locations
                staff_query = User.objects.filter(
                    is_staff_member=True,
                    locations__in=admin.locations.all()
                ).distinct()
                
                # Further filter by location_id if provided
                if location_id:
                    staff_query = staff_query.filter(locations__id=location_id).distinct()
                
                staff_members = []
                for staff in staff_query:
                    locations = list(staff.locations.values('id', 'name'))
                    staff_data = {
                        'id': staff.id,
                        'email': staff.email,
                        'first_name': staff.first_name,
                        'last_name': staff.last_name,
                        'locations': locations
                    }
                    staff_members.append(staff_data)
                
                logger.info(f"Staff members list accessed by franchise admin {request.user.email}")
                return Response(staff_members)
            
            else:
                logger.warning(f"Unauthorized user {request.user.email} attempted to list staff members")
                return Response(
                    {'error': 'Not authorized to view staff members'},
                    status=status.HTTP_403_FORBIDDEN
                )

    def patch(self, request):
        """Update staff member details"""
        if 'id' not in request.data:
            logger.warning("Attempt to update staff member without providing ID")
            return Response(
                {'error': 'Staff member ID required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            staff = get_object_or_404(User, id=request.data['id'], is_staff_member=True)
            
            # Check if franchise admin has access to this staff member
            if request.user.is_franchise_admin:
                admin_locations = request.user.locations.all()
                staff_locations = staff.locations.all()
                
                # Check if there's an overlap in locations
                if not any(loc in admin_locations for loc in staff_locations):
                    logger.warning(f"Franchise admin {request.user.email} attempted to update unauthorized staff {staff.email}")
                    return Response(
                        {'error': 'You do not have access to this staff member'},
                        status=status.HTTP_403_FORBIDDEN
                    )
                
                # If updating locations, ensure franchise admin has access to all new locations
                if 'location_ids' in request.data:
                    admin_location_ids = [loc.id for loc in admin_locations]
                    if not all(loc_id in admin_location_ids for loc_id in request.data['location_ids']):
                        logger.warning(f"Franchise admin {request.user.email} attempted to assign staff to unauthorized locations")
                        return Response(
                            {'error': 'You do not have access to all requested locations'},
                            status=status.HTTP_403_FORBIDDEN
                        )
                    
                    # Ensure at least one location is assigned
                    if not request.data['location_ids']:
                        logger.warning(f"Attempt to update staff member without assigning locations")
                        return Response(
                            {'error': 'At least one location must be assigned to a staff member'},
                            status=status.HTTP_400_BAD_REQUEST
                        )
            
            # Update fields
            for field in ['first_name', 'last_name', 'email']:
                if field in request.data:
                    setattr(staff, field, request.data[field])
            
            # Update locations if provided
            if 'location_ids' in request.data:
                # Ensure at least one location is assigned
                if not request.data['location_ids']:
                    logger.warning(f"Attempt to update staff member without assigning locations")
                    return Response(
                        {'error': 'At least one location must be assigned to a staff member'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                    
                locations = LocationModel.objects.filter(id__in=request.data['location_ids'])
                staff.locations.set(locations)
            
            # Update password if provided
            if 'password' in request.data:
                staff.set_password(request.data['password'])
            
            staff.save()
            
            # Return updated staff data with locations
            locations = list(staff.locations.values('id', 'name'))
            
            logger.info(f"Staff member {staff.email} updated by {request.user.email}")
            return Response({
                'message': 'Staff member updated successfully',
                'id': staff.id,
                'email': staff.email,
                'first_name': staff.first_name,
                'last_name': staff.last_name,
                'locations': locations
            })
            
        except Exception as e:
            logger.error(f"Error updating staff member: {str(e)}")
            return Response({'error': str(e)}, status=status.HTTP_404_NOT_FOUND)

    def delete(self, request):
        """Delete staff member"""
        if 'id' not in request.query_params:
            logger.warning("Attempt to delete staff member without providing ID")
            return Response(
                {'error': 'Specify ?id=<staff_id>'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            staff = get_object_or_404(User, id=request.query_params['id'], is_staff_member=True)
            
            # Check if franchise admin has access to this staff member
            if request.user.is_franchise_admin:
                admin_locations = request.user.locations.all()
                staff_locations = staff.locations.all()
                
                # Check if there's an overlap in locations
                if not any(loc in admin_locations for loc in staff_locations):
                    logger.warning(f"Franchise admin {request.user.email} attempted to delete unauthorized staff {staff.email}")
                    return Response(
                        {'error': 'You do not have access to this staff member'},
                        status=status.HTTP_403_FORBIDDEN
                    )
            
            staff_email = staff.email
            staff.delete()
            logger.warning(f"Staff member {staff_email} deleted by {request.user.email}")
            return Response(
                {'message': 'Staff member deleted successfully'},
                status=status.HTTP_204_NO_CONTENT
            )
            
        except Exception as e:
            logger.error(f"Error deleting staff member: {str(e)}")
            return Response({'error': str(e)}, status=status.HTTP_404_NOT_FOUND) 