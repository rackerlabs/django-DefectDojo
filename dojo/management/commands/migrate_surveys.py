from django.core.management.base import BaseCommand
from django.db import connection
import sys
from dojo.models import TextQuestion


"""
Author: Cody Maffucci
This script will migrate survey data from one external app to core dojo
"""


class Command(BaseCommand):
    help = "import survey data from defectDojo_engagement_survey tables to dojo tables"

    def handle(self, *args, **options):
        # Get a connection to the db
        with connection.cursor() as cursor:
            # Check if there are any tables to migrate
            # Has to be specially ordered for parental reasons
            table_list = [
                "defectDojo_engagement_survey_question",
                "defectDojo_engagement_survey_choice",
                "defectDojo_engagement_survey_choicequestion",
                "defectDojo_engagement_survey_engagement_survey",
                "defectDojo_engagement_survey_answered_survey",
                "defectDojo_engagement_survey_general_survey",
                "defectDojo_engagement_survey_answer",
                "defectDojo_engagement_survey_textanswer",
                "defectDojo_engagement_survey_choiceanswer",
                "defectDojo_engagement_survey_choiceanswer_answer",
                "defectDojo_engagement_survey_choicequestion_choices",
                "defectDojo_engagement_survey_engagement_survey_questions",
                "defectDojo_engagement_survey_textquestion",
            ]
            survey_tables = [
                table for table in table_list if table.split("_")[0] == "defectDojo"
            ]
            if len(survey_tables) == 0:
                sys.exit(
                    "There are no defectDojo_enagagement_survey tables to migrate."
                )
            # Get unique ploymorphic id for the system
            ctype_id = 0
            # First create a temp question to pull the polymorphic_ctype_id from
            created_question = TextQuestion.objects.create(
                optional=False, order=1, text="What is love?"
            )
            # Get the ID used in this system
            cursor.execute("select polymorphic_ctype_id from dojo_question;")
            row = cursor.fetchone()
            ctype_id = row[0]
            # Copy the tables over
            for table in survey_tables:
                new_table_name = "dojo" + table[28:]
                # Take all contents from ddse table and insert into dojo table
                copy_string = (
                    "INSERT INTO `"
                    + new_table_name
                    + "` SELECT * FROM `"
                    + table
                    + "`;"
                )
                cursor.execute(str(copy_string))
                # Update polymorphic id on some tables
                if new_table_name == "dojo_question" or new_table_name == "dojo_answer":
                    update_string = (
                        "UPDATE `"
                        + new_table_name
                        + "` SET polymorphic_ctype_id = "
                        + str(ctype_id)
                        + ";"
                    )
                    cursor.execute(str(update_string))
                # Drop the ddse table
            print("All defectDojo_engagement_sruvey tables migrated to dojo tables")

            # Delete the old tables in reverse order to drop the children first
            for table in reversed(table_list):
                cursor.execute("DROP TABLE `" + table + "`;")
            print("All defectDojo_engagement_sruvey tables removed")
