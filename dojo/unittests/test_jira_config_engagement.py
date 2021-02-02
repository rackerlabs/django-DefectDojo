from django.urls import reverse
from .dojo_test_case import DojoTestCase
from dojo.models import Engagement, JIRA_Project, Product
from django.utils.http import urlencode
from unittest.mock import patch
from dojo.jira_link import helper as jira_helper

# from unittest import skip
import logging

logger = logging.getLogger(__name__)


class JIRAConfigEngagementTest(DojoTestCase):
    fixtures = ["dojo_testdata.json"]

    product_id = 999

    def __init__(self, *args, **kwargs):
        DojoTestCase.__init__(self, *args, **kwargs)

    def setUp(self):
        self.system_settings(enable_jira=True)
        self.client.force_login(self.get_test_admin())
        # product 3 has no jira project config, double check to make sure someone didn't molest the fixture
        # running this in __init__ throws database access denied error
        self.product_id = 3
        product = Product.objects.get(id=self.product_id)
        self.assertIsNone(jira_helper.get_jira_project(product))

    def get_new_engagement_with_jira_project_data(self):
        return {
            "name": "new engagement",
            "description": "new description",
            "lead": 1,
            "product": self.product_id,
            "target_start": "2070-11-27",
            "target_end": "2070-12-04",
            "status": "Not Started",
            "jira-project-form-jira_instance": 2,
            "jira-project-form-project_key": "IUNSEC",
            "jira-project-form-product_jira_sla_notification": "on",
        }

    def get_new_engagement_without_jira_project_data(self):
        return {
            "name": "new engagement",
            "description": "new description",
            "lead": 1,
            "product": self.product_id,
            "target_start": "2070-11-27",
            "target_end": "2070-12-04",
            "status": "Not Started",
            # 'project_key': 'IFFF',
            # 'jira_instance': 2,
            # 'enable_engagement_epic_mapping': 'on',
            # 'push_notes': 'on',
            "jira-project-form-product_jira_sla_notification": "on",  # default is true so we have to supply to make has_changed() work OK
        }

    def get_engagement_with_jira_project_data(self, engagement):
        return {
            "name": engagement.name,
            "description": engagement.description,
            "lead": 1,
            "product": engagement.product.id,
            "target_start": "2070-11-27",
            "target_end": "2070-12-04",
            "status": "Not Started",
            "jira-project-form-jira_instance": 2,
            "jira-project-form-project_key": "ISEC",
            "jira-project-form-product_jira_sla_notification": "on",
        }

    def get_engagement_with_jira_project_data2(self, engagement):
        return {
            "name": engagement.name,
            "description": engagement.description,
            "lead": 1,
            "product": engagement.product.id,
            "target_start": "2070-11-27",
            "target_end": "2070-12-04",
            "status": "Not Started",
            "jira-project-form-jira_instance": 2,
            "jira-project-form-project_key": "ISEC2",
            "jira-project-form-product_jira_sla_notification": "on",
        }

    def get_engagement_with_empty_jira_project_data(self, engagement):
        return {
            "name": engagement.name,
            "description": engagement.description,
            "lead": 1,
            "product": engagement.product.id,
            "target_start": "2070-11-27",
            "target_end": "2070-12-04",
            "status": "Not Started",
            # 'project_key': 'IFFF',
            # 'jira_instance': 2,
            # 'enable_engagement_epic_mapping': 'on',
            # 'push_notes': 'on',
            "jira-project-form-product_jira_sla_notification": "on",  # default is true so we have to supply to make has_changed() work OK
        }

    def get_expected_redirect_engagement(self, engagement):
        return "/engagement/%i" % engagement.id

    def get_expected_redirect_edit_engagement(self, engagement):
        return "/engagement/edit/%i" % engagement.id

    def add_engagement_jira(self, data, expect_redirect_to=None, expect_200=False):
        response = self.client.get(reverse("new_eng_for_prod", args=(self.product_id,)))

        logger.debug("before: JIRA_Project last")
        self.log_model_instance(JIRA_Project.objects.last())

        print("data: " + str(data))

        if not expect_redirect_to and not expect_200:
            expect_redirect_to = "/engagement/%i"

        response = self.client.post(
            reverse("new_eng_for_prod", args=(self.product_id,)),
            urlencode(data),
            content_type="application/x-www-form-urlencoded",
        )

        print("response: " + str(response))

        logger.debug("after: JIRA_Project last")
        self.log_model_instance(JIRA_Project.objects.last())

        # print('url: ' + response.url)

        engagement = None
        if expect_200:
            self.assertEqual(response.status_code, 200)
        elif expect_redirect_to:
            self.assertEqual(response.status_code, 302)
            # print('response: ' + response)
            print("url: " + response.url)
            try:
                engagement = Engagement.objects.get(id=response.url.split("/")[-1])
            except:
                try:
                    engagement = Engagement.objects.get(id=response.url.split("/")[-2])
                except:
                    raise ValueError(
                        "error parsing id from redirect uri: " + response.url
                    )
            self.assertTrue(response.url == (expect_redirect_to % engagement.id))
        else:
            self.assertEqual(response.status_code, 200)

        return engagement

    def add_engagement_jira_with_data(
        self,
        data,
        expected_delta_jira_project_db,
        expect_redirect_to=None,
        expect_200=False,
    ):
        jira_project_count_before = self.db_jira_project_count()

        response = self.add_engagement_jira(
            data, expect_redirect_to=expect_redirect_to, expect_200=expect_200
        )

        self.assertEqual(
            self.db_jira_project_count(),
            jira_project_count_before + expected_delta_jira_project_db,
        )

        return response

    def add_engagement_with_jira_project(
        self,
        expected_delta_jira_project_db=0,
        expect_redirect_to=None,
        expect_200=False,
    ):
        return self.add_engagement_jira_with_data(
            self.get_new_engagement_with_jira_project_data(),
            expected_delta_jira_project_db,
            expect_redirect_to=expect_redirect_to,
            expect_200=expect_200,
        )

    def add_engagement_without_jira_project(
        self,
        expected_delta_jira_project_db=0,
        expect_redirect_to=None,
        expect_200=False,
    ):
        return self.add_engagement_jira_with_data(
            self.get_new_engagement_without_jira_project_data(),
            expected_delta_jira_project_db,
            expect_redirect_to=expect_redirect_to,
            expect_200=expect_200,
        )

    def edit_engagement_jira(
        self, engagement, data, expect_redirect_to=None, expect_200=False
    ):
        response = self.client.get(reverse("edit_engagement", args=(engagement.id,)))

        logger.debug("before: JIRA_Project last")
        self.log_model_instance(JIRA_Project.objects.last())

        response = self.client.post(
            reverse("edit_engagement", args=(engagement.id,)),
            urlencode(data),
            content_type="application/x-www-form-urlencoded",
        )
        # self.log_model_instance(engagement)
        logger.debug("after: JIRA_Project last")
        self.log_model_instance(JIRA_Project.objects.last())

        if expect_200:
            self.assertEqual(response.status_code, 200)
        elif expect_redirect_to:
            self.assertRedirects(response, expect_redirect_to)
        else:
            self.assertEqual(response.status_code, 200)
        return response

    def edit_jira_project_for_engagement_with_data(
        self,
        engagement,
        data,
        expected_delta_jira_project_db=0,
        expect_redirect_to=None,
        expect_200=None,
    ):
        jira_project_count_before = self.db_jira_project_count()
        print("before: " + str(jira_project_count_before))

        if not expect_redirect_to and not expect_200:
            expect_redirect_to = self.get_expected_redirect_engagement(engagement)

        response = self.edit_engagement_jira(
            engagement,
            data,
            expect_redirect_to=expect_redirect_to,
            expect_200=expect_200,
        )

        print("after: " + str(self.db_jira_project_count()))

        self.assertEqual(
            self.db_jira_project_count(),
            jira_project_count_before + expected_delta_jira_project_db,
        )
        return response

    def edit_jira_project_for_engagement(
        self,
        engagement,
        expected_delta_jira_project_db=0,
        expect_redirect_to=None,
        expect_200=False,
    ):
        return self.edit_jira_project_for_engagement_with_data(
            engagement,
            self.get_engagement_with_jira_project_data(engagement),
            expected_delta_jira_project_db,
            expect_redirect_to=expect_redirect_to,
            expect_200=expect_200,
        )

    def edit_jira_project_for_engagement2(
        self,
        engagement,
        expected_delta_jira_project_db=0,
        expect_redirect_to=None,
        expect_200=False,
    ):
        return self.edit_jira_project_for_engagement_with_data(
            engagement,
            self.get_engagement_with_jira_project_data2(engagement),
            expected_delta_jira_project_db,
            expect_redirect_to=expect_redirect_to,
            expect_200=expect_200,
        )

    def empty_jira_project_for_engagement(
        self,
        engagement,
        expected_delta_jira_project_db=0,
        expect_redirect_to=None,
        expect_200=False,
    ):
        jira_project_count_before = self.db_jira_project_count()
        print("before: " + str(jira_project_count_before))

        if not expect_redirect_to and not expect_200:
            expect_redirect_to = self.get_expected_redirect_engagement(engagement)

        response = self.edit_engagement_jira(
            engagement,
            self.get_engagement_with_empty_jira_project_data(engagement),
            expect_redirect_to=expect_redirect_to,
            expect_200=expect_200,
        )

        print("after: " + str(self.db_jira_project_count()))

        self.assertEqual(
            self.db_jira_project_count(),
            jira_project_count_before + expected_delta_jira_project_db,
        )
        return response

    @patch("dojo.jira_link.views.jira_helper.is_jira_project_valid")
    def test_add_jira_project_to_engagement_without_jira_project(self, jira_mock):
        jira_mock.return_value = True  # cannot set return_value in decorated AND have the mock into the method
        # TODO: add engagement also via API, but let's focus on JIRA here
        engagement = self.add_engagement_without_jira_project(
            expected_delta_jira_project_db=0
        )
        response = self.edit_jira_project_for_engagement(
            engagement, expected_delta_jira_project_db=1
        )
        self.assertEqual(jira_mock.call_count, 1)

    @patch("dojo.jira_link.views.jira_helper.is_jira_project_valid")
    def test_add_empty_jira_project_to_engagement_without_jira_project(self, jira_mock):
        jira_mock.return_value = True  # cannot set return_value in decorated AND have the mock into the method
        engagement = self.add_engagement_without_jira_project(
            expected_delta_jira_project_db=0
        )
        response = self.empty_jira_project_for_engagement(
            engagement, expected_delta_jira_project_db=0
        )
        self.assertEqual(jira_mock.call_count, 0)

    @patch("dojo.jira_link.views.jira_helper.is_jira_project_valid")
    def test_edit_jira_project_to_engagement_with_jira_project(self, jira_mock):
        jira_mock.return_value = True  # cannot set return_value in decorated AND have the mock into the method
        engagement = self.add_engagement_with_jira_project(
            expected_delta_jira_project_db=1
        )
        response = self.edit_jira_project_for_engagement2(
            engagement, expected_delta_jira_project_db=0
        )
        self.assertEqual(jira_mock.call_count, 2)

    @patch("dojo.jira_link.views.jira_helper.is_jira_project_valid")
    def test_edit_empty_jira_project_to_engagement_with_jira_project(self, jira_mock):
        jira_mock.return_value = True  # cannot set return_value in decorated AND have the mock into the method
        engagement = self.add_engagement_with_jira_project(
            expected_delta_jira_project_db=1
        )
        # clearing out jira config used to be possible. what todo?
        # - delete jira project? would disconnect all existing jira issues in defect dojo from the config?
        # - allow jira project with empty jira instance and/or empty project_key? unpredictable behaviour
        # - so prevent clearing out these values
        # response = self.empty_jira_project_for_engagement(Engagement.objects.get(id=3), -1)
        # errors means it won't redirect to view_engagement, but returns a 200 and redisplays the edit engagement page
        response = self.empty_jira_project_for_engagement(
            engagement, expected_delta_jira_project_db=0, expect_200=True
        )
        self.assertEqual(jira_mock.call_count, 1)

    @patch("dojo.jira_link.views.jira_helper.is_jira_project_valid")
    def test_add_jira_project_to_engagement_without_jira_project_invalid_project(
        self, jira_mock
    ):
        jira_mock.return_value = False  # cannot set return_value in decorated AND have the mock into the method
        # errors means it won't redirect to view_engagement, but returns a 200 and redisplays the edit engagement page
        response = self.edit_jira_project_for_engagement(
            Engagement.objects.get(id=3),
            expected_delta_jira_project_db=0,
            expect_200=True,
        )
        self.assertEqual(jira_mock.call_count, 1)

    @patch("dojo.jira_link.views.jira_helper.is_jira_project_valid")
    def test_edit_jira_project_to_engagement_with_jira_project_invalid_project(
        self, jira_mock
    ):
        jira_mock.return_value = True  # cannot set return_value in decorated AND have the mock into the method
        engagement = self.add_engagement_with_jira_project(
            expected_delta_jira_project_db=1
        )
        jira_mock.return_value = False
        #  jira key is changed, so jira project will be checked
        response = self.edit_jira_project_for_engagement2(
            engagement, expected_delta_jira_project_db=0, expect_200=True
        )
        self.assertEqual(jira_mock.call_count, 2)

    @patch("dojo.jira_link.views.jira_helper.is_jira_project_valid")
    def test_add_engagement_with_jira_project(self, jira_mock):
        jira_mock.return_value = True  # cannot set return_value in decorated AND have the mock into the method
        engagement = self.add_engagement_with_jira_project(
            expected_delta_jira_project_db=1
        )
        self.assertIsNotNone(engagement)
        self.assertEqual(jira_mock.call_count, 1)

    @patch("dojo.jira_link.views.jira_helper.is_jira_project_valid")
    def test_add_engagement_with_jira_project_invalid_jira_project(self, jira_mock):
        jira_mock.return_value = False  # cannot set return_value in decorated AND have the mock into the method
        engagement = self.add_engagement_with_jira_project(
            expected_delta_jira_project_db=0, expect_redirect_to="/engagement/%i/edit"
        )
        # engagement still added even while jira errors
        self.assertIsNotNone(engagement)
        self.assertEqual(jira_mock.call_count, 1)

    @patch("dojo.jira_link.views.jira_helper.is_jira_project_valid")
    def test_add_engagement_without_jira_project(self, jira_mock):
        jira_mock.return_value = True  # cannot set return_value in decorated AND have the mock into the method
        engagement = self.add_engagement_without_jira_project(
            expected_delta_jira_project_db=0
        )
        self.assertIsNotNone(engagement)
        self.assertEqual(jira_mock.call_count, 0)

    # with jira disabled the jiraform should not be checked at all
    @patch("dojo.forms.JIRAProjectForm.is_valid")
    def test_add_engagement_with_jira_project_to_engagement_jira_disabled(
        self, jira_mock
    ):
        jira_mock.return_value = True  # cannot set return_value in decorated AND have the mock into the method
        self.system_settings(enable_jira=False)
        engagement = self.add_engagement_with_jira_project(
            expected_delta_jira_project_db=0
        )
        self.assertIsNotNone(engagement)
        self.assertEqual(jira_mock.call_count, 0)

    # with jira disabled the jiraform should not be checked at all
    @patch("dojo.forms.JIRAProjectForm.is_valid")
    def test_edit_jira_project_to_engagement_with_jira_project_invalid_project_jira_disabled(
        self, jira_mock
    ):
        self.system_settings(enable_jira=False)
        jira_mock.return_value = True  # cannot set return_value in decorated AND have the mock into the method
        response = self.edit_jira_project_for_engagement(
            Engagement.objects.get(id=3), expected_delta_jira_project_db=0
        )
        response = self.edit_jira_project_for_engagement2(
            Engagement.objects.get(id=3), expected_delta_jira_project_db=0
        )
        self.assertEqual(jira_mock.call_count, 0)


# inheriting a JIRA Project config from a product can influence some logic and field mandatoriness etc.
# so run all the same test again, but with the product above it having a JIRA Project Config
class JIRAConfigEngagementTest_Inheritance(JIRAConfigEngagementTest):
    def __init__(self, *args, **kwargs):
        JIRAConfigEngagementTest.__init__(self, *args, **kwargs)

    @patch("dojo.jira_link.views.jira_helper.is_jira_project_valid")
    def setUp(self, jira_mock, *args, **kwargs):
        jira_mock.return_value = True
        JIRAConfigEngagementTest.setUp(self, *args, **kwargs)
        # product 2 has jira project config, double check to make sure someone didn't molest the fixture
        self.product_id = 2
        product = Product.objects.get(id=self.product_id)
        self.assertIsNotNone(jira_helper.get_jira_project(product))


# TODO UI
# linking / unlinking
