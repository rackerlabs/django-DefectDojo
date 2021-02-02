import csv
import hashlib
import io
from datetime import datetime

from django.contrib.auth.models import User

from dojo.models import Finding, Notes


class ColumnMappingStrategy(object):

    mapped_column = None

    def __init__(self):
        self.successor = None

    def map_column_value(self, finding, column_value):
        pass

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
        finding.date = datetime.strptime(column_value, "%Y-%m-%d %H:%M:%S").date()


class TitleColumnMappingStrategy(ColumnMappingStrategy):
    def __init__(self):
        self.mapped_column = "title"
        super(TitleColumnMappingStrategy, self).__init__()

    def map_column_value(self, finding, column_value):
        finding.title = column_value


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


class NotesColumnMappingStrategy(ColumnMappingStrategy):
    def __init__(self):
        self.mapped_column = "notes"
        super(NotesColumnMappingStrategy, self).__init__()

    def map_column_value(self, finding, column_value):
        if column_value != "":
            user = User.objects.all().first()
            note = Notes(entry=column_value, author=user)
            note.save()
            finding.reporter = user.id
            finding.save()
            finding.notes.add(note)


class SKFCsvParser(object):
    def create_chain(self):
        date_column_strategy = DateColumnMappingStrategy()
        title_column_strategy = TitleColumnMappingStrategy()
        description_column_strategy = DescriptionColumnMappingStrategy()
        mitigation_column_strategy = MitigationColumnMappingStrategy()
        notes_strategy = NotesColumnMappingStrategy()

        mitigation_column_strategy.successor = notes_strategy
        description_column_strategy.successor = mitigation_column_strategy
        title_column_strategy.successor = description_column_strategy
        date_column_strategy.successor = title_column_strategy

        self.chain = date_column_strategy

    def read_column_names(self, row):
        index = 0
        for column in row:
            self.column_names[index] = column
            index += 1

    def get_findings(self, filename, test):
        self.chain = None
        self.column_names = dict()
        self.dupes = dict()
        self.items = ()
        self.create_chain()

        if filename is None:
            self.items = ()
            return

        content = filename.read().decode("utf-8")

        row_number = 0
        reader = csv.reader(
            io.StringIO(content), delimiter=",", quotechar='"', escapechar="\\"
        )
        for row in reader:
            finding = Finding(test=test)
            finding.severity = "Info"

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

            if finding is not None:
                key = hashlib.md5(
                    str(
                        finding.severity
                        + "|"
                        + finding.title
                        + "|"
                        + finding.description
                    ).encode("utf-8")
                ).hexdigest()

                if key not in self.dupes:
                    self.dupes[key] = finding

            row_number += 1

        self.items = list(self.dupes.values())
