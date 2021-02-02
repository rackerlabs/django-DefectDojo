from django.core.management.base import BaseCommand
from pytz import timezone
from celery.decorators import task

locale = timezone(get_system_setting("time_zone"))

"""
Author: Aaron Weaver
This script will update the hashcode and dedupe findings in DefectDojo:
"""


class Command(BaseCommand):
    help = "No input commands for dedupe findings."

    def handle(self, *args, **options):
        rename_whitesource_finding()


@task(name="rename_whitesource_finding_task")
def rename_whitesource_finding():
    whitesource_id = Test_Type.objects.get(name="Whitesource Scan").id
    findings = Finding.objects.filter(found_by=whitesource_id)
    findings = findings.order_by("-pk")
    logger.info(
        "######## Updating Hashcodes - deduplication is done in the background upon finding save ########"
    )
    for finding in findings:
        logger.info("Updating Whitesource Finding with id: %d" % finding.id)
        lib_name_begin = re.search(
            "\\*\\*Library Filename\\*\\* : ", finding.description
        ).span(0)[1]
        lib_name_end = re.search(
            "\\*\\*Library Description\\*\\*", finding.description
        ).span(0)[0]
        lib_name = finding.description[lib_name_begin : lib_name_end - 1]
        if finding.cve is None:
            finding.title = "CVE-None | " + lib_name
        else:
            finding.title = finding.cve + " | " + lib_name
        if not finding.cwe:
            logger.debug(
                "Set cwe for finding %d to 1035 if not an cwe Number is set"
                % finding.id
            )
            finding.cwe = 1035
        finding.title = finding.title.rstrip()  # delete \n at the end of the title
        from titlecase import titlecase

        finding.title = titlecase(finding.title)
        finding.hash_code = finding.compute_hash_code()
        finding.save()
