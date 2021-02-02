from django.core.management.base import BaseCommand
from pytz import timezone

from dojo.models import Finding
from dojo.utils import get_system_setting
import logging

locale = timezone(get_system_setting("time_zone"))

logger = logging.getLogger(__name__)
deduplicationLogger = logging.getLogger("dojo.specific-loggers.deduplication")

"""
Author: Aaron Weaver
This script will update the hashcode and dedupe findings in DefectDojo:
"""


class Command(BaseCommand):
    help = "No input commands for dedupe findings."

    def handle(self, *args, **options):

        findings = Finding.objects.all()
        logger.info(
            "######## Updating Hashcodes (deduplication is done in the background  upon finding save ########"
        )
        deduplicationLogger.info(
            "######## Updating Hashcodes (deduplication is done in the background  upon finding save ########"
        )
        for finding in findings:
            finding.hash_code = finding.compute_hash_code()
            finding.save()
        logger.info(
            "######## Done Updating Hashcodes (deduplication is done in the background upon finding save ########"
        )
        deduplicationLogger.info(
            "######## Done Updating Hashcodes (deduplication is done in the background upon finding save ########"
        )
