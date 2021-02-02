from django.test import TestCase
from dojo.tools.php_symfony_security_check.parser import PhpSymfonySecurityCheckParser
from dojo.models import Test


class TestPhpSymfonySecurityCheckerParser(TestCase):
    def test_php_symfony_security_check_parser_with_no_vuln_has_no_findings(self):
        testfile = open(
            "dojo/unittests/scans/php_symfony_security_check_sample/php_symfony_no_vuln.json"
        )
        parser = PhpSymfonySecurityCheckParser()
        findings = parser.get_findings(testfile, Test())
        testfile.close()
        items = findings
        self.assertEqual(0, len(items))

    def test_php_symfony_security_check_parser_with_one_criticle_vuln_has_one_findings(
        self,
    ):
        testfile = open(
            "dojo/unittests/scans/php_symfony_security_check_sample/php_symfony_one_vuln.json"
        )
        parser = PhpSymfonySecurityCheckParser()
        findings = parser.get_findings(testfile, Test())
        testfile.close()
        self.assertEqual(1, len(findings))

    def test_php_symfony_security_check_parser_with_many_vuln_has_many_findings(self):
        testfile = open(
            "dojo/unittests/scans/php_symfony_security_check_sample/php_symfony_many_vuln.json"
        )
        parser = PhpSymfonySecurityCheckParser()
        findings = parser.get_findings(testfile, Test())
        testfile.close()
        items = findings
        self.assertEqual(8, len(items))
        self.assertEqual("symfony/cache", items[0].component_name)
        self.assertEqual("3.4.16", items[0].component_version)
