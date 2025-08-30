from rest_framework.permissions import BasePermission
from pos.utils.logger import POSLogger

logger = POSLogger(__name__)

class IsSuperAdmin(BasePermission):
    """
    Allows access only to super admin users.
    """
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            logger.warning("Unauthenticated user tried to access super admin resource")
            return False
        return request.user.is_super_admin

class IsFranchiseAdmin(BasePermission):
    """
    Allows access only to franchise admin users.
    """
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            logger.warning("Unauthenticated user tried to access admin resource")
            return False
        return request.user.is_franchise_admin

class IsStaffMember(BasePermission):
    """
    Allows access only to staff members.
    """
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            logger.warning("Unauthenticated user tried to access staff resource")
            return False
        return request.user.is_staff_member

class IsAuthenticatedAndActive(BasePermission):
    """
    Allows access only to authenticated and active users.
    """
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            logger.warning("Unauthenticated user tried to access protected resource")
            return False
        if not request.user.is_active:
            logger.warning(f"Inactive user {request.user.email} tried to access protected resource")
            return False
        return True

class HasLocationAccess(BasePermission):
    """
    Allows access only to users who have access to the specified location.
    """
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            logger.warning("Unauthenticated user tried to access location resource")
            return False
            
        location_id = view.kwargs.get('location_id') or request.query_params.get('location_id')
        if not location_id:
            logger.warning("Location ID not provided in request")
            return False
            
        has_access = request.user.has_location_access(location_id)
        if not has_access:
            logger.warning(f"User {request.user.email} tried to access location {location_id} without permission")
        return has_access 