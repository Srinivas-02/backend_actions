from django.conf import settings
from django.core.mail import send_mail
from pos.apps.locations.models import LocationModel

def send_email(subject, message,  to_email_list):
    """ Send Email"""

    send_mail(
        subject,
        message,
        settings.EMAIL_HOST_USER,
        to_email_list,
        fail_silently=False,
    )


def user_allowed_locations(user):
    """
    Return a queryset of locations the user can access.
    Super Admin -> all locations
    Franchise Admin -> only assigned locations
    Others -> none
    """
    if getattr(user, 'is_super_admin', False):
        return LocationModel.objects.all()
    if getattr(user, 'is_franchise_admin', False):
        return user.locations.all()  
    return LocationModel.objects.none()

def ensure_can_access_location(user, location_id):
    """
    Return True if user can access the given location_id.
    """
    return user_allowed_locations(user).filter(pk=location_id).exists()