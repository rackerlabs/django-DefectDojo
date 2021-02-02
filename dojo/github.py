# python
import logging
import sys

# External libs
from github import Github

# Dojo related imports
from dojo.models import Engagement, Product, GITHUB_PKey, GITHUB_Issue
from django.template.loader import render_to_string

# Create global
logger = logging.getLogger(__name__)


def reopen_external_issue_github(find, note, prod, eng):

    from dojo.utils import get_system_setting

    if not get_system_setting("enable_github"):
        return

    # Check if we have github info related to the product
    if GITHUB_PKey.objects.filter(product=prod).count() == 0:
        return

    github_product = GITHUB_PKey.objects.get(product=prod)
    if github_product is None:
        logger.error("Unable to get project key")
        return

    github_conf = github_product.git_conf
    g_issue = GITHUB_Issue.objects.get(finding=find)

    try:
        g_ctx = Github(github_conf.api_key)
        repo = g_ctx.get_repo(github_product.git_project)
        issue = repo.get_issue(int(g_issue.issue_id))
    except:
        e = sys.exc_info()[0]
        logger.error("cannot update finding in github: " + e)

    logger.info("Will close github issue " + g_issue.issue_id)
    issue.edit(state="open")
    issue.create_comment(note)


def close_external_issue_github(find, note, prod, eng):

    from dojo.utils import get_system_setting

    if not get_system_setting("enable_github"):
        return

    # Check if we have github info related to the product
    if GITHUB_PKey.objects.filter(product=prod).count() == 0:
        return

    github_product = GITHUB_PKey.objects.get(product=prod)
    if github_product is None:
        logger.error("Unable to get project key")
        return

    github_conf = github_product.git_conf
    g_issue = GITHUB_Issue.objects.get(finding=find)

    try:
        g_ctx = Github(github_conf.api_key)
        repo = g_ctx.get_repo(github_product.git_project)
        issue = repo.get_issue(int(g_issue.issue_id))
    except:
        e = sys.exc_info()[0]
        logger.error("cannot update finding in github: " + e)

    logger.info("Will close github issue " + g_issue.issue_id)
    issue.edit(state="closed")
    issue.create_comment(note)


def update_external_issue_github(find, prod, eng):

    from dojo.utils import get_system_setting

    if not get_system_setting("enable_github"):
        return

    # Check if we have github info related to the product
    if GITHUB_PKey.objects.filter(product=prod).count() == 0:
        return

    github_product = GITHUB_PKey.objects.get(product=prod)
    if github_product is None:
        logger.error("Unable to get project key")
        return

    github_conf = github_product.git_conf
    g_issue = GITHUB_Issue.objects.get(finding=find)

    try:
        g_ctx = Github(github_conf.api_key)
        repo = g_ctx.get_repo(github_product.git_project)
        issue = repo.get_issue(int(g_issue.issue_id))
        issue.edit(
            title=find.title,
            body=github_body(find),
            labels=["defectdojo", "security / " + find.severity],
        )
    except:
        e = sys.exc_info()[0]
        logger.error("cannot update finding in github: " + e)


def add_external_issue_github(find, prod, eng):

    from dojo.utils import get_system_setting

    if not get_system_setting("enable_github"):
        return

    # Check if we have github info related to the product
    if GITHUB_PKey.objects.filter(product=prod).count() == 0:
        logger.debug("cannot find github conf for this product")
        return

    github_pkey = GITHUB_PKey.objects.get(product=prod)
    if github_pkey is None:
        logger.error("Unable to get product conf")
        return

    github_conf = github_pkey.git_conf

    # We push only active and verified issues
    if "Active" in find.status() and "Verified" in find.status():
        eng = Engagement.objects.get(test=find.test)
        prod = Product.objects.get(engagement=eng)
        github_product_key = GITHUB_PKey.objects.get(product=prod)
        logger.info(
            "Create issue with github profile: "
            + str(github_conf)
            + " on product: "
            + str(github_product_key)
        )

        try:
            g = Github(github_conf.api_key)
            user = g.get_user()
            logger.debug("logged in with github user: " + user.login)
            logger.debug("Look for project: " + github_product_key.git_project)
            repo = g.get_repo(github_product_key.git_project)
            logger.debug("Found repo: " + str(repo.url))
            issue = repo.create_issue(
                title=find.title,
                body=github_body(find),
                labels=["defectdojo", "security / " + find.severity],
            )
            logger.debug("created issue: " + str(issue.html_url))
            g_issue = GITHUB_Issue(
                issue_id=issue.number, issue_url=issue.html_url, finding=find
            )
            g_issue.save()
        except:
            e = sys.exc_info()[0]
            logger.error("cannot create finding in github: " + e)


def github_body(find):
    template = "issue-trackers/github-body.tpl"
    kwargs = {}
    kwargs["finding"] = find
    return render_to_string(template, kwargs)
