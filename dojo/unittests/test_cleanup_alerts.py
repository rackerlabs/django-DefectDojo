from dojo.tasks import cleanup_alerts
from django.test import TestCase
from django.conf import settings
from dojo.models import User, Alerts
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)


class TestCleanupAlerts(TestCase):
    fixtures = ["dojo_testdata.json"]

    def setUp(self):
        testuser = User.objects.get(username="admin")
        Alerts.objects.filter(user_id=testuser).delete()
        Alerts.objects.create(
            title="B",
            user_id=testuser,
            created=datetime(2021, 1, 8, 16, 54, 23, 597051, tzinfo=timezone.utc),
        )
        Alerts.objects.create(
            title="A",
            user_id=testuser,
            created=datetime(2021, 1, 7, 16, 54, 23, 597051, tzinfo=timezone.utc),
        )
        Alerts.objects.create(
            title="C",
            user_id=testuser,
            created=datetime(2021, 1, 9, 16, 54, 23, 597051, tzinfo=timezone.utc),
        )

    def test_delete_alerts_disabled(self):
        settings.MAX_ALERTS_PER_USER = -1
        testuser = User.objects.get(username="admin")
        alerts_before = Alerts.objects.filter(user_id=testuser).count()
        cleanup_alerts()
        alerts_after = Alerts.objects.filter(user_id=testuser).count()
        self.assertEquals(alerts_before, alerts_after)

    def test_delete_all_alerts(self):
        settings.MAX_ALERTS_PER_USER = 0
        testuser = User.objects.get(username="admin")
        cleanup_alerts()
        alerts_after = Alerts.objects.filter(user_id=testuser).count()
        self.assertEquals(alerts_after, 0)

    def test_delete_more_than_two_alerts(self):
        settings.MAX_ALERTS_PER_USER = 2
        testuser = User.objects.get(username="admin")
        cleanup_alerts()
        alerts_after = Alerts.objects.filter(user_id=testuser).count()
        self.assertEquals(alerts_after, 2)
        self.assertEquals(Alerts.objects.filter(user_id=testuser, title="A").count(), 0)
        self.assertEquals(Alerts.objects.filter(user_id=testuser, title="B").count(), 1)
        self.assertEquals(Alerts.objects.filter(user_id=testuser, title="C").count(), 1)

        cleanup_alerts()
        alerts_after = Alerts.objects.filter(user_id=testuser).count()
        self.assertEquals(alerts_after, 2)
