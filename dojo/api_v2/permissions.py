from rest_framework import permissions


class UserHasProductPermission(permissions.BasePermission):
    """
    @brief      To ensure that one user can only access authorized project
    """

    def has_object_permission(self, request, view, obj):
        return (
            request.user
            in (obj.authorized_users.all() | obj.prod_type.authorized_users.all())
            or request.user.is_staff
        )


class UserHasReportGeneratePermission(permissions.BasePermission):
    """
    @brief      To ensure that one user can only access authorized project
    """

    def has_object_permission(self, request, view, obj):
        return (
            request.user
            in (
                obj.product.authorized_users.all()
                | obj.product.prod_type.authorized_users.all()
            )
            or request.user.is_staff
        )


class UserHasScanSettingsPermission(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        return (
            request.user
            in (
                obj.product.authorized_users.all()
                | obj.product.prod_type.authorized_users.all()
            )
            or request.user.is_staff
        )


class UserHasScanPermission(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        return (
            request.user
            in (
                obj.scan_settings.product.authorized_users.all()
                | obj.scan_settings.product.prod_type.authorized_users.all()
            )
            or request.user.is_staff
        )


class IsSuperUser(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user and request.user.is_superuser
