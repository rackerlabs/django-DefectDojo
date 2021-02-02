from django.core.management.base import BaseCommand
from dojo.models import System_Settings


class Command(BaseCommand):
    help = "Updates product grade calculation"

    def handle(self, *args, **options):
        code = """def grade_product(crit, high, med, low):
            health=100
            if crit > 0:
                health = 40
                health = health - ((crit - 1) * 5)
            if high > 0:
                if health == 100:
                    health = 60
                health = health - ((high - 1) * 3)
            if med > 0:
                if health == 100:
                    health = 80
                health = health - ((med - 1) * 2)
            if low > 0:
                if health == 100:
                    health = 95
                health = health - low

            if health < 5:
                health = 5

            return health
            """
        system_settings = System_Settings.objects.get(id=1)
        system_settings.product_grade = code
        system_settings.save()
