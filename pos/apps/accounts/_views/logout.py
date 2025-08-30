"""Logout views"""

from django.http import JsonResponse
from django.utils.timezone import now
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import AccessToken

from pos.apps.accounts.models import BlacklistedToken  # Adjust import path as needed
from pos.utils.logger import POSLogger

logger = POSLogger(__name__)

class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            access_token_str = request.headers.get("Authorization").split()[1]
            access_token = AccessToken(access_token_str)
            
            # Blacklist the token
            BlacklistedToken.objects.create(jti=access_token["jti"], blacklisted_on=now())
            
            user = request.user
            user.is_logged_in = False
            user.save()
            
            logger.info(f"User {request.user.email} logged out successfully")
            
            # Return response and clear cookies
            response = JsonResponse({"message": "Logout successful"}, status=status.HTTP_200_OK)
            response.delete_cookie("sessionid")
            response.delete_cookie("csrftoken")
            return response
            
        except Exception as e:
            logger.error(f"Logout error: {str(e)}")
            return JsonResponse({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)