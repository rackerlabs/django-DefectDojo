from django.test import TestCase
from dojo.tools.nuclei.parser import NucleiParser
from dojo.models import Test


class TestNucleiParser(TestCase):

    def test_parse_no_findings(self):
        testfile = open("dojo/unittests/scans/nuclei/no_findings.json")
        parser = NucleiParser()
        findings = parser.get_findings(testfile, Test())
        self.assertEqual(0, len(findings))

    def test_parse_many_findings(self):
        testfile = open("dojo/unittests/scans/nuclei/many_findings.json")
        parser = NucleiParser()
        findings = parser.get_findings(testfile, Test())
        self.assertEqual(9, len(findings))

        with self.subTest(i=0):
            finding = findings[0]
            self.assertEqual("OpenSSH 5.3 Detection: nuclei-example.com:22", finding.title)
            self.assertEqual("Low", finding.severity)
            self.assertEqual(1, finding.nb_occurences)
            self.assertIsNotNone(finding.description)
            self.assertEqual("network,openssh", finding.unsaved_tags)
            self.assertIsNotNone(finding.references)
            self.assertEqual("nuclei-example.com", finding.unsaved_endpoints[0].host)
            self.assertEqual(22, finding.unsaved_endpoints[0].port)

        with self.subTest(i=1):
            finding = findings[1]
            self.assertEqual("nginx version detect: https://nuclei-example.com", finding.title)
            self.assertEqual("Info", finding.severity)
            self.assertEqual(1, finding.nb_occurences)
            self.assertIsNotNone(finding.description)
            self.assertIsNone(finding.unsaved_tags)
            self.assertIsNone(finding.references)
            self.assertEqual(None, finding.unsaved_endpoints[0].path)
            self.assertEqual("nuclei-example.com", finding.unsaved_endpoints[0].host)
            self.assertEqual(443, finding.unsaved_endpoints[0].port)

        with self.subTest(i=2):
            finding = findings[2]
            self.assertEqual("phpMyAdmin setup page: https://nuclei-example.com/phpmyadmin/setup/index.php", finding.title)
            self.assertEqual("Medium", finding.severity)
            self.assertEqual(1, finding.nb_occurences)
            self.assertIsNotNone(finding.description)
            self.assertIsNotNone(finding.references)
            self.assertEqual("phpmyadmin", finding.unsaved_tags)
            self.assertEqual("phpmyadmin/setup/index.php", finding.unsaved_endpoints[0].path)
            self.assertEqual("nuclei-example.com", finding.unsaved_endpoints[0].host)
            self.assertEqual(443, finding.unsaved_endpoints[0].port)

        with self.subTest(i=3):
            finding = findings[3]
            self.assertEqual("Wappalyzer Technology Detection: http://127.0.0.1:8080/WebGoat", finding.title)
            self.assertEqual("Info", finding.severity)
            self.assertEqual(3, finding.nb_occurences)
            self.assertIsNotNone(finding.description)
            self.assertIsNone(finding.references)
            self.assertIsNone(finding.unsaved_tags)
            self.assertEqual("WebGoat", finding.unsaved_endpoints[0].path)
            self.assertEqual("127.0.0.1", finding.unsaved_endpoints[0].host)
            self.assertEqual(8080, finding.unsaved_endpoints[0].port)

        with self.subTest(i=4):
            finding = findings[4]
            self.assertEqual("Wappalyzer Technology Detection: http://127.0.0.1:9090/WebWolf", finding.title)
            self.assertEqual("Info", finding.severity)
            self.assertEqual(2, finding.nb_occurences)
            self.assertIsNotNone(finding.description)
            self.assertIsNone(finding.references)
            self.assertIsNone(finding.unsaved_tags)
            self.assertEqual("WebWolf", finding.unsaved_endpoints[0].path)
            self.assertEqual("127.0.0.1", finding.unsaved_endpoints[0].host)
            self.assertEqual(9090, finding.unsaved_endpoints[0].port)

        with self.subTest(i=5):
            finding = findings[5]
            self.assertEqual("Wappalyzer Technology Detection: https://nuclei-example.com", finding.title)
            self.assertEqual("Info", finding.severity)
            self.assertEqual(6, finding.nb_occurences)
            self.assertIsNotNone(finding.description)
            self.assertIsNone(finding.references)
            self.assertIsNone(finding.unsaved_tags)
            self.assertEqual(None, finding.unsaved_endpoints[0].path)
            self.assertEqual("nuclei-example.com", finding.unsaved_endpoints[0].host)
            self.assertEqual(443, finding.unsaved_endpoints[0].port)

        with self.subTest(i=6):
            finding = findings[6]
            self.assertEqual("WAF Detection: https://nuclei-example.com/", finding.title)
            self.assertEqual("Info", finding.severity)
            self.assertEqual(2, finding.nb_occurences)
            self.assertIsNotNone(finding.description)
            self.assertIsNone(finding.references)
            self.assertIsNone(finding.unsaved_tags)
            self.assertEqual(None, finding.unsaved_endpoints[0].path)
            self.assertEqual("nuclei-example.com", finding.unsaved_endpoints[0].host)
            self.assertEqual(443, finding.unsaved_endpoints[0].port)

        with self.subTest(i=7):
            finding = findings[7]
            self.assertEqual("phpMyAdmin Panel: https://nuclei-example.com/phpmyadmin/", finding.title)
            self.assertEqual("Info", finding.severity)
            self.assertEqual(1, finding.nb_occurences)
            self.assertIsNotNone(finding.description)
            self.assertIsNone(finding.references)
            self.assertEqual("panel", finding.unsaved_tags)
            self.assertEqual("phpmyadmin/", finding.unsaved_endpoints[0].path)
            self.assertEqual("nuclei-example.com", finding.unsaved_endpoints[0].host)
            self.assertEqual(443, finding.unsaved_endpoints[0].port)

        with self.subTest(i=8):
            finding = findings[8]
            self.assertEqual("MySQL DB with enabled native password: nuclei-example.com:3306", finding.title)
            self.assertEqual("Info", finding.severity)
            self.assertEqual(1, finding.nb_occurences)
            self.assertIsNotNone(finding.description)
            self.assertIsNone(finding.references)
            self.assertEqual("network,mysql,bruteforce,db", finding.unsaved_tags)
            self.assertEqual(None, finding.unsaved_endpoints[0].path)
            self.assertEqual("nuclei-example.com", finding.unsaved_endpoints[0].host)
            self.assertEqual(3306, finding.unsaved_endpoints[0].port)

        testfile.close()
        for finding in findings:
            for endpoint in finding.unsaved_endpoints:
                endpoint.clean()
