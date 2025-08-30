from django.http import JsonResponse
from django.contrib.auth import authenticate
from django.contrib.auth import get_user_model
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.response import Response
from rest_framework import status
from pos.apps.locations.models import LocationModel as Location

User = get_user_model()

class LocationLoginView(APIView):
    """First step for staff - verify location credentials"""
    permission_classes = [AllowAny]
    authentication_classes = []  # Disable authentication for this view
    def post(self, request):
        location_name = request.data.get('location_name')
        location_password = request.data.get('location_password')
        
        if not location_name or not location_password:
            return Response(
                {'error': 'Location name and password are required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            location = Location.objects.get(name=location_name, is_active=True)
            if location.password != location_password: 
                raise Location.DoesNotExist
                
            return Response({
                'success': True,
                'location_id': location.id,
                'location_name': location.name
            })
        except Location.DoesNotExist:
            return Response(
                {'error': 'Invalid location credentials'},
                status=status.HTTP_401_UNAUTHORIZED
            )

class UserLoginView(APIView):
    """Handles both staff and admin logins"""
    permission_classes = [AllowAny]
    authentication_classes = []  # Disable authentication for this view
    def get_tokens_for_user(self, user):
        refresh = RefreshToken.for_user(user)
        return {
            'refresh': str(refresh),
            'access': str(refresh.access_token),
        }
    
    def post(self, request):
        email = request.data.get('email')
        password = request.data.get('password')

        
        if not email or not password:
            return Response(
                {'error': 'Email and password are required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # just for testing in development

        test_email = "franchiseadmin@gmail.com"
        test_password = "admin"

        if email == test_email and password == test_password:
            # Only in development! Add check if needed
            user, created = User.objects.get_or_create(
                email=test_email,
                defaults={
                    'first_name': 'franchise',
                    'last_name': 'admin',
                    'is_super_admin': False,
                    'is_franchise_admin': True,
                    'is_staff_member': False,
                }
            )
            # You can set a password if you want, but it's not necessary for dev
            tokens = self.get_tokens_for_user(user)
            user_locations = user.locations.filter(is_active=True)
            response_data = {
                **tokens,
                'user': {
                    'id': user.id,
                    'email': user.email,
                    'first_name': user.first_name,
                    'last_name': user.last_name,
                    'is_super_admin': user.is_super_admin,
                    'is_franchise_admin': user.is_franchise_admin,
                    'is_staff_member': user.is_staff_member,
                },
                'locations' : [
                    {
                        'id': location.id,
                        'name': location.name
                    } for location in user_locations
                ]
            }
            return Response(response_data)

        # 2. Normal login 
        user = authenticate(username=email, password=password)
        if not user or not user.is_active:
            return Response(
                {'error': 'Invalid credentials'},
                status=status.HTTP_401_UNAUTHORIZED
            )

        tokens = self.get_tokens_for_user(user)

        if user.is_super_admin:
            user_locations = Location.objects.all()
        else:
            user_locations = user.locations.filter(is_active=True)

        response_data = {
            **tokens,
            'user': {
                'id': user.id,
                'email': user.email,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'is_super_admin': user.is_super_admin,
                'is_franchise_admin': user.is_franchise_admin,
                'is_staff_member': user.is_staff_member,
            },
            'locations' : [
                {
                    'id': location.id,
                    'name': location.name
                } for location in user_locations
            ]
        }
        return Response(response_data)
