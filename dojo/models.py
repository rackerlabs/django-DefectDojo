import base64
import hashlib
import logging
import os
import re
from uuid import uuid4
from django.conf import settings
from watson import search as watson
from auditlog.registry import auditlog
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.core.validators import RegexValidator
from django.core.exceptions import ValidationError
from django.db import models
from django.utils.deconstruct import deconstructible
from django.utils.timezone import now
from django.utils.functional import cached_property
from imagekit.models import ImageSpecField
from imagekit.processors import ResizeToCover
from django.utils import timezone
from pytz import all_timezones
from tagging.registry import register as tag_register
from multiselectfield import MultiSelectField
from django import forms
from django.utils.translation import gettext as _
from dojo.signals import dedupe_signal
from dojo.tag.prefetching_tag_descriptor import PrefetchingTagDescriptor
from django.contrib.contenttypes.fields import GenericRelation
from tagging.models import TaggedItem
from dateutil.relativedelta import relativedelta

fmt = getattr(settings, 'LOG_FORMAT', None)
lvl = getattr(settings, 'LOG_LEVEL', logging.DEBUG)

logging.basicConfig(format=fmt, level=lvl)
import logging
logger = logging.getLogger(__name__)
deduplicationLogger = logging.getLogger("dojo.specific-loggers.deduplication")


@deconstructible
class UniqueUploadNameProvider:
    """
    A callable to be passed as upload_to parameter to FileField.

    Uploaded files will get random names based on UUIDs inside the given directory;
    strftime-style formatting is supported within the directory path. If keep_basename
    is True, the original file name is prepended to the UUID. If keep_ext is disabled,
    the filename extension will be dropped.
    """

    def __init__(self, directory=None, keep_basename=False, keep_ext=True):
        self.directory = directory
        self.keep_basename = keep_basename
        self.keep_ext = keep_ext

    def __call__(self, model_instance, filename):
        base, ext = os.path.splitext(filename)
        filename = "%s_%s" % (base, uuid4()) if self.keep_basename else str(uuid4())
        if self.keep_ext:
            filename += ext
        if self.directory is None:
            return filename
        return os.path.join(now().strftime(self.directory), filename)


class Regulation(models.Model):
    PRIVACY_CATEGORY = 'privacy'
    FINANCE_CATEGORY = 'finance'
    EDUCATION_CATEGORY = 'education'
    MEDICAL_CATEGORY = 'medical'
    OTHER_CATEGORY = 'other'
    CATEGORY_CHOICES = (
        (PRIVACY_CATEGORY, _('Privacy')),
        (FINANCE_CATEGORY, _('Finance')),
        (EDUCATION_CATEGORY, _('Education')),
        (MEDICAL_CATEGORY, _('Medical')),
        (OTHER_CATEGORY, _('Other')),
    )

    name = models.CharField(max_length=128, help_text=_('The name of the legislation.'))
    acronym = models.CharField(max_length=20, unique=True, help_text=_('A shortened representation of the name.'))
    category = models.CharField(max_length=9, choices=CATEGORY_CHOICES, help_text=_('The subject of the regulation.'))
    jurisdiction = models.CharField(max_length=64, help_text=_('The territory over which the regulation applies.'))
    description = models.TextField(blank=True, help_text=_('Information about the regulation\'s purpose.'))
    reference = models.URLField(blank=True, help_text=_('An external URL for more information.'))

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.acronym + ' (' + self.jurisdiction + ')'


class System_Settings(models.Model):
    enable_auditlog = models.BooleanField(
        default=True,
        blank=False,
        verbose_name='Enable audit logging',
        help_text="With this setting turned on, Dojo maintains an audit log "
                  "of changes made to entities (Findings, Tests, Engagements, Procuts, ...)"
                  "If you run big import you may want to disable this "
                  "because the way django-auditlog currently works, there's a "
                  "big performance hit. Especially during (re-)imports.")
    enable_deduplication = models.BooleanField(
        default=False,
        blank=False,
        verbose_name='Deduplicate findings',
        help_text="With this setting turned on, Dojo deduplicates findings by "
                  "comparing endpoints, cwe fields, and titles. "
                  "If two findings share a URL and have the same CWE or "
                  "title, Dojo marks the less recent finding as a duplicate. "
                  "When deduplication is enabled, a list of "
                  "deduplicated findings is added to the engagement view.")
    delete_dupulicates = models.BooleanField(default=False, blank=False)
    max_dupes = models.IntegerField(blank=True, null=True,
                                    verbose_name='Max Duplicates',
                                    help_text="When enabled, if a single "
                                              "issue reaches the maximum "
                                              "number of duplicates, the "
                                              "oldest will be deleted.")
    enable_jira = models.BooleanField(default=False,
                                      verbose_name='Enable JIRA integration',
                                      blank=False)
    enable_jira_web_hook = models.BooleanField(default=False,
                                      verbose_name='Enable JIRA web hook. Please note: It is strongly recommended to whitelist the Jira server using a proxy such as Nginx.',
                                      blank=False)
    jira_choices = (('Critical', 'Critical'),
                    ('High', 'High'),
                    ('Medium', 'Medium'),
                    ('Low', 'Low'),
                    ('Info', 'Info'))
    jira_minimum_severity = models.CharField(max_length=20, blank=True,
                                             null=True, choices=jira_choices,
                                             default='None')
    jira_labels = models.CharField(max_length=200, blank=True, null=True,
                                   help_text='JIRA issue labels space seperated')

    enable_github = models.BooleanField(default=False,
                                      verbose_name='Enable GITHUB integration',
                                      blank=False)

    enable_slack_notifications = \
        models.BooleanField(default=False,
                            verbose_name='Enable Slack notifications',
                            blank=False)
    slack_channel = models.CharField(max_length=100, default='', blank=True)
    slack_token = models.CharField(max_length=100, default='', blank=True,
                                   help_text='Token required for interacting '
                                             'with Slack. Get one at '
                                             'https://api.slack.com/tokens')
    slack_username = models.CharField(max_length=100, default='', blank=True)
    enable_hipchat_notifications = \
        models.BooleanField(default=False,
                            verbose_name='Enable HipChat notifications',
                            blank=False)
    hipchat_site = models.CharField(max_length=100, default='', blank=True,
                                    help_text='The full fqdn of your '
                                              'hipchat site, e.g. '
                                              '"yoursite.hipchat.com"')
    hipchat_channel = models.CharField(max_length=100, default='', blank=True)
    hipchat_token = \
        models.CharField(max_length=100, default='', blank=True,
                         help_text='Token required for interacting with '
                                   'HipChat. Get one at '
                                   'https://patriktest.hipchat.com/addons/')
    enable_mail_notifications = models.BooleanField(default=False, blank=False)
    mail_notifications_from = models.CharField(max_length=200,
                                               default='from@example.com',
                                               blank=True)
    mail_notifications_to = models.CharField(max_length=200, default='',
                                             blank=True)
    s_finding_severity_naming = \
        models.BooleanField(default=False, blank=False,
                            help_text='With this setting turned on, Dojo '
                                      'will display S0, S1, S2, etc in most '
                                      'places, whereas if turned off '
                                      'Critical, High, Medium, etc will '
                                      'be displayed.')
    false_positive_history = models.BooleanField(default=False, help_text="DefectDojo will automatically mark the finding as a false positive if the finding has been previously marked as a false positive.")

    url_prefix = models.CharField(max_length=300, default='', blank=True, help_text="URL prefix if DefectDojo is installed in it's own virtual subdirectory.")
    team_name = models.CharField(max_length=100, default='', blank=True)
    time_zone = models.CharField(max_length=50,
                                 choices=[(tz, tz) for tz in all_timezones],
                                 default='UTC', blank=False)
    display_endpoint_uri = models.BooleanField(default=False, verbose_name="Display Endpoint Full URI", help_text="Displays the full endpoint URI in the endpoint view.")
    enable_product_grade = models.BooleanField(default=False, verbose_name="Enable Product Grading", help_text="Displays a grade letter next to a product to show the overall health.")
    product_grade = models.CharField(max_length=800, blank=True)
    product_grade_a = models.IntegerField(default=90,
                                          verbose_name="Grade A",
                                          help_text="Percentage score for an "
                                                    "'A' >=")
    product_grade_b = models.IntegerField(default=80,
                                          verbose_name="Grade B",
                                          help_text="Percentage score for a "
                                                    "'B' >=")
    product_grade_c = models.IntegerField(default=70,
                                          verbose_name="Grade C",
                                          help_text="Percentage score for a "
                                                    "'C' >=")
    product_grade_d = models.IntegerField(default=60,
                                          verbose_name="Grade D",
                                          help_text="Percentage score for a "
                                                    "'D' >=")
    product_grade_f = models.IntegerField(default=59,
                                          verbose_name="Grade F",
                                          help_text="Percentage score for an "
                                                    "'F' <=")
    enable_benchmark = models.BooleanField(
        default=True,
        blank=False,
        verbose_name="Enable Benchmarks",
        help_text="Enables Benchmarks such as the OWASP ASVS "
                  "(Application Security Verification Standard)")

    enable_template_match = models.BooleanField(
        default=False,
        blank=False,
        verbose_name="Enable Remediation Advice",
        help_text="Enables global remediation advice and matching on CWE and Title. The text will be replaced for mitigation, impact and references on a finding. Useful for providing consistent impact and remediation advice regardless of the scanner.")

    engagement_auto_close = models.BooleanField(
        default=False,
        blank=False,
        verbose_name="Enable Engagement Auto-Close",
        help_text="Closes an engagement after 3 days (default) past due date including last update.")

    engagement_auto_close_days = models.IntegerField(
        default=3,
        blank=False,
        verbose_name="Engagement Auto-Close Days",
        help_text="Closes an engagement after the specified number of days past due date including last update.")

    enable_finding_sla = models.BooleanField(
        default=True,
        blank=False,
        verbose_name="Enable Finding SLA's",
        help_text="Enables Finding SLA's for time to remediate.")

    sla_critical = models.IntegerField(default=7,
                                          verbose_name="Crital Finding SLA Days",
                                          help_text="# of days to remediate a critical finding.")

    sla_high = models.IntegerField(default=30,
                                          verbose_name="High Finding SLA Days",
                                          help_text="# of days to remediate a high finding.")
    sla_medium = models.IntegerField(default=90,
                                          verbose_name="Medium Finding SLA Days",
                                          help_text="# of days to remediate a medium finding.")

    sla_low = models.IntegerField(default=120,
                                          verbose_name="Low Finding SLA Days",
                                          help_text="# of days to remediate a low finding.")
    allow_anonymous_survey_repsonse = models.BooleanField(
        default=False,
        blank=False,
        verbose_name="Allow Anonymous Survey Responses",
        help_text="Enable anyone with a link to the survey to answer a survey"
    )
    credentials = models.CharField(max_length=3000, blank=True)
    column_widths = models.CharField(max_length=1500, blank=True)
    drive_folder_ID = models.CharField(max_length=100, blank=True)
    enable_google_sheets = models.BooleanField(default=False, null=True, blank=True)
    email_address = models.EmailField(max_length=100, blank=True)

    from dojo.middleware import System_Settings_Manager
    objects = System_Settings_Manager()


class SystemSettingsFormAdmin(forms.ModelForm):
    product_grade = forms.CharField(widget=forms.Textarea)

    class Meta:
        model = System_Settings
        fields = ['product_grade']


class System_SettingsAdmin(admin.ModelAdmin):
    form = SystemSettingsFormAdmin
    fields = ('product_grade',)


def get_current_date():
    return timezone.now().date()


def get_current_datetime():
    return timezone.now()


User = get_user_model()


# proxy class for convenience and UI
class Dojo_User(User):
    class Meta:
        proxy = True

    def get_full_name(self):
        """
        Returns the first_name plus the last_name, with a space in between.
        """
        full_name = '%s %s (%s)' % (self.first_name,
                                    self.last_name,
                                    self.username)
        return full_name.strip()

    def __unicode__(self):
        return self.get_full_name()

    def __str__(self):
        return self.get_full_name()


class UserContactInfo(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    title = models.CharField(blank=True, null=True, max_length=150)
    phone_regex = RegexValidator(regex=r'^\+?1?\d{9,15}$',
                                 message="Phone number must be entered in the format: '+999999999'. "
                                         "Up to 15 digits allowed.")
    phone_number = models.CharField(validators=[phone_regex], blank=True,
                                    max_length=15,
                                    help_text="Phone number must be entered in the format: '+999999999'. "
                                              "Up to 15 digits allowed.")
    cell_number = models.CharField(validators=[phone_regex], blank=True,
                                   max_length=15,
                                   help_text="Phone number must be entered in the format: '+999999999'. "
                                             "Up to 15 digits allowed.")
    twitter_username = models.CharField(blank=True, null=True, max_length=150)
    github_username = models.CharField(blank=True, null=True, max_length=150)
    slack_username = models.CharField(blank=True, null=True, max_length=150, help_text="Email address associated with your slack account", verbose_name="Slack Email Address")
    slack_user_id = models.CharField(blank=True, null=True, max_length=25)
    hipchat_username = models.CharField(blank=True, null=True, max_length=150)
    block_execution = models.BooleanField(default=False, help_text="Instead of async deduping a finding the findings will be deduped synchronously and will 'block' the user until completion.")


class Contact(models.Model):
    name = models.CharField(max_length=100)
    email = models.EmailField()
    team = models.CharField(max_length=100)
    is_admin = models.BooleanField(default=False)
    is_globally_read_only = models.BooleanField(default=False)
    updated = models.DateTimeField(editable=False)


class Note_Type(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.CharField(max_length=200)
    is_single = models.BooleanField(default=False, null=False)
    is_active = models.BooleanField(default=True, null=False)
    is_mandatory = models.BooleanField(default=True, null=False)

    def __unicode__(self):
        return self.name

    def __str__(self):
        return self.name


class Product_Type(models.Model):
    name = models.CharField(max_length=255, unique=True)
    critical_product = models.BooleanField(default=False)
    key_product = models.BooleanField(default=False)
    updated = models.DateTimeField(auto_now=True, null=True)
    created = models.DateTimeField(auto_now_add=True, null=True)

    @cached_property
    def critical_present(self):
        c_findings = Finding.objects.filter(
            test__engagement__product__prod_type=self, severity='Critical')
        if c_findings.count() > 0:
            return True

    @cached_property
    def high_present(self):
        c_findings = Finding.objects.filter(
            test__engagement__product__prod_type=self, severity='High')
        if c_findings.count() > 0:
            return True

    @cached_property
    def calc_health(self):
        h_findings = Finding.objects.filter(
            test__engagement__product__prod_type=self, severity='High')
        c_findings = Finding.objects.filter(
            test__engagement__product__prod_type=self, severity='Critical')
        health = 100
        if c_findings.count() > 0:
            health = 40
            health = health - ((c_findings.count() - 1) * 5)
        if h_findings.count() > 0:
            if health == 100:
                health = 60
            health = health - ((h_findings.count() - 1) * 2)
        if health < 5:
            return 5
        else:
            return health

    # def findings_count(self):
    #     return Finding.objects.filter(mitigated__isnull=True,
    #                                   verified=True,
    #                                   false_p=False,
    #                                   duplicate=False,
    #                                   out_of_scope=False,
    #                                   test__engagement__product__prod_type=self).filter(
    #         Q(severity="Critical") |
    #         Q(severity="High") |
    #         Q(severity="Medium") |
    #         Q(severity="Low")).count()

    @property
    def unaccepted_open_findings(self):
        engagements = Engagement.objects.filter(product__prod_type=self)
        accepted_findings = Finding.objects.filter(risk_acceptance__engagement__in=engagements)
        accepted_ids = [f.id for f in accepted_findings.only('id')]
        return Finding.objects.filter(active=True, verified=True, duplicate=False,
                                      test__engagement__product__prod_type=self).exclude(id__in=accepted_ids)

    # def products_count(self):
    #     return Product.objects.filter(prod_type=self).count()

    class Meta:
        ordering = ('name',)

    def __unicode__(self):
        return self.name

    def __str__(self):
        return self.name

    def get_breadcrumbs(self):
        bc = [{'title': self.__unicode__(),
               'url': reverse('edit_product_type', args=(self.id,))}]
        return bc


class Product_Line(models.Model):
    name = models.CharField(max_length=300)
    description = models.CharField(max_length=2000)

    def __unicode__(self):
        return self.name

    def __str__(self):
        return self.name


class Report_Type(models.Model):
    name = models.CharField(max_length=255)


class Test_Type(models.Model):
    name = models.CharField(max_length=200, unique=True)
    static_tool = models.BooleanField(default=False)
    dynamic_tool = models.BooleanField(default=False)

    def __unicode__(self):
        return self.name

    def __str__(self):
        return self.name

    class Meta:
        ordering = ('name',)

    def get_breadcrumbs(self):
        bc = [{'title': self.__unicode__(),
               'url': None}]
        return bc


class DojoMeta(models.Model):
    name = models.CharField(max_length=120)
    value = models.CharField(max_length=300)
    product = models.ForeignKey('Product',
                                on_delete=models.CASCADE,
                                null=True,
                                editable=False,
                                related_name='product_meta')
    endpoint = models.ForeignKey('Endpoint',
                                 on_delete=models.CASCADE,
                                 null=True,
                                 editable=False,
                                 related_name='endpoint_meta')

    """
    Verify that this metadata entry belongs only to one object.
    """
    def clean(self):
        if self.product_id is None and self.endpoint_id is None:
            raise ValidationError('Metadata entries need either a product or an endpoint')
        if self.product_id is not None and self.endpoint_id is not None:
            raise ValidationError('Metadata entries may not have both a product and an endpoint')

    def __unicode__(self):
        return "%s: %s" % (self.name, self.value)

    def __str__(self):
        return "%s: %s" % (self.name, self.value)

    class Meta:
        unique_together = (('product', 'name'),
                           ('endpoint', 'name'))


class Product(models.Model):
    WEB_PLATFORM = 'web'
    IOT = 'iot'
    DESKTOP_PLATFORM = 'desktop'
    MOBILE_PLATFORM = 'mobile'
    WEB_SERVICE_PLATFORM = 'web service'
    PLATFORM_CHOICES = (
        (WEB_SERVICE_PLATFORM, _('API')),
        (DESKTOP_PLATFORM, _('Desktop')),
        (IOT, _('Internet of Things')),
        (MOBILE_PLATFORM, _('Mobile')),
        (WEB_PLATFORM, _('Web')),
    )

    CONSTRUCTION = 'construction'
    PRODUCTION = 'production'
    RETIREMENT = 'retirement'
    LIFECYCLE_CHOICES = (
        (CONSTRUCTION, _('Construction')),
        (PRODUCTION, _('Production')),
        (RETIREMENT, _('Retirement')),
    )

    THIRD_PARTY_LIBRARY_ORIGIN = 'third party library'
    PURCHASED_ORIGIN = 'purchased'
    CONTRACTOR_ORIGIN = 'contractor'
    INTERNALLY_DEVELOPED_ORIGIN = 'internal'
    OPEN_SOURCE_ORIGIN = 'open source'
    OUTSOURCED_ORIGIN = 'outsourced'
    ORIGIN_CHOICES = (
        (THIRD_PARTY_LIBRARY_ORIGIN, _('Third Party Library')),
        (PURCHASED_ORIGIN, _('Purchased')),
        (CONTRACTOR_ORIGIN, _('Contractor Developed')),
        (INTERNALLY_DEVELOPED_ORIGIN, _('Internally Developed')),
        (OPEN_SOURCE_ORIGIN, _('Open Source')),
        (OUTSOURCED_ORIGIN, _('Outsourced')),
    )

    VERY_HIGH_CRITICALITY = 'very high'
    HIGH_CRITICALITY = 'high'
    MEDIUM_CRITICALITY = 'medium'
    LOW_CRITICALITY = 'low'
    VERY_LOW_CRITICALITY = 'very low'
    NONE_CRITICALITY = 'none'
    BUSINESS_CRITICALITY_CHOICES = (
        (VERY_HIGH_CRITICALITY, _('Very High')),
        (HIGH_CRITICALITY, _('High')),
        (MEDIUM_CRITICALITY, _('Medium')),
        (LOW_CRITICALITY, _('Low')),
        (VERY_LOW_CRITICALITY, _('Very Low')),
        (NONE_CRITICALITY, _('None')),
    )

    name = models.CharField(max_length=255, unique=True)
    description = models.CharField(max_length=4000)

    '''
    The following three fields are deprecated and no longer in use.
    They remain in model for backwards compatibility and will be removed
    in a future release.  prod_manager, tech_contact, manager

    The admin script migrate_product_contacts should be used to migrate data
    from these fields to their replacements.
    ./manage.py migrate_product_contacts
    '''
    prod_manager = models.CharField(default=0, max_length=200, null=True, blank=True)  # unused
    tech_contact = models.CharField(default=0, max_length=200, null=True, blank=True)  # unused
    manager = models.CharField(default=0, max_length=200, null=True, blank=True)  # unused

    product_manager = models.ForeignKey(Dojo_User, null=True, blank=True,
                                        related_name='product_manager', on_delete=models.CASCADE)
    technical_contact = models.ForeignKey(Dojo_User, null=True, blank=True,
                                          related_name='technical_contact', on_delete=models.CASCADE)
    team_manager = models.ForeignKey(Dojo_User, null=True, blank=True,
                                     related_name='team_manager', on_delete=models.CASCADE)

    created = models.DateTimeField(editable=False, null=True, blank=True)
    prod_type = models.ForeignKey(Product_Type, related_name='prod_type',
                                  null=True, blank=True, on_delete=models.CASCADE)
    updated = models.DateTimeField(editable=False, null=True, blank=True)
    tid = models.IntegerField(default=0, editable=False)
    authorized_users = models.ManyToManyField(User, blank=True)
    prod_numeric_grade = models.IntegerField(null=True, blank=True)

    # Metadata
    business_criticality = models.CharField(max_length=9, choices=BUSINESS_CRITICALITY_CHOICES, blank=True, null=True)
    platform = models.CharField(max_length=11, choices=PLATFORM_CHOICES, blank=True, null=True)
    lifecycle = models.CharField(max_length=12, choices=LIFECYCLE_CHOICES, blank=True, null=True)
    origin = models.CharField(max_length=19, choices=ORIGIN_CHOICES, blank=True, null=True)
    user_records = models.PositiveIntegerField(blank=True, null=True, help_text=_('Estimate the number of user records within the application.'))
    revenue = models.DecimalField(max_digits=15, decimal_places=2, blank=True, null=True, help_text=_('Estimate the application\'s revenue.'))
    external_audience = models.BooleanField(default=False, help_text=_('Specify if the application is used by people outside the organization.'))
    internet_accessible = models.BooleanField(default=False, help_text=_('Specify if the application is accessible from the public internet.'))
    regulations = models.ManyToManyField(Regulation, blank=True)

    # used for prefetching tags because django-tagging doesn't support that out of the box
    tagged_items = GenericRelation(TaggedItem)

    def __unicode__(self):
        return self.name

    def __str__(self):
        return self.name

    class Meta:
        ordering = ('name',)

    @cached_property
    def findings_count(self):
        try:
            # if prefetched, it's already there
            return self.active_finding_count
        except AttributeError:
            # ideally it's always prefetched and we can remove this code in the future
            self.active_finding_count = Finding.objects.filter(mitigated__isnull=True,
                                            active=True,
                                            false_p=False,
                                            duplicate=False,
                                            out_of_scope=False,
                                            test__engagement__product=self).count()
            return self.active_finding_count

    # @property
    # def active_engagement_count(self):
    #     return Engagement.objects.filter(active=True, product=self).count()

    # @property
    # def closed_engagement_count(self):
    #     return Engagement.objects.filter(active=False, product=self).count()

    # @property
    # def last_engagement_date(self):
    #     return Engagement.objects.filter(product=self).first()

    @cached_property
    def endpoint_count(self):
        # endpoints = Endpoint.objects.filter(
        #     finding__test__engagement__product=self,
        #     finding__active=True,
        #     finding__verified=True,
        #     finding__mitigated__isnull=True)

        endpoints = self.active_endpoints

        hosts = []
        ids = []
        for e in endpoints:
            if ":" in e.host:
                host_no_port = e.host[:e.host.index(':')]
            else:
                host_no_port = e.host

            if host_no_port in hosts:
                continue
            else:
                hosts.append(host_no_port)
                ids.append(e.id)

        return len(hosts)

    def open_findings(self, start_date=None, end_date=None):
        if start_date is None or end_date is None:
            return {}
        else:
            critical = Finding.objects.filter(test__engagement__product=self,
                                              mitigated__isnull=True,
                                              verified=True,
                                              false_p=False,
                                              duplicate=False,
                                              out_of_scope=False,
                                              severity="Critical",
                                              date__range=[start_date,
                                                           end_date]).count()
            high = Finding.objects.filter(test__engagement__product=self,
                                          mitigated__isnull=True,
                                          verified=True,
                                          false_p=False,
                                          duplicate=False,
                                          out_of_scope=False,
                                          severity="High",
                                          date__range=[start_date,
                                                       end_date]).count()
            medium = Finding.objects.filter(test__engagement__product=self,
                                            mitigated__isnull=True,
                                            verified=True,
                                            false_p=False,
                                            duplicate=False,
                                            out_of_scope=False,
                                            severity="Medium",
                                            date__range=[start_date,
                                                         end_date]).count()
            low = Finding.objects.filter(test__engagement__product=self,
                                         mitigated__isnull=True,
                                         verified=True,
                                         false_p=False,
                                         duplicate=False,
                                         out_of_scope=False,
                                         severity="Low",
                                         date__range=[start_date,
                                                      end_date]).count()
            return {'Critical': critical,
                    'High': high,
                    'Medium': medium,
                    'Low': low,
                    'Total': (critical + high + medium + low)}

    def get_breadcrumbs(self):
        bc = [{'title': self.__unicode__(),
               'url': reverse('view_product', args=(self.id,))}]
        return bc

    @property
    def get_product_type(self):
        return self.prod_type if self.prod_type is not None else 'unknown'

    def open_findings_list(self):
        findings = Finding.objects.filter(test__engagement__product=self,
                                          mitigated__isnull=True,
                                          verified=True,
                                          false_p=False,
                                          duplicate=False,
                                          out_of_scope=False
                                          )
        findings_list = []
        for i in findings:
            findings_list.append(i.id)
        return findings_list


class ScanSettings(models.Model):
    product = models.ForeignKey(Product, default=1, editable=False, on_delete=models.CASCADE)
    addresses = models.TextField(default="none")
    user = models.ForeignKey(User, editable=False, on_delete=models.CASCADE)
    date = models.DateTimeField(editable=False, blank=True,
                                default=get_current_datetime)
    frequency = models.CharField(max_length=10000, null=True,
                                 blank=True)
    email = models.CharField(max_length=512)
    protocol = models.CharField(max_length=10, default='TCP')

    def addresses_as_list(self):
        if self.addresses:
            return [a.strip() for a in self.addresses.split(',')]
        return []

    def get_breadcrumbs(self):
        bc = self.product.get_breadcrumbs()
        bc += [{'title': "Scan Settings",
                'url': reverse('view_scan_settings',
                               args=(self.product.id, self.id,))}]
        return bc


"""
Modified by Fatimah and Micheal
removed ip_scans field
"""


class Scan(models.Model):
    scan_settings = models.ForeignKey(ScanSettings, default=1, editable=False, on_delete=models.CASCADE)
    date = models.DateTimeField(editable=False, blank=True,
                                default=get_current_datetime)
    protocol = models.CharField(max_length=10, default='TCP')
    status = models.CharField(max_length=10, default='Pending', editable=False)
    baseline = models.BooleanField(default=False, verbose_name="Current Baseline")

    def __unicode__(self):
        return self.scan_settings.protocol + " Scan " + str(self.date)

    def __str__(self):
        return self.scan_settings.protocol + " Scan " + str(self.date)

    def get_breadcrumbs(self):
        bc = self.scan_settings.get_breadcrumbs()
        bc += [{'title': self.__unicode__(),
                'url': reverse('view_scan', args=(self.id,))}]
        return bc


"""
Modified by Fatimah and Micheal
Changed services from a ManytToMany field to a formatted string
"port,protocol,status"
Added scan_id
"""


class IPScan(models.Model):
    address = models.TextField(editable=False, default="none")
    services = models.CharField(max_length=800, null=True)
    scan = models.ForeignKey(Scan, default=1, editable=False, on_delete=models.CASCADE)


class Tool_Type(models.Model):
    name = models.CharField(max_length=200)
    description = models.CharField(max_length=2000, null=True)

    class Meta:
        ordering = ['name']

    def __unicode__(self):
        return self.name

    def __str__(self):
        return self.name


class Tool_Configuration(models.Model):
    name = models.CharField(max_length=200, null=False)
    description = models.CharField(max_length=2000, null=True, blank=True)
    url = models.CharField(max_length=2000, null=True)
    tool_type = models.ForeignKey(Tool_Type, related_name='tool_type', on_delete=models.CASCADE)
    authentication_type = models.CharField(max_length=15,
                                           choices=(
                                               ('API', 'API Key'),
                                               ('Password',
                                                'Username/Password'),
                                               ('SSH', 'SSH')),
                                           null=True, blank=True)
    username = models.CharField(max_length=200, null=True, blank=True)
    password = models.CharField(max_length=600, null=True, blank=True)
    auth_title = models.CharField(max_length=200, null=True, blank=True,
                                  verbose_name="Title for SSH/API Key")
    ssh = models.CharField(max_length=6000, null=True, blank=True)
    api_key = models.CharField(max_length=600, null=True, blank=True,
                               verbose_name="API Key")

    class Meta:
        ordering = ['name']

    def __unicode__(self):
        return self.name

    def __str__(self):
        return self.name


class Network_Locations(models.Model):
    location = models.CharField(max_length=500, help_text="Location of network testing: Examples: VPN, Internet or Internal.")

    def __unicode__(self):
        return self.location

    def __str__(self):
        return self.location


class Engagement_Presets(models.Model):
    title = models.CharField(max_length=500, default=None, help_text="Brief description of preset.")
    test_type = models.ManyToManyField(Test_Type, default=None, blank=True)
    network_locations = models.ManyToManyField(Network_Locations, default=None, blank=True)
    notes = models.CharField(max_length=2000, help_text="Description of what needs to be tested or setting up environment for testing", null=True, blank=True)
    scope = models.CharField(max_length=800, help_text="Scope of Engagement testing, IP's/Resources/URL's)", default=None, blank=True)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    created = models.DateTimeField(auto_now_add=True, null=False)

    def __unicode__(self):
        return self.title

    def __str__(self):
        return self.title

    class Meta:
        ordering = ['title']


class Engagement_Type(models.Model):
    name = models.CharField(max_length=200)

    def __unicode__(self):
        return self.name

    def __str__(self):
        return self.name


class Engagement(models.Model):
    name = models.CharField(max_length=300, null=True, blank=True)
    description = models.CharField(max_length=2000, null=True, blank=True)
    version = models.CharField(max_length=100, null=True, blank=True, help_text="Version of the product the engagement tested.")
    eng_type = models.ForeignKey(Engagement_Type, null=True, blank=True, on_delete=models.CASCADE)
    first_contacted = models.DateField(null=True, blank=True)
    target_start = models.DateField(null=False, blank=False)
    target_end = models.DateField(null=False, blank=False)
    lead = models.ForeignKey(User, editable=True, null=True, on_delete=models.CASCADE)
    requester = models.ForeignKey(Contact, null=True, blank=True, on_delete=models.CASCADE)
    preset = models.ForeignKey(Engagement_Presets, null=True, blank=True, help_text="Settings and notes for performing this engagement.", on_delete=models.CASCADE)
    reason = models.CharField(max_length=2000, null=True, blank=True)
    report_type = models.ForeignKey(Report_Type, null=True, blank=True, on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    updated = models.DateTimeField(auto_now=True, null=True)
    created = models.DateTimeField(auto_now_add=True, null=True)
    active = models.BooleanField(default=True, editable=False)
    tracker = models.URLField(max_length=200, help_text="Link to epic or ticket system with changes to version.", editable=True, blank=True, null=True)
    test_strategy = models.URLField(editable=True, blank=True, null=True)
    threat_model = models.BooleanField(default=True)
    api_test = models.BooleanField(default=True)
    pen_test = models.BooleanField(default=True)
    check_list = models.BooleanField(default=True)
    status = models.CharField(editable=True, max_length=2000, default='',
                              null=True,
                              choices=(('Not Started', 'Not Started'),
                                       ('Blocked', 'Blocked'),
                                       ('Cancelled', 'Cancelled'),
                                       ('Completed', 'Completed'),
                                       ('In Progress', 'In Progress'),
                                       ('On Hold', 'On Hold'),
                                       ('Waiting for Resource', 'Waiting for Resource')))
    progress = models.CharField(max_length=100,
                                default='threat_model', editable=False)
    tmodel_path = models.CharField(max_length=1000, default='none',
                                   editable=False, blank=True, null=True)
    risk_path = models.CharField(max_length=1000, default='none',
                                 editable=False, blank=True, null=True)
    risk_acceptance = models.ManyToManyField("Risk_Acceptance",
                                             default=None,
                                             editable=False,
                                             blank=True)
    done_testing = models.BooleanField(default=False, editable=False)
    engagement_type = models.CharField(editable=True, max_length=30, default='Interactive',
                                       null=True,
                                       choices=(('Interactive', 'Interactive'),
                                                ('CI/CD', 'CI/CD')))
    build_id = models.CharField(editable=True, max_length=150,
                                   null=True, blank=True, help_text="Build ID of the product the engagement tested.", verbose_name="Build ID")
    commit_hash = models.CharField(editable=True, max_length=150,
                                   null=True, blank=True, help_text="Commit hash from repo", verbose_name="Commit Hash")
    branch_tag = models.CharField(editable=True, max_length=150,
                                   null=True, blank=True, help_text="Tag or branch of the product the engagement tested.", verbose_name="Branch/Tag")
    build_server = models.ForeignKey(Tool_Configuration, verbose_name="Build Server", help_text="Build server responsible for CI/CD test", null=True, blank=True, related_name='build_server', on_delete=models.CASCADE)
    source_code_management_server = models.ForeignKey(Tool_Configuration, null=True, blank=True, verbose_name="SCM Server", help_text="Source code server for CI/CD test", related_name='source_code_management_server', on_delete=models.CASCADE)
    source_code_management_uri = models.URLField(max_length=600, null=True, blank=True, editable=True, verbose_name="Repo", help_text="Resource link to source code")
    orchestration_engine = models.ForeignKey(Tool_Configuration, verbose_name="Orchestration Engine", help_text="Orchestration service responsible for CI/CD test", null=True, blank=True, related_name='orchestration', on_delete=models.CASCADE)
    deduplication_on_engagement = models.BooleanField(default=False)

    # used for prefetching tags because django-tagging doesn't support that out of the box
    tagged_items = GenericRelation(TaggedItem)

    class Meta:
        ordering = ['-target_start']

    def is_overdue(self):
        if self.engagement_type == 'CI/CD':
            overdue_grace_days = 10
        else:
            overdue_grace_days = 0

        max_end_date = timezone.now() - relativedelta(days=overdue_grace_days)

        if self.target_end < max_end_date.date():
            return True

        return False

    def __unicode__(self):
        return "Engagement: %s (%s)" % (self.name if self.name else '',
                                        self.target_start.strftime(
                                            "%b %d, %Y"))

    def __str__(self):
        return "Engagement: %s (%s)" % (self.name if self.name else '',
                                        self.target_start.strftime(
                                            "%b %d, %Y"))

    def get_breadcrumbs(self):
        bc = self.product.get_breadcrumbs()
        bc += [{'title': self.__unicode__(),
                'url': reverse('view_engagement', args=(self.id,))}]
        return bc

    @property
    def unaccepted_open_findings(self):
        accepted_findings = Finding.objects.filter(risk_acceptance__engagement=self)
        accepted_ids = [f.id for f in accepted_findings.only('id')]
        return Finding.objects.filter(active=True, verified=True, duplicate=False,
                                      test__engagement=self).exclude(id__in=accepted_ids)

    def accept_risks(self, accepted_risks):
        self.risk_acceptance.add(*accepted_risks)


class CWE(models.Model):
    url = models.CharField(max_length=1000)
    description = models.CharField(max_length=2000)
    number = models.IntegerField()


class Endpoint_Params(models.Model):
    param = models.CharField(max_length=150)
    value = models.CharField(max_length=150)
    method_type = (('GET', 'GET'),
                   ('POST', 'POST'))
    method = models.CharField(max_length=20, blank=False, null=True, choices=method_type)


class Endpoint(models.Model):
    protocol = models.CharField(null=True, blank=True, max_length=10,
                                help_text="The communication protocol such as 'http', 'ftp', etc.")
    host = models.CharField(null=True, blank=True, max_length=500,
                            help_text="The host name or IP address, you can also include the port number. For example"
                                      "'127.0.0.1', '127.0.0.1:8080', 'localhost', 'yourdomain.com'.")
    fqdn = models.CharField(null=True, blank=True, max_length=500)
    port = models.IntegerField(null=True, blank=True,
                               help_text="The network port associated with the endpoint.")
    path = models.CharField(null=True, blank=True, max_length=500,
                            help_text="The location of the resource, it should start with a '/'. For example"
                                      "/endpoint/420/edit")
    query = models.CharField(null=True, blank=True, max_length=1000,
                             help_text="The query string, the question mark should be omitted."
                                       "For example 'group=4&team=8'")
    fragment = models.CharField(null=True, blank=True, max_length=500,
                                help_text="The fragment identifier which follows the hash mark. The hash mark should "
                                          "be omitted. For example 'section-13', 'paragraph-2'.")
    product = models.ForeignKey(Product, null=True, blank=True, on_delete=models.CASCADE)
    endpoint_params = models.ManyToManyField(Endpoint_Params, blank=True,
                                             editable=False)
    remediated = models.BooleanField(default=False, blank=True)

    # used for prefetching tags because django-tagging doesn't support that out of the box
    tagged_items = GenericRelation(TaggedItem)

    class Meta:
        ordering = ['product', 'protocol', 'host', 'path', 'query', 'fragment']

    def __unicode__(self):
        from urllib.parse import uses_netloc

        netloc = self.host
        port = self.port
        scheme = self.protocol
        url = self.path if self.path else ''
        query = self.query
        fragment = self.fragment

        if port:
            # If http or https on standard ports then don't tack on the port number
            if (port != 443 and scheme == "https") or (port != 80 and scheme == "http"):
                netloc += ':%s' % port

        if netloc or (scheme and scheme in uses_netloc and url[:2] != '//'):
            if url and url[:1] != '/':
                url = '/' + url
            if scheme and scheme in uses_netloc and url[:2] != '//':
                url = '//' + (netloc or '') + url
            else:
                url = (netloc or '') + url
        if scheme:
            url = scheme + ':' + url
        if query:
            url = url + '?' + query
        if fragment:
            url = url + '#' + fragment
        return url

    def __str__(self):
        from urllib.parse import uses_netloc

        netloc = self.host
        port = self.port
        scheme = self.protocol
        url = self.path if self.path else ''
        query = self.query
        fragment = self.fragment

        if port:
            # If http or https on standard ports then don't tack on the port number
            if (port != 443 and scheme == "https") or (port != 80 and scheme == "http"):
                netloc += ':%s' % port

        if netloc or (scheme and scheme in uses_netloc and url[:2] != '//'):
            if url and url[:1] != '/':
                url = '/' + url
            if scheme and scheme in uses_netloc and url[:2] != '//':
                url = '//' + (netloc or '') + url
            else:
                url = (netloc or '') + url
        if scheme:
            url = scheme + ':' + url
        if query:
            url = url + '?' + query
        if fragment:
            url = url + '#' + fragment
        return url

    def __hash__(self):
        return self.__str__().__hash__()

    def __eq__(self, other):
        if isinstance(other, Endpoint):
            return self.__unicode__() == other.__unicode__()
        else:
            return NotImplemented

    @cached_property
    def finding_count(self):
        host = self.host_no_port

        endpoints = Endpoint.objects.filter(host__regex="^" + host + ":?",
                                            product=self.product).distinct()

        findings = Finding.objects.filter(endpoints__in=endpoints,
                                          active=True,
                                          verified=True,
                                          out_of_scope=False).distinct()

        return findings.count()

    def active_findings(self):
        host = self.host_no_port

        endpoints = Endpoint.objects.filter(host__regex="^" + host + ":?",
                                            product=self.product).distinct()
        return Finding.objects.filter(endpoints__in=endpoints,
                                      active=True,
                                      verified=True,
                                      mitigated__isnull=True,
                                      false_p=False,
                                      duplicate=False).distinct().order_by(
            'numerical_severity')

    @cached_property
    def finding_count_endpoint(self):
        findings = Finding.objects.filter(endpoints=self,
                                          active=True,
                                          verified=True,
                                          duplicate=False,
                                          out_of_scope=False).distinct()

        return findings.count()

    def get_breadcrumbs(self):
        bc = self.product.get_breadcrumbs()
        bc += [{'title': self.host_no_port,
                'url': reverse('view_endpoint', args=(self.id,))}]
        return bc

    @staticmethod
    def from_uri(uri):
        return Endpoint()

    @property
    def host_no_port(self):
        if ":" in self.host:
            return self.host[:self.host.index(":")]
        else:
            return self.host

    @property
    def host_with_port(self):
        host = self.host
        port = self.port
        scheme = self.protocol
        if ":" in host:
            return host
        elif (port is None) and (scheme == "https"):
            return host + ':443'
        elif (port is None) and (scheme == "http"):
            return host + ':80'
        else:
            return str(self)


class NoteHistory(models.Model):
    note_type = models.ForeignKey(Note_Type, null=True, blank=True, on_delete=models.CASCADE)
    data = models.TextField()
    time = models.DateTimeField(null=True, editable=False,
                                default=get_current_datetime)
    current_editor = models.ForeignKey(User, editable=False, null=True, on_delete=models.CASCADE)


class Notes(models.Model):
    note_type = models.ForeignKey(Note_Type, related_name='note_type', null=True, blank=True, on_delete=models.CASCADE)
    entry = models.TextField()
    date = models.DateTimeField(null=False, editable=False,
                                default=get_current_datetime)
    author = models.ForeignKey(User, related_name='editor_notes_set', editable=False, on_delete=models.CASCADE)
    private = models.BooleanField(default=False)
    edited = models.BooleanField(default=False)
    editor = models.ForeignKey(User, related_name='author_notes_set', editable=False, null=True, on_delete=models.CASCADE)
    edit_time = models.DateTimeField(null=True, editable=False,
                                default=get_current_datetime)
    history = models.ManyToManyField(NoteHistory, blank=True,
                                   editable=False)

    class Meta:
        ordering = ['-date']

    def __unicode__(self):
        return self.entry

    def __str__(self):
        return self.entry


class Development_Environment(models.Model):
    name = models.CharField(max_length=200)

    def __unicode__(self):
        return self.name

    def __str__(self):
        return self.name

    def get_breadcrumbs(self):
        return [{"title": self.__unicode__(),
                 "url": reverse("edit_dev_env", args=(self.id,))}]


class Test(models.Model):
    engagement = models.ForeignKey(Engagement, editable=False, on_delete=models.CASCADE)
    lead = models.ForeignKey(User, editable=True, null=True, on_delete=models.CASCADE)
    test_type = models.ForeignKey(Test_Type, on_delete=models.CASCADE)
    title = models.CharField(max_length=255, null=True, blank=True)
    description = models.TextField(null=True, blank=True)
    target_start = models.DateTimeField()
    target_end = models.DateTimeField()
    estimated_time = models.TimeField(null=True, blank=True, editable=False)
    actual_time = models.TimeField(null=True, blank=True, editable=False, )
    percent_complete = models.IntegerField(null=True, blank=True,
                                           editable=True)
    notes = models.ManyToManyField(Notes, blank=True,
                                   editable=False)
    environment = models.ForeignKey(Development_Environment, null=True,
                                    blank=False, on_delete=models.CASCADE)

    updated = models.DateTimeField(auto_now=True, null=True)
    created = models.DateTimeField(auto_now_add=True, null=True)

    # used for prefetching tags because django-tagging doesn't support that out of the box
    tagged_items = GenericRelation(TaggedItem)

    version = models.CharField(max_length=100, null=True, blank=True)

    def test_type_name(self):
        return self.test_type.name

    def __unicode__(self):
        if self.title:
            return "%s (%s)" % (self.title, self.test_type)
        return str(self.test_type)

    def __str__(self):
        if self.title:
            return "%s (%s)" % (self.title, self.test_type)
        return str(self.test_type)

    def get_breadcrumbs(self):
        bc = self.engagement.get_breadcrumbs()
        bc += [{'title': self.__unicode__(),
                'url': reverse('view_test', args=(self.id,))}]
        return bc

    def verified_finding_count(self):
        return self.finding_set.filter(verified=True).count()

    @property
    def unaccepted_open_findings(self):
        accepted_findings = Finding.objects.filter(risk_acceptance__engagement=self.engagement)
        accepted_ids = [f.id for f in accepted_findings.only('id')]
        return Finding.objects.filter(active=True, verified=True, duplicate=False, test=self).exclude(
            id__in=accepted_ids)

    def accept_risks(self, accepted_risks):
        self.engagement.risk_acceptance.add(*accepted_risks)


class VA(models.Model):
    address = models.TextField(editable=False, default="none")
    user = models.ForeignKey(User, editable=False, on_delete=models.CASCADE)
    result = models.ForeignKey(Test, editable=False, null=True, blank=True, on_delete=models.CASCADE)
    status = models.BooleanField(default=False, editable=False)
    start = models.CharField(max_length=100)


class Sonarqube_Issue(models.Model):
    key = models.CharField(max_length=30, unique=True, help_text="SonarQube issue key")
    status = models.CharField(max_length=20, help_text="SonarQube issue status")
    type = models.CharField(max_length=15, help_text="SonarQube issue type")

    def __str__(self):
        return self.key


class Sonarqube_Issue_Transition(models.Model):
    sonarqube_issue = models.ForeignKey(Sonarqube_Issue, on_delete=models.CASCADE, db_index=True)
    created = models.DateTimeField(null=False, editable=False, default=now)
    finding_status = models.CharField(max_length=100)
    sonarqube_status = models.CharField(max_length=50)
    transitions = models.CharField(max_length=100)

    class Meta:
        ordering = ('-created', )


class Sonarqube_Product(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    sonarqube_project_key = models.CharField(
        max_length=200, null=True, blank=True, verbose_name="SonarQube Project Key"
    )
    sonarqube_tool_config = models.ForeignKey(
        Tool_Configuration, verbose_name="SonarQube Configuration",
        null=True, blank=True, on_delete=models.CASCADE
    )

    def __unicode__(self):
        return '{} | {}'.format(self.product.name, self.sonarqube_project_key)

    def __str__(self):
        return '{} | {}'.format(self.product.name, self.sonarqube_project_key)


class Finding(models.Model):
    title = models.CharField(max_length=511)
    date = models.DateField(default=get_current_date)
    cwe = models.IntegerField(default=0, null=True, blank=True)
    cve_regex = RegexValidator(regex=r'^[A-Z]{1,10}(-\d+)+$',
                               message="Vulnerability ID must be entered in the format: 'ABC-9999-9999'.")
    cve = models.CharField(validators=[cve_regex], max_length=28, null=True,
                           help_text="CVE or other vulnerability identifier")
    url = models.TextField(null=True, blank=True, editable=False)
    severity = models.CharField(max_length=200, help_text="The severity level of this flaw (Critical, High, Medium, Low, Informational)")
    description = models.TextField()
    mitigation = models.TextField()
    impact = models.TextField()
    steps_to_reproduce = models.TextField(null=True, blank=True)
    severity_justification = models.TextField(null=True, blank=True)
    endpoints = models.ManyToManyField(Endpoint, blank=True)
    unsaved_endpoints = []
    unsaved_request = None
    unsaved_response = None
    unsaved_tags = None
    references = models.TextField(null=True, blank=True, db_column="refs")
    test = models.ForeignKey(Test, editable=False, on_delete=models.CASCADE)
    # TODO: Will be deprecated soon
    is_template = models.BooleanField(default=False)
    active = models.BooleanField(default=True)
    verified = models.BooleanField(default=True)
    false_p = models.BooleanField(default=False, verbose_name="False Positive")
    duplicate = models.BooleanField(default=False)
    duplicate_finding = models.ForeignKey('self', editable=False, null=True,
                                          related_name='original_finding',
                                          blank=True, on_delete=models.CASCADE)
    out_of_scope = models.BooleanField(default=False)
    under_review = models.BooleanField(default=False)
    review_requested_by = models.ForeignKey(Dojo_User, null=True, blank=True,
                                            related_name='review_requested_by', on_delete=models.CASCADE)
    reviewers = models.ManyToManyField(User, blank=True)

    # Defect Tracking Review
    under_defect_review = models.BooleanField(default=False)
    defect_review_requested_by = models.ForeignKey(Dojo_User, null=True, blank=True,
                                                   related_name='defect_review_requested_by', on_delete=models.CASCADE)
    is_Mitigated = models.BooleanField(default=False)
    thread_id = models.IntegerField(default=0, editable=False)
    mitigated = models.DateTimeField(editable=False, null=True, blank=True)
    mitigated_by = models.ForeignKey(User, null=True, editable=False,
                                     related_name="mitigated_by", on_delete=models.CASCADE)
    reporter = models.ForeignKey(User, editable=False, default=1, related_name='reporter', on_delete=models.CASCADE)
    notes = models.ManyToManyField(Notes, blank=True,
                                   editable=False)
    numerical_severity = models.CharField(max_length=4)
    last_reviewed = models.DateTimeField(null=True, editable=False)
    last_reviewed_by = models.ForeignKey(User, null=True, editable=False,
                                         related_name='last_reviewed_by', on_delete=models.CASCADE)
    images = models.ManyToManyField('FindingImage', blank=True)

    line_number = models.CharField(null=True, blank=True, max_length=200,
                                   editable=False)  # Deprecated will be removed, use line
    sourcefilepath = models.TextField(null=True, blank=True, editable=False)  # Not used? to remove
    sourcefile = models.TextField(null=True, blank=True, editable=False)
    param = models.TextField(null=True, blank=True, editable=False)
    payload = models.TextField(null=True, blank=True, editable=False)
    hash_code = models.TextField(null=True, blank=True, editable=False)

    line = models.IntegerField(null=True, blank=True,
                               verbose_name="Line number",
                               help_text="Line number. For SAST, when source (start of the attack vector) and sink (end of the attack vector) information are available, put sink information here")
    file_path = models.CharField(
        null=True,
        blank=True,
        max_length=4000,
        help_text="File name with path. For SAST, when source (start of the attack vector) and sink (end of the attack vector) information are available, put sink information here")
    component_name = models.CharField(null=True, blank=True, max_length=200,
                                     help_text="Name of the component containing the finding. ")
    component_version = models.CharField(null=True, blank=True, max_length=100,
                                        help_text="Version of the component.")
    found_by = models.ManyToManyField(Test_Type, editable=False)
    static_finding = models.BooleanField(default=False)
    dynamic_finding = models.BooleanField(default=True)
    created = models.DateTimeField(auto_now_add=True, null=True)
    jira_creation = models.DateTimeField(editable=True, null=True)
    jira_change = models.DateTimeField(editable=True, null=True)
    scanner_confidence = models.IntegerField(null=True, blank=True, default=None, editable=False, help_text="Confidence level of vulnerability which is supplied by the scannner.")
    sonarqube_issue = models.ForeignKey(Sonarqube_Issue, null=True, blank=True, help_text="SonarQube issue", on_delete=models.CASCADE)
    unique_id_from_tool = models.CharField(null=True, blank=True, max_length=500, help_text="Vulnerability technical id from the source tool. Allows to track unique vulnerabilities")
    sast_source_object = models.CharField(null=True, blank=True, max_length=500, help_text="Source object (variable, function...) of the attack vector")
    sast_sink_object = models.CharField(null=True, blank=True, max_length=500, help_text="Sink object (variable, function...) of the attack vector")
    sast_source_line = models.IntegerField(null=True, blank=True,
                               verbose_name="Line number",
                               help_text="Source line number of the attack vector")
    sast_source_file_path = models.CharField(null=True, blank=True, max_length=4000, help_text="Source filepath of the attack vector")
    nb_occurences = models.IntegerField(null=True, blank=True,
                               verbose_name="Number of occurences",
                               help_text="Number of occurences in the source tool when several vulnerabilites were found and aggregated by the scanner")

    # used for prefetching tags because django-tagging doesn't support that out of the box
    tagged_items = GenericRelation(TaggedItem)

    SEVERITIES = {'Info': 4, 'Low': 3, 'Medium': 2,
                  'High': 1, 'Critical': 0}

    class Meta:
        ordering = ('numerical_severity', '-date', 'title')
        indexes = [
            models.Index(fields=['cve']),
            models.Index(fields=['cwe']),
            models.Index(fields=['out_of_scope']),
            models.Index(fields=['false_p']),
            models.Index(fields=['verified']),
            models.Index(fields=['mitigated']),
            models.Index(fields=['active']),
            models.Index(fields=['numerical_severity']),
            models.Index(fields=['date']),
            models.Index(fields=['title']),
        ]

    @classmethod
    def unaccepted_open_findings(cls):
        return cls.objects.filter(active=True, verified=True, duplicate=False, risk_acceptance__isnull=True)

    @property
    def similar_findings(self):
        filtered = Finding.objects.all()

        if self.test.engagement.deduplication_on_engagement:
            filtered = filtered.filter(test__engagement=self.test.engagement)
        else:
            filtered = filtered.filter(test__engagement__product=self.test.engagement.product)

        if self.cve:
            filtered = filtered.filter(cve=self.cve)
        if self.cwe:
            filtered = filtered.filter(cwe=self.cwe)
        if self.file_path:
            filtered = filtered.filter(file_path=self.file_path)
        if self.line:
            filtered = filtered.filter(line=self.line)
        if self.unique_id_from_tool:
            filtered = filtered.filter(unique_id_from_tool=self.unique_id_from_tool)
        return filtered.exclude(pk=self.pk)[:10]

    def compute_hash_code(self):
        if hasattr(settings, 'HASHCODE_FIELDS_PER_SCANNER') and hasattr(settings, 'HASHCODE_ALLOWS_NULL_CWE') and hasattr(settings, 'HASHCODE_ALLOWED_FIELDS'):
            # Default fields
            if self.dynamic_finding:
                hashcodeFields = ['title', 'cwe', 'line', 'file_path', 'description', 'endpoints']
            else:
                hashcodeFields = ['title', 'cwe', 'line', 'file_path', 'description']

            # Check for an override for this scan_type in the deduplication configuration
            scan_type = self.test.test_type.name
            if (scan_type in settings.HASHCODE_FIELDS_PER_SCANNER):
                hashcodeFieldsCandidate = settings.HASHCODE_FIELDS_PER_SCANNER[scan_type]
                # check that the configuration is valid: all elements of HASHCODE_FIELDS_PER_SCANNER should be in HASHCODE_ALLOWED_FIELDS
                if (all(elem in settings.HASHCODE_ALLOWED_FIELDS for elem in hashcodeFieldsCandidate)):
                    # Makes sure that we have a cwe if we need one
                    if (scan_type in settings.HASHCODE_ALLOWS_NULL_CWE):
                        if (settings.HASHCODE_ALLOWS_NULL_CWE[scan_type] or self.cwe != 0):
                            hashcodeFields = hashcodeFieldsCandidate
                        else:
                            deduplicationLogger.warn(
                                "Cannot compute hash_code based on configured fields because cwe is 0 for finding of title '" + self.title + "' found in file '" + str(self.file_path) +
                                "'. Fallback to legacy mode for this finding.")
                    else:
                        # no configuration found for this scanner: defaulting to accepting null cwe when we find one
                        hashcodeFields = hashcodeFieldsCandidate
                        if(self.cwe == 0):
                            deduplicationLogger.debug(
                                "Accepting null cwe by default for finding of title '" + self.title + "' found in file '" + str(self.file_path) +
                                "'. This is because no configuration was found for scanner " + scan_type + " in HASHCODE_ALLOWS_NULL_CWE")
                else:
                    deduplicationLogger.debug(
                        "compute_hash_code - configuration error: some elements of HASHCODE_FIELDS_PER_SCANNER are not in the allowed list HASHCODE_ALLOWED_FIELDS. "
                        "Using default fields")
            else:
                deduplicationLogger.debug(
                    "No configuration for hash_code computation found; using default fields for " + ('dynamic' if self.dynamic_finding else 'static') + ' scanners')
            deduplicationLogger.debug("computing hash_code for finding id " + str(self.id) + " for scan_type " + scan_type + " based on: " + ', '.join(hashcodeFields))
            fields_to_hash = ''
            for hashcodeField in hashcodeFields:
                if(hashcodeField != 'endpoints'):
                    # Generically use the finding attribute having the same name, converts to str in case it's integer
                    fields_to_hash = fields_to_hash + str(getattr(self, hashcodeField))
                    deduplicationLogger.debug(hashcodeField + ' : ' + str(getattr(self, hashcodeField)))
                else:
                    # For endpoints, need to compute the field
                    myEndpoints = self.get_endpoints()
                    fields_to_hash = fields_to_hash + myEndpoints
                    deduplicationLogger.debug(hashcodeField + ' : ' + myEndpoints)
            deduplicationLogger.debug("compute_hash_code - fields_to_hash = " + fields_to_hash)
            return self.hash_fields(fields_to_hash)
        else:
            deduplicationLogger.debug("no or incomplete configuration per hash_code found; using legacy algorithm")
            return self.compute_hash_code_legacy()

    def compute_hash_code_legacy(self):
        fields_to_hash = self.title + str(self.cwe) + str(self.line) + str(self.file_path) + self.description
        if self.dynamic_finding:
            fields_to_hash = fields_to_hash + self.get_endpoints()
        deduplicationLogger.debug("compute_hash_code_legacy - fields_to_hash = " + fields_to_hash)
        return self.hash_fields(fields_to_hash)

    # Get endpoints from self.unsaved_endpoints
    # This sometimes reports "None" for some endpoints but we keep it to avoid hash_code change due to this historically behavior
    def get_endpoints(self):
        endpoint_str = ''
        if len(self.unsaved_endpoints) > 0 and self.id is None:
            deduplicationLogger.debug("get_endpoints: there are unsaved_endpoints and self.id is None")
            for e in self.unsaved_endpoints:
                endpoint_str += str(e.host_with_port)
        else:
            deduplicationLogger.debug("get_endpoints: there aren't unsaved_endpoints or self.id is not None. endpoints count: " + str(self.endpoints.count()))
            for e in self.endpoints.all():
                endpoint_str += str(e.host_with_port)
        return endpoint_str

    # Compute the hash_code from the fields to hash
    def hash_fields(self, fields_to_hash):
        # get bytes to hash
        if(isinstance(fields_to_hash, str)):
            hash_string = fields_to_hash.encode('utf-8').strip()
        elif(isinstance(fields_to_hash, bytes)):
            hash_string = fields_to_hash.strip()
        else:
            deduplicationLogger.debug("trying to convert hash_string of type " + str(type(fields_to_hash)) + " to str and then bytes")
            hash_string = str(fields_to_hash).encode('utf-8').strip()
        return hashlib.sha256(hash_string).hexdigest()

    def remove_from_any_risk_acceptance(self):
        for r in self.risk_acceptance_set.all():
            r.accepted_findings.remove(self)
            if not r.accepted_findings.exists():
                r.delete()

    def duplicate_finding_set(self):
        if self.duplicate:
            return Finding.objects.get(id=self.duplicate_finding.id).original_finding.all().order_by('title')
        else:
            return self.original_finding.all().order_by('title')

    def get_scanner_confidence_text(self):
        scanner_confidence_text = ""
        scanner_confidence = self.scanner_confidence
        if scanner_confidence:
            if scanner_confidence <= 2:
                scanner_confidence_text = "Certain"
            elif scanner_confidence >= 3 and scanner_confidence <= 5:
                scanner_confidence_text = "Firm"
            elif scanner_confidence >= 6:
                scanner_confidence_text = "Tentative"

        return scanner_confidence_text

    @staticmethod
    def get_numerical_severity(severity):
        if severity == 'Critical':
            return 'S0'
        elif severity == 'High':
            return 'S1'
        elif severity == 'Medium':
            return 'S2'
        elif severity == 'Low':
            return 'S3'
        elif severity == 'Info':
            return 'S4'
        else:
            return 'S5'

    @staticmethod
    def get_number_severity(severity):
        if severity == 'Critical':
            return 4
        elif severity == 'High':
            return 3
        elif severity == 'Medium':
            return 2
        elif severity == 'Low':
            return 1
        elif severity == 'Info':
            return 0
        else:
            return 5

    def __unicode__(self):
        return self.title

    def __str__(self):
        return self.title

    def status(self):
        status = []
        if self.active:
            status += ['Active']
        else:
            status += ['Inactive']
        if self.verified:
            status += ['Verified']
        if self.mitigated or self.is_Mitigated:
            status += ['Mitigated']
        if self.false_p:
            status += ['False Positive']
        if self.out_of_scope:
            status += ['Out Of Scope']
        if self.duplicate:
            status += ['Duplicate']
        if self.risk_acceptance_set.exists():
            status += ['Accepted']

        if not len(status):
            status += ['Initial']

        return ", ".join([str(s) for s in status])

    @property
    def age(self):
        if self.mitigated:
            diff = self.mitigated.date() - self.date
        else:
            diff = get_current_date() - self.date
        days = diff.days
        return days if days > 0 else 0

    def sla(self):
        sla_calculation = None
        severity = self.severity
        from dojo.utils import get_system_setting
        sla_age = get_system_setting('sla_' + self.severity.lower())
        if sla_age and self.active:
            sla_calculation = sla_age - self.age
        elif sla_age and self.mitigated:
            age = self.age
            if age < sla_age:
                sla_calculation = 0
            else:
                sla_calculation = sla_age - age
        return sla_calculation

    def github(self):
        try:
            return self.github_issue
        except GITHUB_Issue.DoesNotExist:
            return None

    def has_github_issue(self):
        try:
            issue = self.github_issue
            return True
        except GITHUB_Issue.DoesNotExist:
            return False

    def github_conf(self):
        try:
            github_product_key = GITHUB_PKey.objects.get(product=self.test.engagement.product)
            github_conf = github_product_key.conf
        except:
            github_conf = None
            pass
        return github_conf

    # newer version that can work with prefetching
    def github_conf_new(self):
        try:
            return self.test.engagement.product.github_pkey_set.all()[0].conf
        except:
            return None
            pass

    def jira(self):
        try:
            return self.jira_issue
        except JIRA_Issue.DoesNotExist:
            return None

    def has_jira_issue(self):
        try:
            issue = self.jira_issue
            return True
        except JIRA_Issue.DoesNotExist:
            return False

    def jira_conf(self):
        try:
            jpkey = JIRA_PKey.objects.get(product=self.test.engagement.product)
            jconf = jpkey.conf
        except:
            jconf = None
            pass
        return jconf

    # newer version that can work with prefetching
    def jira_conf_new(self):
        try:
            return self.test.engagement.product.jira_pkey_set.all()[0].conf
        except:
            return None
            pass

    def long_desc(self):
        long_desc = ''
        long_desc += '*' + self.title + '*\n\n'
        long_desc += '*Severity:* ' + str(self.severity) + '\n\n'
        long_desc += '*Cve:* ' + str(self.cve) + '\n\n'
        long_desc += '*Product/Engagement:* ' + self.test.engagement.product.name + ' / ' + self.test.engagement.name + '\n\n'
        if self.test.engagement.branch_tag:
            long_desc += '*Branch/Tag:* ' + self.test.engagement.branch_tag + '\n\n'
        if self.test.engagement.build_id:
            long_desc += '*BuildID:* ' + self.test.engagement.build_id + '\n\n'
        if self.test.engagement.commit_hash:
            long_desc += '*Commit hash:* ' + self.test.engagement.commit_hash + '\n\n'
        long_desc += '*Systems*: \n\n'

        for e in self.endpoints.all():
            long_desc += str(e) + '\n\n'
        long_desc += '*Description*: \n' + self.description + '\n\n'
        long_desc += '*Mitigation*: \n' + self.mitigation + '\n\n'
        long_desc += '*Impact*: \n' + self.impact + '\n\n'
        long_desc += '*References*:' + self.references
        return long_desc

    def save(self, dedupe_option=True, false_history=False, rules_option=True,
             issue_updater_option=True, push_to_jira=False, *args, **kwargs):
        # Make changes to the finding before it's saved to add a CWE template
        new_finding = False

        jira_issue_exists = JIRA_Issue.objects.filter(finding=self).exists()
        if push_to_jira:
            self.jira_change = timezone.now()
            if not jira_issue_exists:
                self.jira_creation = timezone.now()
        # If the product has "Push_all_issues" enabled,
        # then we're pushing this to JIRA no matter what
        if not push_to_jira:
            # only if there is a JIRA configuration
            push_to_jira = self.jira_conf_new() and \
                           self.jira_conf_new().jira_pkey_set.first().push_all_issues

        if self.pk is None:
            # We enter here during the first call from serializers.py
            logger.debug("Saving finding of id " + str(self.id) + " dedupe_option:" + str(dedupe_option) + " (self.pk is None)")
            false_history = True
            from dojo.utils import apply_cwe_to_template
            self = apply_cwe_to_template(self)
            # calling django.db.models superclass save method
            super(Finding, self).save(*args, **kwargs)
        else:
            # We enter here during the second call from serializers.py
            logger.debug("Saving finding of id " + str(self.id) + " dedupe_option:" + str(dedupe_option) + " (self.pk is not None)")
            # calling django.db.models superclass save method
            super(Finding, self).save(*args, **kwargs)

            # Run async the tool issue update to update original issue with Defect Dojo updates
            if issue_updater_option:
                from dojo.tools import tool_issue_updater
                tool_issue_updater.async_tool_issue_update(self)
        if (self.file_path is not None) and (self.endpoints.count() == 0):
            self.static_finding = True
            self.dynamic_finding = False
        elif (self.file_path is not None):
            self.static_finding = True

        # Finding.save is called once from serializers.py with dedupe_option=False because the finding is not ready yet, for example the endpoints are not built
        # It is then called a second time with dedupe_option defaulted to true; now we can compute the hash_code and run the deduplication
        if(dedupe_option):
            if (self.hash_code is not None):
                deduplicationLogger.debug("Hash_code already computed for finding")
            else:
                self.hash_code = self.compute_hash_code()
        self.found_by.add(self.test.test_type)

        if rules_option:
            from dojo.tasks import async_rules
            from dojo.utils import sync_rules
            try:
                if self.reporter.usercontactinfo.block_execution:
                    sync_rules(self, *args, **kwargs)
                else:
                    async_rules(self, *args, **kwargs)
            except UserContactInfo.DoesNotExist:
                async_rules(self, *args, **kwargs)
                pass
        from dojo.utils import calculate_grade
        calculate_grade(self.test.engagement.product)
        # Assign the numerical severity for correct sorting order
        self.numerical_severity = Finding.get_numerical_severity(self.severity)
        super(Finding, self).save()
        system_settings = System_Settings.objects.get()
        if dedupe_option and self.hash_code is not None:
            if system_settings.enable_deduplication:
                from dojo.tasks import async_dedupe
                try:
                    if self.reporter.usercontactinfo.block_execution:
                        dedupe_signal.send(sender=self.__class__, new_finding=self)
                    else:
                        async_dedupe.delay(self, *args, **kwargs)
                except:
                    async_dedupe.delay(self, *args, **kwargs)
                    pass
            else:
                deduplicationLogger.debug("skipping dedupe because it's disabled in system settings")
        if system_settings.false_positive_history and false_history:
            from dojo.tasks import async_false_history
            from dojo.utils import sync_false_history
            try:
                if self.reporter.usercontactinfo.block_execution:
                    sync_false_history(self, *args, **kwargs)
                else:
                    async_false_history.delay(self, *args, **kwargs)
            except:
                async_false_history.delay(self, *args, **kwargs)
                pass

        # Title Casing
        from titlecase import titlecase
        self.title = titlecase(self.title)

        from dojo.utils import calculate_grade
        calculate_grade(self.test.engagement.product)

        # Adding a snippet here for push to JIRA so that it's in one place
        if push_to_jira:
            from dojo.tasks import update_issue_task, add_issue_task
            if jira_issue_exists:
                update_issue_task.delay(self, True)
            else:
                add_issue_task.delay(self, True)

    def delete(self, *args, **kwargs):
        for find in self.original_finding.all():
            # Explicitely delete the duplicates
            super(Finding, find).delete()
        super(Finding, self).delete(*args, **kwargs)
        from dojo.utils import calculate_grade
        calculate_grade(self.test.engagement.product)

    def clean(self):
        no_check = ["test", "reporter"]
        bigfields = ["description", "mitigation", "references", "impact",
                     "url"]
        for field_obj in self._meta.fields:
            field = field_obj.name
            if field not in no_check:
                val = getattr(self, field)
                if not val and field == "title":
                    setattr(self, field, "No title given")
                if not val and field in bigfields:
                    setattr(self, field, "No %s given" % field)

    def severity_display(self):
        try:
            system_settings = System_Settings.objects.get()
            if system_settings.s_finding_severity_naming:
                return self.numerical_severity
            else:
                return self.severity

        except:
            return self.severity

    def get_breadcrumbs(self):
        bc = self.test.get_breadcrumbs()
        bc += [{'title': self.__unicode__(),
                'url': reverse('view_finding', args=(self.id,))}]
        return bc

    def get_report_requests(self):
        if self.burprawrequestresponse_set.count() >= 3:
            return BurpRawRequestResponse.objects.filter(finding=self)[0:3]
        elif self.burprawrequestresponse_set.count() > 0:
            return BurpRawRequestResponse.objects.filter(finding=self)

    def get_request(self):
        if self.burprawrequestresponse_set.count() > 0:
            reqres = BurpRawRequestResponse.objects.filter(finding=self)[0]
        return base64.b64decode(reqres.burpRequestBase64)

    def get_response(self):
        if self.burprawrequestresponse_set.count() > 0:
            reqres = BurpRawRequestResponse.objects.filter(finding=self)[0]
        res = base64.b64decode(reqres.burpResponseBase64)
        # Removes all blank lines
        res = re.sub(r'\n\s*\n', '\n', res)
        return res


Finding.endpoints.through.__unicode__ = lambda \
    x: "Endpoint: " + x.endpoint.host


class Stub_Finding(models.Model):
    title = models.TextField(max_length=1000, blank=False, null=False)
    date = models.DateField(default=get_current_date, blank=False, null=False)
    severity = models.CharField(max_length=200, blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    test = models.ForeignKey(Test, editable=False, on_delete=models.CASCADE)
    reporter = models.ForeignKey(User, editable=False, default=1, on_delete=models.CASCADE)

    class Meta:
        ordering = ('-date', 'title')

    def __unicode__(self):
        return self.title

    def __str__(self):
        return self.title

    def get_breadcrumbs(self):
        bc = self.test.get_breadcrumbs()
        bc += [{'title': "Potential Finding: " + self.__unicode__(),
                'url': reverse('view_potential_finding', args=(self.id,))}]
        return bc


class Finding_Template(models.Model):
    title = models.TextField(max_length=1000)
    cwe = models.IntegerField(default=None, null=True, blank=True)
    cve_regex = RegexValidator(regex=r'^[A-Z]{1,10}(-\d+)+$',
                               message="Vulnerability ID must be entered in the format: 'ABC-9999-9999'.")
    cve = models.CharField(validators=[cve_regex], max_length=28, null=True)
    severity = models.CharField(max_length=200, null=True, blank=True)
    description = models.TextField(null=True, blank=True)
    mitigation = models.TextField(null=True, blank=True)
    impact = models.TextField(null=True, blank=True)
    references = models.TextField(null=True, blank=True, db_column="refs")
    last_used = models.DateTimeField(null=True, editable=False)
    numerical_severity = models.CharField(max_length=4, null=True, blank=True, editable=False)
    template_match = models.BooleanField(default=False, verbose_name='Template Match Enabled', help_text="Enables this template for matching remediation advice. Match will be applied to all active, verified findings by CWE.")
    template_match_title = models.BooleanField(default=False, verbose_name='Match Template by Title and CWE', help_text="Matches by title text (contains search) and CWE.")

    # used for prefetching tags because django-tagging doesn't support that out of the box
    tagged_items = GenericRelation(TaggedItem)

    SEVERITIES = {'Info': 4, 'Low': 3, 'Medium': 2,
                  'High': 1, 'Critical': 0}

    class Meta:
        ordering = ['-cwe']

    def __unicode__(self):
        return self.title

    def __str__(self):
        return self.title

    def get_breadcrumbs(self):
        bc = [{'title': self.__unicode__(),
               'url': reverse('view_template', args=(self.id,))}]
        return bc


class Check_List(models.Model):
    session_management = models.CharField(max_length=50, default='none')
    session_issues = models.ManyToManyField(Finding,
                                            related_name='session_issues',
                                            blank=True)
    encryption_crypto = models.CharField(max_length=50, default='none')
    crypto_issues = models.ManyToManyField(Finding,
                                           related_name='crypto_issues',
                                           blank=True)
    configuration_management = models.CharField(max_length=50, default='')
    config_issues = models.ManyToManyField(Finding,
                                           related_name='config_issues',
                                           blank=True)
    authentication = models.CharField(max_length=50, default='none')
    auth_issues = models.ManyToManyField(Finding,
                                         related_name='auth_issues',
                                         blank=True)
    authorization_and_access_control = models.CharField(max_length=50,
                                                        default='none')
    author_issues = models.ManyToManyField(Finding,
                                           related_name='author_issues',
                                           blank=True)
    data_input_sanitization_validation = models.CharField(max_length=50,
                                                          default='none')
    data_issues = models.ManyToManyField(Finding, related_name='data_issues',
                                         blank=True)
    sensitive_data = models.CharField(max_length=50, default='none')
    sensitive_issues = models.ManyToManyField(Finding,
                                              related_name='sensitive_issues',
                                              blank=True)
    other = models.CharField(max_length=50, default='none')
    other_issues = models.ManyToManyField(Finding, related_name='other_issues',
                                          blank=True)
    engagement = models.ForeignKey(Engagement, editable=False,
                                   related_name='eng_for_check', on_delete=models.CASCADE)

    @staticmethod
    def get_status(pass_fail):
        if pass_fail == 'Pass':
            return 'success'
        elif pass_fail == 'Fail':
            return 'danger'
        else:
            return 'warning'

    def get_breadcrumb(self):
        bc = self.engagement.get_breadcrumb()
        bc += [{'title': "Check List",
                'url': reverse('complete_checklist',
                               args=(self.engagement.id,))}]
        return bc


class BurpRawRequestResponse(models.Model):
    finding = models.ForeignKey(Finding, blank=True, null=True, on_delete=models.CASCADE)
    burpRequestBase64 = models.BinaryField()
    burpResponseBase64 = models.BinaryField()

    def get_request(self):
        return str(base64.b64decode(self.burpRequestBase64), errors='ignore')

    def get_response(self):
        res = str(base64.b64decode(self.burpResponseBase64), errors='ignore')
        # Removes all blank lines
        res = re.sub(r'\n\s*\n', '\n', res)
        return res


class Risk_Acceptance(models.Model):
    path = models.FileField(upload_to='risk/%Y/%m/%d',
                            editable=False, null=False,
                            blank=False, verbose_name="Risk Acceptance File")
    accepted_findings = models.ManyToManyField(Finding)
    expiration_date = models.DateTimeField(default=None, null=True, blank=True)
    accepted_by = models.CharField(max_length=200, default=None, null=True, blank=True, verbose_name='Accepted By', help_text="The entity or person that accepts the risk.")
    reporter = models.ForeignKey(User, editable=False, on_delete=models.CASCADE)
    notes = models.ManyToManyField(Notes, editable=False)
    compensating_control = models.TextField(default=None, blank=True, null=True, help_text="If a compensating control exists to mitigate the finding or reduce risk, then list the compensating control(s).")
    created = models.DateTimeField(null=False, editable=False, default=now)
    updated = models.DateTimeField(editable=False, default=now)

    def __unicode__(self):
        return "Risk Acceptance added on %s" % self.created.strftime(
            "%b %d, %Y")

    def __str__(self):
        return "Risk Acceptance added on %s" % self.created.strftime(
            "%b %d, %Y")

    def filename(self):
        return os.path.basename(self.path.name) \
            if self.path is not None else ''

    def get_breadcrumbs(self):
        bc = self.engagement_set.first().get_breadcrumbs()
        bc += [{'title': self.__unicode__(),
                'url': reverse('view_risk', args=(
                    self.engagement_set.first().product.id, self.id,))}]
        return bc


class Report(models.Model):
    name = models.CharField(max_length=200)
    type = models.CharField(max_length=100, default='Finding')
    format = models.CharField(max_length=15, default='AsciiDoc')
    requester = models.ForeignKey(User, on_delete=models.CASCADE)
    task_id = models.CharField(max_length=50)
    file = models.FileField(upload_to='reports/%Y/%m/%d',
                            verbose_name='Report File', null=True)
    status = models.CharField(max_length=10, default='requested')
    options = models.TextField()
    datetime = models.DateTimeField(auto_now_add=True)
    done_datetime = models.DateTimeField(null=True)

    def __unicode__(self):
        return self.name

    def __str__(self):
        return self.name

    def get_url(self):
        return reverse('download_report', args=(self.id,))

    class Meta:
        ordering = ['-datetime']


class FindingImage(models.Model):
    image = models.ImageField(upload_to=UniqueUploadNameProvider('finding_images'))
    caption = models.CharField(max_length=500, blank=True)
    image_thumbnail = ImageSpecField(source='image',
                                     processors=[ResizeToCover(100, 100)],
                                     format='JPEG',
                                     options={'quality': 70})
    image_small = ImageSpecField(source='image',
                                 processors=[ResizeToCover(640, 480)],
                                 format='JPEG',
                                 options={'quality': 100})
    image_medium = ImageSpecField(source='image',
                                  processors=[ResizeToCover(800, 600)],
                                  format='JPEG',
                                  options={'quality': 100})
    image_large = ImageSpecField(source='image',
                                 processors=[ResizeToCover(1024, 768)],
                                 format='JPEG',
                                 options={'quality': 100})

    def __unicode__(self):
        return self.image.name or 'No Image'

    def __str__(self):
        return self.image.name or 'No Image'


class FindingImageAccessToken(models.Model):
    """This will allow reports to request the images without exposing the
    media root to the world without
    authentication"""
    user = models.ForeignKey(User, null=False, blank=False, on_delete=models.CASCADE)
    image = models.ForeignKey(FindingImage, null=False, blank=False, on_delete=models.CASCADE)
    token = models.CharField(max_length=255)
    size = models.CharField(max_length=9,
                            choices=(
                                ('small', 'Small'),
                                ('medium', 'Medium'),
                                ('large', 'Large'),
                                ('thumbnail', 'Thumbnail'),
                                ('original', 'Original')),
                            default='medium')

    def save(self, *args, **kwargs):
        if not self.token:
            self.token = uuid4()
        return super(FindingImageAccessToken, self).save(*args, **kwargs)


class BannerConf(models.Model):
    banner_enable = models.BooleanField(default=False, null=True, blank=True)
    banner_message = models.CharField(max_length=500, help_text="This message will be displayed on the login page", default='')


class GITHUB_Conf(models.Model):
    configuration_name = models.CharField(max_length=2000, help_text="Enter a name to give to this configuration", default='')
    api_key = models.CharField(max_length=2000, help_text="Enter your Github API Key", default='')

    def __unicode__(self):
        return self.configuration_name

    def __str__(self):
        return self.configuration_name


class GITHUB_Issue(models.Model):
    issue_id = models.CharField(max_length=200)
    issue_url = models.URLField(max_length=2000, verbose_name="GitHub issue URL")
    finding = models.OneToOneField(Finding, null=True, blank=True, on_delete=models.CASCADE)

    def __unicode__(self):
        return str(self.github_issue_id) + '| GitHub Issue URL: ' + str(self.github_issue_url)

    def __str__(self):
        return str(self.github_issue_id) + '| GitHub Issue URL: ' + str(self.github_issue_url)


class GITHUB_Clone(models.Model):
    github_id = models.CharField(max_length=200)
    github_clone_id = models.CharField(max_length=200)


class GITHUB_Details_Cache(models.Model):
    github_id = models.CharField(max_length=200)
    github_key = models.CharField(max_length=200)
    github_status = models.CharField(max_length=200)
    github_resolution = models.CharField(max_length=200)


class GITHUB_PKey(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE)

    git_project = models.CharField(max_length=200, blank=True, verbose_name="Github project", help_text="Specify your project location. (:user/:repo)")
    git_conf = models.ForeignKey(GITHUB_Conf, verbose_name="Github Configuration",
                                 null=True, blank=True, on_delete=models.CASCADE)
    git_push_notes = models.BooleanField(default=False, blank=True, help_text="Notes added to findings will be automatically added to the corresponding github issue")

    def __unicode__(self):
        return self.product.name + " | " + self.git_project

    def __str__(self):
        return self.product.name + " | " + self.git_project


class JIRA_Conf(models.Model):
    configuration_name = models.CharField(max_length=2000, help_text="Enter a name to give to this configuration", default='')
    url = models.URLField(max_length=2000, verbose_name="JIRA URL", help_text="For configuring Jira, view: https://defectdojo.readthedocs.io/en/latest/features.html#jira-integration")
    #    product = models.ForeignKey(Product)
    username = models.CharField(max_length=2000)
    password = models.CharField(max_length=2000)
    #    project_key = models.CharField(max_length=200,null=True, blank=True)
    #    enabled = models.BooleanField(default=True)
    if hasattr(settings, 'JIRA_ISSUE_TYPE_CHOICES_CONFIG'):
        default_issue_type_choices = settings.JIRA_ISSUE_TYPE_CHOICES_CONFIG
    else:
        default_issue_type_choices = (
                                        ('Task', 'Task'),
                                        ('Story', 'Story'),
                                        ('Epic', 'Epic'),
                                        ('Spike', 'Spike'),
                                        ('Bug', 'Bug'),
                                        ('Security', 'Security')
                                    )
    default_issue_type = models.CharField(max_length=15,
                                          choices=default_issue_type_choices,
                                          default='Bug',
                                          help_text='You can define extra issue types in settings.py')
    epic_name_id = models.IntegerField(help_text="To obtain the 'Epic name id' visit https://<YOUR JIRA URL>/rest/api/2/field and search for Epic Name. Copy the number out of cf[number] and paste it here.")
    open_status_key = models.IntegerField(help_text="To obtain the 'open status key' visit https://<YOUR JIRA URL>/rest/api/latest/issue/<ANY VALID ISSUE KEY>/transitions?expand=transitions.fields")
    close_status_key = models.IntegerField(help_text="To obtain the 'open status key' visit https://<YOUR JIRA URL>/rest/api/latest/issue/<ANY VALID ISSUE KEY>/transitions?expand=transitions.fields")
    info_mapping_severity = models.CharField(max_length=200, help_text="Maps to the 'Priority' field in Jira. For example: Info")
    low_mapping_severity = models.CharField(max_length=200, help_text="Maps to the 'Priority' field in Jira. For example: Low")
    medium_mapping_severity = models.CharField(max_length=200, help_text="Maps to the 'Priority' field in Jira. For example: Medium")
    high_mapping_severity = models.CharField(max_length=200, help_text="Maps to the 'Priority' field in Jira. For example: High")
    critical_mapping_severity = models.CharField(max_length=200, help_text="Maps to the 'Priority' field in Jira. For example: Critical")
    finding_text = models.TextField(null=True, blank=True, help_text="Additional text that will be added to the finding in Jira. For example including how the finding was created or who to contact for more information.")
    accepted_mapping_resolution = models.CharField(null=True, blank=True, max_length=300, help_text="JIRA resolution names (comma-separated values) that maps to an Accepted Finding")
    false_positive_mapping_resolution = models.CharField(null=True, blank=True, max_length=300, help_text="JIRA resolution names (comma-separated values) that maps to a False Positive Finding")

    @property
    def accepted_resolutions(self):
        return [m.strip() for m in (self.accepted_mapping_resolution or '').split(',')]

    @property
    def false_positive_resolutions(self):
        return [m.strip() for m in (self.false_positive_mapping_resolution or '').split(',')]

    def __unicode__(self):
        return self.url + " | " + self.username

    def __str__(self):
        return self.url + " | " + self.username

    def get_priority(self, status):
        if status == 'Info':
            return self.info_mapping_severity
        elif status == 'Low':
            return self.low_mapping_severity
        elif status == 'Medium':
            return self.medium_mapping_severity
        elif status == 'High':
            return self.high_mapping_severity
        elif status == 'Critical':
            return self.critical_mapping_severity
        else:
            return 'N/A'


class JIRA_Issue(models.Model):
    jira_id = models.CharField(max_length=200)
    jira_key = models.CharField(max_length=200)
    finding = models.OneToOneField(Finding, null=True, blank=True, on_delete=models.CASCADE)
    engagement = models.OneToOneField(Engagement, null=True, blank=True, on_delete=models.CASCADE)

    def __unicode__(self):
        text = ""
        if self.finding:
            text = self.finding.test.engagement.product.name + " | Finding: " + self.finding.title + ", ID: " + str(self.finding.id)
        elif self.engagement:
            text = self.engagement.product.name + " | Engagement: " + self.engagement.name + ", ID: " + str(self.engagement.id)
        return text + " | Jira Key: " + str(self.jira_key)

    def __str__(self):
        text = ""
        if self.finding:
            text = self.finding.test.engagement.product.name + " | Finding: " + self.finding.title + ", ID: " + str(self.finding.id)
        elif self.engagement:
            text = self.engagement.product.name + " | Engagement: " + self.engagement.name + ", ID: " + str(self.engagement.id)
        return text + " | Jira Key: " + str(self.jira_key)


class JIRA_Clone(models.Model):
    jira_id = models.CharField(max_length=200)
    jira_clone_id = models.CharField(max_length=200)


class JIRA_Details_Cache(models.Model):
    jira_id = models.CharField(max_length=200)
    jira_key = models.CharField(max_length=200)
    jira_status = models.CharField(max_length=200)
    jira_resolution = models.CharField(max_length=200)


class JIRA_PKey(models.Model):
    project_key = models.CharField(max_length=200, blank=True)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    conf = models.ForeignKey(JIRA_Conf, verbose_name="JIRA Configuration",
                             null=True, blank=True, on_delete=models.CASCADE)
    component = models.CharField(max_length=200, blank=True)
    push_all_issues = models.BooleanField(default=False, blank=True,
         help_text="Automatically maintain parity with JIRA. Always create and update JIRA tickets for findings in this Product.")
    enable_engagement_epic_mapping = models.BooleanField(default=False,
                                                         blank=True)
    push_notes = models.BooleanField(default=False, blank=True)

    def __unicode__(self):
        return self.product.name + " | " + self.project_key

    def __str__(self):
        return self.product.name + " | " + self.project_key


NOTIFICATION_CHOICES = (
    ("slack", "slack"), ("hipchat", "hipchat"), ("mail", "mail"),
    ("alert", "alert"))


class Notifications(models.Model):
    product_added = MultiSelectField(choices=NOTIFICATION_CHOICES, default='alert', blank=True)
    engagement_added = MultiSelectField(choices=NOTIFICATION_CHOICES, default='alert', blank=True)
    test_added = MultiSelectField(choices=NOTIFICATION_CHOICES, default='alert', blank=True)
    scan_added = MultiSelectField(choices=NOTIFICATION_CHOICES, default='alert', blank=True, help_text='Triggered whenever an (re-)import has been done that created/updated/closed findings.')
    report_created = MultiSelectField(choices=NOTIFICATION_CHOICES, default='alert', blank=True)
    jira_update = MultiSelectField(choices=NOTIFICATION_CHOICES, default='alert', blank=True)
    upcoming_engagement = MultiSelectField(choices=NOTIFICATION_CHOICES, default='alert', blank=True)
    stale_engagement = MultiSelectField(choices=NOTIFICATION_CHOICES, default='alert', blank=True)
    auto_close_engagement = MultiSelectField(choices=NOTIFICATION_CHOICES, default='alert', blank=True)
    user_mentioned = MultiSelectField(choices=NOTIFICATION_CHOICES, default='alert', blank=True)
    code_review = MultiSelectField(choices=NOTIFICATION_CHOICES, default='alert', blank=True)
    review_requested = MultiSelectField(choices=NOTIFICATION_CHOICES, default='alert', blank=True)
    other = MultiSelectField(choices=NOTIFICATION_CHOICES, default='alert', blank=True)
    user = models.ForeignKey(Dojo_User, default=None, null=True, editable=False, on_delete=models.CASCADE)
    product = models.ForeignKey(Product, default=None, null=True, editable=False, on_delete=models.CASCADE)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['user', 'product'], name="notifications_user_product")
        ]

    @classmethod
    def merge_notifications_list(cls, notifications_list):
        print('merging')
        if not notifications_list:
            print('return empty list')
            return []

        result = None
        for notifications in notifications_list:
            print('id: ', notifications.id)
            print('not.user.get_full_name: ', notifications.user.get_full_name())
            if result is None:
                # we start by copying the first instance, because creating a new instance would set all notification columns to 'alert' :-()
                result = notifications
                # result.pk = None # detach from db
            else:
                # from dojo.utils import concat_comma_separated_strings
                print('combining: ' + str(result.scan_added) + ' with ' + str(notifications.scan_added))
                # result.scan_added = (result.scan_added or []).extend(notifications.scan_added)
                # if result.scan_added:
                #     result.scan_added.extend(notifications.scan_added)
                # else:
                #     result.scan_added = notifications.scan_added

                # This concat looks  better, but requires Python 3.6+
                # result.scan_added = [*result.scan_added, *notifications.scan_added]
                from dojo.utils import merge_sets_safe
                result.product_added = merge_sets_safe(result.product_added, notifications.product_added)
                result.engagement_added = merge_sets_safe(result.engagement_added, notifications.engagement_added)
                result.test_added = merge_sets_safe(result.test_added, notifications.test_added)
                result.scan_added = merge_sets_safe(result.scan_added, notifications.scan_added)
                result.report_created = merge_sets_safe(result.report_created, notifications.report_created)
                result.jira_update = merge_sets_safe(result.jira_update, notifications.jira_update)
                result.upcoming_engagement = merge_sets_safe(result.upcoming_engagement, notifications.upcoming_engagement)
                result.stale_engagement = merge_sets_safe(result.stale_engagement, notifications.stale_engagement)
                result.auto_close_engagement = merge_sets_safe(result.auto_close_engagement, notifications.auto_close_engagement)
                result.user_mentioned = merge_sets_safe(result.user_mentioned, notifications.user_mentioned)
                result.code_review = merge_sets_safe(result.code_review, notifications.code_review)
                result.review_requested = merge_sets_safe(result.review_requested, notifications.review_requested)
                result.other = merge_sets_safe(result.other, notifications.other)

        return result


class Tool_Product_Settings(models.Model):
    name = models.CharField(max_length=200, null=False)
    description = models.CharField(max_length=2000, null=True, blank=True)
    url = models.CharField(max_length=2000, null=True, blank=True)
    product = models.ForeignKey(Product, default=1, editable=False, on_delete=models.CASCADE)
    tool_configuration = models.ForeignKey(Tool_Configuration, null=False,
                                           related_name='tool_configuration', on_delete=models.CASCADE)
    tool_project_id = models.CharField(max_length=200, null=True, blank=True)
    notes = models.ManyToManyField(Notes, blank=True, editable=False)

    class Meta:
        ordering = ['name']


class Tool_Product_History(models.Model):
    product = models.ForeignKey(Tool_Product_Settings, editable=False, on_delete=models.CASCADE)
    last_scan = models.DateTimeField(null=False, editable=False, default=now)
    succesfull = models.BooleanField(default=True, verbose_name="Succesfully")
    configuration_details = models.CharField(max_length=2000, null=True,
                                             blank=True)


class Alerts(models.Model):
    title = models.CharField(max_length=100, default='', null=False)
    description = models.CharField(max_length=2000, null=True)
    url = models.URLField(max_length=2000, null=True)
    source = models.CharField(max_length=100, default='Generic')
    icon = models.CharField(max_length=25, default='icon-user-check')
    user_id = models.ForeignKey(User, null=True, editable=False, on_delete=models.CASCADE)
    created = models.DateTimeField(null=False, editable=False, default=now)

    class Meta:
        ordering = ['-created']


class Cred_User(models.Model):
    name = models.CharField(max_length=200, null=False)
    username = models.CharField(max_length=200, null=False)
    password = models.CharField(max_length=600, null=False)
    role = models.CharField(max_length=200, null=False)
    authentication = models.CharField(max_length=15,
                                      choices=(
                                          ('Form', 'Form Authentication'),
                                          ('SSO', 'SSO Redirect')),
                                      default='Form')
    http_authentication = models.CharField(max_length=15,
                                           choices=(
                                               ('Basic', 'Basic'),
                                               ('NTLM', 'NTLM')),
                                           null=True, blank=True)
    description = models.CharField(max_length=2000, null=True, blank=True)
    url = models.URLField(max_length=2000, null=False)
    environment = models.ForeignKey(Development_Environment, null=False, on_delete=models.CASCADE)
    login_regex = models.CharField(max_length=200, null=True, blank=True)
    logout_regex = models.CharField(max_length=200, null=True, blank=True)
    notes = models.ManyToManyField(Notes, blank=True, editable=False)
    is_valid = models.BooleanField(default=True, verbose_name="Login is valid")

    # selenium_script = models.CharField(max_length=1000, default='none',
    #    editable=False, blank=True, null=True,
    #    verbose_name="Selenium Script File")

    class Meta:
        ordering = ['name']

    def __unicode__(self):
        return self.name + " (" + self.role + ")"

    def __str__(self):
        return self.name + " (" + self.role + ")"


class Cred_Mapping(models.Model):
    cred_id = models.ForeignKey(Cred_User, null=False,
                                related_name="cred_user",
                                verbose_name="Credential", on_delete=models.CASCADE)
    product = models.ForeignKey(Product, null=True, blank=True,
                                related_name="product", on_delete=models.CASCADE)
    finding = models.ForeignKey(Finding, null=True, blank=True,
                                related_name="finding", on_delete=models.CASCADE)
    engagement = models.ForeignKey(Engagement, null=True, blank=True,
                                   related_name="engagement", on_delete=models.CASCADE)
    test = models.ForeignKey(Test, null=True, blank=True, related_name="test", on_delete=models.CASCADE)
    is_authn_provider = models.BooleanField(default=False,
                                            verbose_name="Authentication Provider")
    url = models.URLField(max_length=2000, null=True, blank=True)

    def __unicode__(self):
        return self.cred_id.name + " (" + self.cred_id.role + ")"

    def __str__(self):
        return self.cred_id.name + " (" + self.cred_id.role + ")"


class Language_Type(models.Model):
    language = models.CharField(max_length=100, null=False)
    color = models.CharField(max_length=7, null=True, verbose_name='HTML color')

    def __unicode__(self):
        return self.language

    def __str__(self):
        return self.language


class Languages(models.Model):
    language = models.ForeignKey(Language_Type, on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    user = models.ForeignKey(User, editable=True, blank=True, null=True, on_delete=models.CASCADE)
    files = models.IntegerField(blank=True, null=True, verbose_name='Number of files')
    blank = models.IntegerField(blank=True, null=True, verbose_name='Number of blank lines')
    comment = models.IntegerField(blank=True, null=True, verbose_name='Number of comment lines')
    code = models.IntegerField(blank=True, null=True, verbose_name='Number of code lines')
    created = models.DateTimeField(null=False, editable=False, default=now)

    def __unicode__(self):
        return self.language.language

    def __str__(self):
        return self.language.language

    class Meta:
        unique_together = [('language', 'product')]


class App_Analysis(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    name = models.CharField(max_length=200, null=False)
    user = models.ForeignKey(User, editable=True, on_delete=models.CASCADE)
    confidence = models.IntegerField(blank=True, null=True, verbose_name='Confidence level')
    version = models.CharField(max_length=200, null=True, blank=True, verbose_name='Version Number')
    icon = models.CharField(max_length=200, null=True, blank=True)
    website = models.URLField(max_length=400, null=True, blank=True)
    website_found = models.URLField(max_length=400, null=True, blank=True)
    created = models.DateTimeField(null=False, editable=False, default=now)

    # used for prefetching tags because django-tagging doesn't support that out of the box
    tagged_items = GenericRelation(TaggedItem)

    def __unicode__(self):
        return self.name + " | " + self.product.name

    def __str__(self):
        return self.name + " | " + self.product.name


class Objects_Review(models.Model):
    name = models.CharField(max_length=100, null=True)
    created = models.DateTimeField(null=False, editable=False, default=now)

    def __unicode__(self):
        return self.name

    def __str__(self):
        return self.name


class Objects(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    name = models.CharField(max_length=100, null=True, blank=True)
    path = models.CharField(max_length=600, verbose_name='Full file path',
                            null=True, blank=True)
    folder = models.CharField(max_length=400, verbose_name='Folder',
                              null=True, blank=True)
    artifact = models.CharField(max_length=400, verbose_name='Artifact',
                                null=True, blank=True)
    review_status = models.ForeignKey(Objects_Review, on_delete=models.CASCADE)
    created = models.DateTimeField(null=False, editable=False, default=now)

    # used for prefetching tags because django-tagging doesn't support that out of the box
    tagged_items = GenericRelation(TaggedItem)

    def __unicode__(self):
        name = None
        if self.path is not None:
            name = self.path
        elif self.folder is not None:
            name = self.folder
        elif self.artifact is not None:
            name = self.artifact

        return name

    def __str__(self):
        name = None
        if self.path is not None:
            name = self.path
        elif self.folder is not None:
            name = self.folder
        elif self.artifact is not None:
            name = self.artifact

        return name


class Objects_Engagement(models.Model):
    engagement = models.ForeignKey(Engagement, on_delete=models.CASCADE)
    object_id = models.ForeignKey(Objects, on_delete=models.CASCADE)
    build_id = models.CharField(max_length=150, null=True)
    created = models.DateTimeField(null=False, editable=False, default=now)
    full_url = models.URLField(max_length=400, null=True, blank=True)
    type = models.CharField(max_length=30, null=True)
    percentUnchanged = models.CharField(max_length=10, null=True)

    def __unicode__(self):
        data = ""
        if self.object_id.path:
            data = self.object_id.path
        elif self.object_id.folder:
            data = self.object_id.folder
        elif self.object_id.artifact:
            data = self.object_id.artifact

        return data + " | " + self.engagement.name + " | " + str(self.engagement.id)

    def __str__(self):
        data = ""
        if self.object_id.path:
            data = self.object_id.path
        elif self.object_id.folder:
            data = self.object_id.folder
        elif self.object_id.artifact:
            data = self.object_id.artifact

        return data + " | " + self.engagement.name + " | " + str(self.engagement.id)


class Testing_Guide_Category(models.Model):
    name = models.CharField(max_length=300)
    created = models.DateTimeField(null=False, editable=False, default=now)
    updated = models.DateTimeField(editable=False, default=now)

    class Meta:
        ordering = ('name',)

    def __unicode__(self):
        return self.name

    def __str__(self):
        return self.name


class Testing_Guide(models.Model):
    testing_guide_category = models.ForeignKey(Testing_Guide_Category, on_delete=models.CASCADE)
    identifier = models.CharField(max_length=20, blank=True, null=True, help_text="Test Unique Identifier")
    name = models.CharField(max_length=400, help_text="Name of the test")
    summary = models.CharField(max_length=800, help_text="Summary of the test")
    objective = models.CharField(max_length=800, help_text="Objective of the test")
    how_to_test = models.TextField(default=None, help_text="How to test the objective")
    results_expected = models.CharField(max_length=800, help_text="What the results look like for a test")
    created = models.DateTimeField(null=False, editable=False, default=now)
    updated = models.DateTimeField(editable=False, default=now)

    def __unicode__(self):
        return self.testing_guide_category.name + ': ' + self.name

    def __str__(self):
        return self.testing_guide_category.name + ': ' + self.name


class Benchmark_Type(models.Model):
    name = models.CharField(max_length=300)
    version = models.CharField(max_length=15)
    source = (('PCI', 'PCI'),
              ('OWASP ASVS', 'OWASP ASVS'),
              ('OWASP Mobile ASVS', 'OWASP Mobile ASVS'))
    benchmark_source = models.CharField(max_length=20, blank=False,
                                        null=True, choices=source,
                                        default='OWASP ASVS')
    created = models.DateTimeField(null=False, editable=False, default=now)
    updated = models.DateTimeField(editable=False, default=now)
    enabled = models.BooleanField(default=True)

    def __unicode__(self):
        return self.name + " " + self.version

    def __str__(self):
        return self.name + " " + self.version


class Benchmark_Category(models.Model):
    type = models.ForeignKey(Benchmark_Type, verbose_name='Benchmark Type', on_delete=models.CASCADE)
    name = models.CharField(max_length=300)
    objective = models.TextField()
    references = models.TextField(blank=True, null=True)
    enabled = models.BooleanField(default=True)
    created = models.DateTimeField(null=False, editable=False, default=now)
    updated = models.DateTimeField(editable=False, default=now)

    class Meta:
        ordering = ('name',)

    def __unicode__(self):
        return self.name + ': ' + self.type.name

    def __str__(self):
        return self.name + ': ' + self.type.name


class Benchmark_Requirement(models.Model):
    category = models.ForeignKey(Benchmark_Category, on_delete=models.CASCADE)
    objective_number = models.CharField(max_length=15, null=True)
    objective = models.TextField()
    references = models.TextField(blank=True, null=True)
    level_1 = models.BooleanField(default=False)
    level_2 = models.BooleanField(default=False)
    level_3 = models.BooleanField(default=False)
    enabled = models.BooleanField(default=True)
    cwe_mapping = models.ManyToManyField(CWE, blank=True)
    testing_guide = models.ManyToManyField(Testing_Guide, blank=True)
    created = models.DateTimeField(null=False, editable=False, default=now)
    updated = models.DateTimeField(editable=False, default=now)

    def __unicode__(self):
        return str(self.objective_number) + ': ' + self.category.name

    def __str__(self):
        return str(self.objective_number) + ': ' + self.category.name


class Benchmark_Product(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    control = models.ForeignKey(Benchmark_Requirement, on_delete=models.CASCADE)
    pass_fail = models.BooleanField(default=False, verbose_name='Pass',
                                    help_text='Does the product meet the requirement?')
    enabled = models.BooleanField(default=True,
                                  help_text='Applicable for this specific product.')
    notes = models.ManyToManyField(Notes, blank=True, editable=False)
    created = models.DateTimeField(null=False, editable=False, default=now)
    updated = models.DateTimeField(editable=False, default=now)

    def __unicode__(self):
        return self.product.name + ': ' + self.control.objective_number + ': ' + self.control.category.name

    def __str__(self):
        return self.product.name + ': ' + self.control.objective_number + ': ' + self.control.category.name

    class Meta:
        unique_together = [('product', 'control')]


class Benchmark_Product_Summary(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    benchmark_type = models.ForeignKey(Benchmark_Type, on_delete=models.CASCADE)
    asvs_level = (('Level 1', 'Level 1'),
                    ('Level 2', 'Level 2'),
                    ('Level 3', 'Level 3'))
    desired_level = models.CharField(max_length=15,
                                     null=False, choices=asvs_level,
                                     default='Level 1')
    current_level = models.CharField(max_length=15, blank=True,
                                     null=True, choices=asvs_level,
                                     default='None')
    asvs_level_1_benchmark = models.IntegerField(null=False, default=0, help_text="Total number of active benchmarks for this application.")
    asvs_level_1_score = models.IntegerField(null=False, default=0, help_text="ASVS Level 1 Score")
    asvs_level_2_benchmark = models.IntegerField(null=False, default=0, help_text="Total number of active benchmarks for this application.")
    asvs_level_2_score = models.IntegerField(null=False, default=0, help_text="ASVS Level 2 Score")
    asvs_level_3_benchmark = models.IntegerField(null=False, default=0, help_text="Total number of active benchmarks for this application.")
    asvs_level_3_score = models.IntegerField(null=False, default=0, help_text="ASVS Level 3 Score")
    publish = models.BooleanField(default=False, help_text='Publish score to Product.')
    created = models.DateTimeField(null=False, editable=False, default=now)
    updated = models.DateTimeField(editable=False, default=now)

    def __unicode__(self):
        return self.product.name + ': ' + self.benchmark_type.name

    def __str__(self):
        return self.product.name + ': ' + self.benchmark_type.name

    class Meta:
        unique_together = [('product', 'benchmark_type')]


# product_opts = [f.name for f in Product._meta.fields]
# test_opts = [f.name for f in Test._meta.fields]
# test_type_opts = [f.name for f in Test_Type._meta.fields]
finding_opts = [f.name for f in Finding._meta.fields]
# endpoint_opts = [f.name for f in Endpoint._meta.fields]
# engagement_opts = [f.name for f in Engagement._meta.fields]
# product_type_opts = [f.name for f in Product_Type._meta.fields]
# single_options = product_opts + test_opts + test_type_opts + finding_opts + \
#                  endpoint_opts + engagement_opts + product_type_opts
all_options = []
for x in finding_opts:
    all_options.append((x, x))
operator_options = (('Matches', 'Matches'),
                    ('Contains', 'Contains'))
application_options = (('Append', 'Append'),
                      ('Replace', 'Replace'))
blank_options = (('', ''),)


class Rule(models.Model):
    # add UI notification to let people know what rules were applied

    name = models.CharField(max_length=200)
    enabled = models.BooleanField(default=True)
    text = models.TextField()
    operator = models.CharField(max_length=30, choices=operator_options)
    """
    model_object_options = (('Product', 'Product'),
                            ('Engagement', 'Engagement'), ('Test', 'Test'),
                            ('Finding', 'Finding'), ('Endpoint', 'Endpoint'),
                            ('Product Type', 'Product_Type'), ('Test Type', 'Test_Type'))
    """
    model_object_options = (('Finding', 'Finding'),)
    model_object = models.CharField(max_length=30, choices=model_object_options)
    match_field = models.CharField(max_length=200, choices=all_options)
    match_text = models.TextField()
    application = models.CharField(max_length=200, choices=application_options)
    applies_to = models.CharField(max_length=30, choices=model_object_options)
    # TODO: Add or ?
    # and_rules = models.ManyToManyField('self')
    applied_field = models.CharField(max_length=200, choices=(all_options))
    child_rules = models.ManyToManyField('self', editable=False)
    parent_rule = models.ForeignKey('self', editable=False, null=True, on_delete=models.CASCADE)


class Child_Rule(models.Model):
    # add UI notification to let people know what rules were applied
    operator = models.CharField(max_length=30, choices=operator_options)
    """
    model_object_options = (('Product', 'Product'),
                            ('Engagement', 'Engagement'), ('Test', 'Test'),
                            ('Finding', 'Finding'), ('Endpoint', 'Endpoint'),
                            ('Product Type', 'Product_Type'), ('Test Type', 'Test_Type'))
    """
    model_object_options = (('Finding', 'Finding'),)
    model_object = models.CharField(max_length=30, choices=model_object_options)
    match_field = models.CharField(max_length=200, choices=all_options)
    match_text = models.TextField()
    # TODO: Add or ?
    # and_rules = models.ManyToManyField('self')
    parent_rule = models.ForeignKey(Rule, editable=False, null=True, on_delete=models.CASCADE)


class FieldRule(models.Model):
    field = models.CharField(max_length=200)
    update_options = (('Append', 'Append'),
                        ('Replace', 'Replace'))
    update_type = models.CharField(max_length=30, choices=update_options)
    text = models.CharField(max_length=200)


class CommonNote(models.Model):
    notes = models.ManyToManyField(Notes, blank=True,
                                   editable=False)
    title = models.TextField(max_length=1000)
    scanner = models.TextField(max_length=100)
    product = models.TextField(max_length=100)
    cwe = models.IntegerField(default=0, null=True, blank=True)


def enable_disable_auditlog(enable=True):
    if enable:
        # Register for automatic logging to database
        logger.info('enabling audit logging')
        auditlog.register(Dojo_User)
        auditlog.register(Endpoint)
        auditlog.register(Engagement)
        auditlog.register(Finding)
        auditlog.register(Product)
        auditlog.register(Test)
        auditlog.register(Risk_Acceptance)
        auditlog.register(Finding_Template)
        auditlog.register(Cred_User)
    else:
        logger.info('disabling audit logging')
        auditlog.unregister(Dojo_User)
        auditlog.unregister(Endpoint)
        auditlog.unregister(Engagement)
        auditlog.unregister(Finding)
        auditlog.unregister(Product)
        auditlog.unregister(Test)
        auditlog.unregister(Risk_Acceptance)
        auditlog.unregister(Finding_Template)
        auditlog.unregister(Cred_User)


from dojo.utils import get_system_setting
enable_disable_auditlog(enable=get_system_setting('enable_auditlog'))  # on startup choose safe to retrieve system settiung)

# Register for automatic logging to database
auditlog.register(Dojo_User)
auditlog.register(Endpoint)
auditlog.register(Engagement)
auditlog.register(Finding)
auditlog.register(Product)
auditlog.register(Test)
auditlog.register(Risk_Acceptance)
auditlog.register(Finding_Template)
auditlog.register(Cred_User)

# Register tagging for models
tag_register(Product)
tag_register(Test)
tag_register(Finding)
tag_register(Engagement)
tag_register(Endpoint)
tag_register(Finding_Template)
tag_register(App_Analysis)
tag_register(Objects)

# Patch to support prefetching
PrefetchingTagDescriptor.patch()

# Benchmarks
admin.site.register(Benchmark_Type)
admin.site.register(Benchmark_Requirement)
admin.site.register(Benchmark_Category)
admin.site.register(Benchmark_Product)
admin.site.register(Benchmark_Product_Summary)

# Testing
admin.site.register(Testing_Guide_Category)
admin.site.register(Testing_Guide)

admin.site.register(Engagement_Presets)
admin.site.register(Network_Locations)
admin.site.register(Objects)
admin.site.register(Objects_Review)
admin.site.register(Objects_Engagement)
admin.site.register(Languages)
admin.site.register(Language_Type)
admin.site.register(App_Analysis)
admin.site.register(Test)
admin.site.register(Finding)
admin.site.register(FindingImage)
admin.site.register(FindingImageAccessToken)
admin.site.register(Stub_Finding)
admin.site.register(Engagement)
admin.site.register(Risk_Acceptance)
admin.site.register(Check_List)
admin.site.register(Test_Type)
admin.site.register(Endpoint)
admin.site.register(Product)
admin.site.register(Product_Type)
admin.site.register(Dojo_User)
admin.site.register(UserContactInfo)
admin.site.register(Notes)
admin.site.register(Note_Type)
admin.site.register(CommonNote)
admin.site.register(Report)
admin.site.register(Scan)
admin.site.register(ScanSettings)
admin.site.register(IPScan)
admin.site.register(Alerts)
admin.site.register(JIRA_Issue)
admin.site.register(JIRA_Conf)
admin.site.register(JIRA_PKey)
admin.site.register(GITHUB_Conf)
admin.site.register(GITHUB_PKey)
admin.site.register(Tool_Configuration)
admin.site.register(Tool_Product_Settings)
admin.site.register(Tool_Type)
admin.site.register(Cred_User)
admin.site.register(Cred_Mapping)
admin.site.register(System_Settings, System_SettingsAdmin)
admin.site.register(CWE)
admin.site.register(Regulation)

# Watson
watson.register(Product)
watson.register(Test)
watson.register(Finding)
watson.register(Finding_Template)
watson.register(Endpoint)
watson.register(Engagement)
watson.register(App_Analysis)

# SonarQube Integration
admin.site.register(Sonarqube_Issue)
admin.site.register(Sonarqube_Issue_Transition)
admin.site.register(Sonarqube_Product)
