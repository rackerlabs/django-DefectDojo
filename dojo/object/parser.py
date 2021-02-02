#  #   product
import logging
import json

from django.urls import reverse
from django.utils import timezone

from dojo.notifications.helper import create_notification
from dojo.models import (
    Test,
    Test_Type,
    Development_Environment,
    Objects_Engagement,
    Objects_Product,
    Objects_Review,
)


logger = logging.getLogger(__name__)


def find_item(item, object_queryset):
    object_type = None
    found_object = None

    #  Check for file
    for object in object_queryset:
        if object.path == item:
            object_type = "file"
            found_object = object
            break
        elif object.folder is not None:
            if object.folder in item:
                object_type = "path"
                found_object = object
                break
        elif object.artifact is not None:
            if item in object.artifact:
                object_type = "artifact"
                found_object = object
                break

    return object_type, found_object


def import_object_eng(request, engagement, json_data):
    create_test_code_review = False
    create_alert = False

    # Get the product from the engagement
    product = engagement.product

    # Retrieve the files currently set for this product
    object_queryset = Objects_Product.objects.filter(
        product=engagement.product.id
    ).order_by("-path")
    tree = json_data.read()
    try:
        data = json.loads(str(tree, "utf-8"))
    except:
        data = json.loads(tree)

    # Set default review status
    review_status_id = 1
    review_status = Objects_Review.objects.get(pk=review_status_id)

    for file in data:
        # Save the file if the object isn't in object table
        file_type, found_object = find_item(file["path"], object_queryset)

        if found_object is None or file_type == "path":
            review_status_id = 1

            if file_type == "path":
                # Copy the review status
                review_status_id = found_object.review_status.id

            # Set default review status
            review_status = Objects_Review.objects.get(pk=review_status_id)

            # if found_object is None:
            object = Objects_Product(
                product=product, path=file["path"], review_status=review_status
            )
            object.save()
            found_object = object
            if file_type == "path":
                for tag in found_object.tags.all():
                    object.tags.add(tag)

        full_url = None
        file_type = None
        percentUnchanged = None
        build_id = None
        if "full_url" in file:
            full_url = file["full_url"]
        if "type" in file:
            file_type = file["type"]
        if "percentUnchanged" in file:
            percentUnchanged = file["percentUnchanged"]
        if "build_id" in file:
            build_id = file["build_id"][:12]

        # Find the status so the appropriate action takes place
        if found_object.review_status.id == 2:
            create_alert = True
        elif found_object.review_status.id == 3:
            create_test_code_review = True
            create_alert = True

        # Save the changed files to the engagement view
        object_eng = Objects_Engagement(
            engagement=engagement,
            object_id=found_object,
            full_url=full_url,
            type=file_type,
            percentUnchanged=percentUnchanged,
            build_id=build_id,
        )
        object_eng.save()

    # Create the notification
    if create_alert:
        create_notification(
            event="code_review",
            title="Manual Code Review Requested",
            description="Manual code review requested as tracked file changes were found in the latest build.",
            engagement=engagement,
            url=reverse("view_object_eng", args=(engagement.id,)),
        )

    # Create the test within the engagement
    if create_test_code_review:
        environment, env_created = Development_Environment.objects.get_or_create(
            name="Development"
        )
        tt = Test_Type.objects.get(pk=27)  # Manual code review
        if tt:
            test = Test(
                engagement=engagement,
                test_type=tt,
                target_start=timezone.now(),
                target_end=timezone.now() + timezone.timedelta(days=1),
                environment=environment,
                percent_complete=0,
            )
            test.save()
            create_notification(
                event="test_added",
                title="Test added for Manual Code Review",
                test=test,
                engagement=engagement,
                url=request.build_absolute_uri(
                    reverse("view_engagement", args=(engagement.id,))
                ),
            )
