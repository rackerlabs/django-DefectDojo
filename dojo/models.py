import base64
import hashlib
import logging
from operator import itemgetter
import os
import re
from uuid import uuid4
from django.conf import settings

from auditlog.registry import auditlog
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.core.validators import RegexValidator, validate_ipv46_address
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q, Count
from django_extensions.db.models import TimeStampedModel
from django.utils.deconstruct import deconstructible
from django.utils.timezone import now
from django.utils.functional import cached_property
from django.utils import timezone
from pytz import all_timezones
from polymorphic.models import PolymorphicModel
from multiselectfield import MultiSelectField
from django import forms
from django.utils.translation import gettext as _
from dateutil.relativedelta import relativedelta
from tagulous.models import TagField
import tagulous.admin
from django.db.models import JSONField
from itertools import groupby
import hyperlink
from cvss import CVSS3

logger = logging.getLogger(__name__)
deduplicationLogger = logging.getLogger("dojo.specific-loggers.deduplication")

SEVERITY_CHOICES = (('Info', 'Info'), ('Low', 'Low'), ('Medium', 'Medium'),
                    ('High', 'High'), ('Critical', 'Critical'))

IMPORT_CREATED_FINDING = 'N'
IMPORT_CLOSED_FINDING = 'C'
IMPORT_REACTIVATED_FINDING = 'R'
IMPORT_UPDATED_FINDING = 'U'

IMPORT_ACTIONS = [
    (IMPORT_CREATED_FINDING, 'created'),
    (IMPORT_CLOSED_FINDING, 'closed'),
    (IMPORT_REACTIVATED_FINDING, 'reactivated'),
    (IMPORT_UPDATED_FINDING, 'updated'),
]


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
    CORPORATE_CATEGORY = 'corporate'
    OTHER_CATEGORY = 'other'
    CATEGORY_CHOICES = (
        (PRIVACY_CATEGORY, _('Privacy')),
        (FINANCE_CATEGORY, _('Finance')),
        (EDUCATION_CATEGORY, _('Education')),
        (MEDICAL_CATEGORY, _('Medical')),
        (CORPORATE_CATEGORY, _('Corporate')),
        (OTHER_CATEGORY, _('Other')),
    )

    name = models.CharField(max_length=128, unique=True, help_text=_('The name of the regulation.'))
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
    delete_duplicates = models.BooleanField(default=False, blank=False, help_text="Requires next setting: maximum number of duplicates to retain.")
    max_dupes = models.IntegerField(blank=True, null=True, default=10,
                                    verbose_name='Max Duplicates',
                                    help_text="When enabled, if a single "
                                              "issue reaches the maximum "
                                              "number of duplicates, the "
                                              "oldest will be deleted. Duplicate will not be deleted when left empty. A value of 0 will remove all duplicates.")

    enable_jira = models.BooleanField(default=False,
                                      verbose_name='Enable JIRA integration',
                                      blank=False)

    enable_jira_web_hook = models.BooleanField(default=False,
                                      verbose_name='Enable JIRA web hook',
                                      help_text='Please note: It is strongly recommended to use a secret below and / or IP whitelist the JIRA server using a proxy such as Nginx.',
                                      blank=False)

    disable_jira_webhook_secret = models.BooleanField(default=False,
                                      verbose_name='Disable web hook secret',
                                      help_text='Allows incoming requests without a secret (discouraged legacy behaviour)',
                                      blank=False)

    # will be set to random / uuid by initializer so null needs to be True
    jira_webhook_secret = models.CharField(max_length=64, blank=False, null=True, verbose_name='JIRA Webhook URL',
                                           help_text='Secret needed in URL for incoming JIRA Webhook')

    jira_choices = (('Critical', 'Critical'),
                    ('High', 'High'),
                    ('Medium', 'Medium'),
                    ('Low', 'Low'),
                    ('Info', 'Info'))
    jira_minimum_severity = models.CharField(max_length=20, blank=True,
                                             null=True, choices=jira_choices,
                                             default='Low')
    jira_labels = models.CharField(max_length=200, blank=True, null=True,
                                   help_text='JIRA issue labels space seperated')

    enable_github = models.BooleanField(default=False,
                                      verbose_name='Enable GITHUB integration',
                                      blank=False)

    enable_slack_notifications = \
        models.BooleanField(default=False,
                            verbose_name='Enable Slack notifications',
                            blank=False)
    slack_channel = models.CharField(max_length=100, default='', blank=True,
                    help_text='Optional. Needed if you want to send global notifications.')
    slack_token = models.CharField(max_length=100, default='', blank=True,
                                   help_text='Token required for interacting '
                                             'with Slack. Get one at '
                                             'https://api.slack.com/tokens')
    slack_username = models.CharField(max_length=100, default='', blank=True,
                     help_text='Optional. Will take your bot name otherwise.')
    enable_msteams_notifications = \
        models.BooleanField(default=False,
                            verbose_name='Enable Microsoft Teams notifications',
                            blank=False)
    msteams_url = models.CharField(max_length=400, default='', blank=True,
                                    help_text='The full URL of the '
                                              'incoming webhook')
    enable_mail_notifications = models.BooleanField(default=False, blank=False)
    mail_notifications_from = models.CharField(max_length=200,
                                               default='from@example.com',
                                               blank=True)
    mail_notifications_to = models.CharField(max_length=200, default='',
                                             blank=True)
    false_positive_history = models.BooleanField(default=False, help_text="DefectDojo will automatically mark the finding as a false positive if the finding has been previously marked as a false positive. Not needed when using deduplication, advised to not combine these two.")

    url_prefix = models.CharField(max_length=300, default='', blank=True, help_text="URL prefix if DefectDojo is installed in it's own virtual subdirectory.")
    team_name = models.CharField(max_length=100, default='', blank=True)
    time_zone = models.CharField(max_length=50,
                                 choices=[(tz, tz) for tz in all_timezones],
                                 default='UTC', blank=False)
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
                                          verbose_name="Critical Finding SLA Days",
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
    credentials = models.TextField(max_length=3000, blank=True)
    disclaimer = models.TextField(max_length=3000, default='', blank=True,
                                  verbose_name="Custom Disclaimer",
                                  help_text="Include this custom disclaimer on all notifications and generated reports")
    column_widths = models.TextField(max_length=1500, blank=True)
    drive_folder_ID = models.CharField(max_length=100, blank=True)
    enable_google_sheets = models.BooleanField(default=False, null=True, blank=True)
    email_address = models.EmailField(max_length=100, blank=True)
    risk_acceptance_form_default_days = models.IntegerField(null=True, blank=True, default=180, help_text="Default expiry period for risk acceptance form.")
    risk_acceptance_notify_before_expiration = models.IntegerField(null=True, blank=True, default=10,
                    verbose_name="Risk acceptance expiration heads up days", help_text="Notify X days before risk acceptance expires. Leave empty to disable.")
    enable_credentials = models.BooleanField(
        default=True,
        blank=False,
        verbose_name='Enable credentials',
        help_text="With this setting turned off, credentials will be disabled in the user interface.")
    enable_questionnaires = models.BooleanField(
        default=True,
        blank=False,
        verbose_name='Enable questionnaires',
        help_text="With this setting turned off, questionnaires will be disabled in the user interface.")
    enable_checklists = models.BooleanField(
        default=True,
        blank=False,
        verbose_name='Enable checklists',
        help_text="With this setting turned off, checklists will be disabled in the user interface.")

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
        ordering = ['first_name']

    def get_full_name(self):
        return Dojo_User.generate_full_name(self)

    def __str__(self):
        return self.get_full_name()

    @staticmethod
    def wants_block_execution(user):
        # this return False if there is no user, i.e. in celery processes, unittests, etc.
        return hasattr(user, 'usercontactinfo') and user.usercontactinfo.block_execution

    @staticmethod
    def force_password_reset(user):
        return hasattr(user, 'usercontactinfo') and user.usercontactinfo.force_password_reset

    def disable_force_password_reset(user):
        if hasattr(user, 'usercontactinfo'):
            user.usercontactinfo.force_password_reset = False
            user.usercontactinfo.save()

    def enable_force_password_reset(user):
        if hasattr(user, 'usercontactinfo'):
            user.usercontactinfo.force_password_reset = True
            user.usercontactinfo.save()

    @staticmethod
    def generate_full_name(user):
        """
        Returns the first_name plus the last_name, with a space in between.
        """
        full_name = '%s %s (%s)' % (user.first_name,
                                    user.last_name,
                                    user.username)
        return full_name.strip()


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
    block_execution = models.BooleanField(default=False, help_text="Instead of async deduping a finding the findings will be deduped synchronously and will 'block' the user until completion.")
    force_password_reset = models.BooleanField(default=False, help_text='Forces this user to reset their password on next login.')


class Role(models.Model):
    name = models.CharField(max_length=255, unique=True)
    is_owner = models.BooleanField(default=False)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ('name',)


class Dojo_Group(models.Model):
    name = models.CharField(max_length=255, unique=True)
    description = models.CharField(max_length=4000, null=True, blank=True)
    users = models.ManyToManyField(Dojo_User, through='Dojo_Group_Member', related_name='users', blank=True)

    def __str__(self):
        return self.name


class Dojo_Group_Member(models.Model):
    group = models.ForeignKey(Dojo_Group, on_delete=models.CASCADE)
    user = models.ForeignKey(Dojo_User, on_delete=models.CASCADE)
    role = models.ForeignKey(Role, on_delete=models.CASCADE, help_text="This role determines the permissions of the user to manage the group.", verbose_name="Group role")


class Global_Role(models.Model):
    user = models.OneToOneField(User, null=True, blank=True, on_delete=models.CASCADE)
    group = models.OneToOneField(Dojo_Group, null=True, blank=True, on_delete=models.CASCADE)
    role = models.ForeignKey(Role, on_delete=models.CASCADE, null=True, blank=True, help_text="The global role will be applied to all product types and products.", verbose_name="Global role")


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

    def __str__(self):
        return self.name


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

    def __str__(self):
        return self.entry


class FileUpload(models.Model):
    title = models.CharField(max_length=100, unique=True)
    file = models.FileField(upload_to=UniqueUploadNameProvider('uploaded_files'))


class Product_Type(models.Model):
    """Product types represent the top level model, these can be business unit divisions, different offices or locations, development teams, or any other logical way of distinguishing “types” of products.

       Examples:
         * IAM Team
         * Internal / 3rd Party
         * Main company / Acquisition
         * San Francisco / New York offices
    """
    name = models.CharField(max_length=255, unique=True)
    description = models.CharField(max_length=4000, null=True, blank=True)
    critical_product = models.BooleanField(default=False)
    key_product = models.BooleanField(default=False)
    updated = models.DateTimeField(auto_now=True, null=True)
    created = models.DateTimeField(auto_now_add=True, null=True)
    authorized_users = models.ManyToManyField(User, blank=True)
    members = models.ManyToManyField(Dojo_User, through='Product_Type_Member', related_name='prod_type_members', blank=True)
    authorization_groups = models.ManyToManyField(Dojo_Group, through='Product_Type_Group', related_name='product_type_groups', blank=True)

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

    # only used by bulk risk acceptance api
    @property
    def unaccepted_open_findings(self):
        return Finding.objects.filter(risk_accepted=False, active=True, duplicate=False, test__engagement__product__prod_type=self)

    class Meta:
        ordering = ('name',)

    def __str__(self):
        return self.name

    def get_breadcrumbs(self):
        bc = [{'title': str(self),
               'url': reverse('edit_product_type', args=(self.id,))}]
        return bc

    def get_absolute_url(self):
        from django.urls import reverse
        return reverse('product_type', args=[str(self.id)])


class Product_Line(models.Model):
    name = models.CharField(max_length=300)
    description = models.CharField(max_length=2000)

    def __str__(self):
        return self.name


class Report_Type(models.Model):
    name = models.CharField(max_length=255)


class Test_Type(models.Model):
    name = models.CharField(max_length=200, unique=True)
    static_tool = models.BooleanField(default=False)
    dynamic_tool = models.BooleanField(default=False)
    active = models.BooleanField(default=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ('name',)

    def get_breadcrumbs(self):
        bc = [{'title': str(self),
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
    finding = models.ForeignKey('Finding',
                                 on_delete=models.CASCADE,
                                 null=True,
                                 editable=False,
                                 related_name='finding_meta')

    """
    Verify that this metadata entry belongs only to one object.
    """
    def clean(self):

        ids = [self.product_id,
               self.endpoint_id,
               self.finding_id]
        ids_count = 0

        for id in ids:
            if id is not None:
                ids_count += 1

        if ids_count == 0:
            raise ValidationError('Metadata entries need either a product, an endpoint or a finding')
        if ids_count > 1:
            raise ValidationError('Metadata entries may not have more than one relation, either a product, an endpoint either or a finding')

    def __str__(self):
        return "%s: %s" % (self.name, self.value)

    class Meta:
        unique_together = (('product', 'name'),
                           ('endpoint', 'name'),
                           ('finding', 'name'))


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

    product_manager = models.ForeignKey(Dojo_User, null=True, blank=True,
                                        related_name='product_manager', on_delete=models.CASCADE)
    technical_contact = models.ForeignKey(Dojo_User, null=True, blank=True,
                                          related_name='technical_contact', on_delete=models.CASCADE)
    team_manager = models.ForeignKey(Dojo_User, null=True, blank=True,
                                     related_name='team_manager', on_delete=models.CASCADE)

    created = models.DateTimeField(editable=False, null=True, blank=True)
    prod_type = models.ForeignKey(Product_Type, related_name='prod_type',
                                  null=False, blank=False, on_delete=models.CASCADE)
    updated = models.DateTimeField(editable=False, null=True, blank=True)
    tid = models.IntegerField(default=0, editable=False)
    authorized_users = models.ManyToManyField(User, blank=True)
    members = models.ManyToManyField(Dojo_User, through='Product_Member', related_name='product_members', blank=True)
    authorization_groups = models.ManyToManyField(Dojo_Group, through='Product_Group', related_name='product_groups', blank=True)
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

    tags = TagField(blank=True, force_lowercase=True, help_text="Add tags that help describe this product. Choose from the list or add new tags. Press Enter key to add.")

    enable_simple_risk_acceptance = models.BooleanField(default=False, help_text=_('Allows simple risk acceptance by checking/unchecking a checkbox.'))
    enable_full_risk_acceptance = models.BooleanField(default=True, help_text=_('Allows full risk acceptance using a risk acceptance form, expiration date, uploaded proof, etc.'))

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
            self.active_finding_count = Finding.objects.filter(active=True,
                                            test__engagement__product=self).count()
            return self.active_finding_count

    @cached_property
    def findings_active_verified_count(self):
        try:
            # if prefetched, it's already there
            return self.active_verified_finding_count
        except AttributeError:
            # ideally it's always prefetched and we can remove this code in the future
            self.active_verified_finding_count = Finding.objects.filter(active=True,
                                            verified=True,
                                            test__engagement__product=self).count()
            return self.active_verified_finding_count

    @cached_property
    def endpoint_host_count(self):
        # active_endpoints is (should be) prefetched
        endpoints = self.active_endpoints

        hosts = []
        for e in endpoints:
            if e.host in hosts:
                continue
            else:
                hosts.append(e.host)

        return len(hosts)

    @cached_property
    def endpoint_count(self):
        # active_endpoints is (should be) prefetched
        return len(self.active_endpoints)

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
        bc = [{'title': str(self),
               'url': reverse('view_product', args=(self.id,))}]
        return bc

    @property
    def get_product_type(self):
        return self.prod_type if self.prod_type is not None else 'unknown'

    # only used in APIv2 serializers.py, query should be aligned with findings_count
    @cached_property
    def open_findings_list(self):
        findings = Finding.objects.filter(test__engagement__product=self,
                                          active=True,
                                          )
        findings_list = []
        for i in findings:
            findings_list.append(i.id)
        return findings_list

    @property
    def has_jira_configured(self):
        import dojo.jira_link.helper as jira_helper
        return jira_helper.has_jira_configured(self)

    def get_absolute_url(self):
        from django.urls import reverse
        return reverse('view_product', args=[str(self.id)])


class Product_Member(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    user = models.ForeignKey(Dojo_User, on_delete=models.CASCADE)
    role = models.ForeignKey(Role, on_delete=models.CASCADE)


class Product_Group(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    group = models.ForeignKey(Dojo_Group, on_delete=models.CASCADE)
    role = models.ForeignKey(Role, on_delete=models.CASCADE)


class Product_Type_Member(models.Model):
    product_type = models.ForeignKey(Product_Type, on_delete=models.CASCADE)
    user = models.ForeignKey(Dojo_User, on_delete=models.CASCADE)
    role = models.ForeignKey(Role, on_delete=models.CASCADE)


class Product_Type_Group(models.Model):
    product_type = models.ForeignKey(Product_Type, on_delete=models.CASCADE)
    group = models.ForeignKey(Dojo_Group, on_delete=models.CASCADE)
    role = models.ForeignKey(Role, on_delete=models.CASCADE)


class Tool_Type(models.Model):
    name = models.CharField(max_length=200)
    description = models.CharField(max_length=2000, null=True, blank=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class Tool_Configuration(models.Model):
    name = models.CharField(max_length=200, null=False)
    description = models.CharField(max_length=2000, null=True, blank=True)
    url = models.CharField(max_length=2000, null=True, blank=True)
    tool_type = models.ForeignKey(Tool_Type, related_name='tool_type', on_delete=models.CASCADE)
    authentication_type = models.CharField(max_length=15,
                                           choices=(
                                               ('API', 'API Key'),
                                               ('Password',
                                                'Username/Password'),
                                               ('SSH', 'SSH')),
                                           null=True, blank=True)
    extras = models.CharField(max_length=255, null=True, blank=True, help_text="Additional definitions that will be "
                                                                              "consumed by scanner")
    username = models.CharField(max_length=200, null=True, blank=True)
    password = models.CharField(max_length=600, null=True, blank=True)
    auth_title = models.CharField(max_length=200, null=True, blank=True,
                                  verbose_name="Title for SSH/API Key")
    ssh = models.CharField(max_length=6000, null=True, blank=True)
    api_key = models.CharField(max_length=600, null=True, blank=True,
                               verbose_name="API Key")

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


# declare form here as we can't import forms.py due to circular imports not even locally
class ToolConfigForm_Admin(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput, required=False)
    api_key = forms.CharField(widget=forms.PasswordInput, required=False)
    ssh = forms.CharField(widget=forms.PasswordInput, required=False)

    # django doesn't seem to have an easy way to handle password fields as PasswordInput requires reentry of passwords
    password_from_db = None
    ssh_from_db = None
    api_key_from_db = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance:
            # keep password from db to use if the user entered no password
            self.password_from_db = self.instance.password
            self.ssh_from_db = self.instance.ssh
            self.api_key = self.instance.api_key

    def clean(self):
        cleaned_data = super().clean()
        if not cleaned_data['password'] and not cleaned_data['ssh'] and not cleaned_data['api_key']:
            cleaned_data['password'] = self.password_from_db
            cleaned_data['ssh'] = self.ssh_from_db
            cleaned_data['api_key'] = self.api_key_from_db

        return cleaned_data


class Tool_Configuration_Admin(admin.ModelAdmin):
    form = ToolConfigForm_Admin


class Network_Locations(models.Model):
    location = models.CharField(max_length=500, help_text="Location of network testing: Examples: VPN, Internet or Internal.")

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

    class Meta:
        ordering = ['title']

    def __str__(self):
        return self.title


ENGAGEMENT_STATUS_CHOICES = (('Not Started', 'Not Started'),
                             ('Blocked', 'Blocked'),
                             ('Cancelled', 'Cancelled'),
                             ('Completed', 'Completed'),
                             ('In Progress', 'In Progress'),
                             ('On Hold', 'On Hold'),
                             ('Waiting for Resource', 'Waiting for Resource'))


class Engagement(models.Model):
    name = models.CharField(max_length=300, null=True, blank=True)
    description = models.CharField(max_length=2000, null=True, blank=True)
    version = models.CharField(max_length=100, null=True, blank=True, help_text="Version of the product the engagement tested.")
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
    notes = models.ManyToManyField(Notes, blank=True, editable=False)
    files = models.ManyToManyField(FileUpload, blank=True, editable=False)
    status = models.CharField(editable=True, max_length=2000, default='',
                              null=True,
                              choices=ENGAGEMENT_STATUS_CHOICES)
    progress = models.CharField(max_length=100,
                                default='threat_model', editable=False)
    tmodel_path = models.CharField(max_length=1000, default='none',
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
    deduplication_on_engagement = models.BooleanField(default=False, verbose_name="Deduplication within this engagement only", help_text="If enabled deduplication will only mark a finding in this engagement as duplicate of another finding if both findings are in this engagement. If disabled, deduplication is on the product level.")

    tags = TagField(blank=True, force_lowercase=True, help_text="Add tags that help describe this engagement. Choose from the list or add new tags. Press Enter key to add.")

    class Meta:
        ordering = ['-target_start']
        indexes = [
            models.Index(fields=['product', 'active']),
        ]

    def is_overdue(self):
        if self.engagement_type == 'CI/CD':
            overdue_grace_days = 10
        else:
            overdue_grace_days = 0

        max_end_date = timezone.now() - relativedelta(days=overdue_grace_days)

        if self.target_end < max_end_date.date():
            return True

        return False

    def __str__(self):
        return "Engagement: %s (%s)" % (self.name if self.name else '',
                                        self.target_start.strftime(
                                            "%b %d, %Y"))

    def get_breadcrumbs(self):
        bc = self.product.get_breadcrumbs()
        bc += [{'title': str(self),
                'url': reverse('view_engagement', args=(self.id,))}]
        return bc

    # only used by bulk risk acceptance api
    @property
    def unaccepted_open_findings(self):
        return Finding.objects.filter(risk_accepted=False, active=True, verified=True, duplicate=False, test__engagement=self)

    def accept_risks(self, accepted_risks):
        self.risk_acceptance.add(*accepted_risks)

    @property
    def has_jira_issue(self):
        import dojo.jira_link.helper as jira_helper
        return jira_helper.has_jira_issue(self)

    def get_absolute_url(self):
        from django.urls import reverse
        return reverse('view_engagement', args=[str(self.id)])

    @property
    def is_ci_cd(self):
        return self.engagement_type == "CI/CD"

    def delete(self, *args, **kwargs):
        logger.debug('%d engagement delete', self.id)
        import dojo.finding.helper as helper
        helper.prepare_duplicates_for_delete(engagement=self)
        super().delete(*args, **kwargs)
        calculate_grade(self.product)


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


class Endpoint_Status(models.Model):
    date = models.DateTimeField(default=get_current_date)
    last_modified = models.DateTimeField(null=True, editable=False, default=get_current_datetime)
    mitigated = models.BooleanField(default=False, blank=True)
    mitigated_time = models.DateTimeField(editable=False, null=True, blank=True)
    mitigated_by = models.ForeignKey(User, editable=True, null=True, on_delete=models.CASCADE)
    false_positive = models.BooleanField(default=False, blank=True)
    out_of_scope = models.BooleanField(default=False, blank=True)
    risk_accepted = models.BooleanField(default=False, blank=True)
    endpoint = models.ForeignKey('Endpoint', null=True, blank=True, on_delete=models.CASCADE, related_name='status_endpoint')
    finding = models.ForeignKey('Finding', null=True, blank=True, on_delete=models.CASCADE, related_name='status_finding')

    @property
    def age(self):
        if self.mitigated:
            diff = self.mitigated_time.date() - self.date.date()
        else:
            diff = get_current_date() - self.date.date()
        days = diff.days
        return days if days > 0 else 0

    def __str__(self):
        field_values = []
        for field in self._meta.get_fields():
            field_values.append(str(getattr(self, field.name, '')))
        return ' '.join(field_values)

    class Meta:
        indexes = [
            models.Index(fields=['finding', 'mitigated']),
            models.Index(fields=['endpoint', 'mitigated']),
        ]


class Endpoint(models.Model):
    protocol = models.CharField(null=True, blank=True, max_length=20,
                                 help_text="The communication protocol/scheme such as 'http', 'ftp', 'dns', etc.")
    userinfo = models.CharField(null=True, blank=True, max_length=500,
                              help_text="User info as 'alice', 'bob', etc.")
    host = models.CharField(null=True, blank=True, max_length=500,
                            help_text="The host name or IP address. It must not include the port number. "
                                      "For example '127.0.0.1', 'localhost', 'yourdomain.com'.")
    port = models.IntegerField(null=True, blank=True,
                               help_text="The network port associated with the endpoint.")
    path = models.CharField(null=True, blank=True, max_length=500,
                            help_text="The location of the resource, it must not start with a '/'. For example "
                                      "endpoint/420/edit")
    query = models.CharField(null=True, blank=True, max_length=1000,
                             help_text="The query string, the question mark should be omitted."
                                       "For example 'group=4&team=8'")
    fragment = models.CharField(null=True, blank=True, max_length=500,
                                help_text="The fragment identifier which follows the hash mark. The hash mark should "
                                          "be omitted. For example 'section-13', 'paragraph-2'.")
    product = models.ForeignKey(Product, null=True, blank=True, on_delete=models.CASCADE)
    endpoint_params = models.ManyToManyField(Endpoint_Params, blank=True, editable=False)
    mitigated = models.BooleanField(default=False, blank=True)
    endpoint_status = models.ManyToManyField(Endpoint_Status, blank=True, related_name='endpoint_endpoint_status')

    tags = TagField(blank=True, force_lowercase=True, help_text="Add tags that help describe this endpoint. Choose from the list or add new tags. Press Enter key to add.")

    class Meta:
        ordering = ['product', 'host', 'protocol', 'port', 'userinfo', 'path', 'query', 'fragment']
        indexes = [
            models.Index(fields=['product', 'mitigated']),
        ]

    def clean(self):
        errors = []
        if self.protocol or self.protocol == '':
            if not re.match(r'^[A-Za-z][A-Za-z0-9\.\-\+]+$', self.protocol):  # https://tools.ietf.org/html/rfc3986#section-3.1
                errors.append(ValidationError('Protocol "{}" has invalid format'.format(self.protocol)))
            if self.protocol == '':
                self.protocol = None

        if self.userinfo or self.userinfo == '':
            if not re.match(r'^[A-Za-z0-9\.\-_~%\!\$&\'\(\)\*\+,;=:]+$', self.userinfo):  # https://tools.ietf.org/html/rfc3986#section-3.2.1
                errors.append(ValidationError('Userinfo "{}" has invalid format'.format(self.userinfo)))
            if self.userinfo == '':
                self.userinfo = None

        if self.host:
            if not re.match(r'^[A-Za-z0-9][A-Za-z0-9_\.\-\+]+$', self.host):
                try:
                    validate_ipv46_address(self.host)
                except ValidationError:
                    errors.append(ValidationError('Host "{}" has invalid format'.format(self.host)))
        else:
            errors.append(ValidationError('Host must not be empty'))

        if self.port or self.port == 0:
            try:
                int_port = int(self.port)
                if not (0 <= int_port < 65536):
                    errors.append(ValidationError('Port "{}" has invalid format - out of range'.format(self.port)))
                self.port = int_port
            except ValueError:
                errors.append(ValidationError('Port "{}" has invalid format - it is not a number'.format(self.port)))

        if self.path or self.path == '':
            while len(self.path) > 0 and self.path[0] == "/":  # Endpoint store "root-less" path
                self.path = self.path[1:]
            if self.path == '':
                self.path = None

        if self.query or self.query == '':
            if len(self.query) > 0 and self.query[0] == "?":
                self.query = self.query[1:]
            if self.query == '':
                self.query = None

        if self.fragment or self.fragment == '':
            if len(self.fragment) > 0 and self.fragment[0] == "#":
                self.fragment = self.fragment[1:]
            if self.fragment == '':
                self.fragment = None

        if errors:
            raise ValidationError(errors)

    def __str__(self):
        try:
            if self.host:
                dummy_scheme = 'dummy-scheme'  # workaround for https://github.com/python-hyper/hyperlink/blob/b8c9152cd826bbe8e6cc125648f3738235019705/src/hyperlink/_url.py#L988
                url = hyperlink.EncodedURL(
                    scheme=self.protocol if self.protocol else dummy_scheme,
                    userinfo=self.userinfo or '',
                    host=self.host,
                    port=self.port,
                    path=tuple(self.path.split('/')) if self.path else (),
                    query=tuple(
                        (
                            qe.split(u"=", 1)
                            if u"=" in qe
                            else (qe, None)
                        )
                        for qe in self.query.split(u"&")
                    ) if self.query else (),  # inspired by https://github.com/python-hyper/hyperlink/blob/b8c9152cd826bbe8e6cc125648f3738235019705/src/hyperlink/_url.py#L1427
                    fragment=self.fragment or ''
                )
                # Return a normalized version of the URL to avoid differences where there shouldn't be any difference.
                # Example: https://google.com and https://google.com:443
                normalize_path = self.path  # it used to add '/' at the end of host
                clean_url = url.normalize(scheme=True, host=True, path=normalize_path, query=True, fragment=True, userinfo=True, percents=True).to_uri().to_text()
                if not self.protocol:
                    if clean_url[:len(dummy_scheme) + 3] == (dummy_scheme + '://'):
                        clean_url = clean_url[len(dummy_scheme) + 3:]
                    else:
                        raise ValueError('hyperlink lib did not create URL as was expected')
                return clean_url
            else:
                raise ValueError('Missing host')
        except:
            url = ''
            if self.protocol:
                url += '{}://'.format(self.protocol)
            if self.userinfo:
                url += '{}@'.format(self.userinfo)
            if self.host:
                url += self.host
            if self.port:
                url += ':{}'.format(self.port)
            if self.path:
                url += '{}{}'.format('/' if self.path[0] != '/' else '', self.path)
            if self.query:
                url += '?{}'.format(self.query)
            if self.fragment:
                url += '#{}'.format(self.fragment)
            return url

    def __hash__(self):
        return self.__str__().__hash__()

    def __eq__(self, other):
        if isinstance(other, Endpoint):
            return str(self) == str(other)
        else:
            return NotImplemented

    @property
    def is_broken(self):
        try:
            self.clean()
        except:
            return True
        else:
            if self.product:
                return False
            else:
                return True

    def vulnerable(self):
        return self.active_findings_count() > 0

    def findings(self):
        return Finding.objects.filter(endpoints=self).distinct()

    def findings_count(self):
        return self.findings().count()

    def active_findings(self):
        return self.findings().filter(active=True,
                                      verified=True,
                                      out_of_scope=False,
                                      mitigated__isnull=True,
                                      false_p=False,
                                      duplicate=False).order_by('numerical_severity')

    def active_findings_count(self):
        return self.active_findings().count()

    def closed_findings(self):
        return self.findings().filter(mitigated__isnull=False)

    def closed_findings_count(self):
        return self.closed_findings().count()

    def host_endpoints(self):
        return Endpoint.objects.filter(host=self.host,
                                       product=self.product).distinct()

    def host_endpoints_count(self):
        return self.host_endpoints().count()

    def host_mitigated_endpoints(self):
        return Endpoint.objects.filter(host=self.host,
                                       product=self.product,
                                       mitigated=True).distinct()

    def host_mitigated_endpoints_count(self):
        return self.host_mitigated_endpoints().count()

    def host_findings(self):
        return Finding.objects.filter(endpoints__in=self.host_endpoints()).distinct()

    def host_findings_count(self):
        return self.host_finding().count()

    def host_active_findings(self):
        return self.host_findings().filter(active=True,
                                           verified=True,
                                           out_of_scope=False,
                                           mitigated__isnull=True,
                                           false_p=False,
                                           duplicate=False).order_by('numerical_severity')

    def host_active_findings_count(self):
        return self.host_active_findings().count()

    def host_closed_findings(self):
        return self.host_findings().filter(mitigated__isnull=False)

    def host_closed_findings_count(self):
        return self.host_closed_findings().count()

    def get_breadcrumbs(self):
        bc = self.product.get_breadcrumbs()
        bc += [{'title': self.host,
                'url': reverse('view_endpoint', args=(self.id,))}]
        return bc

    @staticmethod
    def from_uri(uri):
        try:
            url = hyperlink.parse(url=uri)
        except hyperlink.URLParseError as e:
            raise ValidationError('Invalid URL format: {}'.format(e))

        query_parts = []  # inspired by https://github.com/python-hyper/hyperlink/blob/b8c9152cd826bbe8e6cc125648f3738235019705/src/hyperlink/_url.py#L1768
        for k, v in url.query:
            if v is None:
                query_parts.append(k)
            else:
                query_parts.append(u"=".join([k, v]))
        query_string = u"&".join(query_parts)

        return Endpoint(
            protocol=url.scheme if url.scheme != '' else None,
            userinfo=':'.join(url.userinfo) if url.userinfo not in [(), ('',)] else None,
            host=url.host if url.host != '' else None,
            port=url.port,
            path='/'.join(url.path) if url.path not in [(), ('',)] else None,
            query=query_string if query_string != '' else None,
            fragment=url.fragment if url.fragment != '' else None
        )

    def get_absolute_url(self):
        from django.urls import reverse
        return reverse('view_endpoint', args=[str(self.id)])


class Development_Environment(models.Model):
    name = models.CharField(max_length=200)

    def __str__(self):
        return self.name

    def get_breadcrumbs(self):
        return [{"title": str(self),
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
    files = models.ManyToManyField(FileUpload, blank=True, editable=False)
    environment = models.ForeignKey(Development_Environment, null=True,
                                    blank=False, on_delete=models.CASCADE)

    updated = models.DateTimeField(auto_now=True, null=True)
    created = models.DateTimeField(auto_now_add=True, null=True)

    tags = TagField(blank=True, force_lowercase=True, help_text="Add tags that help describe this test. Choose from the list or add new tags. Press Enter key to add.")

    version = models.CharField(max_length=100, null=True, blank=True)

    build_id = models.CharField(editable=True, max_length=150,
                                   null=True, blank=True, help_text="Build ID that was tested, a reimport may update this field.", verbose_name="Build ID")
    commit_hash = models.CharField(editable=True, max_length=150,
                                   null=True, blank=True, help_text="Commit hash tested, a reimport may update this field.", verbose_name="Commit Hash")
    branch_tag = models.CharField(editable=True, max_length=150,
                                   null=True, blank=True, help_text="Tag or branch that was tested, a reimport may update this field.", verbose_name="Branch/Tag")

    class Meta:
        indexes = [
            models.Index(fields=['engagement', 'test_type']),
        ]

    def test_type_name(self) -> str:
        return self.test_type.name

    def __str__(self):
        if self.title:
            return "%s (%s)" % (self.title, self.test_type)
        return str(self.test_type)

    def get_breadcrumbs(self):
        bc = self.engagement.get_breadcrumbs()
        bc += [{'title': str(self),
                'url': reverse('view_test', args=(self.id,))}]
        return bc

    # only used by bulk risk acceptance api
    @property
    def unaccepted_open_findings(self):
        return Finding.objects.filter(risk_accepted=False, active=True, verified=True, duplicate=False, test=self)

    def accept_risks(self, accepted_risks):
        self.engagement.risk_acceptance.add(*accepted_risks)

    @property
    def dedupe_algo(self):
        deduplicationAlgorithm = settings.DEDUPE_ALGO_LEGACY
        if hasattr(settings, 'DEDUPLICATION_ALGORITHM_PER_PARSER'):
            scan_type = self.test_type.name

            # Check for an override for this scan_type in the deduplication configuration
            if (scan_type in settings.DEDUPLICATION_ALGORITHM_PER_PARSER):
                deduplicationAlgorithm = settings.DEDUPLICATION_ALGORITHM_PER_PARSER[scan_type]

        return deduplicationAlgorithm

    def get_absolute_url(self):
        from django.urls import reverse
        return reverse('view_test', args=[str(self.id)])

    def delete(self, *args, **kwargs):
        logger.debug('%d test delete', self.id)
        super().delete(*args, **kwargs)
        calculate_grade(self.engagement.product)


class Test_Import(TimeStampedModel):

    IMPORT_TYPE = 'import'
    REIMPORT_TYPE = 'reimport'

    test = models.ForeignKey(Test, editable=False, null=False, blank=False, on_delete=models.CASCADE)
    findings_affected = models.ManyToManyField('Finding', through='Test_Import_Finding_Action')
    import_settings = JSONField(null=True)
    type = models.CharField(max_length=64, null=False, blank=False, default='unknown')

    version = models.CharField(max_length=100, null=True, blank=True)
    build_id = models.CharField(editable=True, max_length=150,
                                   null=True, blank=True, help_text="Build ID that was tested, a reimport may update this field.", verbose_name="Build ID")
    commit_hash = models.CharField(editable=True, max_length=150,
                                   null=True, blank=True, help_text="Commit hash tested, a reimport may update this field.", verbose_name="Commit Hash")
    branch_tag = models.CharField(editable=True, max_length=150,
                                   null=True, blank=True, help_text="Tag or branch that was tested, a reimport may update this field.", verbose_name="Branch/Tag")

    def get_queryset(self):
        logger.debug('prefetch test_import counts')
        super_query = super().get_queryset()
        super_query = super_query.annotate(created_findings_count=Count('findings', filter=Q(test_import_finding_action__action=IMPORT_CREATED_FINDING)))
        super_query = super_query.annotate(closed_findings_count=Count('findings', filter=Q(test_import_finding_action__action=IMPORT_CLOSED_FINDING)))
        super_query = super_query.annotate(reactivated_findings_count=Count('findings', filter=Q(test_import_finding_action__action=IMPORT_REACTIVATED_FINDING)))
        super_query = super_query.annotate(updated_findings_count=Count('findings', filter=Q(test_import_finding_action__action=IMPORT_UPDATED_FINDING)))
        return super_query

    class Meta:
        ordering = ('-id',)
        indexes = [
            models.Index(fields=['created', 'test', 'type']),
        ]

    def __str__(self):
        return self.created.strftime("%Y-%m-%d %H:%M:%S")


class Test_Import_Finding_Action(TimeStampedModel):
    test_import = models.ForeignKey(Test_Import, editable=False, null=False, blank=False, on_delete=models.CASCADE)
    finding = models.ForeignKey('Finding', editable=False, null=False, blank=False, on_delete=models.CASCADE)
    action = models.CharField(max_length=100, null=True, blank=True, choices=IMPORT_ACTIONS)

    class Meta:
        unique_together = (('test_import', 'finding'))
        ordering = ('test_import', 'action', 'finding')

    def __str__(self):
        return '%i: %s' % (self.finding.id, self.action)


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

    def __str__(self):
        return '{} | {}'.format(self.product.name, self.sonarqube_project_key)


class Finding(models.Model):

    title = models.CharField(max_length=511,
                             verbose_name="Title",
                             help_text="A short description of the flaw.")
    date = models.DateField(default=get_current_date,
                            verbose_name="Date",
                            help_text="The date the flaw was discovered.")

    sla_start_date = models.DateField(
                            blank=True,
                            null=True,
                            verbose_name="SLA Start Date",
                            help_text="(readonly)The date used as start date for SLA calculation. Set by expiring risk acceptances. Empty by default, causing a fallback to 'date'.")

    cwe = models.IntegerField(default=0, null=True, blank=True,
                              verbose_name="CWE",
                              help_text="The CWE number associated with this flaw.")
    cve_regex = RegexValidator(regex=r'^[A-Z]{1,10}(-\d+)+$',
                               message="Vulnerability ID must be entered in the format: 'ABC-9999-9999'.")
    cve = models.CharField(validators=[cve_regex],
                           max_length=28,
                           null=True,
                           blank=False,
                           verbose_name="CVE",
                           help_text="The Common Vulnerabilities and Exposures (CVE) associated with this flaw.")
    cvssv3_regex = RegexValidator(regex=r'^AV:[NALP]|AC:[LH]|PR:[UNLH]|UI:[NR]|S:[UC]|[CIA]:[NLH]', message="CVSS must be entered in format: 'AV:N/AC:L/PR:N/UI:N/S:C/C:H/I:H/A:H'")
    cvssv3 = models.TextField(validators=[cvssv3_regex],
                              max_length=117,
                              null=True,
                              verbose_name="CVSS v3",
                              help_text="Common Vulnerability Scoring System version 3 (CVSSv3) score associated with this flaw.")
    cvssv3_score = models.FloatField(null=True,
                                        blank=True,
                                        verbose_name="CVSSv3 score",
                                        help_text="Numerical CVSSv3 score for the vulnerability. If the vector is given, the score is updated while saving the finding")

    url = models.TextField(null=True,
                           blank=True,
                           editable=False,
                           verbose_name="URL",
                           help_text="External reference that provides more information about this flaw.")  # not displayed and pretty much the same as references. To remove?
    severity = models.CharField(max_length=200,
                                verbose_name="Severity",
                                help_text="The severity level of this flaw (Critical, High, Medium, Low, Informational).")
    description = models.TextField(verbose_name="Description",
                                help_text="Longer more descriptive information about the flaw.")
    mitigation = models.TextField(verbose_name="Mitigation",
                                null=True,
                                blank=True,
                                help_text="Text describing how to best fix the flaw.")
    impact = models.TextField(verbose_name="Impact",
                                null=True,
                                blank=True,
                                help_text="Text describing the impact this flaw has on systems, products, enterprise, etc.")
    steps_to_reproduce = models.TextField(null=True,
                                          blank=True,
                                          verbose_name="Steps to Reproduce",
                                          help_text="Text describing the steps that must be followed in order to reproduce the flaw / bug.")
    severity_justification = models.TextField(null=True,
                                              blank=True,
                                              verbose_name="Severity Justification",
                                              help_text="Text describing why a certain severity was associated with this flaw.")
    endpoints = models.ManyToManyField(Endpoint,
                                       blank=True,
                                       verbose_name="Endpoints",
                                       help_text="The hosts within the product that are susceptible to this flaw.")
    endpoint_status = models.ManyToManyField(Endpoint_Status,
                                             blank=True,
                                             related_name="finding_endpoint_status",
                                             verbose_name="Endpoint Status",
                                             help_text="The status of the endpoint associated with this flaw (Vulnerable, Mitigated, ...).")
    references = models.TextField(null=True,
                                  blank=True,
                                  db_column="refs",
                                  verbose_name="References",
                                  help_text="The external documentation available for this flaw.")
    test = models.ForeignKey(Test,
                             editable=False,
                             on_delete=models.CASCADE,
                             verbose_name="Test",
                             help_text="The test that is associated with this flaw.")
    # TODO: Will be deprecated soon
    is_template = models.BooleanField(default=False,
                                      verbose_name="Is Template",
                                      help_text="Denotes if this finding is a template and can be reused.")
    active = models.BooleanField(default=True,
                                 verbose_name="Active",
                                 help_text="Denotes if this flaw is active or not.")
    # note that false positive findings cannot be verified
    # in defectdojo verified means: "we have verified the finding and it turns out that it's not a false positive"
    verified = models.BooleanField(default=True,
                                   verbose_name="Verified",
                                   help_text="Denotes if this flaw has been manually verified by the tester.")
    false_p = models.BooleanField(default=False,
                                  verbose_name="False Positive",
                                  help_text="Denotes if this flaw has been deemed a false positive by the tester.")
    duplicate = models.BooleanField(default=False,
                                    verbose_name="Duplicate",
                                    help_text="Denotes if this flaw is a duplicate of other flaws reported.")
    duplicate_finding = models.ForeignKey('self',
                                          editable=False,
                                          null=True,
                                          related_name='original_finding',
                                          blank=True, on_delete=models.DO_NOTHING,
                                          verbose_name="Duplicate Finding",
                                          help_text="Link to the original finding if this finding is a duplicate.")
    out_of_scope = models.BooleanField(default=False,
                                       verbose_name="Out Of Scope",
                                       help_text="Denotes if this flaw falls outside the scope of the test and/or engagement.")
    risk_accepted = models.BooleanField(default=False,
                                       verbose_name="Risk Accepted",
                                       help_text="Denotes if this finding has been marked as an accepted risk.")
    under_review = models.BooleanField(default=False,
                                       verbose_name="Under Review",
                                       help_text="Denotes is this flaw is currently being reviewed.")

    last_status_update = models.DateTimeField(editable=False,
                                            null=True,
                                            blank=True,
                                            auto_now_add=True,
                                            verbose_name="Last Status Update",
                                            help_text="Timestamp of latest status update (change in status related fields).")

    review_requested_by = models.ForeignKey(Dojo_User,
                                            null=True,
                                            blank=True,
                                            related_name='review_requested_by',
                                            on_delete=models.CASCADE,
                                            verbose_name="Review Requested By",
                                            help_text="Documents who requested a review for this finding.")
    reviewers = models.ManyToManyField(User,
                                       blank=True,
                                       verbose_name="Reviewers",
                                       help_text="Documents who reviewed the flaw.")

    # Defect Tracking Review
    under_defect_review = models.BooleanField(default=False,
                                              verbose_name="Under Defect Review",
                                              help_text="Denotes if this finding is under defect review.")
    defect_review_requested_by = models.ForeignKey(Dojo_User,
                                                   null=True,
                                                   blank=True,
                                                   related_name='defect_review_requested_by',
                                                   on_delete=models.CASCADE,
                                                   verbose_name="Defect Review Requested By",
                                                   help_text="Documents who requested a defect review for this flaw.")
    is_mitigated = models.BooleanField(default=False,
                                       verbose_name="Is Mitigated",
                                       help_text="Denotes if this flaw has been fixed.")
    thread_id = models.IntegerField(default=0,
                                    editable=False,
                                    verbose_name="Thread ID")
    mitigated = models.DateTimeField(editable=False,
                                     null=True,
                                     blank=True,
                                     verbose_name="Mitigated",
                                     help_text="Denotes if this flaw has been fixed by storing the date it was fixed.")
    mitigated_by = models.ForeignKey(User,
                                     null=True,
                                     editable=False,
                                     related_name="mitigated_by",
                                     on_delete=models.CASCADE,
                                     verbose_name="Mitigated By",
                                     help_text="Documents who has marked this flaw as fixed.")
    reporter = models.ForeignKey(User,
                                 editable=False,
                                 default=1,
                                 related_name='reporter',
                                 on_delete=models.CASCADE,
                                 verbose_name="Reporter",
                                 help_text="Documents who reported the flaw.")
    notes = models.ManyToManyField(Notes,
                                   blank=True,
                                   editable=False,
                                   verbose_name="Notes",
                                   help_text="Stores information pertinent to the flaw or the mitigation.")
    numerical_severity = models.CharField(max_length=4,
                                          verbose_name="Numerical Severity",
                                          help_text="The numerical representation of the severity (S0, S1, S2, S3, S4).")
    last_reviewed = models.DateTimeField(null=True,
                                         editable=False,
                                         verbose_name="Last Reviewed",
                                         help_text="Provides the date the flaw was last 'touched' by a tester.")
    last_reviewed_by = models.ForeignKey(User,
                                         null=True,
                                         editable=False,
                                         related_name='last_reviewed_by',
                                         on_delete=models.CASCADE,
                                         verbose_name="Last Reviewed By",
                                         help_text="Provides the person who last reviewed the flaw.")
    files = models.ManyToManyField(FileUpload,
                                   blank=True,
                                   editable=False,
                                   verbose_name="Files",
                                   help_text="Files(s) related to the flaw.")
    line_number = models.CharField(null=True,
                                   blank=True,
                                   max_length=200,
                                   verbose_name="Line Number",
                                   help_text="Deprecated will be removed, use line",
                                   editable=False)  # Deprecated will be removed, use line
    sourcefilepath = models.TextField(null=True,
                                      blank=True,
                                      editable=False,
                                      verbose_name="Source File Path",
                                      help_text="Filepath of the source code file in which the flaw is located.")  # Not used? to remove
    sourcefile = models.TextField(null=True,
                                  blank=True,
                                  editable=False,
                                  verbose_name="Source File",
                                  help_text="Name of the source code file in which the flaw is located.")
    param = models.TextField(null=True,
                             blank=True,
                             editable=False,
                             verbose_name="Parameter",
                             help_text="Parameter used to trigger the issue (DAST).")
    payload = models.TextField(null=True,
                               blank=True,
                               editable=False,
                               verbose_name="Payload",
                               help_text="Payload used to attack the service / application and trigger the bug / problem.")
    hash_code = models.CharField(null=True,
                                 blank=True,
                                 editable=False,
                                 max_length=64,
                                 verbose_name="Hash Code",
                                 help_text="A hash over a configurable set of fields that is used for findings deduplication.")
    line = models.IntegerField(null=True,
                               blank=True,
                               verbose_name="Line number",
                               help_text="Source line number of the attack vector.")
    file_path = models.CharField(null=True,
                                 blank=True,
                                 max_length=4000,
                                 verbose_name="File path",
                                 help_text="Identified file(s) containing the flaw.")
    component_name = models.CharField(null=True,
                                      blank=True,
                                      max_length=200,
                                      verbose_name="Component name",
                                      help_text="Name of the affected component (library name, part of a system, ...).")
    component_version = models.CharField(null=True,
                                         blank=True,
                                         max_length=100,
                                         verbose_name="Component version",
                                         help_text="Version of the affected component.")
    found_by = models.ManyToManyField(Test_Type,
                                      editable=False,
                                      verbose_name="Found by",
                                      help_text="The name of the scanner that identified the flaw.")
    static_finding = models.BooleanField(default=False,
                                         verbose_name="Static finding (SAST)",
                                         help_text="Flaw has been detected from a Static Application Security Testing tool (SAST).")
    dynamic_finding = models.BooleanField(default=True,
                                          verbose_name="Dynamic finding (DAST)",
                                          help_text="Flaw has been detected from a Dynamic Application Security Testing tool (DAST).")
    created = models.DateTimeField(auto_now_add=True,
                                   null=True,
                                   verbose_name="Created",
                                   help_text="The date the finding was created inside DefectDojo.")
    scanner_confidence = models.IntegerField(null=True,
                                             blank=True,
                                             default=None,
                                             editable=False,
                                             verbose_name="Scanner confidence",
                                             help_text="Confidence level of vulnerability which is supplied by the scanner.")
    sonarqube_issue = models.ForeignKey(Sonarqube_Issue,
                                        null=True,
                                        blank=True,
                                        help_text="The SonarQube issue associated with this finding.",
                                        verbose_name="SonarQube issue",
                                        on_delete=models.CASCADE)
    unique_id_from_tool = models.CharField(null=True,
                                           blank=True,
                                           max_length=500,
                                           verbose_name="Unique ID from tool",
                                           help_text="Vulnerability technical id from the source tool. Allows to track unique vulnerabilities.")
    vuln_id_from_tool = models.CharField(null=True,
                                         blank=True,
                                         max_length=500,
                                         verbose_name="Vulnerability ID from tool",
                                         help_text="Non-unique technical id from the source tool associated with the vulnerability type.")
    sast_source_object = models.CharField(null=True,
                                          blank=True,
                                          max_length=500,
                                          verbose_name="SAST Source Object",
                                          help_text="Source object (variable, function...) of the attack vector.")
    sast_sink_object = models.CharField(null=True,
                                        blank=True,
                                        max_length=500,
                                        verbose_name="SAST Sink Object",
                                        help_text="Sink object (variable, function...) of the attack vector.")
    sast_source_line = models.IntegerField(null=True,
                                           blank=True,
                                           verbose_name="SAST Source Line number",
                                           help_text="Source line number of the attack vector.")
    sast_source_file_path = models.CharField(null=True,
                                             blank=True,
                                             max_length=4000,
                                             verbose_name="SAST Source File Path",
                                             help_text="Source file path of the attack vector.")
    nb_occurences = models.IntegerField(null=True,
                                        blank=True,
                                        verbose_name="Number of occurences",
                                        help_text="Number of occurences in the source tool when several vulnerabilites were found and aggregated by the scanner.")

    # this is useful for vulnerabilities on dependencies : helps answer the question "Did I add this vulnerability or was it discovered recently?"
    publish_date = models.DateTimeField(null=True,
                                         blank=True,
                                         verbose_name="Publish date",
                                         help_text="Date when this vulnerability was made publicly available.")

    tags = TagField(blank=True, force_lowercase=True, help_text="Add tags that help describe this finding. Choose from the list or add new tags. Press Enter key to add.")

    SEVERITIES = {'Info': 4, 'Low': 3, 'Medium': 2,
                  'High': 1, 'Critical': 0}

    class Meta:
        ordering = ('numerical_severity', '-date', 'title')
        indexes = [
            models.Index(fields=['test', 'active', 'verified']),

            models.Index(fields=['test', 'is_mitigated']),
            models.Index(fields=['test', 'duplicate']),
            models.Index(fields=['test', 'out_of_scope']),
            models.Index(fields=['test', 'false_p']),

            models.Index(fields=['test', 'unique_id_from_tool', 'duplicate']),
            models.Index(fields=['test', 'hash_code', 'duplicate']),

            models.Index(fields=['test', 'component_name']),

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
            models.Index(fields=['hash_code']),
            models.Index(fields=['unique_id_from_tool']),
            # models.Index(fields=['file_path']), # can't add index because the field has max length 4000.
            models.Index(fields=['line']),
            models.Index(fields=['component_name']),
            models.Index(fields=['duplicate']),
            models.Index(fields=['is_mitigated']),
            models.Index(fields=['duplicate_finding', 'id']),
        ]

    def __init__(self, *args, **kwargs):
        super(Finding, self).__init__(*args, **kwargs)

        self.unsaved_endpoints = []
        self.unsaved_request = None
        self.unsaved_response = None
        self.unsaved_tags = None

    def get_absolute_url(self):
        from django.urls import reverse
        return reverse('view_finding', args=[str(self.id)])

    def delete(self, *args, **kwargs):
        logger.debug('%d finding delete', self.id)
        import dojo.finding.helper as helper
        helper.finding_delete(self)
        super().delete(*args, **kwargs)
        calculate_grade(self.test.engagement.product)

    # only used by bulk risk acceptance api
    @classmethod
    def unaccepted_open_findings(cls):
        return cls.objects.filter(active=True, verified=True, duplicate=False, risk_accepted=False)

    @property
    def risk_acceptance(self):
        ras = self.risk_acceptance_set.all()
        if ras:
            return ras[0]

        return None

    def compute_hash_code(self):
        if hasattr(settings, 'HASHCODE_FIELDS_PER_SCANNER') and hasattr(settings, 'HASHCODE_ALLOWS_NULL_CWE') and hasattr(settings, 'HASHCODE_ALLOWED_FIELDS'):
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
                            return self.compute_hash_code_legacy()
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
                    return self.compute_hash_code_legacy()
            else:
                deduplicationLogger.debug(
                    "No configuration for hash_code computation found; using default fields for " + ('dynamic' if self.dynamic_finding else 'static') + ' scanners')
                return self.compute_hash_code_legacy()
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
        deduplicationLogger.debug("compute_hash_code_legacy - fields_to_hash = " + fields_to_hash)
        return self.hash_fields(fields_to_hash)

    # Get endpoints to use for hash_code computation
    # (This sometimes reports "None")
    def get_endpoints(self):
        endpoint_str = ''
        if(self.id is None):
            if len(self.unsaved_endpoints) > 0:
                deduplicationLogger.debug("get_endpoints before the finding was saved")
                # convert list of unsaved endpoints to the list of their canonical representation
                endpoint_str_list = list(
                    map(
                        lambda endpoint: str(endpoint),
                        self.unsaved_endpoints
                    ))
                # deduplicate (usually done upon saving finding) and sort endpoints
                endpoint_str = ''.join(
                    sorted(
                        list(
                            dict.fromkeys(endpoint_str_list)
                        )))
            else:
                # we can get here when the parser defines static_finding=True but leaves dynamic_finding defaulted
                # In this case, before saving the finding, both static_finding and dynamic_finding are True
                # After saving dynamic_finding may be set to False probably during the saving process (observed on Bandit scan before forcing dynamic_finding=False at parser level)
                deduplicationLogger.debug("trying to get endpoints on a finding before it was saved but no endpoints found (static parser wrongly identified as dynamic?")
        else:
            deduplicationLogger.debug("get_endpoints: after the finding was saved. Endpoints count: " + str(self.endpoints.count()))
            # convert list of endpoints to the list of their canonical representation
            endpoint_str_list = list(
                map(
                    lambda endpoint: str(endpoint),
                    self.endpoints.all()
                ))
            # sort endpoints strings
            endpoint_str = ''.join(
                sorted(
                    endpoint_str_list
                ))
        return endpoint_str

    # Compute the hash_code from the fields to hash
    def hash_fields(self, fields_to_hash):
        logger.debug('fields_to_hash      : %s', fields_to_hash)
        logger.debug('fields_to_hash lower: %s', fields_to_hash.lower())
        return hashlib.sha256(fields_to_hash.casefold().encode('utf-8').strip()).hexdigest()

    def duplicate_finding_set(self):
        if self.duplicate:
            if self.duplicate_finding is not None:
                originals = Finding.objects.get(
                    id=self.duplicate_finding.id).original_finding.all().order_by('title')
                return originals  # we need to add the duplicate_finding  here as well
            else:
                return []
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

    @staticmethod
    def get_severity(num_severity):
        severities = {0: 'Info', 1: 'Low', 2: 'Medium', 3: 'High', 4: 'Critical'}
        if num_severity in severities.keys():
            return severities[num_severity]

        return None

    def __str__(self):
        return self.title

    def status(self):
        status = []
        if self.under_review:
            status += ['Under Review']
        if self.active:
            status += ['Active']
        else:
            status += ['Inactive']
        if self.verified:
            status += ['Verified']
        if self.mitigated or self.is_mitigated:
            status += ['Mitigated']
        if self.false_p:
            status += ['False Positive']
        if self.out_of_scope:
            status += ['Out Of Scope']
        if self.duplicate:
            status += ['Duplicate']
        if self.risk_accepted:
            status += ['Risk Accepted']
        if not len(status):
            status += ['Initial']

        return ", ".join([str(s) for s in status])

    def _age(self, start_date):
        if self.mitigated:
            diff = self.mitigated.date() - start_date
        else:
            diff = get_current_date() - start_date
        days = diff.days
        return days if days > 0 else 0

    @property
    def age(self):
        return self._age(self.date)

    def get_sla_start_date(self):
        if self.sla_start_date:
            return self.sla_start_date
        else:
            return self.date

    @property
    def sla_age(self):
        return self._age(self.get_sla_start_date())

    def sla_days_remaining(self):
        sla_calculation = None
        severity = self.severity
        from dojo.utils import get_system_setting
        sla_age = get_system_setting('sla_' + self.severity.lower())
        if sla_age:
            sla_calculation = sla_age - self.age
        return sla_calculation

    def sla_deadline(self):
        days_remaining = self.sla_days_remaining()
        if days_remaining:
            return self.date + relativedelta(days=days_remaining)
        return None

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
            return self.test.engagement.product.github_pkey_set.all()[0].git_conf
        except:
            return None
            pass

    @property
    def has_jira_issue(self):
        import dojo.jira_link.helper as jira_helper
        return jira_helper.has_jira_issue(self)

    @cached_property
    def finding_group(self):
        group = self.finding_group_set.all().first()
        # logger.debug('finding.finding_group: %s', group)
        return group

    @cached_property
    def has_jira_group_issue(self):
        if not self.has_finding_group:
            return False

        import dojo.jira_link.helper as jira_helper
        return jira_helper.has_jira_issue(self.finding_group)

    @property
    def has_jira_configured(self):
        import dojo.jira_link.helper as jira_helper
        return jira_helper.has_jira_configured(self)

    @cached_property
    def has_finding_group(self):
        return self.finding_group is not None

    def long_desc(self):
        long_desc = ''
        long_desc += '*' + self.title + '*\n\n'
        long_desc += '*Severity:* ' + str(self.severity) + '\n\n'
        long_desc += '*Cve:* ' + str(self.cve) + '\n\n'
        long_desc += '*CVSS v3:* ' + str(self.cvssv3) + '\n\n'
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
        long_desc += '*Description*: \n' + str(self.description) + '\n\n'
        long_desc += '*Mitigation*: \n' + str(self.mitigation) + '\n\n'
        long_desc += '*Impact*: \n' + str(self.impact) + '\n\n'
        long_desc += '*References*:' + str(self.references)
        return long_desc

    def save_no_options(self, *args, **kwargs):
        return self.save(dedupe_option=False, false_history=False, rules_option=False, product_grading_option=False,
             issue_updater_option=False, push_to_jira=False, user=None, *args, **kwargs)

    def save(self, dedupe_option=True, false_history=False, rules_option=True, product_grading_option=True,
             issue_updater_option=True, push_to_jira=False, user=None, *args, **kwargs):

        from dojo.finding import helper as finding_helper

        system_settings = System_Settings.objects.get()

        if not user:
            from dojo.utils import get_current_user
            user = get_current_user()

        # Title Casing
        from titlecase import titlecase
        self.title = titlecase(self.title[:511])

        # Assign the numerical severity for correct sorting order
        self.numerical_severity = Finding.get_numerical_severity(self.severity)

        # Synchronize cvssv3 score using cvssv3 vector
        if self.cvssv3:
            try:
                cvss_object = CVSS3(self.cvssv3)
                # use the environmental score, which is the most refined score
                self.cvssv3_score = cvss_object.scores()[2]
            except Exception as ex:
                logger.error("Can't compute cvssv3 score for finding id %i. Invalid cvssv3 vector found: '%s'. Exception: %s", self.id, self.cvssv3, ex)

        if rules_option:
            from dojo.utils import do_apply_rules
            do_apply_rules(self, *args, **kwargs)

        # Finding.save is called once from serializers.py with dedupe_option=False because the finding is not ready yet, for example the endpoints are not built
        # It is then called a second time with dedupe_option defaulted to true; now we can compute the hash_code and run the deduplication
        if dedupe_option:
            if (self.hash_code is not None):
                deduplicationLogger.debug("Hash_code already computed for finding")
            else:
                self.hash_code = self.compute_hash_code()
                deduplicationLogger.debug("Hash_code computed for finding: %s", self.hash_code)

        if self.pk is None:
            # We enter here during the first call from serializers.py
            false_history = True
            from dojo.utils import apply_cwe_to_template
            self = apply_cwe_to_template(self)

            if (self.file_path is not None) and (len(self.unsaved_endpoints) == 0):
                self.static_finding = True
                self.dynamic_finding = False
            elif (self.file_path is not None):
                self.static_finding = True

            # because we have reduced the number of (super()).save() calls, the helper is no longer called for new findings
            # so we call it manually
            finding_helper.update_finding_status(self, user, changed_fields={'id': (None, None)})

        else:
            # logger.debug('setting static / dynamic in save')
            # need to have an id/pk before we can access endpoints
            if (self.file_path is not None) and (self.endpoints.count() == 0):
                self.static_finding = True
                self.dynamic_finding = False
            elif (self.file_path is not None):
                self.static_finding = True

        logger.debug("Saving finding of id " + str(self.id) + " dedupe_option:" + str(dedupe_option) + " (self.pk is %s)", "None" if self.pk is None else "not None")
        super(Finding, self).save(*args, **kwargs)

        self.found_by.add(self.test.test_type)

        # only perform post processing (in celery task) if needed. this check avoids submitting 1000s of tasks to celery that will do nothing
        if dedupe_option or false_history or issue_updater_option or product_grading_option or push_to_jira:
            finding_helper.post_process_finding_save(self, dedupe_option=dedupe_option, false_history=false_history, rules_option=rules_option, product_grading_option=product_grading_option,
                issue_updater_option=issue_updater_option, push_to_jira=push_to_jira, user=user, *args, **kwargs)
        else:
            logger.debug('no options selected that require finding post processing')

    # Check if a mandatory field is empty. If it's the case, fill it with "no <fieldName> given"
    def clean(self):
        no_check = ["test", "reporter"]
        bigfields = ["description"]
        for field_obj in self._meta.fields:
            field = field_obj.name
            if field not in no_check:
                val = getattr(self, field)
                if not val and field == "title":
                    setattr(self, field, "No title given")
                if not val and field in bigfields:
                    setattr(self, field, "No %s given" % field)

    def severity_display(self):
        return self.severity

    def get_breadcrumbs(self):
        bc = self.test.get_breadcrumbs()
        bc += [{'title': str(self),
                'url': reverse('view_finding', args=(self.id,))}]
        return bc

    def get_report_requests(self):
        if self.burprawrequestresponse_set.count() >= 3:
            return self.burprawrequestresponse_set.all()[0:3]
        elif self.burprawrequestresponse_set.count() > 0:
            return self.burprawrequestresponse_set.all()

    def get_request(self):
        if self.burprawrequestresponse_set.count() > 0:
            reqres = self.burprawrequestresponse_set().first()
        return base64.b64decode(reqres.burpRequestBase64)

    def get_response(self):
        if self.burprawrequestresponse_set.count() > 0:
            reqres = self.burprawrequestresponse_set.first()
        res = base64.b64decode(reqres.burpResponseBase64)
        # Removes all blank lines
        res = re.sub(r'\n\s*\n', '\n', res)
        return res

    def latest_note(self):
        if self.notes.all():
            note = self.notes.all()[0]
            return note.date.strftime("%Y-%m-%d %H:%M:%S") + ': ' + note.author.get_full_name() + ' : ' + note.entry

        return ''

    def get_sast_source_file_path_with_link(self):
        from dojo.utils import create_bleached_link
        if self.sast_source_file_path is None:
            return None
        if self.test.engagement.source_code_management_uri is None:
            return self.sast_source_file_path
        link = self.test.engagement.source_code_management_uri + '/' + self.sast_source_file_path
        if self.sast_source_line:
            link = link + '#L' + str(self.sast_source_line)
        return create_bleached_link(link, self.sast_source_file_path)

    def get_file_path_with_link(self):
        from dojo.utils import create_bleached_link
        if self.file_path is None:
            return None
        if self.test.engagement.source_code_management_uri is None:
            return self.file_path
        link = self.test.engagement.source_code_management_uri + '/' + self.file_path
        if self.line:
            link = link + '#L' + str(self.line)
        return create_bleached_link(link, self.file_path)

    def get_references_with_links(self):
        import re
        from dojo.utils import create_bleached_link
        if self.references is None:
            return None
        matches = re.findall(r'([\(|\[]?(https?):((//)|(\\\\))+([\w\d:#@%/;$~_?\+-=\\\.&](#!)?)*[\)|\]]?)', self.references)
        for match in matches:
            # Check if match isn't already a markdown link
            if not (match[0].startswith('[') or match[0].startswith('(')):
                self.references = self.references.replace(match[0], create_bleached_link(match[0], match[0]), 1)
        return self.references


class FindingAdmin(admin.ModelAdmin):
    # For efficiency with large databases, display many-to-many fields with raw
    # IDs rather than multi-select
    raw_id_fields = (
        'endpoints',
        'endpoint_status',
    )


Finding.endpoints.through.__str__ = lambda \
    x: "Endpoint: " + str(x.endpoint)


class Stub_Finding(models.Model):
    title = models.TextField(max_length=1000, blank=False, null=False)
    date = models.DateField(default=get_current_date, blank=False, null=False)
    severity = models.CharField(max_length=200, blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    test = models.ForeignKey(Test, editable=False, on_delete=models.CASCADE)
    reporter = models.ForeignKey(User, editable=False, default=1, on_delete=models.CASCADE)

    class Meta:
        ordering = ('-date', 'title')

    def __str__(self):
        return self.title

    def get_breadcrumbs(self):
        bc = self.test.get_breadcrumbs()
        bc += [{'title': "Potential Finding: " + str(self),
                'url': reverse('view_potential_finding', args=(self.id,))}]
        return bc


class Finding_Group(TimeStampedModel):

    GROUP_BY_OPTIONS = [('component_name', 'Component Name'), ('component_name+component_version', 'Component Name + Version'), ('file_path', 'File path')]

    name = models.CharField(max_length=255, blank=False, null=False)
    test = models.ForeignKey(Test, on_delete=models.CASCADE)
    findings = models.ManyToManyField(Finding)
    creator = models.ForeignKey(Dojo_User, on_delete=models.CASCADE)

    def __str__(self):
        return self.name

    @property
    def has_jira_issue(self):
        import dojo.jira_link.helper as jira_helper
        return jira_helper.has_jira_issue(self)

    @cached_property
    def severity(self):
        if not self.findings.all():
            return None
        max_number_severity = max([Finding.get_number_severity(find.severity) for find in self.findings.all()])
        return Finding.get_severity(max_number_severity)

    @cached_property
    def components(self):
        # Using defaultdict() + groupby()
        # Convert list of tuples to dictionary value lists
        component_tuples = set([(find.component_name, find.component_version) for find in self.findings.all()])
        components = dict((k, [v[1] for v in itr]) for k, itr in groupby(
                                component_tuples, itemgetter(0)))
        return ','.join([key + ':' + ', '.join(value) for key, value in components.items() if key and value])

    @property
    def age(self):
        if not self.findings.all():
            return None

        return max([find.age for find in self.findings.all()])

    @cached_property
    def sla_days_remaining_internal(self):
        if not self.findings.all():
            return None

        return min([find.sla_days_remaining() for find in self.findings.all() if find.sla_days_remaining()], default=None)

    def sla_days_remaining(self):
        return self.sla_days_remaining_internal

    def sla_deadline(self):
        if not self.findings.all():
            return None

        return min([find.sla_deadline() for find in self.findings.all() if find.sla_deadline()], default=None)

    # def cves(self):
    #     return ', '.join([find.cve for find in self.findings.all() if find.cve is not None])

    def status(self):
        if not self.findings.all():
            return None

        if any([find.active for find in self.findings.all()]):
            return 'Active'

        if all([find.is_mitigated for find in self.findings.all()]):
            return 'Mitigated'

        return 'Inactive'

    @cached_property
    def mitigated(self):
        return all([find.mitigated is not None for find in self.findings.all()])

    def get_sla_start_date(self):
        return min([find.get_sla_start_date() for find in self.findings.all()])

    def get_absolute_url(self):
        from django.urls import reverse
        return reverse('view_test', args=[str(self.test.id)])

    class Meta:
        ordering = ['id']


class Finding_Template(models.Model):
    title = models.TextField(max_length=1000)
    cwe = models.IntegerField(default=None, null=True, blank=True)
    cve_regex = RegexValidator(regex=r'^[A-Z]{1,10}(-\d+)+$',
                               message="Vulnerability ID must be entered in the format: 'ABC-9999-9999'.")
    cve = models.CharField(validators=[cve_regex], max_length=28, null=True, blank=False)
    cvssv3_regex = RegexValidator(regex=r'^AV:[NALP]|AC:[LH]|PR:[UNLH]|UI:[NR]|S:[UC]|[CIA]:[NLH]', message="CVSS must be entered in format: 'AV:N/AC:L/PR:N/UI:N/S:C/C:H/I:H/A:H'")
    cvssv3 = models.TextField(validators=[cvssv3_regex], max_length=117, null=True)
    severity = models.CharField(max_length=200, null=True, blank=True)
    description = models.TextField(null=True, blank=True)
    mitigation = models.TextField(null=True, blank=True)
    impact = models.TextField(null=True, blank=True)
    references = models.TextField(null=True, blank=True, db_column="refs")
    last_used = models.DateTimeField(null=True, editable=False)
    numerical_severity = models.CharField(max_length=4, null=True, blank=True, editable=False)
    template_match = models.BooleanField(default=False, verbose_name='Template Match Enabled', help_text="Enables this template for matching remediation advice. Match will be applied to all active, verified findings by CWE.")
    template_match_title = models.BooleanField(default=False, verbose_name='Match Template by Title and CWE', help_text="Matches by title text (contains search) and CWE.")

    tags = TagField(blank=True, force_lowercase=True, help_text="Add tags that help describe this finding template. Choose from the list or add new tags. Press Enter key to add.")

    SEVERITIES = {'Info': 4, 'Low': 3, 'Medium': 2,
                  'High': 1, 'Critical': 0}

    class Meta:
        ordering = ['-cwe']

    def __str__(self):
        return self.title

    def get_breadcrumbs(self):
        bc = [{'title': str(self),
               'url': reverse('view_template', args=(self.id,))}]
        return bc

    def get_absolute_url(self):
        from django.urls import reverse
        return reverse('edit_template', args=[str(self.id)])


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
    TREATMENT_ACCEPT = 'A'
    TREATMENT_AVOID = 'V'
    TREATMENT_MITIGATE = 'M'
    TREATMENT_FIX = 'F'
    TREATMENT_TRANSFER = 'T'

    TREATMENT_CHOICES = [
        (TREATMENT_ACCEPT, 'Accept (The risk is acknowledged, yet remains)'),
        (TREATMENT_AVOID, 'Avoid (Do not engage with whatever creates the risk)'),
        (TREATMENT_MITIGATE, 'Mitigate (The risk still exists, yet compensating controls make it less of a threat)'),
        (TREATMENT_FIX, 'Fix (The risk is eradicated)'),
        (TREATMENT_TRANSFER, 'Transfer (The risk is transferred to a 3rd party)'),
    ]

    name = models.CharField(max_length=100, null=False, blank=False, help_text="Descriptive name which in the future may also be used to group risk acceptances together across engagements and products")

    accepted_findings = models.ManyToManyField(Finding)

    recommendation = models.CharField(choices=TREATMENT_CHOICES, max_length=2, null=False, default=TREATMENT_FIX, help_text="Recommendation from the security team.", verbose_name="Security Recommendation")

    recommendation_details = models.TextField(null=True,
                                      blank=True,
                                      help_text="Explanation of security recommendation", verbose_name="Security Recommendation Details")

    decision = models.CharField(choices=TREATMENT_CHOICES, max_length=2, null=False, default=TREATMENT_ACCEPT, help_text="Risk treatment decision by risk owner")
    decision_details = models.TextField(default=None, blank=True, null=True, help_text="If a compensating control exists to mitigate the finding or reduce risk, then list the compensating control(s).")

    accepted_by = models.CharField(max_length=200, default=None, null=True, blank=True, verbose_name='Accepted By', help_text="The person that accepts the risk, can be outside of DefectDojo.")
    path = models.FileField(upload_to='risk/%Y/%m/%d',
                            editable=True, null=True,
                            blank=True, verbose_name="Proof")
    owner = models.ForeignKey(Dojo_User, editable=True, on_delete=models.CASCADE, help_text="User in DefectDojo owning this acceptance. Only the owner and staff users can edit the risk acceptance.")

    expiration_date = models.DateTimeField(default=None, null=True, blank=True, help_text="When the risk acceptance expires, the findings will be reactivated (unless disabled below).")
    expiration_date_warned = models.DateTimeField(default=None, null=True, blank=True, help_text="(readonly) Date at which notice about the risk acceptance expiration was sent.")
    expiration_date_handled = models.DateTimeField(default=None, null=True, blank=True, help_text="(readonly) When the risk acceptance expiration was handled (manually or by the daily job).")
    reactivate_expired = models.BooleanField(null=False, blank=False, default=True, verbose_name="Reactivate findings on expiration", help_text="Reactivate findings when risk acceptance expires?")
    restart_sla_expired = models.BooleanField(default=False, null=False, verbose_name="Restart SLA on expiration", help_text="When enabled, the SLA for findings is restarted when the risk acceptance expires.")

    notes = models.ManyToManyField(Notes, editable=False)
    created = models.DateTimeField(null=False, editable=False, auto_now_add=True)
    updated = models.DateTimeField(editable=False, auto_now=True)

    def __str__(self):
        return str(self.name)

    def filename(self):
        # logger.debug('path: "%s"', self.path)
        if not self.path:
            return None
        return os.path.basename(self.path.name)

    @property
    def name_and_expiration_info(self):
        return str(self.name) + (' (expired ' if self.is_expired else ' (expires ') + (timezone.localtime(self.expiration_date).strftime("%b %d, %Y") if self.expiration_date else 'Never') + ')'

    def get_breadcrumbs(self):
        bc = self.engagement_set.first().get_breadcrumbs()
        bc += [{'title': str(self),
                'url': reverse('view_risk_acceptance', args=(
                    self.engagement_set.first().product.id, self.id,))}]
        return bc

    @property
    def is_expired(self):
        return self.expiration_date_handled is not None

    # relationship is many to many, but we use it as one-to-many
    @property
    def engagement(self):
        engs = self.engagement_set.all()
        if engs:
            return engs[0]

        return None


class FileAccessToken(models.Model):
    """This will allow reports to request the images without exposing the
    media root to the world without
    authentication"""
    user = models.ForeignKey(User, null=False, blank=False, on_delete=models.CASCADE)
    file = models.ForeignKey(FileUpload, null=False, blank=False, on_delete=models.CASCADE)
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
        return super(FileAccessToken, self).save(*args, **kwargs)


class BannerConf(models.Model):
    banner_enable = models.BooleanField(default=False, null=True, blank=True)
    banner_message = models.CharField(max_length=500, help_text="This message will be displayed on the login page. It can contain basic html tags, for example <a href='https://www.fred.com' style='color: #337ab7;' target='_blank'>https://example.com</a>", default='')


class GITHUB_Conf(models.Model):
    configuration_name = models.CharField(max_length=2000, help_text="Enter a name to give to this configuration", default='')
    api_key = models.CharField(max_length=2000, help_text="Enter your Github API Key", default='')

    def __str__(self):
        return self.configuration_name


class GITHUB_Issue(models.Model):
    issue_id = models.CharField(max_length=200)
    issue_url = models.URLField(max_length=2000, verbose_name="GitHub issue URL")
    finding = models.OneToOneField(Finding, null=True, blank=True, on_delete=models.CASCADE)

    def __str__(self):
        return str(self.issue_id) + '| GitHub Issue URL: ' + str(self.issue_url)


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

    def __str__(self):
        return self.product.name + " | " + self.git_project


class JIRA_Instance(models.Model):
    configuration_name = models.CharField(max_length=2000, help_text="Enter a name to give to this configuration", default='')
    url = models.URLField(max_length=2000, verbose_name="JIRA URL", help_text="For more information how to configure Jira, read the DefectDojo documentation.")
    username = models.CharField(max_length=2000)
    password = models.CharField(max_length=2000)

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
    issue_template_dir = models.CharField(max_length=255,
                                      null=True,
                                      blank=True,
                                      help_text='Choose the folder containing the Django templates used to render the JIRA issue description. These are stored in dojo/templates/issue-trackers. Leave empty to use the default jira_full templates.')
    epic_name_id = models.IntegerField(help_text="To obtain the 'Epic name id' visit https://<YOUR JIRA URL>/rest/api/2/field and search for Epic Name. Copy the number out of cf[number] and paste it here.")
    open_status_key = models.IntegerField(verbose_name="Reopen Transition ID", help_text="Transition ID to Re-Open JIRA issues, visit https://<YOUR JIRA URL>/rest/api/latest/issue/<ANY VALID ISSUE KEY>/transitions?expand=transitions.fields to find the ID for your JIRA instance")
    close_status_key = models.IntegerField(verbose_name="Close Transition ID", help_text="Transition ID to Close JIRA issues, visit https://<YOUR JIRA URL>/rest/api/latest/issue/<ANY VALID ISSUE KEY>/transitions?expand=transitions.fields to find the ID for your JIRA instance")
    info_mapping_severity = models.CharField(max_length=200, help_text="Maps to the 'Priority' field in Jira. For example: Info")
    low_mapping_severity = models.CharField(max_length=200, help_text="Maps to the 'Priority' field in Jira. For example: Low")
    medium_mapping_severity = models.CharField(max_length=200, help_text="Maps to the 'Priority' field in Jira. For example: Medium")
    high_mapping_severity = models.CharField(max_length=200, help_text="Maps to the 'Priority' field in Jira. For example: High")
    critical_mapping_severity = models.CharField(max_length=200, help_text="Maps to the 'Priority' field in Jira. For example: Critical")
    finding_text = models.TextField(null=True, blank=True, help_text="Additional text that will be added to the finding in Jira. For example including how the finding was created or who to contact for more information.")
    accepted_mapping_resolution = models.CharField(null=True, blank=True, max_length=300, help_text="JIRA resolution names (comma-separated values) that maps to an Accepted Finding")
    false_positive_mapping_resolution = models.CharField(null=True, blank=True, max_length=300, help_text="JIRA resolution names (comma-separated values) that maps to a False Positive Finding")
    global_jira_sla_notification = models.BooleanField(default=True, blank=False, verbose_name="Globally send SLA notifications as comment?", help_text="This setting can be overidden at the Product level")

    @property
    def accepted_resolutions(self):
        return [m.strip() for m in (self.accepted_mapping_resolution or '').split(',')]

    @property
    def false_positive_resolutions(self):
        return [m.strip() for m in (self.false_positive_mapping_resolution or '').split(',')]

    def __str__(self):
        return self.configuration_name + " | " + self.url + " | " + self.username

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


# declare form here as we can't import forms.py due to circular imports not even locally
class JIRAForm_Admin(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput, required=True)

    # django doesn't seem to have an easy way to handle password fields as PasswordInput requires reentry of passwords
    password_from_db = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance:
            # keep password from db to use if the user entered no password
            self.password_from_db = self.instance.password
            self.fields['password'].required = False

    def clean(self):
        cleaned_data = super().clean()
        if not cleaned_data['password']:
            cleaned_data['password'] = self.password_from_db

        return cleaned_data


class JIRA_Instance_Admin(admin.ModelAdmin):
    form = JIRAForm_Admin


class JIRA_Project(models.Model):
    jira_instance = models.ForeignKey(JIRA_Instance, verbose_name="JIRA Instance",
                             null=True, blank=True, on_delete=models.PROTECT)
    project_key = models.CharField(max_length=200, blank=True)
    product = models.ForeignKey(Product, on_delete=models.CASCADE, null=True)
    issue_template_dir = models.CharField(max_length=255,
                                      null=True,
                                      blank=True,
                                      help_text='Choose the folder containing the Django templates used to render the JIRA issue description. These are stored in dojo/templates/issue-trackers. Leave empty to use the default jira_full templates.')
    engagement = models.OneToOneField(Engagement, on_delete=models.CASCADE, null=True, blank=True)
    component = models.CharField(max_length=200, blank=True)
    push_all_issues = models.BooleanField(default=False, blank=True,
         help_text="Automatically maintain parity with JIRA. Always create and update JIRA tickets for findings in this Product.")
    enable_engagement_epic_mapping = models.BooleanField(default=False,
                                                         blank=True)
    push_notes = models.BooleanField(default=False, blank=True)
    product_jira_sla_notification = models.BooleanField(default=False, blank=True, verbose_name="Send SLA notifications as comment?")
    risk_acceptance_expiration_notification = models.BooleanField(default=False, blank=True, verbose_name="Send Risk Acceptance expiration notifications as comment?")

    def clean(self):
        if not self.jira_instance:
            raise ValidationError('Cannot save JIRA Project Configuration without JIRA Instance')

    def __str__(self):
        return ('%s: ' + self.project_key + '(%s)') % (str(self.id), str(self.jira_instance.url) if self.jira_instance else 'None')


# declare form here as we can't import forms.py due to circular imports not even locally
class JIRAForm_Admin(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput, required=True)

    # django doesn't seem to have an easy way to handle password fields as PasswordInput requires reentry of passwords
    password_from_db = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance:
            # keep password from db to use if the user entered no password
            self.password_from_db = self.instance.password
            self.fields['password'].required = False

    def clean(self):
        cleaned_data = super().clean()
        if not cleaned_data['password']:
            cleaned_data['password'] = self.password_from_db

        return cleaned_data


class JIRA_Conf_Admin(admin.ModelAdmin):
    form = JIRAForm_Admin


class JIRA_Issue(models.Model):
    jira_project = models.ForeignKey(JIRA_Project, on_delete=models.CASCADE, null=True)
    jira_id = models.CharField(max_length=200)
    jira_key = models.CharField(max_length=200)
    finding = models.OneToOneField(Finding, null=True, blank=True, on_delete=models.CASCADE)
    engagement = models.OneToOneField(Engagement, null=True, blank=True, on_delete=models.CASCADE)
    finding_group = models.OneToOneField(Finding_Group, null=True, blank=True, on_delete=models.CASCADE)

    jira_creation = models.DateTimeField(editable=True,
                                         null=True,
                                         verbose_name="Jira creation",
                                         help_text="The date a Jira issue was created from this finding.")
    jira_change = models.DateTimeField(editable=True,
                                       null=True,
                                       verbose_name="Jira last update",
                                       help_text="The date the linked Jira issue was last modified.")

    def set_obj(self, obj):
        if type(obj) == Finding:
            self.finding = obj
        elif type(obj) == Finding_Group:
            self.finding_group = obj
        elif type(obj) == Engagement:
            self.engagement = obj
        else:
            raise ValueError('unknown objec type whiel creating JIRA_Issue: %s', to_str_typed(obj))

    def __str__(self):
        text = ""
        if self.finding:
            text = self.finding.test.engagement.product.name + " | Finding: " + self.finding.title + ", ID: " + str(self.finding.id)
        elif self.engagement:
            text = self.engagement.product.name + " | Engagement: " + self.engagement.name + ", ID: " + str(self.engagement.id)
        return text + " | Jira Key: " + str(self.jira_key)


NOTIFICATION_CHOICES = (
    ("slack", "slack"), ("msteams", "msteams"), ("mail", "mail"),
    ("alert", "alert")
)


class Notifications(models.Model):
    product_type_added = MultiSelectField(choices=NOTIFICATION_CHOICES, default='alert', blank=True)
    product_added = MultiSelectField(choices=NOTIFICATION_CHOICES, default='alert', blank=True)
    engagement_added = MultiSelectField(choices=NOTIFICATION_CHOICES, default='alert', blank=True)
    test_added = MultiSelectField(choices=NOTIFICATION_CHOICES, default='alert', blank=True)
    scan_added = MultiSelectField(choices=NOTIFICATION_CHOICES, default='alert', blank=True, help_text='Triggered whenever an (re-)import has been done that created/updated/closed findings.')
    jira_update = MultiSelectField(choices=NOTIFICATION_CHOICES, default='alert', blank=True, verbose_name="JIRA problems", help_text="JIRA sync happens in the background, errors will be shown as notifications/alerts so make sure to subscribe")
    upcoming_engagement = MultiSelectField(choices=NOTIFICATION_CHOICES, default='alert', blank=True)
    stale_engagement = MultiSelectField(choices=NOTIFICATION_CHOICES, default='alert', blank=True)
    auto_close_engagement = MultiSelectField(choices=NOTIFICATION_CHOICES, default='alert', blank=True)
    close_engagement = MultiSelectField(choices=NOTIFICATION_CHOICES, default='alert', blank=True)
    user_mentioned = MultiSelectField(choices=NOTIFICATION_CHOICES, default='alert', blank=True)
    code_review = MultiSelectField(choices=NOTIFICATION_CHOICES, default='alert', blank=True)
    review_requested = MultiSelectField(choices=NOTIFICATION_CHOICES, default='alert', blank=True)
    other = MultiSelectField(choices=NOTIFICATION_CHOICES, default='alert', blank=True)
    user = models.ForeignKey(Dojo_User, default=None, null=True, editable=False, on_delete=models.CASCADE)
    product = models.ForeignKey(Product, default=None, null=True, editable=False, on_delete=models.CASCADE)
    sla_breach = MultiSelectField(choices=NOTIFICATION_CHOICES, default='alert', blank=True,
        verbose_name="SLA breach",
        help_text="Get notified of (upcoming) SLA breaches")
    risk_acceptance_expiration = MultiSelectField(choices=NOTIFICATION_CHOICES, default='alert', blank=True,
        verbose_name="Risk Acceptance Expiration",
        help_text="Get notified of (upcoming) Risk Acceptance expiries")

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['user', 'product'], name="notifications_user_product")
        ]
        indexes = [
            models.Index(fields=['user', 'product']),
        ]

    @classmethod
    def merge_notifications_list(cls, notifications_list):
        if not notifications_list:
            return []

        result = None
        for notifications in notifications_list:
            if result is None:
                # we start by copying the first instance, because creating a new instance would set all notification columns to 'alert' :-()
                result = notifications
                # result.pk = None # detach from db
            else:
                # TODO This concat looks  better, but requires Python 3.6+
                # result.scan_added = [*result.scan_added, *notifications.scan_added]
                from dojo.utils import merge_sets_safe
                result.product_type_added = merge_sets_safe(result.product_type_added, notifications.product_type_added)
                result.product_added = merge_sets_safe(result.product_added, notifications.product_added)
                result.engagement_added = merge_sets_safe(result.engagement_added, notifications.engagement_added)
                result.test_added = merge_sets_safe(result.test_added, notifications.test_added)
                result.scan_added = merge_sets_safe(result.scan_added, notifications.scan_added)
                result.jira_update = merge_sets_safe(result.jira_update, notifications.jira_update)
                result.upcoming_engagement = merge_sets_safe(result.upcoming_engagement, notifications.upcoming_engagement)
                result.stale_engagement = merge_sets_safe(result.stale_engagement, notifications.stale_engagement)
                result.auto_close_engagement = merge_sets_safe(result.auto_close_engagement, notifications.auto_close_engagement)
                result.close_engagement = merge_sets_safe(result.close_engagement, notifications.close_engagement)
                result.user_mentioned = merge_sets_safe(result.user_mentioned, notifications.user_mentioned)
                result.code_review = merge_sets_safe(result.code_review, notifications.code_review)
                result.review_requested = merge_sets_safe(result.review_requested, notifications.review_requested)
                result.other = merge_sets_safe(result.other, notifications.other)
                result.sla_breach = merge_sets_safe(result.sla_breach, notifications.sla_breach)
                result.risk_acceptance_expiration = merge_sets_safe(result.risk_acceptance_expiration, notifications.risk_acceptance_expiration)

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
    title = models.CharField(max_length=250, default='', null=False)
    description = models.CharField(max_length=2000, null=True, blank=True)
    url = models.URLField(max_length=2000, null=True, blank=True)
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

    def __str__(self):
        return self.cred_id.name + " (" + self.cred_id.role + ")"


class Language_Type(models.Model):
    language = models.CharField(max_length=100, null=False)
    color = models.CharField(max_length=7, null=True, blank=True, verbose_name='HTML color')

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

    tags = TagField(blank=True, force_lowercase=True)

    def __str__(self):
        return self.name + " | " + self.product.name


class Objects_Review(models.Model):
    name = models.CharField(max_length=100, null=True, blank=True)
    created = models.DateTimeField(null=False, editable=False, default=now)

    def __str__(self):
        return self.name


class Objects_Product(models.Model):
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

    tags = TagField(blank=True, force_lowercase=True, help_text="Add tags that help describe this object. Choose from the list or add new tags. Press Enter key to add.")

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
    object_id = models.ForeignKey(Objects_Product, on_delete=models.CASCADE)
    build_id = models.CharField(max_length=150, null=True, blank=True)
    created = models.DateTimeField(null=False, editable=False, default=now)
    full_url = models.URLField(max_length=400, null=True, blank=True)
    type = models.CharField(max_length=30, null=True, blank=True)
    percentUnchanged = models.CharField(max_length=10, null=True, blank=True)

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

    def __str__(self):
        return self.name + ': ' + self.type.name


class Benchmark_Requirement(models.Model):
    category = models.ForeignKey(Benchmark_Category, on_delete=models.CASCADE)
    objective_number = models.CharField(max_length=15, null=True, blank=True)
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

    def __str__(self):
        return self.product.name + ': ' + self.benchmark_type.name

    class Meta:
        unique_together = [('product', 'benchmark_type')]


# product_opts = [f.name for f in Product._meta.fields]
# test_opts = [f.name for f in Test._meta.fields]
# test_type_opts = [f.name for f in Test_Type._meta.fields]
finding_opts = [f.name for f in Finding._meta.fields if f.name not in ['last_status_update']]
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


# ==========================
# Defect Dojo Engaegment Surveys
# ==============================

class Question(PolymorphicModel, TimeStampedModel):
    '''
        Represents a question.
    '''

    class Meta:
        ordering = ['order']

    order = models.PositiveIntegerField(default=1,
                                        help_text='The render order')

    optional = models.BooleanField(
        default=False,
        help_text="If selected, user doesn't have to answer this question")

    text = models.TextField(blank=False, help_text='The question text', default='')

    def __str__(self):
        return self.text


class TextQuestion(Question):
    '''
    Question with a text answer
    '''

    def get_form(self):
        '''
        Returns the form for this model
        '''
        from .forms import TextQuestionForm
        return TextQuestionForm


class Choice(TimeStampedModel):
    '''
    Model to store the choices for multi choice questions
    '''

    order = models.PositiveIntegerField(default=1)

    label = models.TextField(default="")

    class Meta:
        ordering = ['order']

    def __str__(self):
        return self.label


class ChoiceQuestion(Question):
    '''
    Question with answers that are chosen from a list of choices defined
    by the user.
    '''

    multichoice = models.BooleanField(default=False,
                                      help_text="Select one or more")

    choices = models.ManyToManyField(Choice)

    def get_form(self):
        '''
        Returns the form for this model
        '''

        from .forms import ChoiceQuestionForm
        return ChoiceQuestionForm


# meant to be a abstract survey, identified by name for purpose
class Engagement_Survey(models.Model):
    name = models.CharField(max_length=200, null=False, blank=False,
                            editable=True, default='')
    description = models.TextField(editable=True, default='')
    questions = models.ManyToManyField(Question)
    active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Engagement Survey"
        verbose_name_plural = "Engagement Surveys"
        ordering = ('-active', 'name',)

    def __str__(self):
        return self.name


# meant to be an answered survey tied to an engagement

class Answered_Survey(models.Model):
    # tie this to a specific engagement
    engagement = models.ForeignKey(Engagement, related_name='engagement+',
                                   null=True, blank=False, editable=True,
                                   on_delete=models.CASCADE)
    # what surveys have been answered
    survey = models.ForeignKey(Engagement_Survey, on_delete=models.CASCADE)
    assignee = models.ForeignKey(User, related_name='assignee',
                                  null=True, blank=True, editable=True,
                                  default=None, on_delete=models.CASCADE)
    # who answered it
    responder = models.ForeignKey(User, related_name='responder',
                                  null=True, blank=True, editable=True,
                                  default=None, on_delete=models.CASCADE)
    completed = models.BooleanField(default=False)
    answered_on = models.DateField(null=True)

    class Meta:
        verbose_name = "Answered Engagement Survey"
        verbose_name_plural = "Answered Engagement Surveys"

    def __str__(self):
        return self.survey.name


class General_Survey(models.Model):
    survey = models.ForeignKey(Engagement_Survey, on_delete=models.CASCADE)
    num_responses = models.IntegerField(default=0)
    generated = models.DateTimeField(auto_now_add=True, null=True)
    expiration = models.DateTimeField(null=False, blank=False)

    class Meta:
        verbose_name = "General Engagement Survey"
        verbose_name_plural = "General Engagement Surveys"

    def __str__(self):
        return self.survey.name


class Answer(PolymorphicModel, TimeStampedModel):
    ''' Base Answer model
    '''
    question = models.ForeignKey(Question, on_delete=models.CASCADE)

    answered_survey = models.ForeignKey(Answered_Survey,
                                        null=False,
                                        blank=False,
                                        on_delete=models.CASCADE)


class TextAnswer(Answer):
    answer = models.TextField(
        blank=False,
        help_text='The answer text',
        default='')

    def __str__(self):
        return self.answer


class ChoiceAnswer(Answer):
    answer = models.ManyToManyField(
        Choice,
        help_text='The selected choices as the answer')

    def __str__(self):
        if len(self.answer.all()):
            return str(self.answer.all()[0])
        else:
            return 'No Response'


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


from dojo.utils import calculate_grade, get_system_setting, to_str_typed
enable_disable_auditlog(enable=get_system_setting('enable_auditlog'))  # on startup choose safe to retrieve system settiung)

tagulous.admin.register(Product.tags)
tagulous.admin.register(Test.tags)
tagulous.admin.register(Finding.tags)
tagulous.admin.register(Engagement.tags)
tagulous.admin.register(Endpoint.tags)
tagulous.admin.register(Finding_Template.tags)
tagulous.admin.register(App_Analysis.tags)
tagulous.admin.register(Objects_Product.tags)

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
admin.site.register(Objects_Product)
admin.site.register(Objects_Review)
admin.site.register(Objects_Engagement)
admin.site.register(Languages)
admin.site.register(Language_Type)
admin.site.register(App_Analysis)
admin.site.register(Test)
admin.site.register(Finding, FindingAdmin)
admin.site.register(FileUpload)
admin.site.register(FileAccessToken)
admin.site.register(Stub_Finding)
admin.site.register(Engagement)
admin.site.register(Risk_Acceptance)
admin.site.register(Check_List)
admin.site.register(Test_Type)
admin.site.register(Endpoint)
admin.site.register(Product)
admin.site.register(Product_Type)
admin.site.register(UserContactInfo)
admin.site.register(Notes)
admin.site.register(Note_Type)
admin.site.register(Alerts)
admin.site.register(JIRA_Issue)
admin.site.register(JIRA_Instance, JIRA_Instance_Admin)
admin.site.register(JIRA_Project)
admin.site.register(GITHUB_Conf)
admin.site.register(GITHUB_PKey)
admin.site.register(Tool_Configuration, Tool_Configuration_Admin)
admin.site.register(Tool_Product_Settings)
admin.site.register(Tool_Type)
admin.site.register(Cred_User)
admin.site.register(Cred_Mapping)
admin.site.register(System_Settings, System_SettingsAdmin)
admin.site.register(CWE)
admin.site.register(Regulation)
admin.site.register(Notifications)

# SonarQube Integration
admin.site.register(Sonarqube_Issue)
admin.site.register(Sonarqube_Issue_Transition)
admin.site.register(Sonarqube_Product)
