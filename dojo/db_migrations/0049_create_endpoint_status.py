from django.db import migrations, models


class Migration(migrations.Migration):

    """
    This script will create endpoint status objects for findings and endpoints for
    databases that already contain those objects.
    """

    def create_status_objects(apps, schema_editor):
        # Retreive the correct models
        Finding = apps.get_model("dojo", "Finding")
        Endpoint_Status = apps.get_model("dojo", "Endpoint_Status")
        # Get a list of findings that have endpoints
        findings = Finding.objects.annotate(count=models.Count("endpoints")).filter(
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

    dependencies = [
        ("dojo", "0048_sla_notifications"),
    ]

    operations = [migrations.RunPython(create_status_objects)]
