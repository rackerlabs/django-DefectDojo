from collections import namedtuple

# this class can be updated to use @dataclass in Python 3.7
# note that all types are strings except for 'locations' which is a set of strings
BlackduckFinding = namedtuple(
    "BlackduckFinding",
    [
        "vuln_id",
        "description",
        "security_risk",
        "impact",
        "component_name",
        "component_version",
        "vuln_source",
        "url",
        "channel_version_origin_id",
        "component_origin_id",
        "published_date",
        "updated_date",
        "base_score",
        "exploitability",
        "remediation_status",
        "remediation_target_date",
        "remediation_actual_date",
        "remediation_comment",
        "locations",
    ],
)
