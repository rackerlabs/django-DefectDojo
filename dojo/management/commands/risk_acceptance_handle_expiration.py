from django.core.management.base import BaseCommand
import dojo.risk_acceptance.helper as ra_helper
from crum import impersonate
from dojo.models import Dojo_User


class Command(BaseCommand):
    help = "Handle any risk acceptances that are expired (and not handled yet). Also posts expiration heads alerts / jira comments if configured"

    def handle(self, *args, **options):
        # use admin user to make sure we have access to its properties i.e. to determine wants_async
        with impersonate(Dojo_User.objects.get(username="admin")):
            ra_helper.expiration_handler()
