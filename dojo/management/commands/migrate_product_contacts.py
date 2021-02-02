from django.core.management.base import BaseCommand

from pytz import timezone
from dojo.models import Product, Dojo_User
from dojo.utils import get_system_setting

locale = timezone(get_system_setting("time_zone"))

"""
Authors: Jay Paz
        The following three fields are deprecated and no longer in use.
        They remain in model for backwards compatibility and will be removed
        in a future release.  prod_manager, tech_contact, manager

        The admin script migrate_product_contacts should be used to migrate data from
        these fields to their replacements.  ./manage.py migrate_product_contacts
"""


class Command(BaseCommand):
    help = (
        "The Product fields prod_manager, tech_contact, manager have been marked for deprecation.  "
        "Run this script to migrate to new contact fields."
    )

    def handle(self, *args, **options):
        products = Product.objects.all()

        count = 0
        contact_count = 0
        user_created = 0

        for prod in products:
            product_updated = False
            if prod.prod_manager != "0":
                fname = prod.prod_manager.split()[0]
                lname = prod.prod_manager.split()[1]
                user, created = Dojo_User.objects.get_or_create(
                    first_name=fname, last_name=lname
                )
                if created:
                    user.username = fname + "." + lname
                    user.set_unusable_password()
                    user.is_staff = False
                    user.is_superuser = False
                    user.active = True
                    user.save()
                    user_created += 1
                prod.product_manager = user
                prod.prod_manager = "0"
                prod.save()
                contact_count += 1
                product_updated = True
            if prod.manager != "0":
                fname = prod.manager.split()[0]
                lname = prod.manager.split()[1]
                user, created = Dojo_User.objects.get_or_create(
                    first_name=fname, last_name=lname
                )
                if created:
                    user.username = fname + "." + lname
                    user.set_unusable_password()
                    user.is_staff = False
                    user.is_superuser = False
                    user.active = True
                    user.save()
                    user_created += 1
                prod.team_manager = user
                prod.manager = "0"
                prod.save()
                contact_count += 1
                product_updated = True
            if prod.tech_contact != "0":
                fname = prod.tech_contact.split()[0]
                lname = prod.tech_contact.split()[1]
                user, created = Dojo_User.objects.get_or_create(
                    first_name=fname, last_name=lname
                )
                if created:
                    user.username = fname + "." + lname
                    user.set_unusable_password()
                    user.is_staff = False
                    user.is_superuser = False
                    user.active = True
                    user.save()
                    user_created += 1
                prod.technical_contact = user
                prod.tech_contact = "0"
                prod.save()
                contact_count += 1
                product_updated = True

            if product_updated:
                count += 1

        print(
            "A total of %d products have been migrated.  A total of %d contacts were updated.  "
            "A total of %d users were created" % (count, contact_count, user_created)
        )
