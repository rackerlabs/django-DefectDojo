import json

from dojo.models import Finding
from dojo.tools.semgrep.models import SemgrepJSONResult


class SemgrepJSONParser(object):
    def get_findings(self, filehandle, test):
        tree = json.load(filehandle)
        items = []
        results = tree.get("results")
        for item in results:
            title = item["check_id"]
            semgrep_result = SemgrepJSONResult(
                item["extra"], item["path"], item["start"], item["end"]
            )
            findingItem = Finding(
                title=semgrep_result.title,
                severity=semgrep_result.severity,
                numerical_severity=Finding.get_numerical_severity(
                    semgrep_result.severity
                ),
                description=semgrep_result.message,
                mitigation="N/A",
                file_path=item["path"],
                cwe=semgrep_result.cwe,
                line=semgrep_result.start,
                url="N/A",
                impact="N/A",
                static_finding=True,
                test=test,
            )
            items.append(findingItem)
        return items
