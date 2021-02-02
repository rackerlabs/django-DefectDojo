import gitlab

from django.conf import settings
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.db.models import Q
from dojo.models import Engagement, Product, Product_Type, Test
from social_core.backends.azuread_tenant import AzureADTenantOAuth2
from social_core.backends.google import GoogleOAuth2


def social_uid(backend, details, response, *args, **kwargs):
    if settings.AZUREAD_TENANT_OAUTH2_ENABLED and isinstance(
        backend, AzureADTenantOAuth2
    ):
        """Return user details from Azure AD account"""
        fullname, first_name, last_name, upn = (
            response.get("name", ""),
            response.get("given_name", ""),
            response.get("family_name", ""),
            response.get("upn"),
        )
        uid = backend.get_user_id(details, response)
        return {
            "username": upn,
            "email": upn,
            "fullname": fullname,
            "first_name": first_name,
            "last_name": last_name,
            "uid": uid,
        }
    elif settings.GOOGLE_OAUTH_ENABLED and isinstance(backend, GoogleOAuth2):
        """Return user details from Google account"""
        if "sub" in response:
            google_uid = response["sub"]
        elif "email" in response:
            google_uid = response["email"]
        else:
            google_uid = response["id"]
        fullname, first_name, last_name, email = (
            response.get("fullname", ""),
            response.get("first_name", ""),
            response.get("last_name", ""),
            response.get("email"),
        )
        return {
            "username": email,
            "email": email,
            "fullname": fullname,
            "first_name": first_name,
            "last_name": last_name,
            "uid": google_uid,
        }
    else:
        uid = backend.get_user_id(details, response)
        # Used for most backends
        if uid:
            return {"uid": uid}
        # Until OKTA PR in social-core is merged
        # This modified way needs to work
        else:
            return {"uid": response.get("preferred_username")}


def modify_permissions(backend, uid, user=None, social=None, *args, **kwargs):
    if kwargs.get("is_new"):
        user.is_staff = False
        if settings.GITLAB_PROJECT_AUTO_IMPORT is True:
            # Add engagement creation permission if auto_import  is set
            user.user_permissions.set(
                [
                    Permission.objects.get(
                        codename="add_engagement",
                        content_type=ContentType.objects.get_for_model(Engagement),
                    ),
                    Permission.objects.get(
                        codename="add_test",
                        content_type=ContentType.objects.get_for_model(Test),
                    ),
                    Permission.objects.get(
                        codename="change_test",
                        content_type=ContentType.objects.get_for_model(Test),
                    ),
                ]
            )


def update_product_access(backend, uid, user=None, social=None, *args, **kwargs):
    if settings.GITLAB_PROJECT_AUTO_IMPORT is True:
        # Get user's product names
        user_product_names = [
            prod.name
            for prod in Product.objects.filter(
                Q(authorized_users__in=[user])
                | Q(prod_type__authorized_users__in=[user])
            )
        ]
        # Get Gitlab access token
        soc = user.social_auth.get()
        token = soc.extra_data["access_token"]
        # Get user's projects list on Gitlab
        gl = gitlab.Gitlab(settings.SOCIAL_AUTH_GITLAB_API_URL, oauth_token=token)
        # Get each project path_with_namespace as future product name
        projects = gl.projects.list(membership=True, all=True)
        project_names = [project.path_with_namespace for project in projects]
        # Create product_type if necessary
        product_type, created = Product_Type.objects.get_or_create(name="Gitlab Import")
        # For each project: create a new product or update product's authorized_users
        for project_name in project_names:
            if project_name not in user_product_names:
                # Create new product
                product, created = Product.objects.get_or_create(
                    name=project_name, prod_type=product_type
                )
                product.authorized_users.add(user)
                product.save()
        # For each product: if user is not project member any more, remove him from product's authorized users
        for product_name in user_product_names:
            if product_name not in project_names:
                product = Product.objects.get(name=product_name)
                product.authorized_users.remove(user)
                product.save()
