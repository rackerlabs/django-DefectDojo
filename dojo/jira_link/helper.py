import logging
from dojo.utils import get_system_setting
import os
import io
import json
import requests
from django.conf import settings
from django.template.loader import render_to_string
from django.utils import timezone
from jira import JIRA
from jira.exceptions import JIRAError
from dojo.models import (
    Finding,
    Test,
    Engagement,
    Product,
    JIRA_Issue,
    JIRA_Project,
    System_Settings,
    Notes,
    JIRA_Instance,
)
from requests.auth import HTTPBasicAuth
from dojo.notifications.helper import create_notification
from django.contrib import messages
from celery.decorators import task
from dojo.decorators import dojo_async_task, dojo_model_from_id, dojo_model_to_id
from dojo.utils import get_current_request, truncate_with_dots
from django.urls import reverse
from dojo.forms import JIRAProjectForm, JIRAEngagementForm

logger = logging.getLogger(__name__)

RESOLVED_STATUS = [
    "Inactive",
    "Mitigated",
    "False Positive",
    "Out of Scope",
    "Duplicate",
]

OPEN_STATUS = ["Active", "Verified"]


def is_jira_enabled():
    if not get_system_setting("enable_jira"):
        logger.debug("JIRA is disabled, not doing anything")
        return False

    return True


def is_jira_configured_and_enabled(obj):
    if not is_jira_enabled():
        return False

    if get_jira_project(obj) is None:
        logger.debug('JIRA project not found for: "%s" not doing anything', obj)
        return False

    return True


def is_push_to_jira(instance, push_to_jira_parameter=None):
    if not is_jira_configured_and_enabled(instance):
        return False

    jira_project = get_jira_project(instance)

    # caller explicitly stated true or false (False is different from None!)
    if push_to_jira_parameter is not None:
        return push_to_jira_parameter

    # push_to_jira was not specified, so look at push_all_issues in JIRA_Project
    return jira_project.push_all_issues


def is_push_all_issues(instance):
    if not is_jira_configured_and_enabled(instance):
        return False

    jira_project = get_jira_project(instance)
    if jira_project:
        return jira_project.push_all_issues


# use_inheritance=True means get jira_project config from product if engagement itself has none
def get_jira_project(obj, use_inheritance=True):
    if not is_jira_enabled():
        return None

    if obj is None:
        return None

    if isinstance(obj, JIRA_Project):
        return obj

    if isinstance(obj, JIRA_Issue):
        return obj.jira_project

    if isinstance(obj, Finding):
        finding = obj
        return get_jira_project(finding.test)

    if isinstance(obj, Test):
        test = obj
        return get_jira_project(test.engagement)

    if isinstance(obj, Engagement):
        engagement = obj
        jira_project = None
        try:
            jira_project = (
                engagement.jira_project
            )  # first() doesn't work with prefetching
            if jira_project:
                logger.debug("found jira_project %s for %s", jira_project, engagement)
                return jira_project
        except JIRA_Project.DoesNotExist:
            pass  # leave jira_project as None

        if use_inheritance:
            logger.debug(
                "delegating to product %s for %s", engagement.product, engagement
            )
            return get_jira_project(engagement.product)
        else:
            logger.debug(
                "not delegating to product %s for %s", engagement.product, engagement
            )
            return None

    if isinstance(obj, Product):
        # TODO refactor relationships, but now this would brake APIv1 (and v2?)
        product = obj
        jira_projects = (
            product.jira_project_set.all()
        )  # first() doesn't work with prefetching
        jira_project = jira_projects[0] if len(jira_projects) > 0 else None
        if jira_project:
            logger.debug("found jira_project %s for %s", jira_project, product)
            return jira_project

    logger.debug("no jira_project found for %s", obj)
    return None


def get_jira_instance(instance):
    if not is_jira_enabled():
        return None

    jira_project = get_jira_project(instance)
    if jira_project:
        logger.debug(
            "found jira_instance %s for %s", jira_project.jira_instance, instance
        )
        return jira_project.jira_instance

    return None


def get_jira_url(obj):
    logger.debug("getting jira url")

    # finding + engagement
    issue = get_jira_issue(obj)
    if issue is not None:
        return get_jira_issue_url(issue)
    elif isinstance(obj, Finding):
        # finding must only have url if there is a jira_issue
        # engagement can continue to show url of jiraproject instead of jira issue
        return None

    if isinstance(obj, JIRA_Project):
        return get_jira_project_url(obj)

    return get_jira_project_url(get_jira_project(obj))


def get_jira_issue_url(issue):
    logger.debug("getting jira issue url")
    jira_project = get_jira_project(issue)
    jira_instance = get_jira_instance(jira_project)
    if jira_instance is None:
        return None

    # example http://jira.com/browser/SEC-123
    return jira_instance.url + "/browse/" + issue.jira_key


def get_jira_project_url(obj):
    logger.debug("getting jira project url")
    if not isinstance(obj, JIRA_Project):
        jira_project = get_jira_project(obj)
    else:
        jira_project = obj

    if jira_project:
        logger.debug("getting jira project url2")
        jira_instance = get_jira_instance(obj)
        if jira_project and jira_instance:
            logger.debug("getting jira project url3")
            return (
                jira_project.jira_instance.url + "/browse/" + jira_project.project_key
            )

    return None


def get_jira_key(obj):
    if hasattr(obj, "has_jira_issue") and obj.has_jira_issue:
        return get_jira_issue_key(obj)

    if isinstance(obj, JIRA_Project):
        return get_jira_project_key(obj)

    return get_jira_project_key(get_jira_project(obj))


def get_jira_issue_key(obj):
    if obj.has_jira_issue:
        return obj.jira_issue.jira_key

    return None


def get_jira_project_key(obj):
    jira_project = get_jira_project(obj)

    if not get_jira_project:
        return None

    return jira_project.project_key


def get_jira_creation(obj):
    if isinstance(obj, Finding) or isinstance(obj, Engagement):
        if obj.has_jira_issue:
            return obj.jira_issue.jira_creation
    return None


def get_jira_change(obj):
    if isinstance(obj, Finding) or isinstance(obj, Engagement):
        if obj.has_jira_issue:
            return obj.jira_issue.jira_change
    else:
        logger.debug("get_jira_change unsupported object type: %s", obj)
    return None


def get_epic_name_field_name(jira_instance):
    if not jira_instance or not jira_instance.epic_name_id:
        return None

    return "customfield_" + str(jira_instance.epic_name_id)


def has_jira_issue(obj):
    return get_jira_issue(obj) is not None


def get_jira_issue(obj):
    if isinstance(obj, Finding) or isinstance(obj, Engagement):
        try:
            return obj.jira_issue
        except JIRA_Issue.DoesNotExist:
            return None


def has_jira_configured(obj):
    return get_jira_project(obj) is not None


def get_jira_connection_raw(jira_server, jira_username, jira_password):
    try:
        jira = JIRA(
            server=jira_server,
            basic_auth=(jira_username, jira_password),
            options={"verify": settings.JIRA_SSL_VERIFY},
            max_retries=0,
        )

        logger.debug("logged in to JIRA " "%s" " successfully", jira_server)

        return jira
    except JIRAError as e:
        logger.exception(e)

        if e.status_code in [401, 403]:
            log_jira_generic_alert("JIRA Authentication Error", e)
        else:
            log_jira_generic_alert("Unknown JIRA Connection Error", e)

        add_error_message_to_response(
            "Unable to authenticate to JIRA. Please check the URL, username, password, captcha challenge, Network connection. Details in alert on top right. "
            + e.message
        )
        raise e

    except requests.exceptions.RequestException as re:
        logger.exception(re)
        log_jira_generic_alert("Unknown JIRA Connection Error", re)

        add_error_message_to_response(
            "Unable to authenticate to JIRA. Please check the URL, username, password, captcha challenge, Network connection. Details in alert on top right. "
            + str(re)
        )

        raise re

    # except RequestException as re:
    #     logger.exception(re)


def add_error_message_to_response(message):
    if get_current_request():
        messages.add_message(
            get_current_request(), messages.ERROR, message, extra_tags="alert-danger"
        )


# Gets a connection to a Jira server based on the finding
def get_jira_connection(obj):
    jira = None

    jira_instance = obj
    if not isinstance(jira_instance, JIRA_Instance):
        jira_instance = get_jira_instance(obj)

    if jira_instance is not None:
        return get_jira_connection_raw(
            jira_instance.url, jira_instance.username, jira_instance.password
        )


def jira_get_resolution_id(jira, issue, status):
    transitions = jira.transitions(issue)
    resolution_id = None
    for t in transitions:
        if t["name"] == "Resolve Issue":
            resolution_id = t["id"]
            break
        if t["name"] == "Reopen Issue":
            resolution_id = t["id"]
            break

    return resolution_id


def jira_change_resolution_id(jira, issue, jid):
    try:
        if issue and jid:
            jira.transition_issue(issue, jid)
    except JIRAError as jira_error:
        logger.debug(
            "error transisioning jira issue " + issue.key + " " + str(jira_error)
        )
        logger.exception(jira_error)
        log_jira_generic_alert(
            "error transitioning jira issue " + issue.key, str(jira_error)
        )
        return None


# Used for unit testing so geting all the connections is manadatory
def get_jira_status(finding):
    if finding.has_jira_issue:
        j_issue = finding.jira_issue.jira_id
        project = get_jira_project(finding)
        issue = jira_get_issue(project, j_issue)
        return issue.fields.status


# Logs the error to the alerts table, which appears in the notification toolbar
def log_jira_generic_alert(title, description):
    create_notification(
        event="jira_update",
        title=title,
        description=description,
        icon="bullseye",
        source="JIRA",
    )


# Logs the error to the alerts table, which appears in the notification toolbar
def log_jira_alert(error, finding):
    prod_name = finding.test.engagement.product.name if finding else "unknown"

    create_notification(
        event="jira_update",
        title="Error pushing to JIRA " + "(" + truncate_with_dots(prod_name, 25) + ")",
        description="Finding: "
        + str(finding.id if finding else "unknown")
        + ", "
        + error,
        url=reverse("view_finding", args=(finding.id,)) if finding else None,
        icon="bullseye",
        source="Push to JIRA",
        finding=finding,
    )


# Displays an alert for Jira notifications
def log_jira_message(text, finding):
    create_notification(
        event="jira_update",
        title="Pushing to JIRA: ",
        description=text + " Finding: " + str(finding.id),
        url=reverse("view_finding", args=(finding.id,)),
        icon="bullseye",
        source="JIRA",
        finding=finding,
    )


def get_labels(find):
    # Update Label with system setttings label
    labels = []
    system_settings = System_Settings.objects.get()
    system_labels = system_settings.jira_labels
    if system_labels is None:
        return
    else:
        system_labels = system_labels.split()
    if len(system_labels) > 0:
        for system_label in system_labels:
            labels.append(system_label)
    # Update the label with the product name (underscore)
    prod_name = find.test.engagement.product.name.replace(" ", "_")
    labels.append(prod_name)
    return labels


def jira_description(find):
    template = "issue-trackers/jira-description.tpl"
    kwargs = {}
    kwargs["finding"] = find
    kwargs["jira_instance"] = get_jira_instance(find)
    return render_to_string(template, kwargs)


def push_to_jira(obj):
    if isinstance(obj, Finding):
        finding = obj
        if finding.has_jira_issue:
            return update_jira_issue(finding)
        else:
            return add_jira_issue(finding)

    elif isinstance(obj, Engagement):
        engagement = obj
        if engagement.has_jira_issue:
            return update_epic(engagement)
        else:
            return add_epic(engagement)

    else:
        logger.error(
            "unsupported object passed to push_to_jira: %s %i %s",
            obj.__name__,
            obj.id,
            obj,
        )


@dojo_model_to_id
@dojo_async_task
@task
@dojo_model_from_id
def add_jira_issue(find):
    logger.info("trying to create a new jira issue for %d:%s", find.id, find.title)

    if not is_jira_enabled():
        return

    if not is_jira_configured_and_enabled(find):
        logger.error(
            "Finding {} cannot be pushed to JIRA as there is no JIRA configuration for this product.".format(
                find.id
            )
        )
        log_jira_alert(
            "Finding cannot be pushed to JIRA as there is no JIRA configuration for this product.",
            find,
        )
        return

    jira_minimum_threshold = None
    if System_Settings.objects.get().jira_minimum_severity:
        jira_minimum_threshold = Finding.get_number_severity(
            System_Settings.objects.get().jira_minimum_severity
        )

    jira_project = get_jira_project(find)
    jira_instance = get_jira_instance(find)

    if "Active" in find.status() and "Verified" in find.status():
        if (
            jira_minimum_threshold
            and jira_minimum_threshold > Finding.get_number_severity(find.severity)
        ):
            log_jira_alert("Finding below the minimum JIRA severity threshold.", find)
            logger.warn(
                "Finding {} is below the minimum JIRA severity threshold.".format(
                    find.id
                )
            )
            logger.warn("The JIRA issue will NOT be created.")
            return

        logger.debug(
            "Trying to create a new JIRA issue for finding {}...".format(find.id)
        )
        meta = None
        try:
            JIRAError.log_to_tempfile = False
            jira = get_jira_connection(jira_instance)

            fields = {
                "project": {"key": jira_project.project_key},
                "summary": find.title,
                "description": jira_description(find),
                "issuetype": {"name": jira_instance.default_issue_type},
            }

            if jira_project.component:
                fields["components"] = [
                    {"name": jira_project.component},
                ]

            # populate duedate field, but only if it's available for this project + issuetype
            if not meta:
                meta = get_jira_meta(jira, jira_project)

            epic_name_field = get_epic_name_field_name(jira_instance)
            if epic_name_field in meta["projects"][0]["issuetypes"][0]["fields"]:
                # epic name is present in this issuetype
                # epic name is always mandatory in jira, so we populate it
                fields[epic_name_field] = fields["summary"]

            if "priority" in meta["projects"][0]["issuetypes"][0]["fields"]:
                fields["priority"] = {"name": jira_instance.get_priority(find.severity)}

            labels = get_labels(find)
            if labels:
                if "labels" in meta["projects"][0]["issuetypes"][0]["fields"]:
                    fields["labels"] = labels

            if System_Settings.objects.get().enable_finding_sla:

                if "duedate" in meta["projects"][0]["issuetypes"][0]["fields"]:
                    # jira wants YYYY-MM-DD
                    duedate = find.sla_deadline()
                    if duedate:
                        fields["duedate"] = duedate.strftime("%Y-%m-%d")

            if len(find.endpoints.all()) > 0:
                if not meta:
                    meta = get_jira_meta(jira, jira_project)

                if "environment" in meta["projects"][0]["issuetypes"][0]["fields"]:
                    environment = "\n".join(
                        [str(endpoint) for endpoint in find.endpoints.all()]
                    )
                    fields["environment"] = environment

            logger.debug("sending fields to JIRA: %s", fields)

            new_issue = jira.create_issue(fields)

            j_issue = JIRA_Issue(
                jira_id=new_issue.id,
                jira_key=new_issue.key,
                finding=find,
                jira_project=jira_project,
            )
            j_issue.jira_creation = timezone.now()
            j_issue.jira_change = timezone.now()
            j_issue.save()
            issue = jira.issue(new_issue.id)

            find.save(
                push_to_jira=False, dedupe_option=False, issue_updater_option=False
            )

            # Upload dojo finding screenshots to Jira
            for pic in find.images.all():
                jira_attachment(
                    find, jira, issue, settings.MEDIA_ROOT + pic.image_large.name
                )

                # if jira_project.enable_engagement_epic_mapping:
                #      epic = get_jira_issue(eng)
                #      issue_list = [j_issue.jira_id,]
                #      jira.add_jira_issues_to_epic(epic_id=epic.jira_id, issue_keys=[str(j_issue.jira_id)], ignore_epics=True)

            return True
        except JIRAError as e:
            logger.exception(e)
            logger.error(
                "jira_meta for project: %s and url: %s meta: %s",
                jira_project.project_key,
                jira_project.jira_instance.url,
                json.dumps(meta, indent=4),
            )  # this is None safe
            log_jira_alert(e.text, find)
            return False
    else:
        log_jira_alert(
            "A Finding needs to be both Active and Verified to be pushed to JIRA.", find
        )
        logger.warning(
            "A Finding needs to be both Active and Verified to be pushed to JIRA: %s",
            find,
        )
        return False


@dojo_model_to_id
@dojo_async_task
@task
@dojo_model_from_id
def update_jira_issue(find):
    logger.info("trying to update a linked jira issue for %d:%s", find.id, find.title)

    if not is_jira_enabled():
        return False

    jira_project = get_jira_project(find)
    jira_instance = get_jira_instance(find)

    if not jira_project:
        logger.error(
            "Finding {} cannot be pushed to JIRA as there is no JIRA configuration for this product.".format(
                find.id
            )
        )
        log_jira_alert(
            "Finding cannot be pushed to JIRA as there is no JIRA configuration for this product.",
            find,
        )
        return False

    j_issue = find.jira_issue
    meta = None
    try:
        JIRAError.log_to_tempfile = False
        jira = get_jira_connection(jira_instance)

        issue = jira.issue(j_issue.jira_id)

        fields = {}
        # Only update the component if it didn't exist earlier in Jira, this is to avoid assigning multiple components to an item
        if issue.fields.components:
            log_jira_alert(
                "Component not updated, exists in Jira already. Update from Jira instead.",
                find,
            )
        elif jira_project.component:
            # Add component to the Jira issue
            component = [
                {"name": jira_project.component},
            ]
            fields = {"components": component}

        if not meta:
            meta = get_jira_meta(jira, jira_project)

        labels = get_labels(find)
        if labels:
            if "labels" in meta["projects"][0]["issuetypes"][0]["fields"]:
                fields["labels"] = labels

        if len(find.endpoints.all()) > 0:
            if "environment" in meta["projects"][0]["issuetypes"][0]["fields"]:
                environment = "\n".join(
                    [str(endpoint) for endpoint in find.endpoints.all()]
                )
                fields["environment"] = environment

        # Upload dojo finding screenshots to Jira
        for pic in find.images.all():
            jira_attachment(
                find, jira, issue, settings.MEDIA_ROOT + pic.image_large.name
            )

        logger.debug("sending fields to JIRA: %s", fields)

        issue.update(
            summary=find.title,
            description=jira_description(find),
            priority={"name": jira_instance.get_priority(find.severity)},
            fields=fields,
        )

        status_list = find.status()
        if any(item in status_list for item in OPEN_STATUS):
            logger.debug("Transitioning Jira issue to Active")
            jira_change_resolution_id(jira, issue, jira_instance.open_status_key)

        if any(item in status_list for item in RESOLVED_STATUS):
            logger.debug("Transitioning Jira issue to Resolved")
            jira_change_resolution_id(jira, issue, jira_instance.close_status_key)

        find.jira_issue.jira_change = timezone.now()
        find.jira_issue.save()
        find.save(push_to_jira=False, dedupe_option=False, issue_updater_option=False)
        return True

    except JIRAError as e:
        logger.exception(e)
        logger.error(
            "jira_meta for project: %s and url: %s meta: %s",
            jira_project.project_key,
            jira_project.jira_instance.url,
            json.dumps(meta, indent=4),
        )  # this is None safe
        log_jira_alert(e.text, find)
        return False


# gets the metadata for the default issue type in this jira project
def get_jira_meta(jira, jira_project):
    meta = jira.createmeta(
        projectKeys=jira_project.project_key,
        issuetypeNames=jira_project.jira_instance.default_issue_type,
        expand="projects.issuetypes.fields",
    )

    meta_data_error = False
    if len(meta["projects"]) == 0:
        # non-existent project, or no permissions
        # [09/Nov/2020 21:04:22] DEBUG [dojo.jira_link.helper:595] get_jira_meta: {
        #     "expand": "projects",
        #     "projects": []
        # }
        meta_data_error = True
        message = (
            "unable to retrieve metadata from JIRA %s for project %s. Invalid project key or no permissions to this project?"
            % (jira_project.jira_instance, jira_project.project_key)
        )

    elif len(meta["projects"][0]["issuetypes"]) == 0:
        # default issue type doesn't exist in project
        # [09/Nov/2020 21:09:03] DEBUG [dojo.jira_link.helper:595] get_jira_meta: {
        #     "expand": "projects",
        #     "projects": [
        #         {
        #             "expand": "issuetypes",
        #             "self": "https://jira-uat.com/rest/api/2/project/1212",
        #             "id": "1212",
        #             "key": "ISO",
        #             "name": "ISO ISMS",
        #             "avatarUrls": {
        #                 "48x48": "https://jira-uat.com/secure/projectavatar?pid=14431&avatarId=17200",
        #                 "24x24": "https://jira-uat.com/secure/projectavatar?size=small&pid=14431&avatarId=17200",
        #                 "16x16": "https://jira-uat.com/secure/projectavatar?size=xsmall&pid=14431&avatarId=17200",
        #                 "32x32": "https://jira-uat.com/secure/projectavatar?size=medium&pid=14431&avatarId=17200"
        #             },
        #             "issuetypes": []
        #         }
        #     ]
        # }
        meta_data_error = True
        message = (
            "unable to retrieve metadata from JIRA %s for issuetype %s in project %s. Invalid default issue type configured in Defect Dojo?"
            % (
                jira_project.jira_instance,
                jira_project.jira_instance.default_issue_type,
                jira_project.project_key,
            )
        )

    if meta_data_error:
        logger.warn(message)
        logger.warn(
            "get_jira_meta: %s", json.dumps(meta, indent=4)
        )  # this is None safe

        add_error_message_to_response(message)

        raise JIRAError(text=message)
    else:
        return meta


def is_jira_project_valid(jira_project):
    try:
        meta = get_jira_meta(get_jira_connection(jira_project), jira_project)
        return True
    except JIRAError as e:
        logger.debug(
            "invalid JIRA Project Config, can" "t retrieve metadata for: " "%s" "",
            jira_project,
        )
        return False


def jira_attachment(finding, jira, issue, file, jira_filename=None):
    basename = file
    if jira_filename is None:
        basename = os.path.basename(file)

    # Check to see if the file has been uploaded to Jira
    # TODO: JIRA: check for local existince of attachment as it currently crashes if local attachment doesn't exist
    if jira_check_attachment(issue, basename) is False:
        try:
            if jira_filename is not None:
                attachment = io.StringIO()
                attachment.write(jira_filename)
                jira.add_attachment(
                    issue=issue, attachment=attachment, filename=jira_filename
                )
            else:
                # read and upload a file
                with open(file, "rb") as f:
                    jira.add_attachment(issue=issue, attachment=f)
            return True
        except JIRAError as e:
            logger.exception(e)
            log_jira_alert("Attachment: " + e.text, finding)
            return False


def jira_check_attachment(issue, source_file_name):
    file_exists = False
    for attachment in issue.fields.attachment:
        filename = attachment.filename

        if filename == source_file_name:
            file_exists = True
            break

    return file_exists


@dojo_model_to_id
@dojo_async_task
@task
@dojo_model_from_id(model=Engagement)
def close_epic(eng, push_to_jira):
    engagement = eng
    if not is_jira_enabled():
        return False

    if not is_jira_configured_and_enabled(engagement):
        return False

    jira_project = get_jira_project(engagement)
    jira_instance = get_jira_instance(engagement)
    if jira_project.enable_engagement_epic_mapping:
        if push_to_jira:
            try:
                jissue = get_jira_issue(eng)
                if jissue is None:
                    logger.warn("JIRA close epic failed: no issue found")
                    return False

                req_url = (
                    jira_instance.url
                    + "/rest/api/latest/issue/"
                    + jissue.jira_id
                    + "/transitions"
                )
                json_data = {"transition": {"id": jira_instance.close_status_key}}
                r = requests.post(
                    url=req_url,
                    auth=HTTPBasicAuth(jira_instance.username, jira_instance.password),
                    json=json_data,
                )
                if r.status_code != 204:
                    logger.warn("JIRA close epic failed with error: {}".format(r.text))
                    return False
                return True
            except JIRAError as e:
                logger.exception(e)
                log_jira_generic_alert("Jira Engagement/Epic Close Error", str(e))
                return False
    else:
        add_error_message_to_response(
            "Push to JIRA for Epic skipped because enable_engagement_epic_mapping is not checked for this engagement"
        )
        return False


@dojo_model_to_id
@dojo_async_task
@task
@dojo_model_from_id(model=Engagement)
def update_epic(engagement):
    logger.info("trying to update jira EPIC for %d:%s", engagement.id, engagement.name)

    if not is_jira_configured_and_enabled(engagement):
        return False

    logger.debug("config found")

    jira_project = get_jira_project(engagement)
    jira_instance = get_jira_instance(engagement)
    if jira_project.enable_engagement_epic_mapping:
        try:
            jira = get_jira_connection(jira_instance)
            j_issue = get_jira_issue(engagement)
            issue = jira.issue(j_issue.jira_id)
            issue.update(summary=engagement.name, description=engagement.name)
            return True
        except JIRAError as e:
            logger.exception(e)
            log_jira_generic_alert("Jira Engagement/Epic Update Error", str(e))
            return False
    else:
        add_error_message_to_response(
            "Push to JIRA for Epic skipped because enable_engagement_epic_mapping is not checked for this engagement"
        )

        return False


@dojo_model_to_id
@dojo_async_task
@task
@dojo_model_from_id(model=Engagement)
def add_epic(engagement):
    logger.info(
        "trying to create a new jira EPIC for %d:%s", engagement.id, engagement.name
    )

    if not is_jira_configured_and_enabled(engagement):
        return False

    logger.debug("config found")

    jira_project = get_jira_project(engagement)
    jira_instance = get_jira_instance(engagement)
    if jira_project.enable_engagement_epic_mapping:
        issue_dict = {
            "project": {"key": jira_project.project_key},
            "summary": engagement.name,
            "description": engagement.name,
            "issuetype": {"name": "Epic"},
            get_epic_name_field_name(jira_instance): engagement.name,
        }
        try:
            jira = get_jira_connection(jira_instance)
            logger.debug("add_epic: %s", issue_dict)
            new_issue = jira.create_issue(fields=issue_dict)
            j_issue = JIRA_Issue(
                jira_id=new_issue.id,
                jira_key=new_issue.key,
                engagement=engagement,
                jira_project=jira_project,
            )
            j_issue.save()
            return True
        except JIRAError as e:
            # should we try to parse the errors as JIRA is very strange in how it responds.
            # for example a non existent project_key leads to "project key is required" which sounds like something is missing
            # but it's just a non-existent project (or maybe a project for which the account has no create permission?)
            #
            # {"errorMessages":[],"errors":{"project":"project is required"}}
            logger.exception(e)
            error = str(e)
            message = ""
            if "customfield" in error:
                message = (
                    "The 'Epic name id' in your DefectDojo Jira Configuration does not appear to be correct. Please visit, "
                    + jira_instance.url
                    + "/rest/api/2/field and search for Epic Name. Copy the number out of cf[number] and place in your DefectDojo settings for Jira and try again. For example, if your results are cf[100001] then copy 100001 and place it in 'Epic name id'. (Your Epic Id will be different.) \n\n"
                )

            log_jira_generic_alert(
                "Jira Engagement/Epic Creation Error", message + error
            )
            return False
    else:
        add_error_message_to_response(
            "Push to JIRA for Epic skipped because enable_engagement_epic_mapping is not checked for this engagement"
        )
        return False


def jira_get_issue(jira_project, issue_key):
    try:
        jira_instance = jira_project.jira_instance
        jira = get_jira_connection(jira_instance)
        issue = jira.issue(issue_key)

        return issue
    except JIRAError as jira_error:
        logger.debug("error retrieving jira issue " + issue_key + " " + str(jira_error))
        logger.exception(jira_error)
        log_jira_generic_alert(
            "error retrieving jira issue " + issue_key, str(jira_error)
        )
        return None


@dojo_model_to_id(parameter=1)
@dojo_model_to_id
@dojo_async_task
@task
@dojo_model_from_id(model=Notes, parameter=1)
@dojo_model_from_id
def add_comment(find, note, force_push=False):
    if not is_jira_configured_and_enabled(find):
        return False

    logger.debug(
        "trying to add a comment to a linked jira issue for: %d:%s", find.id, find.title
    )
    if not note.private:
        jira_project = get_jira_project(find)
        jira_instance = get_jira_instance(find)

        if jira_project.push_notes or force_push is True:
            try:
                jira = get_jira_connection(jira_instance)
                j_issue = find.jira_issue
                jira.add_comment(
                    j_issue.jira_id,
                    "(%s): %s"
                    % (
                        note.author.get_full_name()
                        if note.author.get_full_name()
                        else note.author.username,
                        note.entry,
                    ),
                )
                return True
            except JIRAError as e:
                log_jira_generic_alert("Jira Add Comment Error", str(e))
                return False


def add_simple_jira_comment(jira_instance, jira_issue, comment):
    try:
        jira = get_jira_connection(jira_instance)

        jira.add_comment(jira_issue.jira_id, comment)
        return True
    except Exception as e:
        log_jira_generic_alert("Jira Add Comment Error", str(e))
        return False


def finding_link_jira(request, finding, new_jira_issue_key):
    logger.debug(
        "linking existing jira issue %s for finding %i", new_jira_issue_key, finding.id
    )

    existing_jira_issue = jira_get_issue(get_jira_project(finding), new_jira_issue_key)

    jira_project = get_jira_project(finding)

    if not existing_jira_issue:
        raise ValueError(
            "JIRA issue not found or cannot be retrieved: " + new_jira_issue_key
        )

    jira_issue = JIRA_Issue(
        jira_id=existing_jira_issue.id,
        jira_key=existing_jira_issue.key,
        finding=finding,
        jira_project=jira_project,
    )

    jira_issue.jira_key = new_jira_issue_key
    # jira timestampe are in iso format: 'updated': '2020-07-17T09:49:51.447+0200'
    # seems to be a pain to parse these in python < 3.7, so for now just record the curent time as
    # as the timestamp the jira link was created / updated in DD
    jira_issue.jira_creation = timezone.now()
    jira_issue.jira_change = timezone.now()

    jira_issue.save()

    finding.save(push_to_jira=False, dedupe_option=False, issue_updater_option=False)

    jira_issue_url = get_jira_url(finding)

    return True


def finding_unlink_jira(request, finding):
    logger.debug(
        "removing linked jira issue %s for finding %i",
        finding.jira_issue.jira_key,
        finding.id,
    )
    finding.jira_issue.delete()
    finding.save(push_to_jira=False, dedupe_option=False, issue_updater_option=False)

    jira_issue_url = get_jira_url(finding)

    return True


# return True if no errors
def process_jira_project_form(request, instance=None, product=None, engagement=None):
    if not get_system_setting("enable_jira"):
        return True, None

    error = False
    jira_project = None
    # supply empty instance to form so it has default values needed to make has_changed() work
    # jform = JIRAProjectForm(request.POST, instance=instance if instance else JIRA_Project(), product=product)
    jform = JIRAProjectForm(
        request.POST, instance=instance, product=product, engagement=engagement
    )
    # logging has_changed because it sometimes doesn't do what we expect
    logger.debug("jform has changed: %s", str(jform.has_changed()))

    if jform.has_changed():  # if no data was changed, no need to do anything!
        logger.debug("jform changed_data: %s", jform.changed_data)
        logger.debug("jform: %s", vars(jform))
        if jform.is_valid():
            try:
                jira_project = jform.save(commit=False)
                # could be a new jira_project, so set product_id
                if engagement:
                    jira_project.engagement_id = engagement.id
                elif product:
                    jira_project.product_id = product.id

                if not jira_project.product_id and not jira_project.engagement_id:
                    raise ValueError(
                        "encountered JIRA_Project without product_id and without engagement_id"
                    )

                # only check jira project if form is sufficiently populated
                if jira_project.jira_instance and jira_project.project_key:
                    # is_jira_project_valid already adds messages if not a valid jira project
                    if not is_jira_project_valid(jira_project):
                        logger.debug(
                            "unable to retrieve jira project from jira instance, invalid?!"
                        )
                        error = True
                    else:
                        jira_project.save()

                        messages.add_message(
                            request,
                            messages.SUCCESS,
                            "JIRA Project config stored successfully.",
                            extra_tags="alert-success",
                        )
                        error = False
                        logger.debug("stored JIRA_Project succesfully")
            except Exception as e:
                error = True
                logger.exception(e)
                pass
        else:
            logger.debug(jform.errors)
            error = True

        if error:
            messages.add_message(
                request,
                messages.ERROR,
                "JIRA Project config not stored due to errors.",
                extra_tags="alert-danger",
            )
    return not error, jform


# return True if no errors
def process_jira_epic_form(request, engagement=None):
    if not get_system_setting("enable_jira"):
        return True, None

    logger.debug(
        "checking jira epic form for engagement: %i:%s",
        engagement.id if engagement else 0,
        engagement,
    )
    # push epic
    error = False
    jira_epic_form = JIRAEngagementForm(request.POST, instance=engagement)

    jira_project = get_jira_project(
        engagement
    )  # uses inheritance to get from product if needed

    if jira_project:
        if jira_epic_form.is_valid():
            if jira_epic_form.cleaned_data.get("push_to_jira"):
                logger.debug("pushing engagement to JIRA")
                if push_to_jira(engagement):
                    messages.add_message(
                        request,
                        messages.SUCCESS,
                        "Push to JIRA for Epic queued succesfully, check alerts on the top right for errors",
                        extra_tags="alert-success",
                    )
                else:
                    error = True

                    messages.add_message(
                        request,
                        messages.ERROR,
                        "Push to JIRA for Epic failed, check alerts on the top right for errors",
                        extra_tags="alert-danger",
                    )
        else:
            logger.debug("invalid jira epic form")
    else:
        logger.debug("no jira_project for this engagement, skipping epic push")

    return not error, jira_epic_form


# some character will mess with JIRA formatting, for example when constructing a link:
# [name|url]. if name contains a '|' is will break it
# so [%s|%s] % (escape_for_jira(name), url)
def escape_for_jira(text):
    return text.replace("|", "%7D")
