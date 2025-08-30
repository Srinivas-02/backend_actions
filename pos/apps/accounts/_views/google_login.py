from django.conf import settings
from django.contrib.auth import get_user_model
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status
from pos.utils.logger import POSLogger
from pos.apps.locations.models import LocationModel as Location


User = get_user_model()

class GoogleLoginView(APIView):
    """
    POST endpoint to handle Google Sign-In.
    Expects a JSON body with a 'token' field containing the Google ID token.
    """
    permission_classes = [AllowAny]
    authentication_classes = []  # Disable authentication for this view
    def post(self, request):
        logger = POSLogger(__name__, level="DEBUG")
        
        logger.debug(f"Request headers: {request.headers}")
        logger.debug(f"Request data: {request.data}")

        token = request.data.get('token')
        if not token:
            logger.error("No token provided in request")
            return Response({'error': 'No token provided.'}, status=status.HTTP_400_BAD_REQUEST)
        logger.info(f"Received token: {token[:20]}...")
        try:
            # Verify the token with Google's OAuth2 API
            idinfo = id_token.verify_oauth2_token(
                token,
                google_requests.Request(),
                settings.GOOGLE_CLIENT_ID
            )

            # Verify issuer
            if idinfo['iss'] not in ['accounts.google.com', 'https://accounts.google.com']:
                raise ValueError('Invalid token issuer.')

            # Ensure email is verified
            if not idinfo.get('email_verified', False):
                return Response({'error': 'Google account email not verified.'}, status=status.HTTP_400_BAD_REQUEST)

            email = idinfo['email']

            domain = email.split('@')[-1].lower()

            # if domain != 'sn15.ai':
            #     return Response({
            #         'error': "Your account is not authorized to sign in ."
            #     }, status=status.HTTP_403_FORBIDDEN)
            

           # check if  user exists in db

            try:
                user = User.objects.get(email=email)
                logger.info(f"\n\n User email from db is : {user.email}\n\n")
            except User.DoesNotExist:
                return Response(
                    {"error" : "Sorry You are not registered to use this application."},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            # Issue our own JWT tokens
            refresh = RefreshToken.for_user(user)
            access_token = str(refresh.access_token)
            refresh_token = str(refresh)
            if not user.is_super_admin:
                user_locations = user.locations.filter(is_active=True)
            else:
                user_locations = Location.objects.all()

            return Response({
                'access': access_token,
                'refresh': refresh_token,
                'user': {
                    'id': user.id,
                    'email': user.email,
                    'first_name': user.first_name,
                    'last_name': user.last_name,
                    'is_franchise_admin': user.is_franchise_admin,
                    'is_super_admin': user.is_super_admin,
                    'is_staff_member': user.is_staff_member,
                },
                'locations' : [
                    {
                        'id': location.id,
                        'name': location.name,
                        "city": location.city,
                        "state": location.state
                    } for location in user_locations
                ]
            })

        except ValueError:
            return Response({'error': 'Invalid Google token.'}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
