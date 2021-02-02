import csv
import hashlib
import io
import re
import socket
from urllib.parse import urlparse

from dateutil.parser import parse

from dojo.models import Endpoint, Finding


class ColumnMappingStrategy(object):

    mapped_column = None

    def __init__(self):
        self.successor = None

    def map_column_value(self, finding, column_value):
        pass

    @staticmethod
    def evaluate_bool_value(column_value):
        if column_value.lower() == "true":
            return True
        elif column_value.lower() == "false":
            return False
        else:
            return None

    def process_column(self, column_name, column_value, finding):

        if column_name.lower() == self.mapped_column and column_value is not None:
            self.map_column_value(finding, column_value)
        elif self.successor is not None:
            self.successor.process_column(column_name, column_value, finding)


class DateColumnMappingStrategy(ColumnMappingStrategy):
    def __init__(self):
        self.mapped_column = "date"
        super(DateColumnMappingStrategy, self).__init__()

    def map_column_value(self, finding, column_value):
        finding.date = parse(column_value).date()


class TitleColumnMappingStrategy(ColumnMappingStrategy):
    def __init__(self):
        self.mapped_column = "title"
        super(TitleColumnMappingStrategy, self).__init__()

    def map_column_value(self, finding, column_value):
        finding.title = column_value


class CweColumnMappingStrategy(ColumnMappingStrategy):
    def __init__(self):
        self.mapped_column = "cweid"
        super(CweColumnMappingStrategy, self).__init__()

    def map_column_value(self, finding, column_value):
        if column_value.isdigit():
            finding.cwe = int(column_value)


class UrlColumnMappingStrategy(ColumnMappingStrategy):
    def __init__(self):
        self.mapped_column = "url"
        super(UrlColumnMappingStrategy, self).__init__()

    def is_valid_ipv4_address(self, address):
        valid = True
        try:
            socket.inet_aton(address.strip())
        except:
            valid = False

        return valid

    def map_column_value(self, finding, column_value):
        url = column_value
        finding.url = url
        o = urlparse(url)

        """
        Todo: Replace this with a centralized parsing function as many of the parsers
        use the same method for parsing urls.

        ParseResult(scheme='http', netloc='www.cwi.nl:80', path='/%7Eguido/Python.html',
                    params='', query='', fragment='')
        """
        if self.is_valid_ipv4_address(url) is False:
            rhost = re.search(
                r"(http|https|ftp)\://([a-zA-Z0-9\.\-]+(\:[a-zA-Z0-9\.&amp;%\$\-]+)*@)*((25[0-5]|2[0-4][0-9]|[0-1]{1}[0-9]{2}|[1-9]{1}[0-9]{1}|[1-9])\.(25[0-5]|2[0-4][0-9]|[0-1]{1}[0-9]{2}|[1-9]{1}[0-9]{1}|[1-9]|0)\.(25[0-5]|2[0-4][0-9]|[0-1]{1}[0-9]{2}|[1-9]{1}[0-9]{1}|[1-9]|0)\.(25[0-5]|2[0-4][0-9]|[0-1]{1}[0-9]{2}|[1-9]{1}[0-9]{1}|[0-9])|localhost|([a-zA-Z0-9\-]+\.)*[a-zA-Z0-9\-]+\.(com|edu|gov|int|mil|net|org|biz|arpa|info|name|pro|aero|coop|museum|[a-zA-Z]{2}))[\:]*([0-9]+)*([/]*($|[a-zA-Z0-9\.\,\?\'\\\+&amp;%\$#\=~_\-]+)).*?$",
                url,
            )

            if rhost:
                protocol = o.scheme
                host = o.netloc
                path = o.path
                query = o.query
                fragment = o.fragment

                port = 80
                if protocol == "https":
                    port = 443

                if rhost.group(11) is not None:
                    port = rhost.group(11)

                try:
                    dupe_endpoint = Endpoint.objects.get(
                        protocol=protocol,
                        host=host + (":" + port) if port is not None else "",
                        query=query,
                        fragment=fragment,
                        path=path,
                        product=finding.test.engagement.product,
                    )
                except:
                    dupe_endpoint = None

                if not dupe_endpoint:
                    endpoint = Endpoint(
                        protocol=protocol,
                        host=host + (":" + str(port)) if port is not None else "",
                        query=query,
                        fragment=fragment,
                        path=path,
                        product=finding.test.engagement.product,
                    )
                else:
                    endpoint = dupe_endpoint

                if not dupe_endpoint:
                    endpoints = [endpoint]
                else:
                    endpoints = [endpoint, dupe_endpoint]

                finding.unsaved_endpoints = endpoints

        # URL is an IP so save as an IP endpoint
        elif self.is_valid_ipv4_address(url) is True:
            try:
                dupe_endpoint = Endpoint.objects.get(
                    protocol=None,
                    host=url,
                    path=None,
                    query=None,
                    fragment=None,
                    product=finding.test.engagement.product,
                )
            except:
                dupe_endpoint = None

            if not dupe_endpoint:
                endpoints = [
                    Endpoint(host=url, product=finding.test.engagement.product)
                ]
            else:
                endpoints = [dupe_endpoint]

            finding.unsaved_endpoints = endpoints


class SeverityColumnMappingStrategy(ColumnMappingStrategy):
    @staticmethod
    def is_valid_severity(severity):
        valid_severity = ("Info", "Low", "Medium", "High", "Critical")
        return severity in valid_severity

    def __init__(self):
        self.mapped_column = "severity"
        super(SeverityColumnMappingStrategy, self).__init__()

    def map_column_value(self, finding, column_value):
        if self.is_valid_severity(column_value):
            finding.severity = column_value
        else:
            finding.severity = "Info"


class DescriptionColumnMappingStrategy(ColumnMappingStrategy):
    def __init__(self):
        self.mapped_column = "description"
        super(DescriptionColumnMappingStrategy, self).__init__()

    def map_column_value(self, finding, column_value):
        finding.description = column_value


class MitigationColumnMappingStrategy(ColumnMappingStrategy):
    def __init__(self):
        self.mapped_column = "mitigation"
        super(MitigationColumnMappingStrategy, self).__init__()

    def map_column_value(self, finding, column_value):
        finding.mitigation = column_value


class ImpactColumnMappingStrategy(ColumnMappingStrategy):
    def __init__(self):
        self.mapped_column = "impact"
        super(ImpactColumnMappingStrategy, self).__init__()

    def map_column_value(self, finding, column_value):
        finding.impact = column_value


class ReferencesColumnMappingStrategy(ColumnMappingStrategy):
    def __init__(self):
        self.mapped_column = "references"
        super(ReferencesColumnMappingStrategy, self).__init__()

    def map_column_value(self, finding, column_value):
        finding.references = column_value


class ActiveColumnMappingStrategy(ColumnMappingStrategy):
    def __init__(self):
        self.mapped_column = "active"
        super(ActiveColumnMappingStrategy, self).__init__()

    def map_column_value(self, finding, column_value):
        finding.active = self.evaluate_bool_value(column_value)


class VerifiedColumnMappingStrategy(ColumnMappingStrategy):
    def __init__(self):
        self.mapped_column = "verified"
        super(VerifiedColumnMappingStrategy, self).__init__()

    def map_column_value(self, finding, column_value):
        finding.verified = self.evaluate_bool_value(column_value)


class FalsePositiveColumnMappingStrategy(ColumnMappingStrategy):
    def __init__(self):
        self.mapped_column = "falsepositive"
        super(FalsePositiveColumnMappingStrategy, self).__init__()

    def map_column_value(self, finding, column_value):
        finding.false_p = self.evaluate_bool_value(column_value)


class DuplicateColumnMappingStrategy(ColumnMappingStrategy):
    def __init__(self):
        self.mapped_column = "duplicate"
        super(DuplicateColumnMappingStrategy, self).__init__()

    def map_column_value(self, finding, column_value):
        finding.duplicate = self.evaluate_bool_value(column_value)


class GenericFindingUploadCsvParser(object):
    def create_chain(self):
        date_column_strategy = DateColumnMappingStrategy()
        title_column_strategy = TitleColumnMappingStrategy()
        cwe_column_strategy = CweColumnMappingStrategy()
        url_column_strategy = UrlColumnMappingStrategy()
        severity_column_strategy = SeverityColumnMappingStrategy()
        description_column_strategy = DescriptionColumnMappingStrategy()
        mitigation_column_strategy = MitigationColumnMappingStrategy()
        impact_column_strategy = ImpactColumnMappingStrategy()
        references_column_strategy = ReferencesColumnMappingStrategy()
        active_column_strategy = ActiveColumnMappingStrategy()
        verified_column_strategy = VerifiedColumnMappingStrategy()
        false_positive_strategy = FalsePositiveColumnMappingStrategy()
        duplicate_strategy = DuplicateColumnMappingStrategy()

        false_positive_strategy.successor = duplicate_strategy
        verified_column_strategy.successor = false_positive_strategy
        active_column_strategy.successor = verified_column_strategy
        references_column_strategy.successor = active_column_strategy
        impact_column_strategy.successor = references_column_strategy
        mitigation_column_strategy.successor = impact_column_strategy
        description_column_strategy.successor = mitigation_column_strategy
        severity_column_strategy.successor = description_column_strategy
        url_column_strategy.successor = severity_column_strategy
        cwe_column_strategy.successor = url_column_strategy
        title_column_strategy.successor = cwe_column_strategy
        date_column_strategy.successor = title_column_strategy

        self.chain = date_column_strategy

    def read_column_names(self, row):
        index = 0
        for column in row:
            self.column_names[index] = column
            index += 1

    def get_findings(self, filename, test, active=False, verified=False):
        self.chain = None
        self.column_names = dict()
        self.create_chain()
        self.active = active
        self.verified = verified
        if filename is None:
            self.items = ()
            return

        content = filename.read()
        if type(content) is bytes:
            content = content.decode("utf-8")
        row_number = 0
        reader = csv.reader(io.StringIO(content), delimiter=",", quotechar='"')

        dupes = dict()
        for row in reader:
            finding = Finding(test=test)

            if row_number == 0:
                self.read_column_names(row)
                row_number += 1
                continue

            column_number = 0
            for column in row:
                self.chain.process_column(
                    self.column_names[column_number], column, finding
                )

                column_number += 1

            if not self.active:
                finding.active = False
            if not self.verified:
                finding.verified = False
            if finding is not None:
                key = hashlib.md5(
                    (
                        finding.severity
                        + "|"
                        + finding.title
                        + "|"
                        + finding.description
                    ).encode("utf-8")
                ).hexdigest()

                if key not in dupes:
                    dupes[key] = finding

            row_number += 1

        return list(dupes.values())
