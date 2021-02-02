import datetime
import sys

from django.core.mail import send_mail
from django.core.management.base import BaseCommand
from pytz import timezone

from dojo.models import ScanSettings, Product
from django.conf import settings

from dojo.utils import get_system_setting

locale = timezone(get_system_setting("time_zone"))

"""
Authors: Fatimah
A script that notifies external unit about the scans.
"""


class Command(BaseCommand):
    help = "Details: Spams External Unit\nArgs: Weekly, Monthly, Quarterly"

    def add_arguments(self, parser):
        parser.add_argument("type")

    def handle(self, *args, **options):
        type = options["type"]

        if not options:
            print("Must specify an argument: Weekly, Monthly, or Quarterly")
            sys.exit(0)
        if type not in ["Weekly", "Monthly", "Quarterly"]:
            print(
                (
                    "Unexpected frequency: "
                    + str(type)
                    + "\nMust specify an argument: Weekly, Monthly, or Quarterly."
                )
            )
            sys.exit(0)

        scSettings = ScanSettings.objects.filter(frequency=type)

        scan_start_time = datetime.datetime.today() + datetime.timedelta(hours=12)
        scan_stop_time = datetime.datetime.today() + datetime.timedelta(hours=24)

        # Send one giant email to External Unit with a list  of all the
        # ipaddresses that will be scanned
        msg = "\nGreetings, \n\n"
        msg += get_system_setting("team_name") + " will be performing port scans of "
        msg += "the following products and target IPs:"
        msg += "\n\nStart Time: " + str(scan_start_time)
        msg += "\n\nStop Time (est): " + str(scan_stop_time)
        msg += "\n\nSource IP: " + settings.PORT_SCAN_SOURCE_IP
        for s in scSettings:
            msg += "\n\nProduct: " + str(Product.objects.get(id=s.product_id).name)

            list_addresses = s.addresses.strip().split(",")
            for la in list_addresses:
                line = la.split(":")
                addr = line[0].strip()
                msg += "\n" + str(addr)

        msg += "\n\nPlease let us know if you have any questions.\n Thanks,\n"
        msg += settings.PORT_SCAN_RESULT_EMAIL_FROM
        send_mail(
            get_system_setting("team_name") + " Port Scan",
            msg,
            settings.PORT_SCAN_RESULT_EMAIL_FROM,
            settings.PORT_SCAN_EXTERNAL_UNIT_EMAIL_LIST,
            fail_silently=False,
        )
