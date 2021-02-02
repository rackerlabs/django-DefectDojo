import hashlib
import json

from dojo.models import Finding


class TruffleHogJSONParser(object):
    def get_findings(self, filename, test):

        data = filename.read()
        self.dupes = dict()
        self.items = ()

        for line in data.splitlines():
            json_data = self.parse_json(line)
            file = json_data["path"]

            reason = json_data["reason"]
            titleText = "Hard Coded " + reason + " in: " + file

            commit = json_data["commit"]
            description = "**Commit:** " + commit.rstrip("\n") + "\n"
            description += "**Commit Hash:** " + json_data["commitHash"] + "\n"
            description += "**Commit Date:** " + json_data["date"] + "\n"
            description += "**Branch:** " + json_data["branch"] + "\n"
            description += "**Reason:** " + json_data["reason"] + "\n"
            description += "**Path:** " + file + "\n"

            severity = "High"
            if reason == "High Entropy":
                severity = "Info"
            elif "Oauth" in reason or "AWS" in reason or "Heroku" in reason:
                severity = "Critical"
            elif reason == "Generic Secret":
                severity = "Medium"

            strings_found = ""
            for string in json_data["stringsFound"]:
                strings_found += string + "\n"

            dupe_key = hashlib.md5((file + reason).encode("utf-8")).hexdigest()
            description += "\n**Strings Found:**\n" + strings_found + "\n"

            if dupe_key in self.dupes:
                finding = self.dupes[dupe_key]
                finding.description = finding.description + description
                self.dupes[dupe_key] = finding
            else:
                self.dupes[dupe_key] = True

                finding = Finding(
                    title=titleText,
                    test=test,
                    cwe=798,
                    active=False,
                    verified=False,
                    description=description,
                    severity=severity,
                    numerical_severity=Finding.get_numerical_severity(severity),
                    mitigation="Secrets and passwords should be stored in a secure vault and/or secure storage.",
                    impact="This weakness can lead to the exposure of resources or functionality to unintended actors, possibly providing attackers with sensitive information or even execute arbitrary code.",
                    references="N/A",
                    file_path=file,
                    url="N/A",
                    dynamic_finding=False,
                    static_finding=True,
                )

                self.dupes[dupe_key] = finding

        self.items = list(self.dupes.values())

    def parse_json(self, json_output):
        try:
            try:
                json_data = json.loads(str(json_output, "utf-8"))
            except:
                json_data = json.loads(json_output)
        except ValueError:
            raise Exception("Invalid format")

        return json_data
