import json
from unittest import mock

from dojo.tools.sonarqube_api.importer import SonarQubeApiImporter
from django.test import TestCase
from dojo.models import Test, Tool_Configuration, Tool_Type, Engagement, Product


class TestSonarqubeImporter(TestCase):

    def setUp(self):
        tool_type = Tool_Type.objects.create(name='SonarQube')
        Tool_Configuration.objects.create(name='SonarQube', tool_type=tool_type, authentication_type="API")

        product = Product(name='product')
        engagement = Engagement(product=product)
        self.test = Test(
            engagement=engagement
        )

    def dummy_product(self, *args, **kwargs):
        with open('dojo/unittests/scans/sonarqube_api/product.json') as json_file:
            data = json.load(json_file)
            return data

    def dummy_issues(self, *args, **kwargs):
        with open('dojo/unittests/scans/sonarqube_api/issues.json') as json_file:
            data = json.load(json_file)
            return data

    def dummy_rule(self, *args, **kwargs):
        with open('dojo/unittests/scans/sonarqube_api/rule.json') as json_file:
            data = json.load(json_file)
            return data

    def dummy_no_hotspot(self, *args, **kwargs):
        with open('dojo/unittests/scans/sonarqube_api/hotspots/no_vuln.json') as json_file:
            data = json.load(json_file)
            return data

    def dummy_one_hotspot(self, *args, **kwargs):
        with open('dojo/unittests/scans/sonarqube_api/hotspots/one_vuln.json') as json_file:
            data = json.load(json_file)
            return data

    def dummy_many_hotspots(self, *args, **kwargs):
        with open('dojo/unittests/scans/sonarqube_api/hotspots/many_vulns.json') as json_file:
            data = json.load(json_file)
            return data

    def dummy_hotspot_rule(self, *args, **kwargs):
        with open('dojo/unittests/scans/sonarqube_api/hotspots/rule.json') as json_file:
            data = json.load(json_file)
            return data

    def empty_list(self, *args, **kwargs):
        return list()

    @mock.patch('dojo.tools.sonarqube_api.api_client.SonarQubeAPI.find_project', dummy_product)
    @mock.patch('dojo.tools.sonarqube_api.api_client.SonarQubeAPI.get_rule', dummy_rule)
    @mock.patch('dojo.tools.sonarqube_api.api_client.SonarQubeAPI.find_issues', dummy_issues)
    @mock.patch('dojo.tools.sonarqube_api.api_client.SonarQubeAPI.find_hotspots', empty_list)
    def test_parse_file_with_one_cwe_and_one_no_cwe_vulns(self):
        parser = SonarQubeApiImporter()
        findings = parser.get_findings(None, self.test)
        self.assertEqual(2, len(findings))

    @mock.patch('dojo.tools.sonarqube_api.api_client.SonarQubeAPI.find_project', dummy_product)
    @mock.patch('dojo.tools.sonarqube_api.api_client.SonarQubeAPI.find_issues', empty_list)
    @mock.patch('dojo.tools.sonarqube_api.api_client.SonarQubeAPI.get_hotspot_rule', dummy_hotspot_rule)
    @mock.patch('dojo.tools.sonarqube_api.api_client.SonarQubeAPI.find_hotspots', dummy_no_hotspot)
    def test_parse_file_with_no_hotspot(self):
        parser = SonarQubeApiImporter()
        findings = parser.get_findings(None, self.test)
        self.assertEqual(0, len(findings))

    @mock.patch('dojo.tools.sonarqube_api.api_client.SonarQubeAPI.find_project', dummy_product)
    @mock.patch('dojo.tools.sonarqube_api.api_client.SonarQubeAPI.find_issues', empty_list)
    @mock.patch('dojo.tools.sonarqube_api.api_client.SonarQubeAPI.get_hotspot_rule', dummy_hotspot_rule)
    @mock.patch('dojo.tools.sonarqube_api.api_client.SonarQubeAPI.find_hotspots', dummy_one_hotspot)
    def test_parse_file_with_one_hotspot(self):
        parser = SonarQubeApiImporter()
        findings = parser.get_findings(None, self.test)
        self.assertEqual(1, len(findings))

    @mock.patch('dojo.tools.sonarqube_api.api_client.SonarQubeAPI.find_project', dummy_product)
    @mock.patch('dojo.tools.sonarqube_api.api_client.SonarQubeAPI.find_issues', empty_list)
    @mock.patch('dojo.tools.sonarqube_api.api_client.SonarQubeAPI.get_hotspot_rule', dummy_hotspot_rule)
    @mock.patch('dojo.tools.sonarqube_api.api_client.SonarQubeAPI.find_hotspots', dummy_many_hotspots)
    def test_parse_file_with_many_hotspots(self):
        parser = SonarQubeApiImporter()
        findings = parser.get_findings(None, self.test)
        self.assertEqual(2, len(findings))

    @mock.patch('dojo.tools.sonarqube_api.api_client.SonarQubeAPI.find_project', dummy_product)
    @mock.patch('dojo.tools.sonarqube_api.api_client.SonarQubeAPI.get_rule', dummy_rule)
    @mock.patch('dojo.tools.sonarqube_api.api_client.SonarQubeAPI.find_issues', dummy_issues)
    @mock.patch('dojo.tools.sonarqube_api.api_client.SonarQubeAPI.get_hotspot_rule', dummy_hotspot_rule)
    @mock.patch('dojo.tools.sonarqube_api.api_client.SonarQubeAPI.find_hotspots', dummy_many_hotspots)
    def test_parse_file_with_two_issues_and_two_hotspots(self):
        parser = SonarQubeApiImporter()
        findings = parser.get_findings(None, self.test)
        self.assertEqual(4, len(findings))
