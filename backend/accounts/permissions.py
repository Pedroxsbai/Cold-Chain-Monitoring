from rest_framework.permissions import BasePermission


class IsAdminRole(BasePermission):
    """Global administrator (role `admin` or Django superuser)."""

    message = "Action réservée à l'administrateur."

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_admin)
