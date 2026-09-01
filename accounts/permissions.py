from rest_framework.permissions import BasePermission


class IsSupervisor(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == "supervisor"


class IsCEO(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == "ceo"


class IsSupervisorOrCEO(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role in ["supervisor", "ceo"]


class IsStaff(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == "staff"


class IsStaffOrSupervisor(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role in ["staff", "supervisor"]
