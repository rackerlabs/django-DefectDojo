from django.test import TestCase

from dojo.models import Test
from dojo.tools.dependency_check.parser import DependencyCheckParser


class TestFile(object):
    def read(self):
        return self.content

    def __init__(self, name, content):
        self.name = name
        self.content = content


class TestDependencyCheckParser(TestCase):
    def test_parse_file_with_no_vulnerabilities_has_no_findings(self):
        content = """<?xml version="1.0"?>
<analysis xmlns="https://jeremylong.github.io/DependencyCheck/dependency-check.1.3.xsd">
    <scanInfo>
    </scanInfo>
    <projectInfo>
        <name>Test Project</name>
        <reportDate>2016-11-05T14:52:15.748-0400</reportDate>
        <credits>This report contains data retrieved from the National Vulnerability Database: http://nvd.nist.gov</credits>
    </projectInfo>
    <dependencies>
        <dependency>
            <fileName>component1.dll</fileName>
            <filePath>C:\\Projectsestproject\\libraries\\component1.dll</filePath>
            <md5>ba5a6a10bae6ce2abbabec9facae23a4</md5>
            <sha1>ae917bbce68733468b1972113e0e1fc5dc7444a0</sha1>
            <evidenceCollected>
                <evidence type="vendor" confidence="HIGH">
                    <source>file</source>
                    <name>name</name>
                    <value>component1.dll</value>
                </evidence>
                <evidence type="product" confidence="HIGH">
                    <source>file</source>
                    <name>name</name>
                    <value>component1</value>
                </evidence>
                <evidence type="version" confidence="MEDIUM">
                    <source>file</source>
                    <name>name</name>
                    <value>component1</value>
                </evidence>
                <evidence type="version" confidence="MEDIUM">
                    <source>file</source>
                    <name>version</name>
                    <value>1</value>
                </evidence>
            </evidenceCollected>
        </dependency>
        <dependency>
            <fileName>component2.dll</fileName>
            <filePath>C:\\Projectsestproject\\libraries\\component2.dll</filePath>
            <md5>21b24bc199530e07cb15d93c7f929f04</md5>
            <sha1>a29f196740ab608199488c574f536529b5c21242</sha1>
            <evidenceCollected>
                <evidence type="vendor" confidence="HIGH">
                    <source>file</source>
                    <name>name</name>
                    <value>component2</value>
                </evidence>
                <evidence type="product" confidence="HIGH">
                    <source>file</source>
                    <name>name</name>
                    <value>component2</value>
                </evidence>
            </evidenceCollected>
        </dependency>
        </dependencies>
</analysis>
 """
        testfile = TestFile("dependency-check-report.xml", content)
        parser = DependencyCheckParser()
        findings = parser.get_findings(testfile, Test())
        self.assertEqual(0, len(findings))

    def test_parse_file_with_single_vulnerability_has_single_finding(self):
        content = """<?xml version="1.0"?>
<analysis xmlns="https://jeremylong.github.io/DependencyCheck/dependency-check.1.3.xsd">
    <scanInfo>
    </scanInfo>
    <projectInfo>
        <name>Test Project</name>
        <reportDate>2016-11-05T14:52:15.748-0400</reportDate>
        <credits>This report contains data retrieved from the National Vulnerability Database: http://nvd.nist.gov</credits>
    </projectInfo>
    <dependencies>
        <dependency>
            <fileName>component1.dll</fileName>
            <filePath>C:\\Projectsestproject\\libraries\\component1.dll</filePath>
            <md5>ba5a6a10bae6ce2abbabec9facae23a4</md5>
            <sha1>ae917bbce68733468b1972113e0e1fc5dc7444a0</sha1>
            <evidenceCollected>
                <evidence type="vendor" confidence="HIGH">
                    <source>file</source>
                    <name>name</name>
                    <value>component1.dll</value>
                </evidence>
                <evidence type="product" confidence="HIGH">
                    <source>file</source>
                    <name>name</name>
                    <value>component1</value>
                </evidence>
                <evidence type="version" confidence="MEDIUM">
                    <source>file</source>
                    <name>name</name>
                    <value>component1</value>
                </evidence>
                <evidence type="version" confidence="MEDIUM">
                    <source>file</source>
                    <name>version</name>
                    <value>1</value>
                </evidence>
            </evidenceCollected>
        </dependency>
        <dependency>
            <fileName>component2.dll</fileName>
            <filePath>C:\\Projectestproject\\libraries\\component2.dll</filePath>
            <md5>21b24bc199530e07cb15d93c7f929f04</md5>
            <sha1>a29f196740ab608199488c574f536529b5c21242</sha1>
            <evidenceCollected>
                <evidence type="vendor" confidence="HIGH">
                    <source>file</source>
                    <name>name</name>
                    <value>component2</value>
                </evidence>
                <evidence type="product" confidence="HIGH">
                    <source>file</source>
                    <name>name</name>
                    <value>component2</value>
                </evidence>
            </evidenceCollected>
            <identifiers>
                <identifier type="maven" confidence="HIGHEST">
                    <name>org.owasp:library:6.7.8</name>
                    <url>https://search.maven.org/remotecontent?filepath=xalan/serializer/2.7.1/serializer-2.7.1.jar</url>
                </identifier>
            </identifiers>
            <vulnerabilities>
                <vulnerability>
                    <name>CVE-0000-0001</name>
                    <cvssScore>7.5</cvssScore>
                    <cvssAccessVector>NETWORK</cvssAccessVector>
                    <cvssAccessComplexity>LOW</cvssAccessComplexity>
                    <cvssAuthenticationr>NONE</cvssAuthenticationr>
                    <cvssConfidentialImpact>PARTIAL</cvssConfidentialImpact>
                    <cvssIntegrityImpact>PARTIAL</cvssIntegrityImpact>
                    <cvssAvailabilityImpact>PARTIAL</cvssAvailabilityImpact>
                    <severity>High</severity>
                    <cwe>CWE-00 Bad Vulnerability</cwe>
                    <description>Description of a bad vulnerability.</description>
                    <references>
                        <reference>
                            <source>Reference1</source>
                            <url>http://localhost/badvulnerability.htm</url>
                            <name>Reference Name</name>
                        </reference>
                        <reference>
                            <source>MISC</source>
                            <url>http://localhost2/reference_for_badvulnerability.pdf</url>
                            <name>Reference for a bad vulnerability</name>
                        </reference>
                    </references>
                    <vulnerableSoftware>
                        <software>cpe:/a:component2:component2:1.0</software>
                    </vulnerableSoftware>
                </vulnerability>
            </vulnerabilities>
        </dependency>
        </dependencies>
</analysis>
 """
        testfile = TestFile("dependency-check-report.xml", content)
        parser = DependencyCheckParser()
        findings = parser.get_findings(testfile, Test())
        items = findings
        self.assertEqual(1, len(items))
        self.assertEqual(items[0].title, "component2.dll | CVE-0000-0001")
        self.assertEqual(items[0].component_name, "org.owasp:library")
        self.assertEqual(items[0].component_version, "6.7.8")

    def test_parse_file_with_multiple_vulnerabilities_has_multiple_findings(self):
        content = """<?xml version="1.0"?>
<analysis xmlns="https://jeremylong.github.io/DependencyCheck/dependency-check.1.3.xsd">
    <scanInfo>
    </scanInfo>
    <projectInfo>
        <name>Test Project</name>
        <reportDate>2016-11-05T14:52:15.748-0400</reportDate>
        <credits>This report contains data retrieved from the National Vulnerability Database: http://nvd.nist.gov</credits>
    </projectInfo>
    <dependencies>
        <dependency>
            <fileName>component1</fileName>
            <filePath>C:\\Projectestproject\\libraries\\component1.dll</filePath>
            <md5>ba5a6a10bae6ce2abbabec9facae23a4</md5>
            <sha1>ae917bbce68733468b1972113e0e1fc5dc7444a0</sha1>
            <evidenceCollected>
                <evidence type="vendor" confidence="HIGH">
                    <source>file</source>
                    <name>name</name>
                    <value>component1.dll</value>
                </evidence>
                <evidence type="product" confidence="HIGH">
                    <source>file</source>
                    <name>name</name>
                    <value>component1</value>
                </evidence>
                <evidence type="version" confidence="MEDIUM">
                    <source>file</source>
                    <name>name</name>
                    <value>component1</value>
                </evidence>
                <evidence type="version" confidence="MEDIUM">
                    <source>file</source>
                    <name>version</name>
                    <value>1</value>
                </evidence>
            </evidenceCollected>
        </dependency>
        <dependency>
            <fileName>adapter-ear1.ear: dom4j-2.1.1.jar</fileName>
            <filePath>/var/lib/adapter-ear1.ear/dom4j-2.1.1.jar</filePath>
            <md5>21b24bc199530e07cb15d93c7f929f04</md5>
            <sha1>a29f196740ab608199488c574f536529b5c21242</sha1>
            <relatedDependencies>
                <relatedDependency>
                    <fileName>adapter-ear8.ear: dom4j-2.1.1.jar</fileName>
                    <filePath>/var/lib/adapter-ear8.ear/dom4j-2.1.1.jar</filePath>
                    <sha256>a520752f350909c191db45a598a88fcca2fa5db17a340dee6b3d0e36f4122e11</sha256>
                    <sha1>080c5a481cd7abf27bfd4b48edf73b1cb214085e</sha1>
                    <md5>add18b9f953221ff565cf7a34aac0ed9</md5>
                </relatedDependency>
                <relatedDependency>
                    <fileName>adapter-ear1.ear: dom4j-extensions-2.1.1.jar</fileName>
                    <filePath>/var/lib/adapter-ear1.ear/dom4j-extensions-2.1.1.jar</filePath>
                    <sha256>a520752f350909c191db45a598a88fcca2fa5db17a340dee6b3d0e36f4122e11</sha256>
                    <sha1>080c5a481cd7abf27bfd4b48edf73b1cb214085e</sha1>
                    <md5>add18b9f953221ff565cf7a34aac0ed9</md5>
                </relatedDependency>
            </relatedDependencies>
            <evidenceCollected>
                <evidence type="vendor" confidence="HIGH">
                    <source>file</source>
                    <name>name</name>
                    <value>org.jdom</value>
                </evidence>
                <evidence type="product" confidence="HIGH">
                    <source>file</source>
                    <name>name</name>
                    <value>dom4j</value>
                </evidence>
            </evidenceCollected>
            <identifiers>
                <identifiers>
                    <package confidence="HIGH">
                        <id>pkg:maven/org.dom4j/dom4j@2.1.1.redhat-00001</id>
                        <url>https://ossindex.sonatype.org/component/pkg:maven/org.dom4j/dom4j@2.1.1.redhat-00001</url>
                    </package>
                    <vulnerabilityIds confidence="HIGHEST">
                        <id>cpe:2.3:a:dom4j_project:dom4j:2.1.1.hat-00001:*:*:*:*:*:*:*</id>
                        <url>https://nvd.nist.gov/vuln/search/results?form_type=Advanced&amp;results_type=overview&amp;search_type=all&amp;cpe_vendor=cpe%3A%2F%3Adom4j_project&amp;cpe_product=cpe%3A%2F%3Adom4j_project%3Adom4j&amp;cpe_version=cpe%3A%2F%3Adom4j_project%3Adom4j%3A2.1.1.hat-00001</url>
                    </vulnerabilityIds>
                </identifiers>
                <identifier type="cpe" confidence="HIGHEST">
                    <name>cpe:/a:apache:xalan-java:2.7.1</name>
                    <url>https://web.nvd.nist.gov/view/vuln/search-results?adv_search=true&amp;cves=on&amp;cpe_version=cpe%3A%2Fa%3Aapache%3Axalan-java%3A2.7.1</url>
                </identifier>
                <identifier type="maven" confidence="HIGHEST">
                    <name>xalan:serializer:2.7.1</name>
                    <url>https://search.maven.org/remotecontent?filepath=xalan/serializer/2.7.1/serializer-2.7.1.jar</url>
                </identifier>
            </identifiers>
            <vulnerabilities>
                <vulnerability>
                    <name>CVE-0000-0001</name>
                    <cvssScore>7.5</cvssScore>
                    <cvssAccessVector>NETWORK</cvssAccessVector>
                    <cvssAccessComplexity>LOW</cvssAccessComplexity>
                    <cvssAuthenticationr>NONE</cvssAuthenticationr>
                    <cvssConfidentialImpact>PARTIAL</cvssConfidentialImpact>
                    <cvssIntegrityImpact>PARTIAL</cvssIntegrityImpact>
                    <cvssAvailabilityImpact>PARTIAL</cvssAvailabilityImpact>
                    <severity>High</severity>
                    <cwe>CWE-00 Bad Vulnerability</cwe>
                    <description>Description of a bad vulnerability.</description>
                    <references>
                        <reference>
                            <source>Reference1</source>
                            <url>http://localhost/badvulnerability.htm</url>
                            <name>Reference Name</name>
                        </reference>
                        <reference>
                            <source>MISC</source>
                            <url>http://localhost2/reference_for_badvulnerability.pdf</url>
                            <name>Reference for a bad vulnerability</name>
                        </reference>
                    </references>
                    <vulnerableSoftware>
                        <software>cpe:/a:component2:component2:1.0</software>
                    </vulnerableSoftware>
                </vulnerability>
            </vulnerabilities>
        </dependency>
        <dependency isVirtual="true">
            <fileName>yargs-parser:5.0.0</fileName>
            <filePath>/var/lib/jenkins/workspace/nl-selfservice_-_metrics_develop/package-lock.json?yargs-parser</filePath>
            <md5/>
            <sha1/>
            <sha256/>
            <relatedDependencies>
                <relatedDependency>
                    <filePath>/var/lib/adapter-ear8.ear/dom4j-2.1.1.jar</filePath>
                    <sha256>a520752f350909c191db45a598a88fcca2fa5db17a340dee6b3d0e36f4122e11</sha256>
                    <sha1>080c5a481cd7abf27bfd4b48edf73b1cb214085e</sha1>
                    <md5>add18b9f953221ff565cf7a34aac0ed9</md5>
                </relatedDependency>
                <relatedDependency>
                    <filePath>/var/lib/adapter-ear1.ear/dom4j-extensions-2.1.1.jar</filePath>
                    <sha256>a520752f350909c191db45a598a88fcca2fa5db17a340dee6b3d0e36f4122e11</sha256>
                    <sha1>080c5a481cd7abf27bfd4b48edf73b1cb214085e</sha1>
                    <md5>add18b9f953221ff565cf7a34aac0ed9</md5>
                </relatedDependency>
            </relatedDependencies>
            <projectReferences>
                <projectReference>package-lock.json: transitive</projectReference>
            </projectReferences>
            <evidenceCollected>
                <evidence type="vendor" confidence="HIGH">
                    <source>package.json</source>
                    <name>name</name>
                    <value>yargs-parser</value>
                </evidence>
                <evidence type="product" confidence="HIGHEST">
                    <source>package.json</source>
                    <name>name</name>
                    <value>yargs-parser</value>
                </evidence>
                <evidence type="version" confidence="HIGHEST">
                    <source>package.json</source>
                    <name>version</name>
                    <value>5.0.0</value>
                </evidence>
            </evidenceCollected>
            <identifiers>
                <package confidence="HIGHEST">
                    <id>pkg:npm/yargs-parser@5.0.0</id>
                    <url>https://ossindex.sonatype.org/component/pkg:npm/yargs-parser@5.0.0</url>
                </package>
            </identifiers>
            <vulnerabilities>
                <vulnerability source="NPM">
                    <name>1500</name>
                    <severity unscored="true">low</severity>
                    <description>Affected versions of `yargs-parser` are vulnerable to prototype pollution. Arguments are not properly sanitized, allowing an attacker to modify the prototype of `Object`, causing the addition or modification of an existing property that will exist on all objects.Parsing the argument `--foo.__proto__.bar baz&apos;` adds a `bar` property with value `baz` to all objects. This is only exploitable if attackers have control over the arguments being passed to `yargs-parser`.</description>
                    <references>
                        <reference>
                            <source>Advisory 1500: Prototype Pollution</source>
                            <name>- [Snyk Report](https://snyk.io/vuln/SNYK-JS-YARGSPARSER-560381)</name>
                        </reference>
                    </references>
                    <vulnerableSoftware>
                        <software>cpe:2.3:a:*:yargs-parser:\\&lt;13.1.2\\|\\|\\&gt;\\=14.0.0\\&lt;15.0.1\\|\\|\\&gt;\\=16.0.0\\&lt;18.1.2:*:*:*:*:*:*:*</software>
                    </vulnerableSoftware>
                </vulnerability>
                <vulnerability source="OSSINDEX">
                    <name>CVE-2020-7608</name>
                    <severity>HIGH</severity>
                    <cvssV3>
                        <baseScore>7.5</baseScore>
                        <attackVector>N</attackVector>
                        <attackComplexity>L</attackComplexity>
                        <privilegesRequired>N</privilegesRequired>
                        <userInteraction>N</userInteraction>
                        <scope>U</scope>
                        <confidentialityImpact>N</confidentialityImpact>
                        <integrityImpact>H</integrityImpact>
                        <availabilityImpact>N</availabilityImpact>
                        <baseSeverity>HIGH</baseSeverity>
                    </cvssV3>
                    <description>yargs-parser could be tricked into adding or modifying properties of Object.prototype using a &quot;__proto__&quot; payload.</description>
                    <references>
                        <reference>
                            <source>OSSINDEX</source>
                            <url>https://ossindex.sonatype.org/vuln/b7740d41-fc85-4d22-8af5-5a3159e114ea?component-type=npm&amp;component-name=yargs-parser</url>
                            <name>[CVE-2020-7608] yargs-parser could be tricked into adding or modifying properties of Object.prot...</name>
                        </reference>
                    </references>
                    <vulnerableSoftware>
                        <software vulnerabilityIdMatched="true">cpe:2.3:a:*:yargs-parser:5.0.0:*:*:*:*:*:*:*</software>
                    </vulnerableSoftware>
                </vulnerability>
                <vulnerability source="OSSINDEX">
                    <name>CWE-400: Uncontrolled Resource Consumption (&apos;Resource Exhaustion&apos;)</name>
                    <severity>HIGH</severity>
                    <cvssV3>
                        <baseScore>7.5</baseScore>
                        <attackVector>N</attackVector>
                        <attackComplexity>L</attackComplexity>
                        <privilegesRequired>N</privilegesRequired>
                        <userInteraction>N</userInteraction>
                        <scope>U</scope>
                        <confidentialityImpact>N</confidentialityImpact>
                        <integrityImpact>N</integrityImpact>
                        <availabilityImpact>H</availabilityImpact>
                        <baseSeverity>HIGH</baseSeverity>
                    </cvssV3>
                    <cwes>
                        <cwe>CWE-400</cwe>
                    </cwes>
                    <description>The software does not properly restrict the size or amount of resources that are requested or influenced by an actor, which can be used to consume more resources than intended.</description>
                    <references>
                        <reference>
                            <source>OSSINDEX</source>
                            <url>https://ossindex.sonatype.org/vuln/7ccaaed0-205b-4382-a963-8a30a0b151b1?component-type=npm&amp;component-name=yargs-parser</url>
                            <name>CWE-400: Uncontrolled Resource Consumption (&apos;Resource Exhaustion&apos;)</name>
                        </reference>
                    </references>
                    <vulnerableSoftware>
                        <software vulnerabilityIdMatched="true">cpe:2.3:a:*:yargs-parser:5.0.0:*:*:*:*:*:*:*</software>
                    </vulnerableSoftware>
                </vulnerability>
            </vulnerabilities>
        </dependency>
        <dependency>
            <fileName>adapter-ear2.ear: dom4j-2.1.1.jar</fileName>
            <filePath>C:\\Projectestproject\\libraries\\component2.dll</filePath>
            <md5>21b24bc199530e07cb15d93c7f929f04</md5>
            <sha1>a29f196740ab608199488c574f536529b5c21242</sha1>
            <evidenceCollected>
                <evidence type="vendor" confidence="HIGH">
                    <source>file</source>
                    <name>name</name>
                    <value>org.jdom</value>
                </evidence>
                <evidence type="product" confidence="HIGH">
                    <source>file</source>
                    <name>name</name>
                    <value>dom4j</value>
                </evidence>
            </evidenceCollected>
            <identifiers>
                <identifiers>
                    <package confidence="HIGH">
                        <id>pkg:maven/org.dom4j/dom4j@2.1.1.redhat-00001</id>
                        <url>https://ossindex.sonatype.org/component/pkg:maven/org.dom4j/dom4j@2.1.1.redhat-00001</url>
                    </package>
                    <vulnerabilityIds confidence="HIGHEST">
                        <id>cpe:2.3:a:dom4j_project:dom4j:2.1.1.hat-00001:*:*:*:*:*:*:*</id>
                        <url>https://nvd.nist.gov/vuln/search/results?form_type=Advanced&amp;results_type=overview&amp;search_type=all&amp;cpe_vendor=cpe%3A%2F%3Adom4j_project&amp;cpe_product=cpe%3A%2F%3Adom4j_project%3Adom4j&amp;cpe_version=cpe%3A%2F%3Adom4j_project%3Adom4j%3A2.1.1.hat-00001</url>
                    </vulnerabilityIds>
                </identifiers>
                <identifier type="cpe" confidence="HIGHEST">
                    <name>cpe:/a:apache:xalan-java:2.7.1</name>
                    <url>https://web.nvd.nist.gov/view/vuln/search-results?adv_search=true&amp;cves=on&amp;cpe_version=cpe%3A%2Fa%3Aapache%3Axalan-java%3A2.7.1</url>
                </identifier>
                <identifier type="maven" confidence="HIGHEST">
                    <name>xalan:serializer:2.7.1</name>
                    <url>https://search.maven.org/remotecontent?filepath=xalan/serializer/2.7.1/serializer-2.7.1.jar</url>
                </identifier>
            </identifiers>
            <vulnerabilities>
                <vulnerability>
                    <name>CVE-0000-0001</name>
                    <cvssScore>7.5</cvssScore>
                    <cvssAccessVector>NETWORK</cvssAccessVector>
                    <cvssAccessComplexity>LOW</cvssAccessComplexity>
                    <cvssAuthenticationr>NONE</cvssAuthenticationr>
                    <cvssConfidentialImpact>PARTIAL</cvssConfidentialImpact>
                    <cvssIntegrityImpact>PARTIAL</cvssIntegrityImpact>
                    <cvssAvailabilityImpact>PARTIAL</cvssAvailabilityImpact>
                    <severity>High</severity>
                    <cwe>CWE-00 Bad Vulnerability</cwe>
                    <description>Description of a bad vulnerability.</description>
                    <references>
                        <reference>
                            <source>Reference1</source>
                            <url>http://localhost/badvulnerability.htm</url>
                            <name>Reference Name</name>
                        </reference>
                        <reference>
                            <source>MISC</source>
                            <url>http://localhost2/reference_for_badvulnerability.pdf</url>
                            <name>Reference for a bad vulnerability</name>
                        </reference>
                    </references>
                    <vulnerableSoftware>
                        <software>cpe:/a:component2:component2:1.0</software>
                    </vulnerableSoftware>
                </vulnerability>
            </vulnerabilities>
        </dependency>
        <dependency>
            <fileName>adapter-ear3.ear: dom4j-2.1.1.jar</fileName>
            <filePath>C:\\Projectestproject\\libraries\\component2.dll</filePath>
            <md5>21b24bc199530e07cb15d93c7f929f04</md5>
            <sha1>a29f196740ab608199488c574f536529b5c21242</sha1>
            <evidenceCollected>
                <evidence type="version" confidence="HIGH">
                    <source>file</source>
                    <name>name</name>
                    <value>2.1.1</value>
                </evidence>
                <evidence type="product" confidence="HIGH">
                    <source>file</source>
                    <name>name</name>
                    <value>dom4j</value>
                </evidence>
            </evidenceCollected>
            <vulnerabilities>
                <vulnerability>
                    <name>CVE-0000-0001</name>
                    <cvssScore>7.5</cvssScore>
                    <cvssAccessVector>NETWORK</cvssAccessVector>
                    <cvssAccessComplexity>LOW</cvssAccessComplexity>
                    <cvssAuthenticationr>NONE</cvssAuthenticationr>
                    <cvssConfidentialImpact>PARTIAL</cvssConfidentialImpact>
                    <cvssIntegrityImpact>PARTIAL</cvssIntegrityImpact>
                    <cvssAvailabilityImpact>PARTIAL</cvssAvailabilityImpact>
                    <severity>High</severity>
                    <cwe>CWE-00 Bad Vulnerability</cwe>
                    <description>Description of a bad vulnerability.</description>
                    <references>
                        <reference>
                            <source>Reference1</source>
                            <url>http://localhost/badvulnerability.htm</url>
                            <name>Reference Name</name>
                        </reference>
                        <reference>
                            <source>MISC</source>
                            <url>http://localhost2/reference_for_badvulnerability.pdf</url>
                            <name>Reference for a bad vulnerability</name>
                        </reference>
                    </references>
                    <vulnerableSoftware>
                        <software>cpe:/a:component2:component2:1.0</software>
                    </vulnerableSoftware>
                </vulnerability>
            </vulnerabilities>
        </dependency>
        <dependency>
            <fileName>adapter-ear4.ear: liquibase-core-3.5.3.jar: jquery.js</fileName>
            <filePath>C:\\Projectestproject\\libraries\\component3.dll</filePath>
            <md5>21b24bc199530e07cb15d93c7f929f03</md5>
            <sha1>a29f196740ab608199488c574f536529b5c21243</sha1>
            <evidenceCollected>
                <evidence type="version" confidence="HIGH">
                    <source>file</source>
                    <name>name</name>
                    <value>3.1.1</value>
                </evidence>
                <evidence type="product" confidence="HIGH">
                    <source>file</source>
                    <name>name</name>
                    <value>jquery</value>
                </evidence>
            </evidenceCollected>
            <vulnerabilities>
                <vulnerability>
                    <name>CVE-0000-0001</name>
                    <cvssScore>7.5</cvssScore>
                    <cvssAccessVector>NETWORK</cvssAccessVector>
                    <cvssAccessComplexity>LOW</cvssAccessComplexity>
                    <cvssAuthenticationr>NONE</cvssAuthenticationr>
                    <cvssConfidentialImpact>PARTIAL</cvssConfidentialImpact>
                    <cvssIntegrityImpact>PARTIAL</cvssIntegrityImpact>
                    <cvssAvailabilityImpact>PARTIAL</cvssAvailabilityImpact>
                    <severity>High</severity>
                    <cwe>CWE-00 Bad Vulnerability</cwe>
                    <description>Description of a bad vulnerability.</description>
                    <references>
                        <reference>
                            <source>Reference1</source>
                            <url>http://localhost/badvulnerability.htm</url>
                            <name>Reference Name</name>
                        </reference>
                        <reference>
                            <source>MISC</source>
                            <url>http://localhost2/reference_for_badvulnerability.pdf</url>
                            <name>Reference for a bad vulnerability</name>
                        </reference>
                    </references>
                    <vulnerableSoftware>
                        <software>cpe:/a:component3:component3:1.0</software>
                    </vulnerableSoftware>
                </vulnerability>
            </vulnerabilities>
        </dependency>
    </dependencies>
</analysis>
 """
        testfile = TestFile("dependency-check-report.xml", content)
        parser = DependencyCheckParser()
        findings = parser.get_findings(testfile, Test())
        items = findings
        self.assertEqual(9, len(items))
        # test also different component_name formats

        # identifier -> package url java + 2 relateddependencies
        self.assertEqual(
            items[0].title, "adapter-ear1.ear: dom4j-2.1.1.jar | CVE-0000-0001"
        )
        self.assertEqual(items[0].component_name, "org.dom4j:dom4j")
        self.assertEqual(items[0].component_version, "2.1.1.redhat-00001")
        self.assertEqual(items[0].description, "Description of a bad vulnerability.")
        self.assertEqual(items[0].severity, "High")
        self.assertEqual(items[0].file_path, "adapter-ear1.ear: dom4j-2.1.1.jar")

        self.assertEqual(
            items[1].title, "adapter-ear8.ear: dom4j-2.1.1.jar | CVE-0000-0001"
        )
        self.assertEqual(items[1].component_name, "org.dom4j:dom4j")
        self.assertEqual(items[1].component_version, "2.1.1.redhat-00001")
        self.assertEqual(items[1].description, "Description of a bad vulnerability.")
        self.assertEqual(items[1].severity, "High")
        self.assertEqual(items[1].file_path, "adapter-ear8.ear: dom4j-2.1.1.jar")

        self.assertEqual(
            items[2].title,
            "adapter-ear1.ear: dom4j-extensions-2.1.1.jar | CVE-0000-0001",
        )
        self.assertEqual(items[2].component_name, "org.dom4j:dom4j")
        self.assertEqual(items[2].component_version, "2.1.1.redhat-00001")
        self.assertEqual(items[2].description, "Description of a bad vulnerability.")
        self.assertEqual(items[2].severity, "High")
        self.assertEqual(
            items[2].file_path, "adapter-ear1.ear: dom4j-extensions-2.1.1.jar"
        )

        # identifier -> package url javascript, no vulnerabilitids, 3 vulnerabilities, relateddependencies without filename (pre v6.0.0)
        self.assertEqual(items[3].title, "yargs-parser:5.0.0 | 1500")
        self.assertEqual(items[3].component_name, "yargs-parser")
        self.assertEqual(items[3].component_version, "5.0.0")
        # assert fails due to special characters, not too important
        # self.assertEqual(items[1].description, "Affected versions of `yargs-parser` are vulnerable to prototype pollution. Arguments are not properly sanitized, allowing an attacker to modify the prototype of `Object`, causing the addition or modification of an existing property that will exist on all objects.Parsing the argument `--foo.__proto__.bar baz&apos;` adds a `bar` property with value `baz` to all objects. This is only exploitable if attackers have control over the arguments being passed to `yargs-parser`.")
        self.assertEqual(items[3].severity, "Low")
        self.assertEqual(items[3].file_path, "yargs-parser:5.0.0")

        self.assertEqual(items[4].title, "yargs-parser:5.0.0 | CVE-2020-7608")
        self.assertEqual(items[4].component_name, "yargs-parser")
        self.assertEqual(items[4].component_version, "5.0.0")
        self.assertEqual(
            items[4].description,
            'yargs-parser could be tricked into adding or modifying properties of Object.prototype using a "__proto__" payload.',
        )
        self.assertEqual(items[4].severity, "High")
        self.assertEqual(items[4].file_path, "yargs-parser:5.0.0")

        self.assertEqual(
            items[5].title,
            "yargs-parser:5.0.0 | CWE-400: Uncontrolled Resource Consumption ('Resource Exhaustion')",
        )
        self.assertEqual(items[5].component_name, "yargs-parser")
        self.assertEqual(items[5].component_version, "5.0.0")
        self.assertEqual(
            items[5].description,
            "The software does not properly restrict the size or amount of resources that are requested or influenced by an actor, which can be used to consume more resources than intended.",
        )
        self.assertEqual(items[5].severity, "High")
        self.assertEqual(items[5].file_path, "yargs-parser:5.0.0")

        # identifier -> cpe java
        self.assertEqual(
            items[6].title, "adapter-ear2.ear: dom4j-2.1.1.jar | CVE-0000-0001"
        )
        self.assertEqual(items[6].component_name, "org.dom4j:dom4j")
        self.assertEqual(items[6].component_version, "2.1.1.redhat-00001")
        self.assertEqual(items[6].severity, "High")
        self.assertEqual(items[6].file_path, "adapter-ear2.ear: dom4j-2.1.1.jar")

        # identifier -> maven java
        self.assertEqual(
            items[7].title, "adapter-ear3.ear: dom4j-2.1.1.jar | CVE-0000-0001"
        )
        self.assertEqual(items[7].component_name, "dom4j")
        self.assertEqual(items[7].component_version, "2.1.1")
        self.assertEqual(items[7].severity, "High")

        # evidencecollected -> single product + single verison javascript
        self.assertEqual(
            items[8].title,
            "adapter-ear4.ear: liquibase-core-3.5.3.jar: jquery.js | CVE-0000-0001",
        )
        self.assertEqual(items[8].component_name, "jquery")
        self.assertEqual(items[8].component_version, "3.1.1")
        self.assertEqual(items[8].severity, "High")

        # evidencecollected -> multiple product + multiple version
        # TODO? Seems like since v6.0.0 there's always a packageurl


# example with multiple evidencecollected
# <evidenceCollected>
#     <evidence type="vendor" confidence="MEDIUM">
#         <source>pom</source>
#         <name>parent-groupid</name>
#         <value>org.jboss</value>
#     </evidence>
#     <evidence type="vendor" confidence="LOW">
#         <source>Manifest</source>
#         <name>specification-vendor</name>
#         <value>JBoss by Red Hat</value>
#     </evidence>
#     <evidence type="vendor" confidence="LOW">
#         <source>pom</source>
#         <name>artifactid</name>
#         <value>dom4j</value>
#     </evidence>
#     <evidence type="vendor" confidence="HIGH">
#         <source>file</source>
#         <name>name</name>
#         <value>dom4j</value>
#     </evidence>
#     <evidence type="vendor" confidence="LOW">
#         <source>Manifest</source>
#         <name>os-arch</name>
#         <value>amd64</value>
#     </evidence>
#     <evidence type="vendor" confidence="MEDIUM">
#         <source>Manifest</source>
#         <name>os-name</name>
#         <value>Linux</value>
#     </evidence>
#     <evidence type="vendor" confidence="HIGH">
#         <source>Manifest</source>
#         <name>Implementation-Vendor</name>
#         <value>JBoss by Red Hat</value>
#     </evidence>
#     <evidence type="vendor" confidence="HIGH">
#         <source>pom</source>
#         <name>name</name>
#         <value>dom4j</value>
#     </evidence>
#     <evidence type="vendor" confidence="MEDIUM">
#         <source>Manifest</source>
#         <name>java-vendor</name>
#         <value>Oracle Corporation</value>
#     </evidence>
#     <evidence type="vendor" confidence="LOW">
#         <source>pom</source>
#         <name>parent-artifactid</name>
#         <value>jboss-parent</value>
#     </evidence>
#     <evidence type="vendor" confidence="HIGHEST">
#         <source>jar</source>
#         <name>package name</name>
#         <value>dom4j</value>
#     </evidence>
#     <evidence type="vendor" confidence="LOW">
#         <source>Manifest</source>
#         <name>implementation-url</name>
#         <value>http://dom4j.github.io/</value>
#     </evidence>
#     <evidence type="vendor" confidence="MEDIUM">
#         <source>Manifest</source>
#         <name>Implementation-Vendor-Id</name>
#         <value>org.dom4j</value>
#     </evidence>
#     <evidence type="vendor" confidence="HIGHEST">
#         <source>pom</source>
#         <name>groupid</name>
#         <value>dom4j</value>
#     </evidence>
#     <evidence type="vendor" confidence="HIGHEST">
#         <source>hint analyzer</source>
#         <name>vendor</name>
#         <value>redhat</value>
#     </evidence>
#     <evidence type="vendor" confidence="HIGHEST">
#         <source>pom</source>
#         <name>url</name>
#         <value>http://dom4j.github.io/</value>
#     </evidence>
#     <evidence type="product" confidence="MEDIUM">
#         <source>pom</source>
#         <name>parent-groupid</name>
#         <value>org.jboss</value>
#     </evidence>
#     <evidence type="product" confidence="HIGH">
#         <source>Manifest</source>
#         <name>Implementation-Title</name>
#         <value>dom4j</value>
#     </evidence>
#     <evidence type="product" confidence="HIGH">
#         <source>file</source>
#         <name>name</name>
#         <value>dom4j</value>
#     </evidence>
#     <evidence type="product" confidence="LOW">
#         <source>Manifest</source>
#         <name>os-arch</name>
#         <value>amd64</value>
#     </evidence>
#     <evidence type="product" confidence="MEDIUM">
#         <source>Manifest</source>
#         <name>os-name</name>
#         <value>Linux</value>
#     </evidence>
#     <evidence type="product" confidence="HIGHEST">
#         <source>pom</source>
#         <name>artifactid</name>
#         <value>dom4j</value>
#     </evidence>
#     <evidence type="product" confidence="MEDIUM">
#         <source>pom</source>
#         <name>parent-artifactid</name>
#         <value>jboss-parent</value>
#     </evidence>
#     <evidence type="product" confidence="HIGH">
#         <source>pom</source>
#         <name>name</name>
#         <value>dom4j</value>
#     </evidence>
#     <evidence type="product" confidence="HIGHEST">
#         <source>jar</source>
#         <name>package name</name>
#         <value>dom4j</value>
#     </evidence>
#     <evidence type="product" confidence="LOW">
#         <source>Manifest</source>
#         <name>implementation-url</name>
#         <value>http://dom4j.github.io/</value>
#     </evidence>
#     <evidence type="product" confidence="HIGHEST">
#         <source>jar</source>
#         <name>package name</name>
#         <value>io</value>
#     </evidence>
#     <evidence type="product" confidence="MEDIUM">
#         <source>pom</source>
#         <name>url</name>
#         <value>http://dom4j.github.io/</value>
#     </evidence>
#     <evidence type="product" confidence="HIGHEST">
#         <source>pom</source>
#         <name>groupid</name>
#         <value>dom4j</value>
#     </evidence>
#     <evidence type="product" confidence="MEDIUM">
#         <source>Manifest</source>
#         <name>specification-title</name>
#         <value>dom4j</value>
#     </evidence>
#     <evidence type="version" confidence="HIGHEST">
#         <source>pom</source>
#         <name>version</name>
#         <value>2.1.1.redhat-00001</value>
#     </evidence>
#     <evidence type="version" confidence="HIGH">
#         <source>Manifest</source>
#         <name>Implementation-Version</name>
#         <value>2.1.1.redhat-00001</value>
#     </evidence>
#     <evidence type="version" confidence="LOW">
#         <source>pom</source>
#         <name>parent-version</name>
#         <value>2.1.1.redhat-00001</value>
#     </evidence>
# </evidenceCollected>
# <identifiers>
#     <package confidence="HIGH">
#         <id>pkg:maven/org.dom4j/dom4j@2.1.1.redhat-00001</id>
#         <url>https://ossindex.sonatype.org/component/pkg:maven/org.dom4j/dom4j@2.1.1.redhat-00001</url>
#     </package>
#     <vulnerabilityIds confidence="HIGHEST">
#         <id>cpe:2.3:a:dom4j_project:dom4j:2.1.1.hat-00001:*:*:*:*:*:*:*</id>
#         <url>https://nvd.nist.gov/vuln/search/results?form_type=Advanced&amp;results_type=overview&amp;search_type=all&amp;cpe_vendor=cpe%3A%2F%3Adom4j_project&amp;cpe_product=cpe%3A%2F%3Adom4j_project%3Adom4j&amp;cpe_version=cpe%3A%2F%3Adom4j_project%3Adom4j%3A2.1.1.hat-00001</url>
#     </vulnerabilityIds>
# </identifiers>
