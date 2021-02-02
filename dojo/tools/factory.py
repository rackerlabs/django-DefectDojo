import logging
from dojo.models import Test_Type

PARSERS = {}
# TODO remove that
SCAN_SONARQUBE_API = "SonarQube API Import"


def register_parser(scan_type, parser):
    logging.info(f"register scan_type:{scan_type}")
    # check double registration or registration with an existing key
    if scan_type in PARSERS:
        raise ValueError(f"Try to register an existing parser {scan_type}")
    PARSERS[scan_type] = parser


def import_parser_factory(file, test, active, verified, scan_type=None):
    """Return a parser by the scan type
    This fucntion exists only for backward compatibility
    """
    if scan_type in PARSERS:
        # create dynamicaly in DB
        test_type, created = Test_Type.objects.get_or_create(name=scan_type)
        if created:
            test_type.save()
        return PARSERS[scan_type]
    else:
        raise ValueError(f"Unknown Test Type {scan_type}")


def get_choices():
    res = list()
    for key in PARSERS:
        res.append((key, key))
    return tuple(res)


def requires_file(scan_type):
    if scan_type is None or scan_type not in PARSERS:
        return False
    # FIXME switch to method of the parser
    # parser = PARSERS[scan_type]
    return scan_type != SCAN_SONARQUBE_API


def handles_active_verified_statuses(scan_type):
    # FIXME switch to method of the parser
    # parser = PARSERS[scan_type]
    return scan_type in ["Generic Findings Import", SCAN_SONARQUBE_API, "Qualys Scan"]


from .acunetix.parser import AcunetixScannerParser

register_parser("Acunetix Scan", AcunetixScannerParser())
from .anchore_engine.parser import AnchoreEngineScanParser

register_parser("Anchore Engine Scan", AnchoreEngineScanParser())
from .anchore_enterprise.parser import AnchoreEnterprisePolicyCheckParser

register_parser("Anchore Enterprise Policy Check", AnchoreEnterprisePolicyCheckParser())
from .appspider.parser import AppSpiderXMLParser

register_parser("AppSpider Scan", AppSpiderXMLParser())
from .aqua.parser import AquaJSONParser

register_parser("Aqua Scan", AquaJSONParser())
from .arachni.parser import ArachniJSONParser

register_parser("Arachni Scan", ArachniJSONParser())
from .aws_prowler.parser import AWSProwlerParser

register_parser("AWS Prowler Scan", AWSProwlerParser())
from .aws_scout2.parser import AWSScout2Parser

register_parser("AWS Scout2 Scan", AWSScout2Parser())
from .awssecurityhub.parser import AwsSecurityFindingFormatParser

register_parser("AWS Security Hub Scan", AwsSecurityFindingFormatParser())
from .bandit.parser import BanditParser

register_parser("Bandit Scan", BanditParser())
from .blackduck_component_risk.parser import BlackduckCRImporter

register_parser("Blackduck Component Risk", BlackduckCRImporter())
from .blackduck.parser import BlackduckHubCSVParser

register_parser("Blackduck Hub Scan", BlackduckHubCSVParser())
from .brakeman.parser import BrakemanScanParser

register_parser("Brakeman Scan", BrakemanScanParser())
from .bugcrowd.parser import BugCrowdCSVParser

register_parser("BugCrowd Scan", BugCrowdCSVParser())
from .bundler_audit.parser import BundlerAuditParser

register_parser("Bundler-Audit Scan", BundlerAuditParser())
from .burp_enterprise.parser import BurpEnterpriseHtmlParser

register_parser("Burp Enterprise Scan", BurpEnterpriseHtmlParser())
from .burp_api.parser import BurpApiParser

register_parser("Burp REST API", BurpApiParser())
from .burp.parser import BurpXmlParser

register_parser("Burp Scan", BurpXmlParser())
from .ccvs.parser import CCVSReportParser

register_parser("CCVS Report", CCVSReportParser())
from .checkmarx.parser import CheckmarxXMLParser

register_parser("Checkmarx Scan", CheckmarxXMLParser())
register_parser("Checkmarx Scan detailed", CheckmarxXMLParser())
from .checkov.parser import CheckovParser

register_parser("Checkov Scan", CheckovParser())
from .choctaw_hog.parser import ChoctawhogParser

register_parser("Choctaw Hog Scan", ChoctawhogParser())
from .clair_klar.parser import ClairKlarParser

register_parser("Clair Klar Scan", ClairKlarParser())
from .clair.parser import ClairParser

register_parser("Clair Scan", ClairParser())
from .cobalt.parser import CobaltCSVParser

register_parser("Cobalt.io Scan", CobaltCSVParser())
from .contrast.parser import ContrastCSVParser

register_parser("Contrast Scan", ContrastCSVParser())
from .crashtest_security_json.parser import CrashtestSecurityJsonParser

register_parser("Crashtest Security JSON File", CrashtestSecurityJsonParser())
from .crashtest_security_xml.parser import CrashtestSecurityXmlParser

register_parser("Crashtest Security XML File", CrashtestSecurityXmlParser())
from .dawnscanner.parser import DawnScannerParser

register_parser("DawnScanner Scan", DawnScannerParser())
from .dependency_check.parser import DependencyCheckParser

register_parser("Dependency Check Scan", DependencyCheckParser())
from .dependency_track.parser import DependencyTrackParser

register_parser(
    "Dependency Track Finding Packaging Format (FPF) Export", DependencyTrackParser()
)
from .drheader.parser import DrHeaderJSONParser

register_parser("DrHeader JSON Importer", DrHeaderJSONParser())
from .dsop.parser import DsopParser

register_parser("DSOP Scan", DsopParser())
from .eslint.parser import ESLintParser

register_parser("ESLint Scan", ESLintParser())
from .fortify.parser import FortifyXMLParser

register_parser("Fortify Scan", FortifyXMLParser())
from .generic.parser import GenericFindingUploadCsvParser

register_parser("Generic Findings Import", GenericFindingUploadCsvParser())
from .github_vulnerability.parser import GithubVulnerabilityParser

register_parser("Github Vulnerability Scan", GithubVulnerabilityParser())
from .gitlab_dep_scan.parser import GitlabDepScanReportParser

register_parser("GitLab Dependency Scanning Report", GitlabDepScanReportParser())
from .gitlab_sast.parser import GitlabSastReportParser

register_parser("GitLab SAST Report", GitlabSastReportParser())
from .gitleaks.parser import GitleaksJSONParser

register_parser("Gitleaks Scan", GitleaksJSONParser())
from .gosec.parser import GosecScannerParser

register_parser("Gosec Scanner", GosecScannerParser())
from .h1.parser import HackerOneJSONParser

register_parser("HackerOne Cases", HackerOneJSONParser())
from .hadolint.parser import HadolintParser

register_parser("Hadolint Dockerfile check", HadolintParser())
from .harbor_vulnerability.parser import HarborVulnerabilityParser

register_parser("Harbor Vulnerability Scan", HarborVulnerabilityParser())
from .huskyci.parser import HuskyCIReportParser

register_parser("HuskyCI Report", HuskyCIReportParser())
from .ibm_app.parser import IbmAppScanDASTXMLParser

register_parser("IBM AppScan DAST", IbmAppScanDASTXMLParser())
from .immuniweb.parser import ImmuniwebXMLParser

register_parser("Immuniweb Scan", ImmuniwebXMLParser())
from .jfrogxray.parser import XrayJSONParser

register_parser("JFrog Xray Scan", XrayJSONParser())
from .kiuwan.parser import KiuwanCSVParser

register_parser("Kiuwan Scan", KiuwanCSVParser())
from .kubebench.parser import KubeBenchParser

register_parser("kube-bench Scan", KubeBenchParser())
from .microfocus_webinspect.parser import MicrofocusWebinspectXMLParser

register_parser("Microfocus Webinspect Scan", MicrofocusWebinspectXMLParser())
from .mobsf.parser import MobSFParser

register_parser("MobSF Scan", MobSFParser())
from .mozilla_observatory.parser import MozillaObservatoryJSONParser

register_parser("Mozilla Observatory Scan", MozillaObservatoryJSONParser())
from .nessus.parser import NessusParser

register_parser("Nessus Scan", NessusParser())
from .netsparker.parser import NetsparkerParser

register_parser("Netsparker Scan", NetsparkerParser())
from .nexpose.parser import NexposeFullXmlParser

register_parser("Nexpose Scan", NexposeFullXmlParser())
from .nikto.parser import NiktoXMLParser

register_parser("Nikto Scan", NiktoXMLParser())
from .nmap.parser import NmapXMLParser

register_parser("Nmap Scan", NmapXMLParser())
from .nsp.parser import NspParser

register_parser("Node Security Platform Scan", NspParser())
from .npm_audit.parser import NpmAuditParser

register_parser("NPM Audit Scan", NpmAuditParser())
from .openscap.parser import OpenscapXMLParser

register_parser("Openscap Vulnerability Scan", OpenscapXMLParser())
from .openvas_csv.parser import OpenVASUploadCsvParser

register_parser("OpenVAS CSV", OpenVASUploadCsvParser())
from .ort.parser import OrtParser

register_parser("ORT evaluated model Importer", OrtParser())
from .ossindex_devaudit.parser import OssIndexDevauditParser

register_parser("OssIndex Devaudit SCA Scan Importer", OssIndexDevauditParser())
from .outpost24.parser import Outpost24Parser

register_parser("Outpost24 Scan", Outpost24Parser())
from .php_security_audit_v2.parser import PhpSecurityAuditV2

register_parser("PHP Security Audit v2", PhpSecurityAuditV2())
from .php_symfony_security_check.parser import PhpSymfonySecurityCheckParser

register_parser("PHP Symfony Security Check", PhpSymfonySecurityCheckParser())
from .qualys_infrascan_webgui.parser import QualysInfraScanParser

register_parser("Qualys Infrastructure Scan (WebGUI XML)", QualysInfraScanParser())
from .qualys.parser import QualysParser

register_parser("Qualys Scan", QualysParser())
from .qualys_webapp.parser import QualysWebAppParser

register_parser("Qualys Webapp Scan", QualysWebAppParser())
from .retirejs.parser import RetireJsParser

register_parser("Retire.js Scan", RetireJsParser())
from .risk_recon.parser import RiskReconParser

register_parser("Risk Recon API Importer", RiskReconParser())
from .safety.parser import SafetyParser

register_parser("Safety Scan", SafetyParser())
from .sarif.parser import SarifParser

register_parser("SARIF", SarifParser())
from .scantist.parser import ScantistJSONParser

register_parser("Scantist Scan", ScantistJSONParser())
from .scout_suite.parser import ScoutSuiteParser

register_parser("Scout Suite Scan", ScoutSuiteParser())
from .semgrep.parser import SemgrepJSONParser

register_parser("Semgrep JSON Report", SemgrepJSONParser())
from .skf.parser import SKFCsvParser

register_parser("SKF Scan", SKFCsvParser())
from .snyk.parser import SnykParser

register_parser("Snyk Scan", SnykParser())
from dojo.tools.sonarqube_api.importer import SonarQubeApiImporter

register_parser("SonarQube API Import", SonarQubeApiImporter())
from .sonarqube.parser import SonarQubeHtmlParser

register_parser("SonarQube Scan", SonarQubeHtmlParser())
register_parser("SonarQube Scan detailed", SonarQubeHtmlParser())
from .sonatype.parser import SonatypeJSONParser

register_parser("Sonatype Application Scan", SonatypeJSONParser())
from .spotbugs.parser import SpotbugsXMLParser

register_parser("SpotBugs Scan", SpotbugsXMLParser())
from .ssl_labs.parser import SSLlabsParser

register_parser("SSL Labs Scan", SSLlabsParser())
from .sslscan.parser import SslscanXMLParser

register_parser("Sslscan", SslscanXMLParser())
from .sslyze.parser_json import SSLyzeJSONParser

register_parser("SSLyze 3 Scan (JSON)", SSLyzeJSONParser())
from .sslyze.parser_xml import SSLyzeXMLParser

register_parser("Sslyze Scan", SSLyzeXMLParser())
from .testssl.parser import TestsslCSVParser

register_parser("Testssl Scan", TestsslCSVParser())
from .trivy.parser import TrivyParser

register_parser("Trivy Scan", TrivyParser())
from .trufflehog.parser import TruffleHogJSONParser

register_parser("Trufflehog Scan", TruffleHogJSONParser())
from .trustwave.parser import TrustwaveUploadCsvParser

register_parser("Trustwave Scan (CSV)", TrustwaveUploadCsvParser())
from .twistlock.parser import TwistlockParser

register_parser("Twistlock Image Scan", TwistlockParser())
from .vcg.parser import VCGParser

register_parser("VCG Scan", VCGParser())
from .veracode.parser import VeracodeXMLParser

register_parser("Veracode Scan", VeracodeXMLParser())
from .wapiti.parser import WapitiXMLParser

register_parser("Wapiti Scan", WapitiXMLParser())
from .whitesource.parser import WhitesourceJSONParser

register_parser("Whitesource Scan", WhitesourceJSONParser())
from .wpscan.parser import WpscanJSONParser

register_parser("Wpscan", WpscanJSONParser())
from .xanitizer.parser import XanitizerXMLParser

register_parser("Xanitizer Scan", XanitizerXMLParser())
from .yarn_audit.parser import YarnAuditParser

register_parser("Yarn Audit Scan", YarnAuditParser())
from .zap.parser import ZapXmlParser

register_parser("ZAP Scan", ZapXmlParser())
