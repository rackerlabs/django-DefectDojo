import requests


def print_map(map, tab):
    for key, value in map.items():
        if isinstance(key, dict):
            print(tab, print_map(key, tab + "\t"))
        elif key is not None:
            print(tab, "Key :: ", key)

        if isinstance(value, dict):
            print(tab, print_map(value, tab + "\t"))
        elif value is not None:
            print(tab, "Value :: ", value)


class RiskReconAPI:
    def __init__(self, api_key, endpoint, data):
        self.key = api_key
        self.url = endpoint
        self.data = data
        self.findings = []
        self.toe_map = {}

        if not self.key:
            raise Exception(
                "Please supply a Risk Recon API key. \n"
                "This can be generated in the system admin panel. \n"
                "See https://defectdojo.readthedocs.io/en/latest/integrations.html#risk-recon-api-importer \n"
            )
        if not self.url:
            raise Exception(
                "Please supply a Risk Recon API url. \n"
                "A general url is https://api.riskrecon.com/v1/ \n"
                "See https://defectdojo.readthedocs.io/en/latest/integrations.html#risk-recon-api-importer \n"
            )
        if self.url.endswith("/"):
            self.url = endpoint[:-1]
        self.session = requests.Session()
        self.map_toes()
        self.get_findings()

    def map_toes(self):
        response = self.session.get(
            url="{}/toes".format(self.url),
            headers={"accept": "application/json", "Authorization": self.key},
        )

        if response.ok:
            comps = {}
            data = response.json()
            if isinstance(self.data, list):
                for company in self.data:
                    name = company.get("name", None)
                    filters = company.get("filters", None)
                    if name:
                        comps[name] = filters
            name_list = comps.keys()
            for item in data:
                toe_id = item.get("toe_id", None)
                name = item.get("toe_short_name", None)
                if not comps or name in name_list:
                    filters = comps.get(name, None)
                    self.toe_map[toe_id] = filters if filters else self.data
        else:
            raise Exception(
                "Unable to query Target of Evaluations due to {} - {}".format(
                    response.status_code, response.content
                )
            )

    def filter_finding(self, finding):
        filters = self.toe_map[finding["toe_id"]]
        if not filters:
            return False

        for filter_item in filters.keys():
            filter_list = filters.get(filter_item, None)
            if filter_list and finding[filter_item] not in filter_list:
                return True

        return False

    def get_findings(self):
        for toe in self.toe_map.keys():
            response = self.session.get(
                url="{}/findings/{}".format(self.url, toe),
                headers={"accept": "application/json", "Authorization": self.key},
            )

            if response.ok:
                data = response.json()
                for finding in data:
                    if not self.filter_finding(finding):
                        self.findings.append(finding)
            else:
                raise Exception(
                    "Unable to collect findings from toe: {} due to {} - {}".format(
                        toe, response.status_code, response.content
                    )
                )
