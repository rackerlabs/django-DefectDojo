from django.core.management.base import BaseCommand
from dojo.utils import sla_compute_and_notify

"""
This command will iterate over findings and send SLA notifications as appropriate
"""


class Command(BaseCommand):
    help = "Launch with no argument."

    def handle(self, *args, **options):
        sla_compute_and_notify()
