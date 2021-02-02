from vcr_unittest import VCRTestCase
from dojo.models import (
    User,
    Endpoint,
    Notes,
    Finding,
    Endpoint_Status,
    Test,
    JIRA_Issue,
    JIRA_Project,
    Product,
)
from dojo.models import System_Settings, Engagement
from django.urls import reverse
from rest_framework.test import APITestCase, APIClient
from rest_framework.authtoken.models import Token
import json
from django.test import TestCase
from itertools import chain
from dojo.jira_link import helper as jira_helper
import logging
import pprint
import copy
from django.utils.http import urlencode

logger = logging.getLogger(__name__)


class DojoTestUtilsMixin(object):
    def get_test_admin(self, *args, **kwargs):
        return User.objects.get(username="admin")

    def system_settings(
        self,
        enable_jira=False,
        enable_jira_web_hook=False,
        disable_jira_webhook_secret=False,
        jira_webhook_secret=None,
    ):
        ss = System_Settings.objects.get()
        ss.enable_jira = enable_jira
        ss.enable_jira_web_hook = enable_jira_web_hook
        ss.disable_jira_webhook_secret = disable_jira_webhook_secret
        ss.jira_webhook_secret = jira_webhook_secret
        ss.save()

    def create_product(
        self, name, *args, description="dummy description", prod_type=None, **kwargs
    ):
        if not prod_type:
            prod_type = Product_Type.objects.first()
        product = Product(name=name, description=description, prod_type=prod_type)
        product.save()

    def create_engagement(self, name, product, *args, description=None, **kwargs):
        engagement = Engagement(name=name, description=description, product=product)
        engagement.save()

    def get_test(self, id):
        return Test.objects.get(id=id)

    def get_engagement(self, id):
        return Engagement.objects.get(id=id)

    def assert_jira_issue_count_in_test(self, test_id, count):
        test = self.get_test(test_id)
        jira_issues = JIRA_Issue.objects.filter(finding__in=test.finding_set.all())
        self.assertEqual(count, len(jira_issues))

    def model_to_dict(self, instance):
        opts = instance._meta
        data = {}
        for f in chain(opts.concrete_fields, opts.private_fields):
            data[f.name] = f.value_from_object(instance)
        for f in opts.many_to_many:
            data[f.name] = [i.id for i in f.value_from_object(instance)]
        return data

    def log_model_instance(self, instance):
        logger.debug(pprint.pprint(self.model_to_dict(instance)))

    def log_model_instances(self, instances):
        for instance in instances:
            self.log_model_instance(instance)

    def db_finding_count(self):
        return Finding.objects.all().count()

    def db_endpoint_count(self):
        return Endpoint.objects.all().count()

    def db_endpoint_status_count(self, mitigated=None):
        eps = Endpoint_Status.objects.all()
        if mitigated is not None:
            eps = eps.filter(mitigated=mitigated)
        return eps.count()

    def db_notes_count(self):
        return Notes.objects.all().count()

    def get_new_product_with_jira_project_data(self):
        return {
            "name": "new product",
            "description": "new description",
            "prod_type": 1,
            "jira-project-form-project_key": "IFFFNEW",
            "jira-project-form-jira_instance": 2,
            "jira-project-form-enable_engagement_epic_mapping": "on",
            "jira-project-form-push_notes": "on",
            "jira-project-form-product_jira_sla_notification": "on",
        }

    def get_new_product_without_jira_project_data(self):
        return {
            "name": "new product",
            "description": "new description",
            "prod_type": 1,
            # 'project_key': 'IFFF',
            # 'jira_instance': 2,
            # 'enable_engagement_epic_mapping': 'on',
            # 'push_notes': 'on',
            "jira-project-form-product_jira_sla_notification": "on",  # default is true so we have to supply to make has_changed() work OK
        }

    def get_product_with_jira_project_data(self, product):
        return {
            "name": product.name,
            "description": product.description,
            "prod_type": product.prod_type.id,
            "jira-project-form-project_key": "IFFF",
            "jira-project-form-jira_instance": 2,
            "jira-project-form-enable_engagement_epic_mapping": "on",
            "jira-project-form-push_notes": "on",
            "jira-project-form-product_jira_sla_notification": "on",
        }

    def get_product_with_jira_project_data2(self, product):
        return {
            "name": product.name,
            "description": product.description,
            "prod_type": product.prod_type.id,
            "jira-project-form-project_key": "IFFF2",
            "jira-project-form-jira_instance": 2,
            "jira-project-form-enable_engagement_epic_mapping": "on",
            "jira-project-form-push_notes": "on",
            "jira-project-form-product_jira_sla_notification": "on",
        }

    def get_product_with_empty_jira_project_data(self, product):
        return {
            "name": product.name,
            "description": product.description,
            "prod_type": product.prod_type.id,
            # 'project_key': 'IFFF',
            # 'jira_instance': 2,
            # 'enable_engagement_epic_mapping': 'on',
            # 'push_notes': 'on',
            "jira-project-form-product_jira_sla_notification": "on",  # default is true so we have to supply to make has_changed() work OK
        }

    def get_expected_redirect_product(self, product):
        return "/product/%i" % product.id

    def add_product_jira(self, data, expect_redirect_to=None, expect_200=False):
        response = self.client.get(reverse("new_product"))

        logger.debug("before: JIRA_Project last")
        self.log_model_instance(JIRA_Project.objects.last())

        if not expect_redirect_to and not expect_200:
            expect_redirect_to = "/product/%i"

        response = self.client.post(
            reverse("new_product"),
            urlencode(data),
            content_type="application/x-www-form-urlencoded",
        )

        logger.debug("after: JIRA_Project last")
        self.log_model_instance(JIRA_Project.objects.last())

        product = None
        if expect_200:
            self.assertEqual(response.status_code, 200)
        elif expect_redirect_to:
            self.assertEqual(response.status_code, 302)
            # print('url: ' + response.url)
            try:
                product = Product.objects.get(id=response.url.split("/")[-1])
            except:
                try:
                    product = Product.objects.get(id=response.url.split("/")[-2])
                except:
                    raise ValueError(
                        "error parsing id from redirect uri: " + response.url
                    )
            self.assertTrue(response.url == (expect_redirect_to % product.id))
        else:
            self.assertEqual(response.status_code, 200)

        return product

    def db_jira_project_count(self):
        return JIRA_Project.objects.all().count()

    def set_jira_push_all_issues(self, engagement_or_product):
        jira_project = jira_helper.get_jira_project(engagement_or_product)
        jira_project.push_all_issues = True
        jira_project.save()

    def add_product_jira_with_data(
        self,
        data,
        expected_delta_jira_project_db,
        expect_redirect_to=None,
        expect_200=False,
    ):
        jira_project_count_before = self.db_jira_project_count()

        response = self.add_product_jira(
            data, expect_redirect_to=expect_redirect_to, expect_200=expect_200
        )

        self.assertEqual(
            self.db_jira_project_count(),
            jira_project_count_before + expected_delta_jira_project_db,
        )

        return response

    def add_product_with_jira_project(
        self,
        expected_delta_jira_project_db=0,
        expect_redirect_to=None,
        expect_200=False,
    ):
        return self.add_product_jira_with_data(
            self.get_new_product_with_jira_project_data(),
            expected_delta_jira_project_db,
            expect_redirect_to=expect_redirect_to,
            expect_200=expect_200,
        )

    def add_product_without_jira_project(
        self,
        expected_delta_jira_project_db=0,
        expect_redirect_to=None,
        expect_200=False,
    ):
        return self.add_product_jira_with_data(
            self.get_new_product_without_jira_project_data(),
            expected_delta_jira_project_db,
            expect_redirect_to=expect_redirect_to,
            expect_200=expect_200,
        )

    def edit_product_jira(
        self, product, data, expect_redirect_to=None, expect_200=False
    ):
        response = self.client.get(reverse("edit_product", args=(product.id,)))

        logger.debug("before: JIRA_Project last")
        self.log_model_instance(JIRA_Project.objects.last())

        response = self.client.post(
            reverse("edit_product", args=(product.id,)),
            urlencode(data),
            content_type="application/x-www-form-urlencoded",
        )
        # self.log_model_instance(product)
        logger.debug("after: JIRA_Project last")
        self.log_model_instance(JIRA_Project.objects.last())

        if expect_200:
            self.assertEqual(response.status_code, 200)
        elif expect_redirect_to:
            self.assertRedirects(response, expect_redirect_to)
        else:
            self.assertEqual(response.status_code, 200)
        return response

    def edit_jira_project_for_product_with_data(
        self,
        product,
        data,
        expected_delta_jira_project_db=0,
        expect_redirect_to=None,
        expect_200=None,
    ):
        jira_project_count_before = self.db_jira_project_count()
        # print('before: ' + str(jira_project_count_before))

        if not expect_redirect_to and not expect_200:
            expect_redirect_to = self.get_expected_redirect_product(product)

        response = self.edit_product_jira(
            product, data, expect_redirect_to=expect_redirect_to, expect_200=expect_200
        )

        # print('after: ' + str(self.db_jira_project_count()))

        self.assertEqual(
            self.db_jira_project_count(),
            jira_project_count_before + expected_delta_jira_project_db,
        )
        return response

    def edit_jira_project_for_product(
        self,
        product,
        expected_delta_jira_project_db=0,
        expect_redirect_to=None,
        expect_200=False,
    ):
        return self.edit_jira_project_for_product_with_data(
            product,
            self.get_product_with_jira_project_data(product),
            expected_delta_jira_project_db,
            expect_redirect_to=expect_redirect_to,
            expect_200=expect_200,
        )

    def edit_jira_project_for_product2(
        self,
        product,
        expected_delta_jira_project_db=0,
        expect_redirect_to=None,
        expect_200=False,
    ):
        return self.edit_jira_project_for_product_with_data(
            product,
            self.get_product_with_jira_project_data2(product),
            expected_delta_jira_project_db,
            expect_redirect_to=expect_redirect_to,
            expect_200=expect_200,
        )

    def empty_jira_project_for_product(
        self,
        product,
        expected_delta_jira_project_db=0,
        expect_redirect_to=None,
        expect_200=False,
    ):
        jira_project_count_before = self.db_jira_project_count()
        # print('before: ' + str(jira_project_count_before))

        if not expect_redirect_to and not expect_200:
            expect_redirect_to = self.get_expected_redirect_product(product)

        response = self.edit_product_jira(
            product,
            self.get_product_with_empty_jira_project_data(product),
            expect_redirect_to=expect_redirect_to,
            expect_200=expect_200,
        )

        # print('after: ' + str(self.db_jira_project_count()))

        self.assertEqual(
            self.db_jira_project_count(),
            jira_project_count_before + expected_delta_jira_project_db,
        )
        return response


class DojoTestCase(TestCase, DojoTestUtilsMixin):
    def __init__(self, *args, **kwargs):
        TestCase.__init__(self, *args, **kwargs)


class DojoAPITestCase(APITestCase, DojoTestUtilsMixin):
    def __init__(self, *args, **kwargs):
        APITestCase.__init__(self, *args, **kwargs)

    def login_as_admin(self):
        testuser = self.get_test_admin()
        token = Token.objects.get(user=testuser)
        self.client = APIClient()
        self.client.credentials(HTTP_AUTHORIZATION="Token " + token.key)

    def import_scan(self, payload):
        # logger.debug('import_scan payload %s', payload)
        response = self.client.post(reverse("importscan-list"), payload)
        # print(response.content)
        self.assertEqual(201, response.status_code, response.content[:1000])
        return json.loads(response.content)

    def reimport_scan(self, payload):
        response = self.client.post(reverse("reimportscan-list"), payload)
        # print(response.content)
        self.assertEqual(201, response.status_code, response.content[:1000])
        return json.loads(response.content)

    def get_test_api(self, test_id):
        response = self.client.get(
            reverse("test-list") + "%s/" % test_id, format="json"
        )
        self.assertEqual(200, response.status_code, response.content[:1000])
        # print('test.content: ', response.content)
        return json.loads(response.content)

    def import_scan_with_params(
        self,
        filename,
        scan_type="ZAP Scan",
        engagement=1,
        minimum_severity="Low",
        active=True,
        verified=True,
        push_to_jira=None,
        tags=None,
        close_old_findings=False,
    ):
        payload = {
            "scan_date": "2020-06-04",
            "minimum_severity": minimum_severity,
            "active": active,
            "verified": verified,
            "scan_type": scan_type,
            "file": open(filename),
            "engagement": engagement,
            "version": "1.0.1",
            "close_old_findings": close_old_findings,
        }

        if push_to_jira is not None:
            payload["push_to_jira"] = push_to_jira

        if tags is not None:
            payload["tags"] = tags

        return self.import_scan(payload)

    def reimport_scan_with_params(
        self,
        test_id,
        filename,
        scan_type="ZAP Scan",
        engagement=1,
        minimum_severity="Low",
        active=True,
        verified=True,
        push_to_jira=None,
        tags=None,
        close_old_findings=True,
    ):
        payload = {
            "test": test_id,
            "scan_date": "2020-06-04",
            "minimum_severity": minimum_severity,
            "active": active,
            "verified": verified,
            "scan_type": scan_type,
            "file": open(filename),
            "engagement": engagement,
            "version": "1.0.1",
            "close_old_findings": close_old_findings,
        }

        if push_to_jira is not None:
            payload["push_to_jira"] = push_to_jira

        if tags is not None:
            payload["tags"] = tags

        return self.reimport_scan(payload)

    def get_finding_api(self, finding_id):
        response = self.client.get(
            reverse("finding-list") + "%s/" % finding_id, format="json"
        )
        self.assertEqual(200, response.status_code, response.content[:1000])
        return response.data

    def post_new_finding_api(self, finding_details, push_to_jira=None):
        payload = copy.deepcopy(finding_details)
        if push_to_jira is not None:
            payload["push_to_jira"] = push_to_jira

        # logger.debug('posting new finding push_to_jira: %s', payload.get('push_to_jira', None))

        response = self.client.post(reverse("finding-list"), payload, format="json")
        self.assertEqual(201, response.status_code, response.content[:1000])
        return response.data

    def put_finding_api(self, finding_id, finding_details, push_to_jira=None):
        payload = copy.deepcopy(finding_details)
        if push_to_jira is not None:
            payload["push_to_jira"] = push_to_jira

        response = self.client.put(
            reverse("finding-list") + "%s/" % finding_id, payload, format="json"
        )
        self.assertEqual(200, response.status_code, response.content[:1000])
        return response.data

    def patch_finding_api(self, finding_id, finding_details, push_to_jira=None):
        payload = copy.deepcopy(finding_details)
        if push_to_jira is not None:
            payload["push_to_jira"] = push_to_jira

        response = self.client.patch(
            reverse("finding-list") + "%s/" % finding_id, payload, format="json"
        )
        self.assertEqual(200, response.status_code, response.content[:1000])
        return response.data

    def get_jira_issue_severity(self, finding_id):
        finding = Finding.objects.get(id=finding_id)
        status = jira_helper.get_jira_status(finding)
        return status

    def assert_jira_status_change(self, old_status, new_status):
        self.assertFalse(old_status == new_status)

    def assert_finding_count_json(self, count, findings_content_json):
        self.assertEqual(findings_content_json["count"], count)

    def get_test_findings_api(self, test_id, active=None, verified=None):
        payload = {"test": test_id}
        if active is not None:
            payload["active"] = active
        if verified is not None:
            payload["verified"] = verified

        response = self.client.get(reverse("finding-list"), payload, format="json")
        self.assertEqual(200, response.status_code, response.content[:1000])
        # print('findings.content: ', response.content)
        return json.loads(response.content)

    def do_finding_tags_api(self, http_method, finding_id, tags=None):
        data = None
        if tags:
            data = {"tags": tags}

        # print('data:' + str(data))

        response = http_method(
            reverse("finding-tags", args=(finding_id,)), data, format="json"
        )
        # print(vars(response))
        # print(response.content)
        self.assertEqual(200, response.status_code, response.content[:1000])
        return response

    def get_finding_tags_api(self, finding_id):
        response = self.do_finding_tags_api(self.client.get, finding_id)
        print(response.data)
        return response.data

    def get_finding_api_filter_tags(self, tags):
        response = self.client.get(
            reverse("finding-list") + "?tags=%s" % tags, format="json"
        )
        self.assertEqual(200, response.status_code, response.content[:1000])
        print(response.data)
        return response.data

    def post_finding_tags_api(self, finding_id, tags):
        response = self.do_finding_tags_api(self.client.post, finding_id, tags)
        return response.data

    def do_finding_remove_tags_api(
        self, http_method, finding_id, tags=None, expected_response_status_code=200
    ):
        data = None
        if tags:
            data = {"tags": tags}

        response = http_method(
            reverse("finding-remove-tags", args=(finding_id,)), data, format="json"
        )
        print(response)
        print(response.content)
        self.assertEqual(
            expected_response_status_code, response.status_code, response.content[:1000]
        )
        return response.data

    def put_finding_remove_tags_api(self, finding_id, tags, *args, **kwargs):
        response = self.do_finding_remove_tags_api(
            self.client.put, finding_id, tags, *args, **kwargs
        )
        return response

    def patch_finding_remove_tags_api(self, finding_id, tags, *args, **kwargs):
        response = self.do_finding_remove_tags_api(
            self.client.patch, finding_id, tags, *args, **kwargs
        )
        return response

    def do_finding_notes_api(self, http_method, finding_id, note=None):
        data = None
        if note:
            data = {"entry": note}

        print("data:" + str(data))

        response = http_method(
            reverse("finding-notes", args=(finding_id,)), data, format="json"
        )
        print(vars(response))
        print(response.content)
        self.assertEqual(200, response.status_code, response.content[:1000])
        return response

    def post_finding_notes_api(self, finding_id, note):
        response = self.do_finding_notes_api(self.client.post, finding_id, note)
        return response.data

    def log_finding_summary_json_api(self, findings_content_json=None):
        # print('summary')
        # print(findings_content_json)
        # print(findings_content_json['count'])

        if not findings_content_json or findings_content_json["count"] == 0:
            logger.debug("no findings")
        else:
            for finding in findings_content_json["results"]:
                logger.debug(
                    str(finding["id"])
                    + ": "
                    + finding["title"][:5]
                    + ":"
                    + finding["severity"]
                    + ": active: "
                    + str(finding["active"])
                    + ": verified: "
                    + str(finding["verified"])
                    + ": is_Mitigated: "
                    + str(finding["is_Mitigated"])
                    + ": notes: "
                    + str([n["id"] for n in finding["notes"]])
                    + ": endpoints: "
                    + str(finding["endpoints"])
                )

        logger.debug("endpoints")
        for ep in Endpoint.objects.all():
            logger.debug(str(ep.id) + ": " + str(ep))

        logger.debug("endpoint statuses")
        for eps in Endpoint_Status.objects.all():
            logger.debug(
                str(eps.id)
                + ": "
                + str(eps.endpoint)
                + ": "
                + str(eps.endpoint.id)
                + ": "
                + str(eps.mitigated)
            )


class DojoVCRAPITestCase(DojoAPITestCase, VCRTestCase):
    def __init__(self, *args, **kwargs):
        DojoAPITestCase.__init__(self, *args, **kwargs)
        VCRTestCase.__init__(self, *args, **kwargs)
