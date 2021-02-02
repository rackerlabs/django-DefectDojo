class DefectDojoFinding:
    def __init__(self, **kwargs):
        self.title = kwargs["title"]
        self.date = kwargs["date"]
        self.cwe = kwargs["cwe"]
        self.url = kwargs["url"]
        self.severity = kwargs["severity"]
        self.description = kwargs["description"]
        self.mitigation = kwargs["mitigation"]
        self.impact = kwargs["impact"]
        self.references = kwargs["references"]
        self.false_p = kwargs["false_p"]
        self.dynamic_finding = False

    def __str__(self):
        return ", ".join(
            [
                "{key}={value}".format(key=key, value=self.__dict__.get(key))
                for key in self.__dict__
            ]
        )


class AcunetixScanReport:
    def __init__(self, **kwargs):
        self.Name = kwargs["Name"]
        self.ShortName = kwargs["ShortName"]
        self.StartURL = kwargs["StartURL"]
        self.StartTime = kwargs["StartTime"]
        self.FinishTime = kwargs["FinishTime"]
        self.ScanTime = kwargs["ScanTime"]
        self.Aborted = kwargs["Aborted"]
        self.Responsive = kwargs["Responsive"]
        self.Banner = kwargs["Banner"]
        self.Os = kwargs["Os"]
        self.WebServer = kwargs["WebServer"]
        self.ReportItems = kwargs["ReportItems"]

    def __str__(self):
        return ", ".join(
            [
                "{key}={value}".format(key=key, value=self.__dict__.get(key))
                for key in self.__dict__
            ]
        )

    def __eq__(self, other):
        return self.__dict__ == other.__dict__
