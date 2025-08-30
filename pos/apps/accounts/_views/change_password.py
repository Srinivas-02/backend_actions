from rest_framework.views import APIView
from rest_framework.response import Response

from django.contrib.auth import authenticate,update_session_auth_hash
from django.contrib.auth.hashers import check_password
from django.conf import settings

import os

from django.http import JsonResponse
from django.template.loader import render_to_string
from rest_framework import status
from pos.apps.utils import send_email
from pos.utils.logger import POSLogger

logger = POSLogger(__name__)
class ChangePasswordView(APIView):
   def post(self, request):
        user = request.user
        data = request.data

        current_password = data.get('current_password')
        new_password = data.get('new_password')
        confirm_password= data.get('confirm_password')

        logger.info(f"\n\n current password is {current_password} \n\n new password is {new_password} \n\n confirm password is {confirm_password} \n\n")

        if not current_password or not new_password or not confirm_password:
            return JsonResponse(
                {"error": "All fields are required."}, status=status.HTTP_400_BAD_REQUEST
            )

        if not user.check_password(current_password):
            return JsonResponse(
                {"error": "Current password is incorrect."}, status=status.HTTP_400_BAD_REQUEST
            )

        if new_password != confirm_password:
            return JsonResponse(
                {"error": "New passwords do not match."}, status=status.HTTP_400_BAD_REQUEST
            )

        if check_password(new_password, user.password):
            return JsonResponse(
                {"error": "New password must be different from the current password."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user.set_password(new_password)
        user.save()

        update_session_auth_hash(request, user)
        self.send_confirmation_email(user)
        

        

        return JsonResponse({"message": "Password changed and email sent successfully."}, status=status.HTTP_200_OK)
   
   def send_confirmation_email(self, user):
        
        subject = 'Password Change Confirmation'
        templates_directory = os.path.join(settings.EMAIL_TEMPLATES_DIR, 'password_reset_confirmation.html')
        message = render_to_string(templates_directory, {'first_name': user.first_name})

        send_email( subject, message, [user.email])
        
 