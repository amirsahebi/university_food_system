from rest_framework.permissions import BasePermission, SAFE_METHODS

class IsAdminOrReadOnly(BasePermission):
    """
    Custom permission to allow:
    - Admins full access to all methods.
    - Non-admins (Students, Chefs, Receivers) access to safe methods (GET, HEAD, OPTIONS).
    """

    def has_permission(self, request, view):
        # SAFE_METHODS are typically GET, HEAD, and OPTIONS
        if request.method in SAFE_METHODS:
            return True
        
        # For non-safe methods, check if the user is an admin
        return request.user.is_authenticated and request.user.role == 'admin'

class IsAdminOnly(BasePermission):
    """
    Custom permission to allow access only to admins.
    """

    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == 'admin'
    
class IsChefOrAdmin(BasePermission):
    """
    Allows access only to chef and admin users.
    """

    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role in ['chef', 'admin']
    
class IsChefOrReceiverOrAdmin(BasePermission):
    """
    Allows access only to chef, receiver, and admin users.
    """

    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role in ['chef', 'receiver', 'admin']

class IsStudentOrAdmin(BasePermission):
    """
    Allows access only to student and admin users.
    """

    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role in ['student', 'admin']

class IsReceiverOrAdmin(BasePermission):
    """
    Allows access only to receiver and admin users.
    """

    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role in ['receiver', 'admin']
