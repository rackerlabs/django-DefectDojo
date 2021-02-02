from django.core.management.base import BaseCommand
from dojo.models import Finding
import logging

deduplicationLogger = logging.getLogger("dojo.specific-loggers.deduplication")


"""
Author: Marian Gawron
This script will identify loop dependencies in findings
"""


class Command(BaseCommand):
    help = "No input commands for fixing Loop findings."

    def handle(self, *args, **options):
        fix_loop_duplicates()


def fix_loop_duplicates():
    candidates = (
        Finding.objects.filter(
            duplicate_finding__isnull=False, original_finding__isnull=False
        )
        .all()
        .order_by("-id")
    )
    deduplicationLogger.info("Identified %d Findings with Loops" % len(candidates))
    for find_id in candidates.values_list("id", flat=True):
        removeLoop(find_id, 5)

    new_originals = Finding.objects.filter(
        duplicate_finding__isnull=True, duplicate=True
    )
    for f in new_originals:
        deduplicationLogger.info("New Original: %d " % f.id)
        f.duplicate = False
        super(Finding, f).save()

    loop_count = Finding.objects.filter(
        duplicate_finding__isnull=False, original_finding__isnull=False
    ).count()
    deduplicationLogger.info("%d Finding found with Loops" % loop_count)


def removeLoop(finding_id, counter):
    # get latest status
    finding = Finding.objects.get(id=finding_id)
    real_original = finding.duplicate_finding

    if not real_original or real_original is None:
        return

    if finding_id == real_original.id:
        finding.duplicate_finding = None
        super(Finding, finding).save()
        return

    # Only modify the findings if the original ID is lower to get the oldest finding as original
    if (real_original.id > finding_id) and (
        real_original.duplicate_finding is not None
    ):
        tmp = finding_id
        finding_id = real_original.id
        real_original = Finding.objects.get(id=tmp)
        finding = Finding.objects.get(id=finding_id)

    if real_original in finding.original_finding.all():
        # remove the original from the duplicate list if it is there
        finding.original_finding.remove(real_original)
        super(Finding, finding).save()
    if counter <= 0:
        # Maximum recursion depth as safety method to circumvent recursion here
        return
    for f in finding.original_finding.all():
        # for all duplicates set the original as their original, get rid of self in between
        f.duplicate_finding = real_original
        super(Finding, f).save()
        super(Finding, real_original).save()
        removeLoop(f.id, counter - 1)
