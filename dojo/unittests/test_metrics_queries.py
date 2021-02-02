"""
Tests for metrics database queries
"""

from datetime import datetime, timezone
from unittest.mock import patch

from django.test import RequestFactory, TestCase
from django.urls import reverse

from dojo.metrics import views
from dojo.models import User


class MockMessages:
    def add(*args, **kwargs):
        pass


class FindingQueriesTest(TestCase):
    fixtures = ["dojo_testdata.json"]

    def setUp(self):
        user = User.objects.get(username="user1")
        self.request = RequestFactory().get(reverse("metrics"))
        self.request.user = user
        self.request._messages = MockMessages()

    @patch("django.utils.timezone.now")
    def test_finding_queries(self, mock_timezone):
        mock_datetime = datetime(2020, 12, 9, tzinfo=timezone.utc)
        mock_timezone.return_value = mock_datetime

        # Queries over Finding and Risk_Acceptance
        with self.assertNumQueries(41):
            product_types = []
            finding_queries = views.finding_querys(product_types, self.request)

            self.assertSequenceEqual(
                list(finding_queries.keys()),
                [
                    "all",
                    "closed",
                    "accepted",
                    "accepted_count",
                    "top_ten",
                    "monthly_counts",
                    "weekly_counts",
                    "weeks_between",
                    "start_date",
                    "end_date",
                ],
            )

            # Assert that we get expected querysets back. This is to be used to
            # support refactoring, in attempt of lowering the query count.
            self.assertSequenceEqual(finding_queries["all"].qs.values(), [])
            self.assertSequenceEqual(finding_queries["closed"].values(), [])
            self.assertSequenceEqual(finding_queries["accepted"].values(), [])
            self.assertSequenceEqual(
                list(finding_queries["accepted_count"].values()),
                [None, None, None, None, None, None],
            )
            self.assertSequenceEqual(finding_queries["top_ten"].values(), [])
            self.assertSequenceEqual(
                list(finding_queries["monthly_counts"].values()),
                [
                    [
                        [
                            "Timestamp",
                            "Date",
                            "S0",
                            "S1",
                            "S2",
                            "S3",
                            "Total",
                            "Closed",
                        ],
                        [
                            1604188800000,
                            datetime(2020, 11, 1, 0, 0, tzinfo=timezone.utc),
                            0,
                            0,
                            0,
                            0,
                            0,
                            0,
                        ],
                        [
                            1606780800000,
                            datetime(2020, 12, 1, 0, 0, tzinfo=timezone.utc),
                            0,
                            0,
                            0,
                            0,
                            0,
                            0,
                        ],
                    ],
                    [
                        [
                            "Timestamp",
                            "Date",
                            "S0",
                            "S1",
                            "S2",
                            "S3",
                            "Total",
                            "Closed",
                        ],
                        [
                            1604188800000,
                            datetime(2020, 11, 1, 0, 0, tzinfo=timezone.utc),
                            0,
                            0,
                            0,
                            0,
                            0,
                        ],
                        [
                            1606780800000,
                            datetime(2020, 12, 1, 0, 0, tzinfo=timezone.utc),
                            0,
                            0,
                            0,
                            0,
                            0,
                        ],
                    ],
                    [
                        [
                            "Timestamp",
                            "Date",
                            "S0",
                            "S1",
                            "S2",
                            "S3",
                            "Total",
                            "Closed",
                        ],
                        [
                            1604188800000,
                            datetime(2020, 11, 1, 0, 0, tzinfo=timezone.utc),
                            0,
                            0,
                            0,
                            0,
                            0,
                        ],
                        [
                            1606780800000,
                            datetime(2020, 12, 1, 0, 0, tzinfo=timezone.utc),
                            0,
                            0,
                            0,
                            0,
                            0,
                        ],
                    ],
                ],
            )
            self.assertDictEqual(
                finding_queries["weekly_counts"],
                {
                    "opened_per_period": [
                        [
                            "Timestamp",
                            "Date",
                            "S0",
                            "S1",
                            "S2",
                            "S3",
                            "Total",
                            "Closed",
                        ],
                        [
                            1607299200000,
                            datetime(2020, 12, 7, 0, 0, tzinfo=timezone.utc),
                            0,
                            0,
                            0,
                            0,
                            0,
                            0,
                        ],
                        [
                            1607904000000,
                            datetime(2020, 12, 14, 0, 0, tzinfo=timezone.utc),
                            0,
                            0,
                            0,
                            0,
                            0,
                            0,
                        ],
                        [
                            1608508800000,
                            datetime(2020, 12, 21, 0, 0, tzinfo=timezone.utc),
                            0,
                            0,
                            0,
                            0,
                            0,
                            0,
                        ],
                    ],
                    "accepted_per_period": [
                        [
                            "Timestamp",
                            "Date",
                            "S0",
                            "S1",
                            "S2",
                            "S3",
                            "Total",
                            "Closed",
                        ],
                        [
                            1607299200000,
                            datetime(2020, 12, 7, 0, 0, tzinfo=timezone.utc),
                            0,
                            0,
                            0,
                            0,
                            0,
                        ],
                        [
                            1607904000000,
                            datetime(2020, 12, 14, 0, 0, tzinfo=timezone.utc),
                            0,
                            0,
                            0,
                            0,
                            0,
                        ],
                        [
                            1608508800000,
                            datetime(2020, 12, 21, 0, 0, tzinfo=timezone.utc),
                            0,
                            0,
                            0,
                            0,
                            0,
                        ],
                    ],
                    "active_per_period": [
                        [
                            "Timestamp",
                            "Date",
                            "S0",
                            "S1",
                            "S2",
                            "S3",
                            "Total",
                            "Closed",
                        ],
                        [
                            1607299200000,
                            datetime(2020, 12, 7, 0, 0, tzinfo=timezone.utc),
                            0,
                            0,
                            0,
                            0,
                            0,
                        ],
                        [
                            1607904000000,
                            datetime(2020, 12, 14, 0, 0, tzinfo=timezone.utc),
                            0,
                            0,
                            0,
                            0,
                            0,
                        ],
                        [
                            1608508800000,
                            datetime(2020, 12, 21, 0, 0, tzinfo=timezone.utc),
                            0,
                            0,
                            0,
                            0,
                            0,
                        ],
                    ],
                },
            )
            self.assertEqual(finding_queries["weeks_between"], 2)
            self.assertIsInstance(finding_queries["start_date"], datetime)
            self.assertIsInstance(finding_queries["end_date"], datetime)


class EndpointQueriesTest(TestCase):
    fixtures = ["dojo_testdata.json"]

    def setUp(self):
        user = User.objects.get(username="user1")
        self.request = RequestFactory().get(reverse("metrics"))
        self.request.user = user
        self.request._messages = MockMessages()

    def test_endpoint_queries(self):
        # Queries over Finding and Endpoint_Status
        with self.assertNumQueries(67):
            product_types = []
            endpoint_queries = views.endpoint_querys(product_types, self.request)

            self.assertSequenceEqual(
                list(endpoint_queries.keys()),
                [
                    "all",
                    "closed",
                    "accepted",
                    "accepted_count",
                    "top_ten",
                    "monthly_counts",
                    "weekly_counts",
                    "weeks_between",
                    "start_date",
                    "end_date",
                ],
            )

            # Assert that we get expected querysets back. This is to be used to
            # support refactoring, in attempt of lowering the query count.
            self.assertSequenceEqual(
                endpoint_queries["all"].values(),
                [
                    {
                        "id": 1,
                        "date": datetime(2020, 7, 1, 0, 0, tzinfo=timezone.utc),
                        "last_modified": datetime(
                            2020, 7, 1, 17, 45, 39, 791907, tzinfo=timezone.utc
                        ),
                        "mitigated": False,
                        "mitigated_time": None,
                        "mitigated_by_id": None,
                        "false_positive": False,
                        "out_of_scope": False,
                        "risk_accepted": False,
                        "endpoint_id": 2,
                        "finding_id": 2,
                    }
                ],
            )
            self.assertSequenceEqual(
                endpoint_queries["closed"].values(),
                [],
            )
            self.assertSequenceEqual(
                endpoint_queries["accepted"].values(),
                [],
            )
            self.assertSequenceEqual(
                list(endpoint_queries["accepted_count"].values()),
                [None, None, None, None, None, None],
            )
            self.assertSequenceEqual(
                endpoint_queries["top_ten"].values(),
                [],
            )
            self.assertSequenceEqual(
                list(endpoint_queries["monthly_counts"].values()),
                [
                    [
                        [
                            "Timestamp",
                            "Date",
                            "S0",
                            "S1",
                            "S2",
                            "S3",
                            "Total",
                            "Closed",
                        ],
                        [
                            1590969600000,
                            datetime(2020, 6, 1, 0, 0, tzinfo=timezone.utc),
                            0,
                            0,
                            0,
                            0,
                            0,
                            0,
                        ],
                        [
                            1593561600000,
                            datetime(2020, 7, 1, 0, 0, tzinfo=timezone.utc),
                            0,
                            1,
                            0,
                            0,
                            1,
                            0,
                        ],
                    ],
                    [
                        [
                            "Timestamp",
                            "Date",
                            "S0",
                            "S1",
                            "S2",
                            "S3",
                            "Total",
                            "Closed",
                        ],
                        [
                            1590969600000,
                            datetime(2020, 6, 1, 0, 0, tzinfo=timezone.utc),
                            0,
                            0,
                            0,
                            0,
                            0,
                        ],
                        [
                            1593561600000,
                            datetime(2020, 7, 1, 0, 0, tzinfo=timezone.utc),
                            0,
                            0,
                            0,
                            0,
                            0,
                        ],
                    ],
                    [
                        [
                            "Timestamp",
                            "Date",
                            "S0",
                            "S1",
                            "S2",
                            "S3",
                            "Total",
                            "Closed",
                        ],
                        [
                            1590969600000,
                            datetime(2020, 6, 1, 0, 0, tzinfo=timezone.utc),
                            0,
                            0,
                            0,
                            0,
                            0,
                        ],
                        [
                            1593561600000,
                            datetime(2020, 7, 1, 0, 0, tzinfo=timezone.utc),
                            0,
                            1,
                            0,
                            0,
                            1,
                        ],
                    ],
                ],
            )
            self.assertSequenceEqual(
                list(endpoint_queries["weekly_counts"].values()),
                [
                    [
                        [
                            "Timestamp",
                            "Date",
                            "S0",
                            "S1",
                            "S2",
                            "S3",
                            "Total",
                            "Closed",
                        ],
                        [
                            1593388800000,
                            datetime(2020, 6, 29, 0, 0, tzinfo=timezone.utc),
                            0,
                            1,
                            0,
                            0,
                            1,
                            0,
                        ],
                        [
                            1593993600000,
                            datetime(2020, 7, 6, 0, 0, tzinfo=timezone.utc),
                            0,
                            0,
                            0,
                            0,
                            0,
                            0,
                        ],
                        [
                            1594598400000,
                            datetime(2020, 7, 13, 0, 0, tzinfo=timezone.utc),
                            0,
                            0,
                            0,
                            0,
                            0,
                            0,
                        ],
                    ],
                    [
                        [
                            "Timestamp",
                            "Date",
                            "S0",
                            "S1",
                            "S2",
                            "S3",
                            "Total",
                            "Closed",
                        ],
                        [
                            1593388800000,
                            datetime(2020, 6, 29, 0, 0, tzinfo=timezone.utc),
                            0,
                            0,
                            0,
                            0,
                            0,
                        ],
                        [
                            1593993600000,
                            datetime(2020, 7, 6, 0, 0, tzinfo=timezone.utc),
                            0,
                            0,
                            0,
                            0,
                            0,
                        ],
                        [
                            1594598400000,
                            datetime(2020, 7, 13, 0, 0, tzinfo=timezone.utc),
                            0,
                            0,
                            0,
                            0,
                            0,
                        ],
                    ],
                    [
                        [
                            "Timestamp",
                            "Date",
                            "S0",
                            "S1",
                            "S2",
                            "S3",
                            "Total",
                            "Closed",
                        ],
                        [
                            1593388800000,
                            datetime(2020, 6, 29, 0, 0, tzinfo=timezone.utc),
                            0,
                            1,
                            0,
                            0,
                            1,
                        ],
                        [
                            1593993600000,
                            datetime(2020, 7, 6, 0, 0, tzinfo=timezone.utc),
                            0,
                            1,
                            0,
                            0,
                            1,
                        ],
                        [
                            1594598400000,
                            datetime(2020, 7, 13, 0, 0, tzinfo=timezone.utc),
                            0,
                            1,
                            0,
                            0,
                            1,
                        ],
                    ],
                ],
            )
            self.assertEqual(endpoint_queries["weeks_between"], 2)
            self.assertEqual(
                endpoint_queries["start_date"],
                datetime(2020, 7, 1, 0, 0, tzinfo=timezone.utc),
            )
            self.assertEqual(
                endpoint_queries["end_date"],
                datetime(2020, 7, 1, 0, 0, tzinfo=timezone.utc),
            )
