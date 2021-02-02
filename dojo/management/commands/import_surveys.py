from django.core.management.base import BaseCommand
from pytz import timezone
from django.db import connection
import os

from dojo.utils import get_system_setting
from dojo.models import TextQuestion

locale = timezone(get_system_setting("time_zone"))

"""
Author: Cody Maffucci
This script will import initial surverys and questions into DefectDojo:
"""


class Command(BaseCommand):
    help = "Import surverys from dojo/fixtures/initial_surveys.py"

    def handle(self, *args, **options):
        # First create a temp question to pull the polymorphic_ctype_id from
        created_question = TextQuestion.objects.create(
            optional=False, order=1, text="What is love?"
        )
        # Get the ID used in this system
        with connection.cursor() as cursor:
            cursor.execute("select polymorphic_ctype_id from dojo_question;")
            row = cursor.fetchone()
            ctype_id = row[0]
        # Find the current id in the surveys file
        path = os.path.dirname(os.path.abspath(__file__))
        path = path[:-19] + "fixtures/initial_surveys.json"
        contents = open(path, "rt").readlines()
        for line in contents:
            if '"polymorphic_ctype": ' in line:
                matchedLine = line
                break
        # Create the new id line
        old_id = "".join(c for c in matchedLine if c.isdigit())
        new_line = matchedLine.replace(old_id, str(ctype_id))
        # Replace the all lines in the file
        with open(path, "wt") as fout:
            for line in contents:
                fout.write(line.replace(matchedLine, new_line))
        # Delete the temp question
        created_question.delete()
