from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, AuthenticationFailed
from pos.apps.accounts.models import BlacklistedToken  
from pos.utils.logger import POSLogger

logger = POSLogger(__name__)

class BlacklistJWTAuthentication(JWTAuthentication):
    def get_validated_token(self, raw_token):
        """
        Overrides the parent method to check if the token has been blacklisted
        """
        # First validate the token using parent method
        validated_token = super().get_validated_token(raw_token)

        print(f"Checking token with JTI: {validated_token['jti']}")
        
        # Check if token is blacklisted
        if BlacklistedToken.objects.filter(jti=validated_token["jti"]).exists():
            logger.warning(f"Attempt to use blacklisted token: {validated_token['jti']}")
            raise InvalidToken("Session ended. Please log in again to access this resource.")
            
        return validated_token