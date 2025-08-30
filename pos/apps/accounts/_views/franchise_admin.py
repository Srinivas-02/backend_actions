import os
from django.shortcuts import get_object_or_404
from django.db import models
from django.db.models import Q
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from pos.apps.accounts.models import User
from pos.apps.locations.models import LocationModel
from pos.utils.logger import POSLogger
from django.core.mail import send_mail
from django.conf import settings
from django.template.loader import render_to_string

logger = POSLogger(__name__)

def send_welcome_mail(user):
    subject = "Welcome to Sip n Snack"
    from_email = settings.EMAIL_HOST_USER
    to_list = [user.email]
    text_body = (
        f"Dear {user.first_name},\n\n"
        "Welcome to Sip n Snack! Your franchise admin account has been created.\n"
        "You can log in to your account at: http://localhost:5173/\n\n"
        "Warm regards,\n"
        "The Sip n Snack Team\n"
    )
    html_body = render_to_string(
        'welcome_message.html',
        {
            'first_name': user.first_name,
            'login_url': "http://localhost:5173/"
        }
    )

    logger.info(f"Welcome mail being sent to {user.email}")

    send_mail(
        subject=subject,
        message=text_body,
        from_email=from_email,
        recipient_list=to_list,
        fail_silently=False,
        html_message=html_body
    )

class FranchiseAdminView(APIView):

    def post(self, request):
        if not (request.user.is_super_admin or request.user.is_franchise_admin):
            return Response({'error': 'Not allowed'}, status=status.HTTP_403_FORBIDDEN)

        required_fields = ['email', 'first_name', 'last_name', 'location_ids']
        if missing := [f for f in required_fields if f not in request.data]:
            logger.warning(f"Missing fields: {missing} by {request.user.email}")
            return Response({'error': f'Missing fields: {", ".join(missing)}'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            franchise_admin = User.objects.create_user(
                email=request.data['email'],
                first_name=request.data['first_name'],
                last_name=request.data['last_name'],
                is_franchise_admin=True,
                created_by=request.user
            )

            location_ids = request.data.get('location_ids', [])
            if not isinstance(location_ids, list):
                franchise_admin.delete()
                return Response({'error': 'location_ids must be a list'}, status=status.HTTP_400_BAD_REQUEST)

            if request.user.is_franchise_admin:
                user_locations = set(request.user.locations.values_list('id', flat=True))
                if not all(loc_id in user_locations for loc_id in location_ids):
                    franchise_admin.delete()
                    return Response({'error': 'Invalid location access'}, status=status.HTTP_403_FORBIDDEN)

            locations = LocationModel.objects.filter(id__in=location_ids)
            if len(locations) != len(location_ids):
                franchise_admin.delete()
                return Response({'error': 'Invalid location IDs'}, status=status.HTTP_400_BAD_REQUEST)

            franchise_admin.locations.set(locations)
            send_welcome_mail(franchise_admin)

            return Response({
                'id': franchise_admin.id,
                'email': franchise_admin.email,
                'message': 'Franchise admin created successfully'
            }, status=status.HTTP_201_CREATED)

        except Exception as e:
            logger.error(f"Error creating franchise admin: {str(e)}")
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    def get(self, request):
        if not request.user.is_authenticated:
            return Response({'error': 'Authentication required'}, status=status.HTTP_401_UNAUTHORIZED)

        if request.user.is_staff_member:
            return Response({'error': 'Not authorized'}, status=status.HTTP_403_FORBIDDEN)

        admin_id = request.query_params.get('id')
        if admin_id:
            try:
                admin = get_object_or_404(User, id=admin_id, is_franchise_admin=True)
                if request.user.is_franchise_admin:
                    user_locations = set(request.user.locations.values_list('id', flat=True))
                    admin_locations = set(admin.locations.values_list('id', flat=True))
                    if not (admin == request.user or user_locations & admin_locations or admin.created_by == request.user):
                        return Response({'error': 'No access'}, status=status.HTTP_403_FORBIDDEN)

                return Response({
                    'id': admin.id,
                    'email': admin.email,
                    'first_name': admin.first_name,
                    'last_name': admin.last_name,
                    'locations': list(admin.locations.values('id', 'name'))
                })
            except Exception as e:
                return Response({'error': str(e)}, status=status.HTTP_404_NOT_FOUND)
        else:
            try:
                if request.user.is_super_admin:
                    franchise_admins = User.objects.filter(is_franchise_admin=True)
                elif request.user.is_franchise_admin:
                    user_locations = set(request.user.locations.values_list('id', flat=True))
                    franchise_admins = User.objects.filter(
                        Q(is_franchise_admin=True) &
                        (Q(locations__id__in=user_locations) | Q(created_by=request.user))
                    ).distinct()
                else:
                    return Response({'error': 'Not authorized'}, status=status.HTTP_403_FORBIDDEN)

                admins_data = [{
                    'id': admin.id,
                    'email': admin.email,
                    'first_name': admin.first_name,
                    'last_name': admin.last_name,
                    'locations': list(admin.locations.values('id', 'name'))
                } for admin in franchise_admins]
                return Response(admins_data)
            except Exception as e:
                return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    def patch(self, request):
        logger.info(f"PATCH request by user {request.user.id} (is_franchise_admin={request.user.is_franchise_admin}, is_super_admin={request.user.is_super_admin})")

        # 1. Same permission check as POST
        if not (request.user.is_super_admin or request.user.is_franchise_admin):
            logger.warning(f"User {request.user.id} lacks admin privileges")
            return Response({'error': 'Admin privileges required'}, 
                        status=status.HTTP_403_FORBIDDEN)

        if 'id' not in request.data:
            return Response({'error': 'Franchise admin ID required'}, 
                        status=status.HTTP_400_BAD_REQUEST)

        try:
            admin = get_object_or_404(User, id=request.data['id'], is_franchise_admin=True)
            logger.info(f"Target admin {admin.id} locations: {list(admin.locations.values_list('id', flat=True))}")

            # 2. Location access check - same as POST
            if request.user.is_franchise_admin:
                # Can only modify admins that share at least one location
                if not admin.locations.filter(id__in=request.user.locations.all()).exists():
                    logger.warning(f"Location mismatch between user {request.user.id} and admin {admin.id}")
                    return Response({'error': 'No shared locations'}, 
                                status=status.HTTP_403_FORBIDDEN)

            # 3. Location assignment validation - same as POST
            if 'location_ids' in request.data:
                location_ids = request.data['location_ids']
                
                if not isinstance(location_ids, list):
                    return Response({'error': 'location_ids must be a list'}, 
                                status=status.HTTP_400_BAD_REQUEST)
                
                if request.user.is_franchise_admin:
                    user_locations = set(request.user.locations.values_list('id', flat=True))
                    if not set(location_ids).issubset(user_locations):
                        logger.warning(f"User {request.user.id} tried assigning invalid locations")
                        return Response({'error': 'Invalid location access'}, 
                                    status=status.HTTP_403_FORBIDDEN)

                locations = LocationModel.objects.filter(id__in=location_ids)
                if len(locations) != len(location_ids):
                    return Response({'error': 'Invalid location IDs'}, 
                                status=status.HTTP_400_BAD_REQUEST)
                
                admin.locations.set(locations)
                logger.info(f"Updated admin {admin.id} locations to {location_ids}")

            # Update basic fields
            for field in ['first_name', 'last_name', 'email', 'is_active']:
                if field in request.data:
                    setattr(admin, field, request.data[field])
                    logger.info(f"Updated {field} for admin {admin.id}")

            admin.save()
            return Response({'message': 'Franchise admin updated'})

        except Exception as e:
            logger.error(f"Error updating admin: {str(e)}", exc_info=True)
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request):
        admin_id = request.query_params.get('id')
        if not admin_id:
            return Response({'error': 'Specify ?id=<franchise_admin_id>'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            admin = get_object_or_404(User, id=admin_id, is_franchise_admin=True)

            if request.user.is_franchise_admin and admin.created_by != request.user:
                return Response({'error': 'No access'}, status=status.HTTP_403_FORBIDDEN)

            admin_email = admin.email
            admin.delete()
            logger.warning(f"Franchise admin {admin_email} deleted by {request.user.email}")
            return Response({'message': 'Franchise admin permanently deleted'}, status=status.HTTP_204_NO_CONTENT)

        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_404_NOT_FOUND)
