from os import path

from django.test import TestCase
from dojo.models import Test
from dojo.tools.burp_graphql.parser import BurpGraphQLParser


class TestBurpGraphQLParser(TestCase):

    def test_burp_one_finding(self):
        with open(path.join(path.dirname(__file__), "../scans/burp_graphql/one_finding.json")) as test_file:
            parser = BurpGraphQLParser()
            findings = parser.get_findings(test_file, Test())
            for finding in findings:
                for endpoint in finding.unsaved_endpoints:
                    endpoint.clean()

            self.assertEqual(1, len(findings))
            self.assertEqual("Finding", findings[0].title)
            self.assertEqual(79, findings[0].cwe)
            self.assertIn("description 1", findings[0].description)
            self.assertIn("remediation 1", findings[0].mitigation)
            self.assertIn("issue description 1", findings[0].impact)
            self.assertIn("issue remediation 1", findings[0].mitigation)
            self.assertEquals('High', findings[0].severity)
            self.assertEqual(1, len(findings[0].unsaved_endpoints))
            self.assertEqual('www.test.com', findings[0].unsaved_endpoints[0].host)
            self.assertEqual('path', findings[0].unsaved_endpoints[0].path)
            self.assertEqual('https', findings[0].unsaved_endpoints[0].protocol)
            self.assertEqual(1, len(findings[0].unsaved_req_resp))
            self.assertEqual('request data 1/request data 2/request data 3/', findings[0].unsaved_req_resp[0]['req'])
            self.assertIn('ref 1', findings[0].references)
            self.assertIn('CWE-79', findings[0].references)

    def test_burp_two_findings(self):
        with open(path.join(path.dirname(__file__), "../scans/burp_graphql/two_findings.json")) as test_file:
            parser = BurpGraphQLParser()
            findings = parser.get_findings(test_file, Test())
            for finding in findings:
                for endpoint in finding.unsaved_endpoints:
                    endpoint.clean()

            self.assertEqual(2, len(findings))
            self.assertEqual("Finding 1", findings[0].title)
            self.assertEqual("Finding 2", findings[1].title)
            self.assertEqual(2, len(findings[1].unsaved_endpoints))
            self.assertEqual(4, len(findings[1].unsaved_req_resp))
            self.assertIn("description 2", findings[1].description)
            self.assertIn("description 3", findings[1].description)

    def test_burp_no_findings(self):
        with open(path.join(path.dirname(__file__), "../scans/burp_graphql/no_findings.json")) as test_file:
            parser = BurpGraphQLParser()
            findings = parser.get_findings(test_file, Test())
            for finding in findings:
                for endpoint in finding.unsaved_endpoints:
                    endpoint.clean()

            self.assertEqual(0, len(findings))

    def test_burp_null_title(self):
        with open(path.join(path.dirname(__file__), "../scans/burp_graphql/null_title.json")) as test_file:
            parser = BurpGraphQLParser()
            findings = parser.get_findings(test_file, Test())
            for finding in findings:
                for endpoint in finding.unsaved_endpoints:
                    endpoint.clean()

            self.assertEqual(0, len(findings))

    def test_burp_null_data(self):
        with open(path.join(path.dirname(__file__), "../scans/burp_graphql/null_data.json")) as test_file:
            parser = BurpGraphQLParser()
            findings = parser.get_findings(test_file, Test())
            for finding in findings:
                for endpoint in finding.unsaved_endpoints:
                    endpoint.clean()

            self.assertEqual(1, len(findings))
            self.assertEqual("Finding", findings[0].title)
