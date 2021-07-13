from django.test import TestCase
import datetime
from dojo.utils import set_duplicate
from dojo.management.commands.fix_loop_duplicates import fix_loop_duplicates
from dojo.models import Finding
import logging
logger = logging.getLogger(__name__)


class TestDuplicationReopen(TestCase):
    fixtures = ['dojo_testdata.json']

    def setUp(self):
        self.finding_a = Finding.objects.get(id=2)
        self.finding_a.pk = None
        self.finding_a.duplicate = False
        self.finding_a.mitigated = datetime.date(1970, 1, 1)
        self.finding_a.is_mitigated = True
        self.finding_a.false_p = True
        self.finding_a.active = False
        self.finding_a.duplicate_finding = None
        self.finding_a.save()
        self.finding_b = Finding.objects.get(id=3)
        self.finding_b.pk = None
        self.finding_a.active = True
        self.finding_b.duplicate = False
        self.finding_b.duplicate_finding = None
        self.finding_b.save()

        self.finding_c = Finding.objects.get(id=4)
        self.finding_c.duplicate = False
        self.finding_c.out_of_scope = True
        self.finding_c.active = False
        self.finding_c.duplicate_finding = None
        self.finding_c.pk = None
        logger.debug('creating finding_c')
        self.finding_c.save()
        self.finding_d = Finding.objects.get(id=5)
        self.finding_d.duplicate = False
        self.finding_d.duplicate_finding = None
        self.finding_d.pk = None
        logger.debug('creating finding_d')
        self.finding_d.save()

    def tearDown(self):
        if self.finding_a.id:
            self.finding_a.delete()
        if self.finding_b.id:
            self.finding_b.delete()
        if self.finding_c.id:
            self.finding_c.delete()
        if self.finding_d.id:
            self.finding_d.delete()

    def test_false_positive_shouldnt_reopen(self):
        # Finding a: FP, mitigated.
        # Finding b: active duplicate finding.
        self.finding_a.active = False
        self.finding_a.verified = False  # in the gui, a FP can not be true
        set_duplicate(self.finding_b, self.finding_a)
        self.finding_b.duplicate = True
        self.finding_b.duplicate_finding = self.finding_a

        super(Finding, self.finding_a).save()
        super(Finding, self.finding_b).save()

        fix_loop_duplicates()

        candidates = Finding.objects.filter(duplicate_finding__isnull=False, original_finding__isnull=False).count()
        self.assertEqual(candidates, 0)

        # Get latest status
        self.finding_a = Finding.objects.get(id=self.finding_a.id)
        self.finding_b = Finding.objects.get(id=self.finding_b.id)

        self.assertTrue(self.finding_a.false_p)
        self.assertTrue(self.finding_a.is_mitigated)
        self.assertFalse(self.finding_a.active)
        self.assertFalse(self.finding_a.verified)

        self.assertFalse(self.finding_b.false_p)
        self.assertFalse(self.finding_b.is_mitigated)
        self.assertFalse(self.finding_b.active)
        self.assertFalse(self.finding_b.verified)

    def test_out_of_scope_shouldnt_reopen(self):
        logger.debug('c: is_mitigated1: %s', self.finding_c.is_mitigated)
        logger.debug('d: is_mitigated1: %s', self.finding_d.is_mitigated)

        self.finding_c.active = False
        self.finding_c.verified = False

        logger.debug('set_duplicate(d,c)')
        set_duplicate(self.finding_d, self.finding_c)

        logger.debug('c: is_mitigated2: %s', self.finding_c.is_mitigated)
        logger.debug('d: is_mitigated2: %s', self.finding_d.is_mitigated)

        # self.finding_d.duplicate = True
        # self.finding_d.duplicate_finding = self.finding_c

        logger.debug('saving finding_c')
        super(Finding, self.finding_c).save()
        logger.debug('saving finding_d')
        super(Finding, self.finding_d).save()

        logger.debug('c: is_mitigated3: %s', self.finding_c.is_mitigated)
        logger.debug('d: is_mitigated3: %s', self.finding_d.is_mitigated)

        candidates = Finding.objects.filter(duplicate_finding__isnull=False, original_finding__isnull=False).count()
        self.assertEqual(candidates, 0)

        # Get latest status
        self.finding_c = Finding.objects.get(id=self.finding_c.id)
        self.finding_d = Finding.objects.get(id=self.finding_d.id)

        self.assertTrue(self.finding_c.out_of_scope)
        self.assertTrue(self.finding_c.is_mitigated)
        self.assertFalse(self.finding_c.active)
        self.assertFalse(self.finding_c.verified)

        self.assertFalse(self.finding_d.out_of_scope)
        self.assertFalse(self.finding_d.is_mitigated)
        self.assertFalse(self.finding_d.active)
        self.assertFalse(self.finding_d.verified)

    def test_mitigated_reopen(self):
        # Mitigated normal finding.
        self.finding_a.active = False
        self.finding_a.verified = True
        self.finding_a.false_p = False
        self.finding_a.mitigated = datetime.date(1970, 1, 1)
        self.finding_a.is_mitigated = True

        # Newly imported, active finding.
        self.finding_b.active = True
        self.finding_b.verified = True
        self.finding_b.duplicate = False
        self.finding_b.duplicate_finding = None

        # Marks b as duplicate, but should reopen a.
        set_duplicate(self.finding_b, self.finding_a)

        super(Finding, self.finding_a).save()
        super(Finding, self.finding_b).save()

        fix_loop_duplicates()

        # Get latest status
        self.finding_a = Finding.objects.get(id=self.finding_a.id)
        self.finding_b = Finding.objects.get(id=self.finding_b.id)

        # a should be not-mitigated and active (open).
        self.assertFalse(self.finding_a.false_p)
        self.assertFalse(self.finding_a.is_mitigated)
        self.assertTrue(self.finding_a.active)
        self.assertTrue(self.finding_a.verified)

        # b should be closed (not active).
        self.assertFalse(self.finding_b.false_p)
        self.assertFalse(self.finding_b.is_mitigated)
        self.assertFalse(self.finding_b.active)
        self.assertFalse(self.finding_b.verified)

    def test_mitigation_by_duplicate(self):
        # 'Duplicate' implies re-import.
        # Normal open finding.
        self.finding_a.active = True
        self.finding_a.verified = True
        self.finding_a.false_p = False
        self.finding_a.mitigated = None
        self.finding_a.is_mitigated = False

        # Newly imported but mitigated finding.
        self.finding_b.active = False
        self.finding_b.verified = True
        self.finding_b.duplicate = False
        self.finding_b.duplicate_finding = None
        self.finding_b.mitigated = datetime.date(1970, 1, 1)
        self.finding_b.is_mitigated = True

        # Marks b as duplicate, but should close (mitigated) a.
        set_duplicate(self.finding_b, self.finding_a)

        super(Finding, self.finding_a).save()
        super(Finding, self.finding_b).save()

        fix_loop_duplicates()

        # Get latest status
        self.finding_a = Finding.objects.get(id=self.finding_a.id)
        self.finding_b = Finding.objects.get(id=self.finding_b.id)

        # a should be mitigated and not active (closed).
        self.assertFalse(self.finding_a.false_p)
        self.assertTrue(self.finding_a.is_mitigated)
        self.assertFalse(self.finding_a.active)
        self.assertTrue(self.finding_a.verified)

        # b should be closed (not active).
        self.assertFalse(self.finding_b.active)
