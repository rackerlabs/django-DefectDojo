__author__ = "Aaron Weaver"

import json
from datetime import datetime

from dojo.models import Endpoint, Finding


class SSLlabsParser(object):
    def get_findings(self, filename, test):
        tree = filename.read()
        try:
            data = json.loads(str(tree, "utf-8"))
        except:
            data = json.loads(tree)

        find_date = datetime.now()
        dupes = {}

        for host in data:
            ssl_endpoints = []
            hostName = ""
            if "host" in host:
                hostName = host["host"]

            if "endpoints" in host:
                ssl_endpoints = host["endpoints"]
            for endpoints in ssl_endpoints:
                categories = ""
                language = ""
                mitigation = "N/A"
                impact = "N/A"
                references = ""
                findingdetail = ""
                title = ""
                group = ""
                status = ""
                port = ""
                ipAddress = ""
                protocol = ""

                grade = ""
                if "grade" in endpoints:
                    grade = endpoints["grade"]
                port = ""
                if "port" in host:
                    port = host["port"]
                ipAddress = ""
                if "ipAddress" in endpoints:
                    ipAddress = endpoints["ipAddress"]
                protocol = ""
                if "protocol" in host:
                    protocol = host["protocol"]

                title = "TLS Grade '%s' for %s" % (grade, hostName)

                sev = self.getCriticalityRating(grade)
                description = "%s \n\n" % title
                cert = ""
                if "cert" in endpoints["details"]:
                    cert = endpoints["details"]["cert"]
                    description = "%sCertifcate Subject: %s\n" % (
                        description,
                        cert["subject"],
                    )
                    description = "%sIssuer Subject: %s\n" % (
                        description,
                        cert["issuerSubject"],
                    )
                    description = "%sSignature Algorithm: %s\n" % (
                        description,
                        cert["sigAlg"],
                    )
                else:
                    for cert in host["certs"]:
                        description = "%sCertifcate Subject: %s\n" % (
                            description,
                            cert["subject"],
                        )
                        description = "%sIssuer Subject: %s\n" % (
                            description,
                            cert["issuerSubject"],
                        )
                        description = "%sSignature Algorithm: %s\n" % (
                            description,
                            cert["sigAlg"],
                        )

                protocol_str = ""
                for protocol_data in endpoints["details"]["protocols"]:
                    protocol_str += (
                        protocol_data["name"] + " " + protocol_data["version"] + "\n"
                    )

                if protocol_str:
                    description += "\nProtocols:\n" + protocol_str

                description += "\nSuites List: "
                suite_info = ""
                try:
                    if "list" in endpoints["details"]["suites"]:
                        for suites in endpoints["details"]["suites"]["list"]:
                            suite_info = suite_info + self.suite_data(suites)
                    elif "suites" in endpoints["details"]:
                        for item in endpoints["details"]["suites"]:
                            for suites in item["list"]:
                                suite_info = suite_info + self.suite_data(suites)
                except:
                    suite_info = "Not provided." + "\n\n"

                description += suite_info
                description += "Additional Information:\n\n"
                if "serverSignature" in endpoints["details"]:
                    description += (
                        "serverSignature: "
                        + endpoints["details"]["serverSignature"]
                        + "\n"
                    )
                if "prefixDelegation" in endpoints["details"]:
                    description += (
                        "prefixDelegation: "
                        + str(endpoints["details"]["prefixDelegation"])
                        + "\n"
                    )
                if "nonPrefixDelegation" in endpoints["details"]:
                    description += (
                        "nonPrefixDelegation: "
                        + str(endpoints["details"]["nonPrefixDelegation"])
                        + "\n"
                    )
                if "vulnBeast" in endpoints["details"]:
                    description += (
                        "vulnBeast: " + str(endpoints["details"]["vulnBeast"]) + "\n"
                    )
                if "renegSupport" in endpoints["details"]:
                    description += (
                        "renegSupport: "
                        + str(endpoints["details"]["renegSupport"])
                        + "\n"
                    )
                if "stsStatus" in endpoints["details"]:
                    description += (
                        "stsStatus: " + endpoints["details"]["stsStatus"] + "\n"
                    )
                if "stsResponseHeader" in endpoints["details"]:
                    description += (
                        "stsResponseHeader: "
                        + endpoints["details"]["stsResponseHeader"]
                        + "\n"
                    )
                if "stsPreload" in endpoints["details"]:
                    description += (
                        "stsPreload: " + str(endpoints["details"]["stsPreload"]) + "\n"
                    )
                if "sessionResumption" in endpoints["details"]:
                    description += (
                        "sessionResumption: "
                        + str(endpoints["details"]["sessionResumption"])
                        + "\n"
                    )
                if "compressionMethods" in endpoints["details"]:
                    description += (
                        "compressionMethods: "
                        + str(endpoints["details"]["compressionMethods"])
                        + "\n"
                    )
                if "supportsNpn" in endpoints["details"]:
                    description += (
                        "supportsNpn: "
                        + str(endpoints["details"]["supportsNpn"])
                        + "\n"
                    )
                if "supportsAlpn" in endpoints["details"]:
                    description += (
                        "supportsAlpn: "
                        + str(endpoints["details"]["supportsAlpn"])
                        + "\n"
                    )
                if "sessionTickets" in endpoints["details"]:
                    description += (
                        "sessionTickets: "
                        + str(endpoints["details"]["sessionTickets"])
                        + "\n"
                    )
                if "ocspStapling" in endpoints["details"]:
                    description += (
                        "ocspStapling: "
                        + str(endpoints["details"]["ocspStapling"])
                        + "\n"
                    )
                if "sniRequired" in endpoints["details"]:
                    description += (
                        "sniRequired: "
                        + str(endpoints["details"]["sniRequired"])
                        + "\n"
                    )
                if "httpStatusCode" in endpoints["details"]:
                    description += (
                        "httpStatusCode: "
                        + str(endpoints["details"]["httpStatusCode"])
                        + "\n"
                    )
                if "supportsRc4" in endpoints["details"]:
                    description += (
                        "supportsRc4: "
                        + str(endpoints["details"]["supportsRc4"])
                        + "\n"
                    )
                if "rc4WithModern" in endpoints["details"]:
                    description += (
                        "rc4WithModern: "
                        + str(endpoints["details"]["rc4WithModern"])
                        + "\n"
                    )
                if "forwardSecrecy" in endpoints["details"]:
                    description += (
                        "forwardSecrecy: "
                        + str(endpoints["details"]["forwardSecrecy"])
                        + "\n"
                    )
                if "protocolIntolerance" in endpoints["details"]:
                    description += (
                        "protocolIntolerance: "
                        + str(endpoints["details"]["protocolIntolerance"])
                        + "\n"
                    )
                if "miscIntolerance" in endpoints["details"]:
                    description += (
                        "miscIntolerance: "
                        + str(endpoints["details"]["miscIntolerance"])
                        + "\n"
                    )
                if "heartbleed" in endpoints["details"]:
                    description += (
                        "heartbleed: " + str(endpoints["details"]["heartbleed"]) + "\n"
                    )
                if "heartbeat" in endpoints["details"]:
                    description += (
                        "heartbeat: " + str(endpoints["details"]["heartbeat"]) + "\n"
                    )
                if "openSslCcs" in endpoints["details"]:
                    description += (
                        "openSslCcs: " + str(endpoints["details"]["openSslCcs"]) + "\n"
                    )
                if "openSSLLuckyMinus20" in endpoints["details"]:
                    description += (
                        "openSSLLuckyMinus20: "
                        + str(endpoints["details"]["openSSLLuckyMinus20"])
                        + "\n"
                    )
                if "poodle" in endpoints["details"]:
                    description += (
                        "poodle: " + str(endpoints["details"]["poodle"]) + "\n"
                    )
                if "poodleTls" in endpoints["details"]:
                    description += (
                        "poodleTls: " + str(endpoints["details"]["poodleTls"]) + "\n"
                    )
                if "fallbackScsv" in endpoints["details"]:
                    description += (
                        "fallbackScsv: "
                        + str(endpoints["details"]["fallbackScsv"])
                        + "\n"
                    )
                if "freak" in endpoints["details"]:
                    description += "freak: " + str(endpoints["details"]["freak"]) + "\n"
                if "hasSct" in endpoints["details"]:
                    description += (
                        "hasSct: " + str(endpoints["details"]["hasSct"]) + "\n"
                    )

                """
                cName = ""
                for commonNames in cert["commonNames"]:
                    cName = "%s %s \n" % (cName, commonNames)

                aName = ""
                for altNames in cert["altNames"]:
                    aName = "%s %s \n" % (aName, altNames)
                """

                protoName = ""
                for protocols in endpoints["details"]["protocols"]:
                    protoName = "%s %s %s\n" % (
                        protoName,
                        protocols["name"],
                        protocols["version"],
                    )

                dupe_key = hostName + grade

                if dupe_key in dupes:
                    find = dupes[dupe_key]
                    if description is not None:
                        find.description += description
                else:
                    find = Finding(
                        title=title,
                        cwe=310,  # Cryptographic Issues
                        test=test,
                        active=False,
                        verified=False,
                        description=description,
                        severity=sev,
                        numerical_severity=Finding.get_numerical_severity(sev),
                        mitigation=mitigation,
                        impact=impact,
                        references=references,
                        url=host,
                        date=find_date,
                        dynamic_finding=True,
                    )
                    dupes[dupe_key] = find
                    find.unsaved_endpoints = list()

                find.unsaved_endpoints.append(
                    Endpoint(
                        host=ipAddress, fqdn=hostName, port=port, protocol=protocol
                    )
                )

            self.items = list(dupes.values())

    # Criticality rating
    # Grades: https://github.com/ssllabs/research/wiki/SSL-Server-Rating-Guide
    # A - Info, B - Medium, C - High, D/F/M/T - Critical
    def getCriticalityRating(self, rating):
        criticality = "Info"
        if "A" in rating:
            criticality = "Info"
        elif "B" in rating:
            criticality = "Medium"
        elif "C" in rating:
            criticality = "High"
        elif "D" in rating or "F" in rating or "M" in rating or "T" in rating:
            criticality = "Critical"

        return criticality

    def suite_data(self, suites):
        suite_info = ""
        suite_info += suites["name"] + "\n"
        suite_info += "Cipher Strength: " + str(suites["cipherStrength"]) + "\n"
        if "ecdhBits" in suites:
            suite_info += "ecdhBits: " + str(suites["ecdhBits"]) + "\n"
        if "ecdhStrength" in suites:
            suite_info += "ecdhStrength: " + str(suites["ecdhStrength"])
        suite_info += "\n\n"
        return suite_info
