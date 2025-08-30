from rest_framework_simplejwt.views import TokenRefreshView
from rest_framework_simplejwt.exceptions import InvalidToken
from rest_framework.response import Response
from rest_framework import status
from pos.utils.logger import POSLogger

logger = POSLogger(__name__)

class CustomTokenRefreshView(TokenRefreshView):
    authentication_classes = []  # Disable authentication for refresh
    
    def post(self, request, *args, **kwargs):
        logger.debug(f"Token refresh request data: {request.data}")
        refresh_token = request.data.get('refresh', '')
        if not refresh_token:
            return Response({"error": "No refresh token provided"}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            # Check if token is in blacklist before attempting refresh
            from pos.apps.accounts.models import BlacklistedToken
            from rest_framework_simplejwt.tokens import RefreshToken
            token = RefreshToken(refresh_token)
            
            if BlacklistedToken.objects.filter(jti=token.get('jti')).exists():
                logger.warning(f"Attempt to use blacklisted refresh token with JTI: {token.get('jti')}")
                return Response(
                    {"error": "This refresh token has been invalidated"}, 
                    status=status.HTTP_401_UNAUTHORIZED
                )
            
            response = super().post(request, *args, **kwargs)
            logger.info("Token refresh successful")
            return response
            
        except InvalidToken as e:
            logger.error(f"Invalid token during refresh: {str(e)}")
            return Response(
                {"error": "Invalid or expired refresh token"}, 
                status=status.HTTP_401_UNAUTHORIZED
            )
        except Exception as e:
            logger.error(f"Unexpected error during token refresh: {str(e)}")
            return Response(
                {"error": "An error occurred while refreshing the token"}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
