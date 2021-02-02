from django.core.management.base import BaseCommand
from django.db.models import Count
from dojo.models import Finding, Endpoint_Status


"""
Author: Cody Maffucci
This script will create endpoint status objects for findings and endpoints for
databases that already contain those objects. This script should only be run when
upgrading to 1.7.0>= as it is unnecessary for fresh installs
"""


class Command(BaseCommand):
    help = "Create status objects for Endpoints for easier tracking"

    def handle(self, *args, **options):
        # Get a list of findings that have endpoints
        findings = Finding.objects.annotate(count=Count("endpoints")).filter(
            count__gt=0
        )
        for finding in findings:
            # Get the list of endpoints on the current finding
            endpoints = finding.endpoints.all()
            for endpoint in endpoints:
                # Superflous error checking
                try:
                    # Create a new status for each endpoint
                    status, created = Endpoint_Status.objects.get_or_create(
                        finding=finding,
                        endpoint=endpoint,
                    )
                    # Check if the status object was created, otherwise, there is nothing to do
                    if created:
                        status.date = finding.date
                        # If the parent endpoint was mitigated with the old system,
                        # reflect the same on the endpoint status object
                        if endpoint.mitigated:
                            status.mitigated = True
                            status.mitigated_by = finding.reporter
                        # Save the status object with at least one updated field
                        status.save()
                        # Attach the status to the endpoint and finding
                        endpoint.endpoint_status.add(status)
                        finding.endpoint_status.add(status)
                except Exception as e:
                    # Something wild happened
                    print(e)
                    pass
