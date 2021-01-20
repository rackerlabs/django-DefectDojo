import re
from datetime import datetime, date
from urllib.parse import urlsplit, urlunsplit
import pickle
from crispy_forms.bootstrap import InlineRadios, InlineCheckboxes
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout
from django.db.models import Count

from dateutil.relativedelta import relativedelta
from django import forms
from django.core import validators
from django.core.validators import RegexValidator
from django.core.exceptions import ValidationError
from django.forms import modelformset_factory
from django.forms.widgets import Widget, Select
from django.utils.dates import MONTHS
from django.utils.safestring import mark_safe
from django.utils import timezone

from dojo.models import Finding, Product_Type, Product, Note_Type, ScanSettings, VA, \
    Check_List, User, Engagement, Test, Test_Type, Notes, Risk_Acceptance, \
    Development_Environment, Dojo_User, Scan, Endpoint, Stub_Finding, Finding_Template, Report, FindingImage, \
    JIRA_Issue, JIRA_Project, JIRA_Instance, GITHUB_Issue, GITHUB_PKey, GITHUB_Conf, UserContactInfo, Tool_Type, \
    Tool_Configuration, Tool_Product_Settings, Cred_User, Cred_Mapping, System_Settings, Notifications, \
    Languages, Language_Type, App_Analysis, Objects_Product, Benchmark_Product, Benchmark_Requirement, \
    Benchmark_Product_Summary, Rule, Child_Rule, Engagement_Presets, DojoMeta, Sonarqube_Product, \
    Engagement_Survey, Answered_Survey, TextAnswer, ChoiceAnswer, Choice, Question, TextQuestion, \
    ChoiceQuestion, General_Survey, Regulation, FileUpload

from dojo.tools import requires_file, SCAN_SONARQUBE_API
from dojo.user.helper import user_is_authorized
from django.urls import reverse
from tagulous.forms import TagField
import logging
from crum import get_current_user
from dojo.utils import get_system_setting

logger = logging.getLogger(__name__)

RE_DATE = re.compile(r'(\d{4})-(\d\d?)-(\d\d?)$')

FINDING_STATUS = (('verified', 'Verified'),
                  ('false_p', 'False Positive'),
                  ('duplicate', 'Duplicate'),
                  ('out_of_scope', 'Out of Scope'))

SEVERITY_CHOICES = (('Info', 'Info'), ('Low', 'Low'), ('Medium', 'Medium'),
                    ('High', 'High'), ('Critical', 'Critical'))


class SelectWithPop(forms.Select):
    def render(self, name, *args, **kwargs):
        html = super(SelectWithPop, self).render(name, *args, **kwargs)
        popup_plus = '<div class="input-group dojo-input-group">' + html + '<span class="input-group-btn"><a href="/' + name + '/add" class="btn btn-primary" class="add-another" id="add_id_' + name + '" onclick="return showAddAnotherPopup(this);"><span class="glyphicon glyphicon-plus"></span></a></span></div>'

        return mark_safe(popup_plus)


class MultipleSelectWithPop(forms.SelectMultiple):
    def render(self, name, *args, **kwargs):
        html = super(MultipleSelectWithPop, self).render(name, *args, **kwargs)
        popup_plus = '<div class="input-group dojo-input-group">' + html + '<span class="input-group-btn"><a href="/' + name + '/add" class="btn btn-primary" class="add-another" id="add_id_' + name + '" onclick="return showAddAnotherPopup(this);"><span class="glyphicon glyphicon-plus"></span></a></span></div>'

        return mark_safe(popup_plus)


class MultipleSelectWithPopPlusMinus(forms.SelectMultiple):
    def render(self, name, *args, **kwargs):
        html = super(MultipleSelectWithPopPlusMinus, self).render(name, *args, **kwargs)
        popup_plus = '<div class="input-group dojo-input-group">' + html + '<span class="input-group-btn"><a href="/' + name + '/add" class="btn btn-primary" class="add-another" id="add_id_' + name + '" onclick="return showAddAnotherPopup(this);"><span class="icon-plusminus"></span></a></span></div>'

        return mark_safe(popup_plus)


class MonthYearWidget(Widget):
    """
    A Widget that splits date input into two <select> boxes for month and year,
    with 'day' defaulting to the first of the month.

    Based on SelectDateWidget, in

    django/trunk/django/forms/extras/widgets.py
    """
    none_value = (0, '---')
    month_field = '%s_month'
    year_field = '%s_year'

    def __init__(self, attrs=None, years=None, required=True):
        # years is an optional list/tuple of years to use in the
        # "year" select box.
        self.attrs = attrs or {}
        self.required = required
        if years:
            self.years = years
        else:
            this_year = date.today().year
            self.years = list(range(this_year - 10, this_year + 1))

    def render(self, name, value, attrs=None, renderer=None):
        try:
            year_val, month_val = value.year, value.month
        except AttributeError:
            year_val = month_val = None
            if isinstance(value, str):
                match = RE_DATE.match(value)
                if match:
                    year_val,
                    month_val,
                    day_val = [int(v) for v in match.groups()]

        output = []

        if 'id' in self.attrs:
            id_ = self.attrs['id']
        else:
            id_ = 'id_%s' % name

        month_choices = list(MONTHS.items())
        if not (self.required and value):
            month_choices.append(self.none_value)
        month_choices.sort()
        local_attrs = self.build_attrs({'id': self.month_field % id_})
        s = Select(choices=month_choices)
        select_html = s.render(self.month_field % name, month_val, local_attrs)

        output.append(select_html)

        year_choices = [(i, i) for i in self.years]
        if not (self.required and value):
            year_choices.insert(0, self.none_value)
        local_attrs['id'] = self.year_field % id_
        s = Select(choices=year_choices)
        select_html = s.render(self.year_field % name, year_val, local_attrs)
        output.append(select_html)

        return mark_safe('\n'.join(output))

    def id_for_label(self, id_):
        return '%s_month' % id_

    id_for_label = classmethod(id_for_label)

    def value_from_datadict(self, data, files, name):
        y = data.get(self.year_field % name)
        m = data.get(self.month_field % name)
        if y == m == "0":
            return None
        if y and m:
            return '%s-%s-%s' % (y, m, 1)
        return data.get(name, None)


class Product_TypeForm(forms.ModelForm):
    authorized_users = forms.ModelMultipleChoiceField(
        queryset=None,
        required=False, label="Authorized Users")

    def __init__(self, *args, **kwargs):
        non_staff = Dojo_User.objects.exclude(is_staff=True) \
            .exclude(is_active=False).order_by('first_name', 'last_name')
        super(Product_TypeForm, self).__init__(*args, **kwargs)
        self.fields['authorized_users'].queryset = non_staff

    class Meta:
        model = Product_Type
        fields = ['name', 'authorized_users', 'critical_product', 'key_product']


class Delete_Product_TypeForm(forms.ModelForm):
    class Meta:
        model = Product_Type
        exclude = ['name', 'critical_product', 'key_product']


class Test_TypeForm(forms.ModelForm):
    class Meta:
        model = Test_Type
        exclude = ['']


class Development_EnvironmentForm(forms.ModelForm):
    class Meta:
        model = Development_Environment
        fields = ['name']


class Delete_Dev_EnvironmentForm(forms.ModelForm):
    class Meta:
        model = Development_Environment
        exclude = ['name']


class ProductForm(forms.ModelForm):
    name = forms.CharField(max_length=50, required=True)
    description = forms.CharField(widget=forms.Textarea(attrs={}),
                                  required=True)

    prod_type = forms.ModelChoiceField(label='Product Type',
                                       queryset=Product_Type.objects.all().order_by('name'),
                                       required=True)

    authorized_users = forms.ModelMultipleChoiceField(
        queryset=None,
        required=False, label="Authorized Users")

    app_analysis = forms.ModelMultipleChoiceField(label='Technologies',
                                           queryset=App_Analysis.objects.all().order_by('name'),
                                           required=False)

    product_manager = forms.ModelChoiceField(queryset=Dojo_User.objects.exclude(is_active=False).order_by('first_name', 'last_name'), required=False)
    technical_contact = forms.ModelChoiceField(queryset=Dojo_User.objects.exclude(is_active=False).order_by('first_name', 'last_name'), required=False)
    team_manager = forms.ModelChoiceField(queryset=Dojo_User.objects.exclude(is_active=False).order_by('first_name', 'last_name'), required=False)

    def __init__(self, *args, **kwargs):
        non_staff = Dojo_User.objects.exclude(is_staff=True) \
            .exclude(is_active=False).order_by('first_name', 'last_name')
        super(ProductForm, self).__init__(*args, **kwargs)
        self.fields['authorized_users'].queryset = non_staff

    class Meta:
        model = Product
        fields = ['name', 'description', 'tags', 'product_manager', 'technical_contact', 'team_manager', 'prod_type', 'regulations', 'app_analysis',
                  'authorized_users', 'business_criticality', 'platform', 'lifecycle', 'origin', 'user_records', 'revenue', 'external_audience',
                  'internet_accessible', 'enable_simple_risk_acceptance', 'enable_full_risk_acceptance']


class DeleteProductForm(forms.ModelForm):
    id = forms.IntegerField(required=True,
                            widget=forms.widgets.HiddenInput())

    class Meta:
        model = Product
        exclude = ['name', 'description', 'prod_manager', 'tech_contact', 'manager', 'created',
                   'prod_type', 'updated', 'tid', 'authorized_users', 'product_manager',
                   'technical_contact', 'team_manager', 'prod_numeric_grade', 'business_criticality',
                   'platform', 'lifecycle', 'origin', 'user_records', 'revenue', 'external_audience',
                   'internet_accessible', 'regulations', 'product_meta']


class NoteTypeForm(forms.ModelForm):
    description = forms.CharField(widget=forms.Textarea(attrs={}),
                                  required=True)

    class Meta:
        model = Note_Type
        fields = ['name', 'description', 'is_single', 'is_mandatory']


class EditNoteTypeForm(NoteTypeForm):

    def __init__(self, *args, **kwargs):
        is_single = kwargs.pop('is_single')
        super(EditNoteTypeForm, self).__init__(*args, **kwargs)
        if is_single is False:
            self.fields['is_single'].widget = forms.HiddenInput()


class DisableOrEnableNoteTypeForm(NoteTypeForm):
    def __init__(self, *args, **kwargs):
        super(DisableOrEnableNoteTypeForm, self).__init__(*args, **kwargs)
        self.fields['name'].disabled = True
        self.fields['description'].disabled = True
        self.fields['is_single'].disabled = True
        self.fields['is_mandatory'].disabled = True
        self.fields['is_active'].disabled = True

    class Meta:
        model = Note_Type
        fields = '__all__'


class DojoMetaDataForm(forms.ModelForm):
    value = forms.CharField(widget=forms.Textarea(attrs={}),
                            required=True)

    def full_clean(self):
        super(DojoMetaDataForm, self).full_clean()
        try:
            self.instance.validate_unique()
        except ValidationError:
            msg = "A metadata entry with the same name exists already for this object."
            self.add_error('name', msg)

    class Meta:
        model = DojoMeta
        fields = '__all__'


class Product_TypeProductForm(forms.ModelForm):
    name = forms.CharField(max_length=50, required=True)
    description = forms.CharField(widget=forms.Textarea(attrs={}),
                                  required=True)
    # tags = forms.CharField(widget=forms.SelectMultiple(choices=[]),
    #                        required=False,
    #                        help_text="Add tags that help describe this product.  "
    #                                  "Choose from the list or add new tags.  Press TAB key to add.")
    authorized_users = forms.ModelMultipleChoiceField(
        queryset=None,
        required=False, label="Authorized Users")
    prod_type = forms.ModelChoiceField(label='Product Type',
                                       queryset=Product_Type.objects.all().order_by('name'),
                                       required=True)

    def __init__(self, *args, **kwargs):
        non_staff = User.objects.exclude(is_staff=True) \
            .exclude(is_active=False)
        super(Product_TypeProductForm, self).__init__(*args, **kwargs)
        self.fields['authorized_users'].queryset = non_staff

    class Meta:
        model = Product
        fields = ['name', 'description', 'tags', 'product_manager', 'technical_contact', 'team_manager', 'prod_type', 'regulations',
                  'authorized_users', 'business_criticality', 'platform', 'lifecycle', 'origin', 'user_records', 'revenue', 'external_audience', 'internet_accessible']


class ImportScanForm(forms.Form):
    SCAN_TYPE_CHOICES = (("", "Please Select a Scan Type"),
                         ("Netsparker Scan", "Netsparker Scan"),
                         ("Burp Scan", "Burp Scan"),
                         ("Burp REST API", "Burp REST API"),
                         ("Nessus Scan", "Nessus Scan"),
                         ("Nmap Scan", "Nmap Scan"),
                         ("Nexpose Scan", "Nexpose Scan"),
                         ("AppSpider Scan", "AppSpider Scan"),
                         ("Veracode Scan", "Veracode Scan"),
                         ("Checkmarx Scan", "Checkmarx Scan"),
                         ("Checkmarx Scan detailed", "Checkmarx Scan detailed"),
                         ("Crashtest Security JSON File", "Crashtest Security JSON File"),
                         ("Crashtest Security XML File", "Crashtest Security XML File"),
                         ("ZAP Scan", "ZAP Scan"),
                         ("Arachni Scan", "Arachni Scan"),
                         ("VCG Scan", "VCG Scan"),
                         ("Dependency Check Scan", "Dependency Check Scan"),
                         ("Dependency Track Finding Packaging Format (FPF) Export", "Dependency Track Finding Packaging Format (FPF) Export"),
                         ("Retire.js Scan", "Retire.js Scan"),
                         ("Node Security Platform Scan", "Node Security Platform Scan"),
                         ("NPM Audit Scan", "NPM Audit Scan"),
                         ("Qualys Scan", "Qualys Scan"),
                         ("Qualys Infrastructure Scan (WebGUI XML)", "Qualys Infrastructure Scan (WebGUI XML)"),
                         ("Qualys Webapp Scan", "Qualys Webapp Scan"),
                         ("OpenVAS CSV", "OpenVAS CSV"),
                         ("Snyk Scan", "Snyk Scan"),
                         ("Generic Findings Import", "Generic Findings Import"),
                         ("Trustwave Scan (CSV)", "Trustwave Scan (CSV)"),
                         ("SKF Scan", "SKF Scan"),
                         ("Clair Klar Scan", "Clair Klar Scan"),
                         ("Bandit Scan", "Bandit Scan"),
                         ("ESLint Scan", "ESLint Scan"),
                         ("SSL Labs Scan", "SSL Labs Scan"),
                         ("Acunetix Scan", "Acunetix Scan"),
                         ("Fortify Scan", "Fortify Scan"),
                         ("Gosec Scanner", "Gosec Scanner"),
                         ("SonarQube Scan", "SonarQube Scan"),
                         ("SonarQube Scan detailed", "SonarQube Scan detailed"),
                         (SCAN_SONARQUBE_API, SCAN_SONARQUBE_API),
                         ("MobSF Scan", "MobSF Scan"),
                         ("Trufflehog Scan", "Trufflehog Scan"),
                         ("Nikto Scan", "Nikto Scan"),
                         ("Clair Scan", "Clair Scan"),
                         ("Brakeman Scan", "Brakeman Scan"),
                         ("SpotBugs Scan", "SpotBugs Scan"),
                         ("AWS Scout2 Scan", "AWS Scout2 Scan"),
                         ("AWS Prowler Scan", "AWS Prowler Scan"),
                         ("Scout Suite Scan", "Scout Suite Scan"),
                         ("IBM AppScan DAST", "IBM AppScan DAST"),
                         ("PHP Security Audit v2", "PHP Security Audit v2"),
                         ("PHP Symfony Security Check", "PHP Symfony Security Check"),
                         ("Safety Scan", "Safety Scan"),
                         ("DawnScanner Scan", "DawnScanner Scan"),
                         ("Anchore Engine Scan", "Anchore Engine Scan"),
                         ("Bundler-Audit Scan", "Bundler-Audit Scan"),
                         ("Twistlock Image Scan", "Twistlock Image Scan"),
                         ("Kiuwan Scan", "Kiuwan Scan"),
                         ("Blackduck Hub Scan", "Blackduck Hub Scan"),
                         ("Blackduck Component Risk", "Blackduck Component Risk"),
                         ("Openscap Vulnerability Scan", "Openscap Vulnerability Scan"),
                         ("Wapiti Scan", "Wapiti Scan"),
                         ("Immuniweb Scan", "Immuniweb Scan"),
                         ("Sonatype Application Scan", "Sonatype Application Scan"),
                         ("Cobalt.io Scan", "Cobalt.io Scan"),
                         ("Mozilla Observatory Scan", "Mozilla Observatory Scan"),
                         ("Whitesource Scan", "Whitesource Scan"),
                         ("Contrast Scan", "Contrast Scan"),
                         ("Microfocus Webinspect Scan", "Microfocus Webinspect Scan"),
                         ("Wpscan", "Wpscan"),
                         ("Sslscan", "Sslscan"),
                         ("JFrog Xray Scan", "JFrog Xray Scan"),
                         ("Sslyze Scan", "Sslyze Scan"),
                         ("SSLyze 3 Scan (JSON)", "SSLyze 3 Scan (JSON)"),
                         ("Testssl Scan", "Testssl Scan"),
                         ("Hadolint Dockerfile check", "Hadolint Dockerfile check"),
                         ("Aqua Scan", "Aqua Scan"),
                         ("HackerOne Cases", "HackerOne Cases"),
                         ("Xanitizer Scan", "Xanitizer Scan"),
                         ("Outpost24 Scan", "Outpost24 Scan"),
                         ("Burp Enterprise Scan", "Burp Enterprise Scan"),
                         ("DSOP Scan", "DSOP Scan"),
                         ("Trivy Scan", "Trivy Scan"),
                         ("Anchore Enterprise Policy Check", "Anchore Enterprise Policy Check"),
                         ("Gitleaks Scan", "Gitleaks Scan"),
                         ("Choctaw Hog Scan", "Choctaw Hog Scan"),
                         ("Harbor Vulnerability Scan", "Harbor Vulnerability Scan"),
                         ("Github Vulnerability Scan", "Github Vulnerability Scan"),
                         ("Yarn Audit Scan", "Yarn Audit Scan"),
                         ("BugCrowd Scan", "BugCrowd Scan"),
                         ("GitLab SAST Report", "GitLab SAST Report"),
                         ("AWS Security Hub Scan", "AWS Security Hub Scan"),
                         ("GitLab Dependency Scanning Report", "GitLab Dependency Scanning Report"),
                         ("HuskyCI Report", "HuskyCI Report"),
                         ("Semgrep JSON Report", "Semgrep JSON Report"),
                         ("Risk Recon API Importer", "Risk Recon API Importer"),
                         ("DrHeader JSON Importer", "DrHeader JSON Importer"),
                         ("Checkov Scan", "Checkov Scan"),
                         ("kube-bench Scan", "Kube-Bench Scan"),
                         ("CCVS Report", "CCVS Report"),
                         ("ORT evaluated model Importer", "ORT evaluated model Importer"),
                         ("SARIF", "SARIF"),
                         ("OssIndex Devaudit SCA Scan Importer", "OssIndex Devaudit SCA Scan Importer"),
                         ("Scantist Scan", "Scantist Scan"),
                         )

    SORTED_SCAN_TYPE_CHOICES = sorted(SCAN_TYPE_CHOICES, key=lambda x: x[1])
    scan_date = forms.DateTimeField(
        required=True,
        label="Scan Completion Date",
        help_text="Scan completion date will be used on all findings.",
        initial=datetime.now().strftime("%Y-%m-%d"),
        widget=forms.TextInput(attrs={'class': 'datepicker'}))
    minimum_severity = forms.ChoiceField(help_text='Minimum severity level to be imported',
                                         required=True,
                                         choices=SEVERITY_CHOICES)
    active = forms.BooleanField(help_text="Select if these findings are currently active.", required=False, initial=True)
    verified = forms.BooleanField(help_text="Select if these findings have been verified.", required=False)
    scan_type = forms.ChoiceField(required=True, choices=SORTED_SCAN_TYPE_CHOICES)
    environment = forms.ModelChoiceField(
        queryset=Development_Environment.objects.all().order_by('name'))
    endpoints = forms.ModelMultipleChoiceField(Endpoint.objects, required=False, label='Systems / Endpoints',
                                               widget=MultipleSelectWithPopPlusMinus(attrs={'size': '5'}))
    tags = TagField(required=False, help_text="Add tags that help describe this scan.  "
                    "Choose from the list or add new tags. Press Enter key to add.")
    file = forms.FileField(widget=forms.widgets.FileInput(
        attrs={"accept": ".xml, .csv, .nessus, .json, .html, .js, .zip, .xlsx"}),
        label="Choose report file",
        required=False)

    def __init__(self, *args, **kwargs):
        super(ImportScanForm, self).__init__(*args, **kwargs)

    def clean(self):
        cleaned_data = super().clean()
        scan_type = cleaned_data.get("scan_type")
        file = cleaned_data.get("file")
        if requires_file(scan_type) and not file:
            raise forms.ValidationError('Uploading a Report File is required for {}'.format(scan_type))
        return cleaned_data

    # date can only be today or in the past, not the future
    def clean_scan_date(self):
        date = self.cleaned_data['scan_date']
        if date.date() > datetime.today().date():
            raise forms.ValidationError("The date cannot be in the future!")
        return date

    def get_scan_type(self):
        TGT_scan = self.cleaned_data['scan_type']
        return TGT_scan


class ReImportScanForm(forms.Form):
    scan_date = forms.DateTimeField(
        required=True,
        label="Scan Completion Date",
        help_text="Scan completion date will be used on all findings.",
        initial=datetime.now().strftime("%m/%d/%Y"),
        widget=forms.TextInput(attrs={'class': 'datepicker'}))
    minimum_severity = forms.ChoiceField(help_text='Minimum severity level to be imported',
                                         required=True,
                                         choices=SEVERITY_CHOICES[0:4])
    active = forms.BooleanField(help_text="Select if these findings are currently active.", required=False, initial=True)
    verified = forms.BooleanField(help_text="Select if these findings have been verified.", required=False)
    endpoints = forms.ModelMultipleChoiceField(Endpoint.objects, required=False, label='Systems / Endpoints',
                                               widget=MultipleSelectWithPopPlusMinus(attrs={'size': '5'}))
    tags = TagField(required=False, help_text="Modify existing tags that help describe this scan.  "
                    "Choose from the list or add new tags. Press Enter key to add.")
    file = forms.FileField(widget=forms.widgets.FileInput(
        attrs={"accept": ".xml, .csv, .nessus, .json, .html, .js, .zip, .xlsx"}),
        label="Choose report file",
        required=False)
    close_old_findings = forms.BooleanField(help_text="Select if old findings get mitigated when importing.",
                                            required=False, initial=True)

    def __init__(self, *args, test=None, **kwargs):
        super(ReImportScanForm, self).__init__(*args, **kwargs)
        self.scan_type = None
        if test:
            self.scan_type = test.test_type.name
            self.fields['tags'].initial = test.tags.all()

    def clean(self):
        cleaned_data = super().clean()
        file = cleaned_data.get("file")
        if requires_file(self.scan_type) and not file:
            raise forms.ValidationError("Uploading a report file is required for re-uploading findings.")
        return cleaned_data

    # date can only be today or in the past, not the future
    def clean_scan_date(self):
        date = self.cleaned_data['scan_date']
        if date.date() > datetime.today().date():
            raise forms.ValidationError("The date cannot be in the future!")
        return date


class DoneForm(forms.Form):
    done = forms.BooleanField()


class UploadThreatForm(forms.Form):
    file = forms.FileField(widget=forms.widgets.FileInput(
        attrs={"accept": ".jpg,.png,.pdf"}),
        label="Select Threat Model")


class MergeFindings(forms.ModelForm):
    FINDING_ACTION = (('', 'Select an Action'), ('inactive', 'Inactive'), ('delete', 'Delete'))

    append_description = forms.BooleanField(label="Append Description", initial=True, required=False,
                                            help_text="Description in all findings will be appended into the merged finding.")

    add_endpoints = forms.BooleanField(label="Add Endpoints", initial=True, required=False,
                                           help_text="Endpoints in all findings will be merged into the merged finding.")

    dynamic_raw = forms.BooleanField(label="Dynamic Scanner Raw Requests", initial=True, required=False,
                                           help_text="Dynamic scanner raw requests in all findings will be merged into the merged finding.")

    tag_finding = forms.BooleanField(label="Add Tags", initial=True, required=False,
                                           help_text="Tags in all findings will be merged into the merged finding.")

    mark_tag_finding = forms.BooleanField(label="Tag Merged Finding", initial=True, required=False,
                                           help_text="Creates a tag titled 'merged' for the finding that will be merged. If the 'Finding Action' is set to 'inactive' the inactive findings will be tagged with 'merged-inactive'.")

    append_reference = forms.BooleanField(label="Append Reference", initial=True, required=False,
                                            help_text="Reference in all findings will be appended into the merged finding.")

    finding_action = forms.ChoiceField(
        required=True,
        choices=FINDING_ACTION,
        label="Finding Action",
        help_text="The action to take on the merged finding. Set the findings to inactive or delete the findings.")

    def __init__(self, *args, **kwargs):
        finding = kwargs.pop('finding')
        findings = kwargs.pop('findings')
        super(MergeFindings, self).__init__(*args, **kwargs)

        self.fields['finding_to_merge_into'] = forms.ModelChoiceField(
            queryset=findings, initial=0, required="False", label="Finding to Merge Into", help_text="Findings selected below will be merged into this finding.")

        # Exclude the finding to merge into from the findings to merge into
        self.fields['findings_to_merge'] = forms.ModelMultipleChoiceField(
            queryset=findings, required=True, label="Findings to Merge",
            widget=forms.widgets.SelectMultiple(attrs={'size': 10}),
            help_text=('Select the findings to merge.'))
        self.fields.keyOrder = ['finding_to_merge_into', 'findings_to_merge', 'append_description', 'add_endpoints', 'append_reference']

    class Meta:
        model = Finding
        fields = ['append_description', 'add_endpoints', 'append_reference']


class EditRiskAcceptanceForm(forms.ModelForm):
    # unfortunately django forces us to repeat many things here. choices, default, required etc.
    recommendation = forms.ChoiceField(choices=Risk_Acceptance.TREATMENT_CHOICES, initial=Risk_Acceptance.TREATMENT_ACCEPT, widget=forms.RadioSelect, label="Security Recommendation")
    decision = forms.ChoiceField(choices=Risk_Acceptance.TREATMENT_CHOICES, initial=Risk_Acceptance.TREATMENT_ACCEPT, widget=forms.RadioSelect)

    path = forms.FileField(label="Proof", required=False, widget=forms.widgets.FileInput(attrs={"accept": ".jpg,.png,.pdf"}))
    expiration_date = forms.DateTimeField(required=False, widget=forms.TextInput(attrs={'class': 'datepicker'}))

    class Meta:
        model = Risk_Acceptance
        exclude = ['accepted_findings', 'notes']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['path'].help_text = 'Existing proof uploaded: %s' % self.instance.filename() if self.instance.filename() else 'None'
        self.fields['expiration_date_warned'].disabled = True
        self.fields['expiration_date_handled'].disabled = True


class RiskAcceptanceForm(EditRiskAcceptanceForm):
    # path = forms.FileField(label="Proof", required=False, widget=forms.widgets.FileInput(attrs={"accept": ".jpg,.png,.pdf"}))
    # expiration_date = forms.DateTimeField(required=False, widget=forms.TextInput(attrs={'class': 'datepicker'}))
    accepted_findings = forms.ModelMultipleChoiceField(
        queryset=Finding.objects.all(), required=True,
        widget=forms.widgets.SelectMultiple(attrs={'size': 10}),
        help_text=('Active, verified findings listed, please select to add findings.'))
    notes = forms.CharField(required=False, max_length=2400,
                            widget=forms.Textarea,
                            label='Notes')

    class Meta:
        model = Risk_Acceptance
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        expiration_delta_days = get_system_setting('risk_acceptance_form_default_days')
        logger.debug('expiration_delta_days: %i', expiration_delta_days)
        if expiration_delta_days > 0:
            expiration_date = timezone.now().date() + relativedelta(days=expiration_delta_days)
            # logger.debug('setting default expiration_date: %s', expiration_date)
            self.fields['expiration_date'].initial = expiration_date
        # self.fields['path'].help_text = 'Existing proof uploaded: %s' % self.instance.filename() if self.instance.filename() else 'None'


class UploadFileForm(forms.ModelForm):

    class Meta:
        model = FileUpload
        fields = ['title', 'file']


ManageFileFormSet = modelformset_factory(FileUpload, extra=3, max_num=10, fields=['title', 'file'], can_delete=True)


class ReplaceRiskAcceptanceForm(forms.ModelForm):
    path = forms.FileField(label="Proof", required=True, widget=forms.widgets.FileInput(attrs={"accept": ".jpg,.png,.pdf"}))

    class Meta:
        model = Risk_Acceptance
        fields = ['path']


class AddFindingsRiskAcceptanceForm(forms.ModelForm):
    accepted_findings = forms.ModelMultipleChoiceField(
        queryset=Finding.objects.all(), required=True,
        widget=forms.widgets.SelectMultiple(attrs={'size': 10}),
        help_text=('Select to add findings.'), label="Add findings as accepted:")

    class Meta:
        model = Risk_Acceptance
        fields = ['accepted_findings']
        # exclude = ('name', 'owner', 'path', 'notes', 'accepted_by', 'expiration_date', 'compensating_control')


class ScanSettingsForm(forms.ModelForm):
    addHelpTxt = "Enter IP addresses in x.x.x.x format separated by commas"
    proHelpTxt = "UDP scans require root privs. See docs for more information"
    msg = 'Addresses must be x.x.x.x format, separated by commas'
    addresses = forms.CharField(
        max_length=2000,
        widget=forms.Textarea,
        help_text=addHelpTxt,
        validators=[
            validators.RegexValidator(
                regex=r'^\s*([0-9]+\.[0-9]+\.[0-9]+\.[0-9]+,*\s*)+\s*$',
                message=msg,
                code='invalid_address')])
    options = (('Weekly', 'Weekly'), ('Monthly', 'Monthly'),
               ('Quarterly', 'Quarterly'))
    frequency = forms.ChoiceField(choices=options)
    prots = [('TCP', 'TCP'), ('UDP', 'UDP')]
    protocol = forms.ChoiceField(
        choices=prots,
        help_text=proHelpTxt)

    class Meta:
        model = ScanSettings
        fields = ['addresses', 'frequency', 'email', 'protocol']


class DeleteIPScanForm(forms.ModelForm):
    id = forms.IntegerField(required=True,
                            widget=forms.widgets.HiddenInput())

    class Meta:
        model = Scan
        exclude = ('scan_settings',
                   'date',
                   'protocol',
                   'status',
                   'baseline')


class VaForm(forms.ModelForm):
    addresses = forms.CharField(max_length=2000, widget=forms.Textarea)
    options = (('Immediately', 'Immediately'),
               ('6AM', '6AM'),
               ('10PM', '10PM'))
    start = forms.ChoiceField(choices=options)

    class Meta:
        model = VA
        fields = ['start', 'addresses']


class CheckForm(forms.ModelForm):
    options = (('Pass', 'Pass'), ('Fail', 'Fail'), ('N/A', 'N/A'))
    session_management = forms.ChoiceField(choices=options)
    encryption_crypto = forms.ChoiceField(choices=options)
    configuration_management = forms.ChoiceField(choices=options)
    authentication = forms.ChoiceField(choices=options)
    authorization_and_access_control = forms.ChoiceField(choices=options)
    data_input_sanitization_validation = forms.ChoiceField(choices=options)
    sensitive_data = forms.ChoiceField(choices=options)
    other = forms.ChoiceField(choices=options)

    def __init__(self, *args, **kwargs):
        findings = kwargs.pop('findings')
        super(CheckForm, self).__init__(*args, **kwargs)
        self.fields['session_issues'].queryset = findings
        self.fields['crypto_issues'].queryset = findings
        self.fields['config_issues'].queryset = findings
        self.fields['auth_issues'].queryset = findings
        self.fields['author_issues'].queryset = findings
        self.fields['data_issues'].queryset = findings
        self.fields['sensitive_issues'].queryset = findings
        self.fields['other_issues'].queryset = findings

    class Meta:
        model = Check_List
        fields = ['session_management', 'session_issues', 'encryption_crypto', 'crypto_issues',
                  'configuration_management', 'config_issues', 'authentication', 'auth_issues',
                  'authorization_and_access_control', 'author_issues',
                  'data_input_sanitization_validation', 'data_issues',
                  'sensitive_data', 'sensitive_issues', 'other', 'other_issues', ]


class EngForm(forms.ModelForm):
    name = forms.CharField(
        max_length=300, required=False,
        help_text="Add a descriptive name to identify this engagement. " +
                  "Without a name the target start date will be used in " +
                  "listings.")
    description = forms.CharField(widget=forms.Textarea(attrs={}),
                                  required=False, help_text="Description of the engagement and details regarding the engagement.")
    product = forms.ModelChoiceField(label='Product',
                                       queryset=Product.objects.all().order_by('name'),
                                       required=True)
    target_start = forms.DateField(widget=forms.TextInput(
        attrs={'class': 'datepicker', 'autocomplete': 'off'}))
    target_end = forms.DateField(widget=forms.TextInput(
        attrs={'class': 'datepicker', 'autocomplete': 'off'}))
    lead = forms.ModelChoiceField(
        queryset=None,
        required=True, label="Testing Lead")
    test_strategy = forms.URLField(required=False, label="Test Strategy URL")

    def __init__(self, *args, **kwargs):
        cicd = False
        product = None
        if 'cicd' in kwargs:
            cicd = kwargs.pop('cicd')

        if 'product' in kwargs:
            product = kwargs.pop('product')

        self.user = None
        if 'user' in kwargs:
            self.user = kwargs.pop('user')

        super(EngForm, self).__init__(*args, **kwargs)

        if product:
            self.fields['preset'] = forms.ModelChoiceField(help_text="Settings and notes for performing this engagement.", required=False, queryset=Engagement_Presets.objects.filter(product=product))
            staff_users = [user.id for user in User.objects.all() if user_is_authorized(user, 'staff', product)]
            self.fields['lead'].queryset = User.objects.filter(id__in=staff_users)
        else:
            self.fields['lead'].queryset = User.objects.exclude(is_staff=False)

        if self.user is not None and not self.user.is_staff and not self.user.is_superuser:
            self.fields['product'].queryset = Product.objects.all().filter(authorized_users__in=[self.user])

        # Don't show CICD fields on a interactive engagement
        if cicd is False:
            del self.fields['build_id']
            del self.fields['commit_hash']
            del self.fields['branch_tag']
            del self.fields['build_server']
            del self.fields['source_code_management_server']
            # del self.fields['source_code_management_uri']
            del self.fields['orchestration_engine']
        else:
            del self.fields['test_strategy']
            del self.fields['status']

    def is_valid(self):
        valid = super(EngForm, self).is_valid()

        # we're done now if not valid
        if not valid:
            return valid
        if self.cleaned_data['target_start'] > self.cleaned_data['target_end']:
            self.add_error('target_start', 'Your target start date exceeds your target end date')
            self.add_error('target_end', 'Your target start date exceeds your target end date')
            return False
        return True

    class Meta:
        model = Engagement
        exclude = ('first_contacted', 'eng_type', 'real_start',
                   'real_end', 'requester', 'reason', 'updated', 'report_type',
                   'product', 'threat_model', 'api_test', 'pen_test', 'check_list', 'engagement_type')


class DeleteEngagementForm(forms.ModelForm):
    id = forms.IntegerField(required=True,
                            widget=forms.widgets.HiddenInput())

    class Meta:
        model = Engagement
        exclude = ['name', 'version', 'eng_type', 'first_contacted', 'target_start',
                   'target_end', 'lead', 'requester', 'reason', 'report_type',
                   'product', 'test_strategy', 'threat_model', 'api_test', 'pen_test',
                   'check_list', 'status', 'description', 'engagement_type', 'build_id',
                   'commit_hash', 'branch_tag', 'build_server', 'source_code_management_server',
                   'source_code_management_uri', 'orchestration_engine', 'preset', 'tracker']


class TestForm(forms.ModelForm):
    title = forms.CharField(max_length=255, required=False)
    description = forms.CharField(widget=forms.Textarea(attrs={'rows': '3'}), required=False)
    test_type = forms.ModelChoiceField(queryset=Test_Type.objects.all().order_by('name'))
    environment = forms.ModelChoiceField(
        queryset=Development_Environment.objects.all().order_by('name'))
    # credential = forms.ModelChoiceField(Cred_User.objects.all(), required=False)
    target_start = forms.DateTimeField(widget=forms.TextInput(
        attrs={'class': 'datepicker', 'autocomplete': 'off'}))
    target_end = forms.DateTimeField(widget=forms.TextInput(
        attrs={'class': 'datepicker', 'autocomplete': 'off'}))

    lead = forms.ModelChoiceField(
        queryset=None,
        required=False, label="Testing Lead")

    def __init__(self, *args, **kwargs):
        obj = None

        if 'engagement' in kwargs:
            obj = kwargs.pop('engagement')

        if 'instance' in kwargs:
            obj = kwargs.get('instance')

        super(TestForm, self).__init__(*args, **kwargs)

        if obj:
            staff_users = [user.id for user in User.objects.all() if user_is_authorized(user, 'staff', obj)]
        else:
            staff_users = [user.id for user in User.objects.exclude(is_staff=False)]
        self.fields['lead'].queryset = User.objects.filter(id__in=staff_users)

    class Meta:
        model = Test
        fields = ['title', 'test_type', 'target_start', 'target_end', 'description',
                  'environment', 'percent_complete', 'tags', 'lead', 'version']


class DeleteTestForm(forms.ModelForm):
    id = forms.IntegerField(required=True,
                            widget=forms.widgets.HiddenInput())

    class Meta:
        model = Test
        exclude = ('test_type',
                   'environment',
                   'target_start',
                   'target_end',
                   'engagement',
                   'percent_complete',
                   'description',
                   'lead')


class AddFindingForm(forms.ModelForm):
    title = forms.CharField(max_length=1000)
    date = forms.DateField(required=True,
                           widget=forms.TextInput(attrs={'class': 'datepicker', 'autocomplete': 'off'}))
    cwe = forms.IntegerField(required=False)
    cve = forms.CharField(max_length=28, required=False)
    cvssv3 = forms.CharField(max_length=117, required=False, widget=forms.TextInput(attrs={'class': 'cvsscalculator', 'data-toggle': 'dropdown', 'aria-haspopup': 'true', 'aria-expanded': 'false'}))
    description = forms.CharField(widget=forms.Textarea)
    severity = forms.ChoiceField(
        choices=SEVERITY_CHOICES,
        error_messages={
            'required': 'Select valid choice: In Progress, On Hold, Completed',
            'invalid_choice': 'Select valid choice: Critical,High,Medium,Low'})
    mitigation = forms.CharField(widget=forms.Textarea)
    impact = forms.CharField(widget=forms.Textarea)
    request = forms.CharField(widget=forms.Textarea, required=False)
    response = forms.CharField(widget=forms.Textarea, required=False)
    endpoints = forms.ModelMultipleChoiceField(Endpoint.objects, required=False, label='Systems / Endpoints',
                                               widget=MultipleSelectWithPopPlusMinus(attrs={'size': '11'}))
    references = forms.CharField(widget=forms.Textarea, required=False)
    is_template = forms.BooleanField(label="Create Template?", required=False,
                                     help_text="A new finding template will be created from this finding.")

    # the only reliable way without hacking internal fields to get predicatble ordering is to make it explicit
    field_order = ('title', 'date', 'cwe', 'cve', 'severity', 'description', 'mitigation', 'impact', 'request', 'response', 'steps_to_reproduce',
                   'severity_justification', 'endpoints', 'references', 'is_template', 'active', 'verified', 'false_p', 'duplicate', 'out_of_scope',
                   'risk_accepted', 'under_defect_review')

    def __init__(self, *args, **kwargs):
        req_resp = kwargs.pop('req_resp')
        super(AddFindingForm, self).__init__(*args, **kwargs)
        if req_resp:
            self.fields['request'].initial = req_resp[0]
            self.fields['response'].initial = req_resp[1]

    def clean(self):
        # self.fields['endpoints'].queryset = Endpoint.objects.all()
        cleaned_data = super(AddFindingForm, self).clean()
        if ((cleaned_data['active'] or cleaned_data['verified']) and cleaned_data['duplicate']):
            raise forms.ValidationError('Duplicate findings cannot be'
                                        ' verified or active')
        if cleaned_data['false_p'] and cleaned_data['verified']:
            raise forms.ValidationError('False positive findings cannot '
                                        'be verified.')
        if cleaned_data['active'] and 'risk_accepted' in cleaned_data and cleaned_data['risk_accepted']:
            raise forms.ValidationError('Active findings cannot '
                                        'be risk accepted.')

        return cleaned_data

    class Meta:
        model = Finding
        order = ('title', 'severity', 'endpoints', 'description', 'impact')
        exclude = ('reporter', 'url', 'numerical_severity', 'endpoint', 'images', 'under_review', 'reviewers',
                   'review_requested_by', 'is_Mitigated', 'jira_creation', 'jira_change', 'endpoint_status', 'sla_start_date')


class AdHocFindingForm(forms.ModelForm):
    title = forms.CharField(max_length=1000)
    date = forms.DateField(required=True,
                           widget=forms.TextInput(attrs={'class': 'datepicker', 'autocomplete': 'off'}))
    cwe = forms.IntegerField(required=False)
    cve = forms.CharField(max_length=28, required=False)
    cvssv3 = forms.CharField(max_length=117, required=False, widget=forms.TextInput(attrs={'class': 'cvsscalculator', 'data-toggle': 'dropdown', 'aria-haspopup': 'true', 'aria-expanded': 'false'}))
    description = forms.CharField(widget=forms.Textarea)
    severity = forms.ChoiceField(
        choices=SEVERITY_CHOICES,
        error_messages={
            'required': 'Select valid choice: In Progress, On Hold, Completed',
            'invalid_choice': 'Select valid choice: Critical,High,Medium,Low'})
    mitigation = forms.CharField(widget=forms.Textarea)
    impact = forms.CharField(widget=forms.Textarea)
    request = forms.CharField(widget=forms.Textarea, required=False)
    response = forms.CharField(widget=forms.Textarea, required=False)
    endpoints = forms.ModelMultipleChoiceField(Endpoint.objects, required=False, label='Systems / Endpoints',
                                               widget=MultipleSelectWithPopPlusMinus(attrs={'size': '11'}))
    references = forms.CharField(widget=forms.Textarea, required=False)
    is_template = forms.BooleanField(label="Create Template?", required=False,
                                     help_text="A new finding template will be created from this finding.")

    # the onyl reliable way without hacking internal fields to get predicatble ordering is to make it explicit
    field_order = ('title', 'date', 'cwe', 'cve', 'severity', 'description', 'mitigation', 'impact', 'request', 'response', 'steps_to_reproduce',
                   'severity_justification', 'endpoints', 'references', 'is_template', 'active', 'verified', 'false_p', 'duplicate', 'out_of_scope',
                   'risk_accepted', 'under_defect_review', 'sla_start_date')

    def __init__(self, *args, **kwargs):
        req_resp = kwargs.pop('req_resp')
        super(AdHocFindingForm, self).__init__(*args, **kwargs)
        if req_resp:
            self.fields['request'].initial = req_resp[0]
            self.fields['response'].initial = req_resp[1]

    def clean(self):
        # self.fields['endpoints'].queryset = Endpoint.objects.all()
        cleaned_data = super(AdHocFindingForm, self).clean()
        if ((cleaned_data['active'] or cleaned_data['verified']) and cleaned_data['duplicate']):
            raise forms.ValidationError('Duplicate findings cannot be'
                                        ' verified or active')
        if cleaned_data['false_p'] and cleaned_data['verified']:
            raise forms.ValidationError('False positive findings cannot '
                                        'be verified.')
        return cleaned_data

    class Meta:
        model = Finding
        exclude = ('reporter', 'url', 'numerical_severity', 'endpoint', 'images', 'under_review', 'reviewers',
                   'review_requested_by', 'is_Mitigated', 'jira_creation', 'jira_change', 'endpoint_status', 'sla_start_date')


class PromoteFindingForm(forms.ModelForm):
    title = forms.CharField(max_length=1000)
    date = forms.DateField(required=True,
                           widget=forms.TextInput(attrs={'class': 'datepicker', 'autocomplete': 'off'}))
    cwe = forms.IntegerField(required=False)
    cve = forms.CharField(max_length=28, required=False)
    cvssv3 = forms.CharField(max_length=117, required=False, widget=forms.TextInput(attrs={'class': 'cvsscalculator', 'data-toggle': 'dropdown', 'aria-haspopup': 'true', 'aria-expanded': 'false'}))
    description = forms.CharField(widget=forms.Textarea)
    severity = forms.ChoiceField(
        choices=SEVERITY_CHOICES,
        error_messages={
            'required': 'Select valid choice: In Progress, On Hold, Completed',
            'invalid_choice': 'Select valid choice: Critical,High,Medium,Low'})
    mitigation = forms.CharField(widget=forms.Textarea)
    impact = forms.CharField(widget=forms.Textarea)
    endpoints = forms.ModelMultipleChoiceField(Endpoint.objects, required=False, label='Systems / Endpoints',
                                               widget=MultipleSelectWithPopPlusMinus(attrs={'size': '11'}))
    references = forms.CharField(widget=forms.Textarea, required=False)

    class Meta:
        model = Finding
        order = ('title', 'severity', 'endpoints', 'description', 'impact')
        exclude = ('reporter', 'url', 'numerical_severity', 'endpoint', 'active', 'false_p', 'verified', 'is_template', 'endpoint_status'
                   'duplicate', 'out_of_scope', 'images', 'under_review', 'reviewers', 'review_requested_by', 'is_Mitigated', 'jira_creation', 'jira_change')


class FindingForm(forms.ModelForm):
    title = forms.CharField(max_length=1000)
    date = forms.DateField(required=True,
                           widget=forms.TextInput(attrs={'class': 'datepicker', 'autocomplete': 'off'}))
    cwe = forms.IntegerField(required=False)
    cve = forms.CharField(max_length=28, required=False, strip=False)
    cvssv3 = forms.CharField(max_length=117, required=False, widget=forms.TextInput(attrs={'class': 'cvsscalculator', 'data-toggle': 'dropdown', 'aria-haspopup': 'true', 'aria-expanded': 'false'}))
    description = forms.CharField(widget=forms.Textarea)
    severity = forms.ChoiceField(
        choices=SEVERITY_CHOICES,
        error_messages={
            'required': 'Select valid choice: In Progress, On Hold, Completed',
            'invalid_choice': 'Select valid choice: Critical,High,Medium,Low'})
    mitigation = forms.CharField(widget=forms.Textarea)
    impact = forms.CharField(widget=forms.Textarea)
    request = forms.CharField(widget=forms.Textarea, required=False)
    response = forms.CharField(widget=forms.Textarea, required=False)
    endpoints = forms.ModelMultipleChoiceField(Endpoint.objects, required=False, label='Systems / Endpoints',
                                               widget=MultipleSelectWithPopPlusMinus(attrs={'size': '11'}))
    references = forms.CharField(widget=forms.Textarea, required=False)

    is_template = forms.BooleanField(label="Create Template?", required=False,
                                     help_text="A new finding template will be created from this finding.")

    # the onyl reliable way without hacking internal fields to get predicatble ordering is to make it explicit
    field_order = ('title', 'date', 'sla_start_date', 'cwe', 'cve', 'severity', 'description', 'mitigation', 'impact', 'request', 'response', 'steps_to_reproduce',
                   'severity_justification', 'endpoints', 'references', 'is_template', 'active', 'verified', 'false_p', 'duplicate', 'out_of_scope',
                   'risk_accepted', 'under_defect_review')

    def __init__(self, *args, **kwargs):
        template = kwargs.pop('template')

        req_resp = None
        if 'req_resp' in kwargs:
            req_resp = kwargs.pop('req_resp')

        super(FindingForm, self).__init__(*args, **kwargs)

        # do not show checkbox if finding is not accepted and simple risk acceptance is disabled
        # if checked, always show to allow unaccept also with full risk acceptance enabled
        if not self.instance.risk_accepted and not self.instance.test.engagement.product.enable_simple_risk_acceptance:
            del self.fields['risk_accepted']
        else:
            if self.instance.risk_accepted:
                self.fields['risk_accepted'].help_text = "Uncheck to unaccept the risk. Use full risk acceptance from the dropdown menu if you need advanced settings such as an expiry date."
            elif self.instance.test.engagement.product.enable_simple_risk_acceptance:
                self.fields['risk_accepted'].help_text = "Check to accept the risk. Use full risk acceptance from the dropdown menu if you need advanced settings such as an expiry date."

        # self.fields['tags'].widget.choices = t
        if req_resp:
            self.fields['request'].initial = req_resp[0]
            self.fields['response'].initial = req_resp[1]

        if self.instance.duplicate:
            self.fields['duplicate'].help_text = "Original finding that is being duplicated here (readonly). Use view finding page to manage duplicate relationships. Unchecking duplicate here will reset this findings duplicate status, but will trigger deduplication logic."
        else:
            self.fields['duplicate'].help_text = "You can mark findings as duplicate only from the view finding page."

        self.fields['sla_start_date'].disabled = True

    def clean(self):
        cleaned_data = super(FindingForm, self).clean()

        cleaned_data['cve'] = None if cleaned_data['cve'] == '' else cleaned_data['cve']
        if (cleaned_data['active'] or cleaned_data['verified']) and cleaned_data['duplicate']:
            raise forms.ValidationError('Duplicate findings cannot be'
                                        ' verified or active')
        if cleaned_data['false_p'] and cleaned_data['verified']:
            raise forms.ValidationError('False positive findings cannot '
                                        'be verified.')
        if cleaned_data['active'] and 'risk_accepted' in cleaned_data and cleaned_data['risk_accepted']:
            raise forms.ValidationError('Active findings cannot '
                                        'be risk accepted.')

        return cleaned_data

    class Meta:
        model = Finding
        exclude = ('reporter', 'url', 'numerical_severity', 'endpoint', 'images', 'under_review', 'reviewers',
                   'review_requested_by', 'is_Mitigated', 'jira_creation', 'jira_change', 'sonarqube_issue', 'endpoint_status')


class StubFindingForm(forms.ModelForm):
    title = forms.CharField(required=True, max_length=1000)

    class Meta:
        model = Stub_Finding
        order = ('title',)
        exclude = (
            'date', 'description', 'severity', 'reporter', 'test', 'is_Mitigated')

    def clean(self):
        cleaned_data = super(StubFindingForm, self).clean()
        if 'title' in cleaned_data:
            if len(cleaned_data['title']) <= 0:
                raise forms.ValidationError("The title is required.")
        else:
            raise forms.ValidationError("The title is required.")

        return cleaned_data


class ApplyFindingTemplateForm(forms.Form):

    title = forms.CharField(max_length=1000, required=True)

    cwe = forms.IntegerField(label="CWE", required=False)
    cve = forms.CharField(label="CVE", max_length=28, required=False)
    cvssv3 = forms.CharField(label="CVSSv3", max_length=117, required=False, widget=forms.TextInput(attrs={'class': 'btn btn-secondary dropdown-toggle', 'data-toggle': 'dropdown', 'aria-haspopup': 'true', 'aria-expanded': 'false'}))

    severity = forms.ChoiceField(required=False, choices=SEVERITY_CHOICES, error_messages={'required': 'Select valid choice: In Progress, On Hold, Completed', 'invalid_choice': 'Select valid choice: Critical,High,Medium,Low'})

    description = forms.CharField(widget=forms.Textarea)
    mitigation = forms.CharField(widget=forms.Textarea)
    impact = forms.CharField(widget=forms.Textarea)
    references = forms.CharField(widget=forms.Textarea, required=False)

    tags = TagField(required=False, help_text="Add tags that help describe this finding template. Choose from the list or add new tags. Press Enter key to add.", initial=Finding.tags.tag_model.objects.all().order_by('name'))

    def __init__(self, template=None, *args, **kwargs):
        super(ApplyFindingTemplateForm, self).__init__(*args, **kwargs)
        self.fields['tags'].autocomplete_tags = Finding.tags.tag_model.objects.all().order_by('name')
        self.template = template

    def clean(self):
        cleaned_data = super(ApplyFindingTemplateForm, self).clean()

        if 'title' in cleaned_data:
            if len(cleaned_data['title']) <= 0:
                raise forms.ValidationError("The title is required.")
        else:
            raise forms.ValidationError("The title is required.")

        return cleaned_data

    class Meta:
        fields = ['title', 'cwe', 'cve', 'cvssv3', 'severity', 'description', 'mitigation', 'impact', 'references', 'tags']
        order = ('title', 'cwe', 'cve', 'cvssv3', 'severity', 'description', 'impact', 'is_Mitigated')


class FindingTemplateForm(forms.ModelForm):
    apply_to_findings = forms.BooleanField(required=False, help_text="Apply template to all findings that match this CWE. (Update will overwrite mitigation, impact and references for any active, verified findings.)")
    title = forms.CharField(max_length=1000, required=True)

    cwe = forms.IntegerField(label="CWE", required=False)
    cve = forms.CharField(label="CVE", max_length=28, required=False)
    cvssv3 = forms.CharField(max_length=117, required=False, widget=forms.TextInput(attrs={'class': 'btn btn-secondary dropdown-toggle', 'data-toggle': 'dropdown', 'aria-haspopup': 'true', 'aria-expanded': 'false'}))
    severity = forms.ChoiceField(
        required=False,
        choices=SEVERITY_CHOICES,
        error_messages={
            'required': 'Select valid choice: In Progress, On Hold, Completed',
            'invalid_choice': 'Select valid choice: Critical,High,Medium,Low'})

    field_order = ['title', 'cwe', 'cve', 'cvssv3', 'severity', 'description', 'mitigation', 'impact', 'references', 'tags', 'template_match', 'template_match_cwe', 'template_match_title', 'apply_to_findings']

    def __init__(self, *args, **kwargs):
        super(FindingTemplateForm, self).__init__(*args, **kwargs)
        self.fields['tags'].autocomplete_tags = Finding.tags.tag_model.objects.all().order_by('name')

    class Meta:
        model = Finding_Template
        order = ('title', 'cwe', 'cve', 'cvssv3', 'severity', 'description', 'impact')
        exclude = ('numerical_severity', 'is_Mitigated', 'last_used', 'endpoint_status')


class DeleteFindingTemplateForm(forms.ModelForm):
    id = forms.IntegerField(required=True,
                            widget=forms.widgets.HiddenInput())

    class Meta:
        model = Finding_Template
        fields = ('id',)


class FindingBulkUpdateForm(forms.ModelForm):
    status = forms.BooleanField(required=False)
    risk_acceptance = forms.BooleanField(required=False)
    risk_accept = forms.BooleanField(required=False)
    risk_unaccept = forms.BooleanField(required=False)

    push_to_jira = forms.BooleanField(required=False)
    # unlink_from_jira = forms.BooleanField(required=False)
    push_to_github = forms.BooleanField(required=False)
    tags = TagField(required=False, autocomplete_tags=Finding.tags.tag_model.objects.all().order_by('name'))

    def __init__(self, *args, **kwargs):
        super(FindingBulkUpdateForm, self).__init__(*args, **kwargs)
        self.fields['severity'].required = False

    def clean(self):
        cleaned_data = super(FindingBulkUpdateForm, self).clean()

        if (cleaned_data['active'] or cleaned_data['verified']) and cleaned_data['duplicate']:
            raise forms.ValidationError('Duplicate findings cannot be'
                                        ' verified or active')
        if cleaned_data['false_p'] and cleaned_data['verified']:
            raise forms.ValidationError('False positive findings cannot '
                                        'be verified.')
        return cleaned_data

    class Meta:
        model = Finding
        fields = ('severity', 'active', 'verified', 'false_p', 'duplicate', 'out_of_scope', 'is_Mitigated')


class EditEndpointForm(forms.ModelForm):

    class Meta:
        model = Endpoint
        exclude = ['product']

    def __init__(self, *args, **kwargs):
        self.product = None
        self.endpoint_instance = None
        super(EditEndpointForm, self).__init__(*args, **kwargs)
        if 'instance' in kwargs:
            self.endpoint_instance = kwargs.pop('instance')
            self.product = self.endpoint_instance.product

    def clean(self):
        from django.core.validators import URLValidator, validate_ipv46_address

        port_re = "(:[0-9]{1,5}|[1-5][0-9]{4}|6[0-4][0-9]{3}|65[0-4][0-9]{2}|655[0-2][0-9]|6553[0-5])"
        cleaned_data = super(EditEndpointForm, self).clean()

        if 'host' in cleaned_data:
            host = cleaned_data['host']
        else:
            raise forms.ValidationError('Please enter a valid URL or IP address.',
                                        code='invalid')

        protocol = cleaned_data['protocol']
        path = cleaned_data['path']
        query = cleaned_data['query']
        fragment = cleaned_data['fragment']

        if protocol and path:
            endpoint = urlunsplit((protocol, host, path, query, fragment))
        else:
            endpoint = host

        try:
            url_validator = URLValidator()
            url_validator(endpoint)
        except forms.ValidationError:
            try:
                # do we have a port number?
                regex = re.compile(port_re)
                host = endpoint
                if regex.findall(endpoint):
                    for g in regex.findall(endpoint):
                        host = re.sub(port_re, '', host)
                validate_ipv46_address(host)
            except forms.ValidationError:
                try:
                    validate_hostname = RegexValidator(regex=r'[a-zA-Z0-9-_]*\.[a-zA-Z]{2,6}')
                    # do we have a port number?
                    regex = re.compile(port_re)
                    host = endpoint
                    if regex.findall(endpoint):
                        for g in regex.findall(endpoint):
                            host = re.sub(port_re, '', host)
                    validate_hostname(host)
                except:
                    raise forms.ValidationError(
                        'It does not appear as though this endpoint is a valid URL or IP address.',
                        code='invalid')

        endpoint = Endpoint.objects.filter(protocol=protocol,
                                           host=host,
                                           path=path,
                                           query=query,
                                           fragment=fragment,
                                           product=self.product)
        if endpoint.count() > 0 and not self.instance:
            raise forms.ValidationError(
                'It appears as though an endpoint with this data already exists for this product.',
                code='invalid')

        return cleaned_data


class AddEndpointForm(forms.Form):
    endpoint = forms.CharField(max_length=5000, required=True, label="Endpoint(s)",
                               help_text="The IP address, host name or full URL. You may enter one endpoint per line. "
                                         "Each must be valid.",
                               widget=forms.widgets.Textarea(attrs={'rows': '15', 'cols': '400'}))
    product = forms.CharField(required=True,
                              widget=forms.widgets.HiddenInput(), help_text="The product this endpoint should be "
                                                                            "associated with.")
    tags = TagField(required=False,
                    help_text="Add tags that help describe this endpoint.  "
                              "Choose from the list or add new tags. Press Enter key to add.")

    def __init__(self, *args, **kwargs):
        product = None
        if 'product' in kwargs:
            product = kwargs.pop('product')
        super(AddEndpointForm, self).__init__(*args, **kwargs)
        if product is None:
            self.fields['product'] = forms.ModelChoiceField(queryset=Product.objects.all())
        else:
            self.fields['product'].initial = product.id

        self.product = product
        self.endpoints_to_process = []

    def save(self):
        processed_endpoints = []
        for e in self.endpoints_to_process:
            endpoint, created = Endpoint.objects.get_or_create(protocol=e[0],
                                                               host=e[1],
                                                               path=e[2],
                                                               query=e[3],
                                                               fragment=e[4],
                                                               product=self.product)
            processed_endpoints.append(endpoint)
        return processed_endpoints

    def clean(self):
        from django.core.validators import URLValidator, validate_ipv46_address

        port_re = "(:[0-9]{1,5}|[1-5][0-9]{4}|6[0-4][0-9]{3}|65[0-4][0-9]{2}|655[0-2][0-9]|6553[0-5])"
        cleaned_data = super(AddEndpointForm, self).clean()

        if 'endpoint' in cleaned_data and 'product' in cleaned_data:
            endpoint = cleaned_data['endpoint']
            product = cleaned_data['product']
            if isinstance(product, Product):
                self.product = product
            else:
                self.product = Product.objects.get(id=int(product))
        else:
            raise forms.ValidationError('Please enter a valid URL or IP address.',
                                        code='invalid')

        endpoints = endpoint.split()
        count = 0
        error = False
        for endpoint in endpoints:
            try:
                url_validator = URLValidator()
                url_validator(endpoint)
                protocol, host, path, query, fragment = urlsplit(endpoint)
                self.endpoints_to_process.append([protocol, host, path, query, fragment])
            except forms.ValidationError:
                try:
                    # do we have a port number?
                    host = endpoint
                    regex = re.compile(port_re)
                    if regex.findall(endpoint):
                        for g in regex.findall(endpoint):
                            host = re.sub(port_re, '', host)
                    validate_ipv46_address(host)
                    protocol, host, path, query, fragment = ("", endpoint, "", "", "")
                    self.endpoints_to_process.append([protocol, host, path, query, fragment])
                except forms.ValidationError:
                    try:
                        regex = re.compile(
                            r'^(?:(?:[A-Z0-9](?:[A-Z0-9-_]{0,61}[A-Z0-9])?\.)+(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}(?<!-)\.?)|'  # domain...
                            r'localhost|'  # localhost...
                            r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}|'  # ...or ipv4
                            r'\[?[A-F0-9]*:[A-F0-9:]+\]?)'  # ...or ipv6
                            r'(?::\d+)?'  # optional port
                            r'(?:/?|[/?]\S+)$', re.IGNORECASE)
                        validate_hostname = RegexValidator(regex=regex)
                        validate_hostname(host)
                        protocol, host, path, query, fragment = (None, host, None, None, None)
                        if "/" in host or "?" in host or "#" in host:
                            # add a fake protocol just to join, wont use in update to database
                            host_with_protocol = "http://" + host
                            p, host, path, query, fragment = urlsplit(host_with_protocol)
                        self.endpoints_to_process.append([protocol, host, path, query, fragment])
                    except forms.ValidationError:
                        raise forms.ValidationError(
                            'Please check items entered, one or more do not appear to be a valid URL or IP address.',
                            code='invalid')

        return cleaned_data


class DeleteEndpointForm(forms.ModelForm):
    id = forms.IntegerField(required=True,
                            widget=forms.widgets.HiddenInput())

    class Meta:
        model = Endpoint
        exclude = ('protocol',
                   'fqdn',
                   'port',
                   'host',
                   'path',
                   'query',
                   'fragment',
                   'product')


class NoteForm(forms.ModelForm):
    entry = forms.CharField(max_length=2400, widget=forms.Textarea(attrs={'rows': 4, 'cols': 15}),
                            label='Notes:')

    class Meta:
        model = Notes
        fields = ['entry', 'private']


class TypedNoteForm(NoteForm):

    def __init__(self, *args, **kwargs):
        queryset = kwargs.pop('available_note_types')
        super(TypedNoteForm, self).__init__(*args, **kwargs)
        self.fields['note_type'] = forms.ModelChoiceField(queryset=queryset, label='Note Type', required=True)

    class Meta():
        model = Notes
        fields = ['note_type', 'entry', 'private']


class DeleteNoteForm(forms.ModelForm):
    id = forms.IntegerField(required=True,
                            widget=forms.widgets.HiddenInput())

    class Meta:
        model = Notes
        fields = ('id',)


class CloseFindingForm(forms.ModelForm):
    entry = forms.CharField(
        required=True, max_length=2400,
        widget=forms.Textarea, label='Notes:',
        error_messages={'required': ('The reason for closing a finding is '
                                     'required, please use the text area '
                                     'below to provide documentation.')})

    def __init__(self, *args, **kwargs):
        queryset = kwargs.pop('missing_note_types')
        super(CloseFindingForm, self).__init__(*args, **kwargs)
        if len(queryset) == 0:
            self.fields['note_type'].widget = forms.HiddenInput()
        else:
            self.fields['note_type'] = forms.ModelChoiceField(queryset=queryset, label='Note Type', required=True)

    class Meta:
        model = Notes
        fields = ['note_type', 'entry']


class DefectFindingForm(forms.ModelForm):
    CLOSE_CHOICES = (("Close Finding", "Close Finding"), ("Not Fixed", "Not Fixed"))
    defect_choice = forms.ChoiceField(required=True, choices=CLOSE_CHOICES)

    entry = forms.CharField(
        required=True, max_length=2400,
        widget=forms.Textarea, label='Notes:',
        error_messages={'required': ('The reason for closing a finding is '
                                     'required, please use the text area '
                                     'below to provide documentation.')})

    class Meta:
        model = Notes
        fields = ['entry']


class ClearFindingReviewForm(forms.ModelForm):
    entry = forms.CharField(
        required=True, max_length=2400,
        help_text='Please provide a message.',
        widget=forms.Textarea, label='Notes:',
        error_messages={'required': ('The reason for clearing a review is '
                                     'required, please use the text area '
                                     'below to provide documentation.')})

    class Meta:
        model = Finding
        fields = ['active', 'verified', 'false_p', 'out_of_scope', 'duplicate']


class ReviewFindingForm(forms.Form):
    reviewers = forms.ModelMultipleChoiceField(queryset=Dojo_User.objects.filter(is_staff=True, is_active=True),
                                               help_text="Select all users who can review Finding.")
    entry = forms.CharField(
        required=True, max_length=2400,
        help_text='Please provide a message for reviewers.',
        widget=forms.Textarea, label='Notes:',
        error_messages={'required': ('The reason for requesting a review is '
                                     'required, please use the text area '
                                     'below to provide documentation.')})

    class Meta:
        fields = ['reviewers', 'entry']


class WeeklyMetricsForm(forms.Form):
    dates = forms.ChoiceField()

    def __init__(self, *args, **kwargs):
        super(WeeklyMetricsForm, self).__init__(*args, **kwargs)
        wmf_options = []

        for i in range(6):
            # Weeks start on Monday
            curr = datetime.now() - relativedelta(weeks=i)
            start_of_period = curr - relativedelta(weeks=1, weekday=0,
                                                   hour=0, minute=0, second=0)
            end_of_period = curr + relativedelta(weeks=0, weekday=0,
                                                 hour=0, minute=0, second=0)

            wmf_options.append((end_of_period.strftime("%b %d %Y %H %M %S %Z"),
                                start_of_period.strftime("%b %d") +
                                " - " + end_of_period.strftime("%b %d")))

        wmf_options = tuple(wmf_options)

        self.fields['dates'].choices = wmf_options


class SimpleMetricsForm(forms.Form):
    date = forms.DateField(
        label="",
        widget=MonthYearWidget())


class SimpleSearchForm(forms.Form):
    query = forms.CharField(required=False)


class DateRangeMetrics(forms.Form):
    start_date = forms.DateField(required=True, label="To",
                                 widget=forms.TextInput(attrs={'class': 'datepicker', 'autocomplete': 'off'}))
    end_date = forms.DateField(required=True,
                               label="From",
                               widget=forms.TextInput(attrs={'class': 'datepicker', 'autocomplete': 'off'}))


class MetricsFilterForm(forms.Form):
    start_date = forms.DateField(required=False,
                                 label="To",
                                 widget=forms.TextInput(attrs={'class': 'datepicker', 'autocomplete': 'off'}))
    end_date = forms.DateField(required=False,
                               label="From",
                               widget=forms.TextInput(attrs={'class': 'datepicker', 'autocomplete': 'off'}))
    finding_status = forms.MultipleChoiceField(
        required=False,
        widget=forms.CheckboxSelectMultiple,
        choices=FINDING_STATUS,
        label="Status")
    severity = forms.MultipleChoiceField(required=False,
                                         choices=(('Low', 'Low'),
                                                  ('Medium', 'Medium'),
                                                  ('High', 'High'),
                                                  ('Critical', 'Critical')),
                                         help_text=('Hold down "Control", or '
                                                    '"Command" on a Mac, to '
                                                    'select more than one.'))
    exclude_product_types = forms.ModelMultipleChoiceField(
        required=False, queryset=Product_Type.objects.all().order_by('name'))

    # add the ability to exclude the exclude_product_types field
    def __init__(self, *args, **kwargs):
        exclude_product_types = kwargs.get('exclude_product_types', False)
        if 'exclude_product_types' in kwargs:
            del kwargs['exclude_product_types']
        super(MetricsFilterForm, self).__init__(*args, **kwargs)
        if exclude_product_types:
            del self.fields['exclude_product_types']


class DojoUserForm(forms.ModelForm):
    class Meta:
        model = Dojo_User
        exclude = ['password', 'last_login', 'is_superuser', 'groups',
                   'username', 'is_staff', 'is_active', 'date_joined',
                   'user_permissions']


class AddDojoUserForm(forms.ModelForm):
    authorized_products = forms.ModelMultipleChoiceField(
        queryset=Product.objects.all(), required=False,
        help_text='Select the products this user should have access to.')
    authorized_product_types = forms.ModelMultipleChoiceField(
        queryset=Product_Type.objects.all(), required=False,
        help_text='Select the product types this user should have access to.')

    class Meta:
        model = Dojo_User
        fields = ['username', 'first_name', 'last_name', 'email', 'is_active',
                  'is_staff', 'is_superuser']
        exclude = ['password', 'last_login', 'groups',
                   'date_joined', 'user_permissions']


class DeleteUserForm(forms.ModelForm):
    id = forms.IntegerField(required=True,
                            widget=forms.widgets.HiddenInput())

    class Meta:
        model = User
        exclude = ['username', 'first_name', 'last_name', 'email', 'is_active',
                   'is_staff', 'is_superuser', 'password', 'last_login', 'groups',
                   'date_joined', 'user_permissions']


class UserContactInfoForm(forms.ModelForm):
    class Meta:
        model = UserContactInfo
        exclude = ['user', 'slack_user_id']


def get_years():
    now = timezone.now()
    return [(now.year, now.year), (now.year - 1, now.year - 1), (now.year - 2, now.year - 2)]


class ProductTypeCountsForm(forms.Form):
    month = forms.ChoiceField(choices=list(MONTHS.items()), required=True, error_messages={
        'required': '*'})
    year = forms.ChoiceField(choices=get_years, required=True, error_messages={
        'required': '*'})
    product_type = forms.ModelChoiceField(required=True,
                                          queryset=Product_Type.objects.all(),
                                          error_messages={
                                              'required': '*'})

    def __init__(self, *args, **kwargs):
        super(ProductTypeCountsForm, self).__init__(*args, **kwargs)
        if get_current_user() is not None and not get_current_user().is_staff:
            self.fields['product_type'].queryset = Product_Type.objects.filter(
                authorized_users__in=[get_current_user()])


class APIKeyForm(forms.ModelForm):
    id = forms.IntegerField(required=True,
                            widget=forms.widgets.HiddenInput())

    class Meta:
        model = User
        exclude = ['username', 'first_name', 'last_name', 'email', 'is_active',
                   'is_staff', 'is_superuser', 'password', 'last_login', 'groups',
                   'date_joined', 'user_permissions']


class ReportOptionsForm(forms.Form):
    yes_no = (('0', 'No'), ('1', 'Yes'))
    include_finding_notes = forms.ChoiceField(choices=yes_no, label="Finding Notes")
    include_finding_images = forms.ChoiceField(choices=yes_no, label="Finding Images")
    include_executive_summary = forms.ChoiceField(choices=yes_no, label="Executive Summary")
    include_table_of_contents = forms.ChoiceField(choices=yes_no, label="Table of Contents")
    report_type = forms.ChoiceField(choices=(('HTML', 'HTML'), ('AsciiDoc', 'AsciiDoc')))


class CustomReportOptionsForm(forms.Form):
    yes_no = (('0', 'No'), ('1', 'Yes'))
    report_name = forms.CharField(required=False, max_length=100)
    include_finding_notes = forms.ChoiceField(required=False, choices=yes_no)
    include_finding_images = forms.ChoiceField(choices=yes_no, label="Finding Images")
    report_type = forms.ChoiceField(choices=(('HTML', 'HTML'), ('AsciiDoc', 'AsciiDoc')))


class DeleteReportForm(forms.ModelForm):
    id = forms.IntegerField(required=True,
                            widget=forms.widgets.HiddenInput())

    class Meta:
        model = Report
        fields = ('id',)


class DeleteFindingForm(forms.ModelForm):
    id = forms.IntegerField(required=True,
                            widget=forms.widgets.HiddenInput())

    class Meta:
        model = Finding
        fields = ('id',)


class FindingFormID(forms.ModelForm):
    id = forms.IntegerField(required=True,
                            widget=forms.widgets.HiddenInput())

    class Meta:
        model = Finding
        fields = ('id',)


class DeleteStubFindingForm(forms.ModelForm):
    id = forms.IntegerField(required=True,
                            widget=forms.widgets.HiddenInput())

    class Meta:
        model = Stub_Finding
        fields = ('id',)


class AddFindingImageForm(forms.ModelForm):
    class Meta:
        model = FindingImage
        exclude = ['']


FindingImageFormSet = modelformset_factory(FindingImage, extra=3, max_num=10, exclude=[''], can_delete=True)


class GITHUB_IssueForm(forms.ModelForm):

    class Meta:
        model = GITHUB_Issue
        exclude = ['product']


class GITHUBForm(forms.ModelForm):
    api_key = forms.CharField(widget=forms.PasswordInput, required=True)

    class Meta:
        model = GITHUB_Conf
        exclude = ['product']


class DeleteGITHUBConfForm(forms.ModelForm):
    id = forms.IntegerField(required=True,
                            widget=forms.widgets.HiddenInput())

    class Meta:
        model = GITHUB_Conf
        fields = ('id',)


class ExpressGITHUBForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput, required=True)
    issue_key = forms.CharField(required=True, help_text='A valid issue ID is required to gather the necessary information.')

    class Meta:
        model = GITHUB_Conf
        exclude = ['product', 'epic_name_id', 'open_status_key',
                    'close_status_key', 'info_mapping_severity',
                    'low_mapping_severity', 'medium_mapping_severity',
                    'high_mapping_severity', 'critical_mapping_severity', 'finding_text']


class JIRA_IssueForm(forms.ModelForm):

    class Meta:
        model = JIRA_Issue
        exclude = ['product']


class JIRAForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput, required=True)

    def __init__(self, *args, **kwargs):
        super(JIRAForm, self).__init__(*args, **kwargs)
        if self.instance:
            self.fields['password'].required = False

    class Meta:
        model = JIRA_Instance
        exclude = ['']


class ExpressJIRAForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput, required=True)
    issue_key = forms.CharField(required=True, help_text='A valid issue ID is required to gather the necessary information.')

    class Meta:
        model = JIRA_Instance
        exclude = ['product', 'epic_name_id', 'open_status_key',
                    'close_status_key', 'info_mapping_severity',
                    'low_mapping_severity', 'medium_mapping_severity',
                    'high_mapping_severity', 'critical_mapping_severity', 'finding_text']


class Benchmark_Product_SummaryForm(forms.ModelForm):

    class Meta:
        model = Benchmark_Product_Summary
        exclude = ['product', 'current_level', 'benchmark_type', 'asvs_level_1_benchmark', 'asvs_level_1_score', 'asvs_level_2_benchmark', 'asvs_level_2_score', 'asvs_level_3_benchmark', 'asvs_level_3_score']


class DeleteBenchmarkForm(forms.ModelForm):
    id = forms.IntegerField(required=True,
                            widget=forms.widgets.HiddenInput())

    class Meta:
        model = Benchmark_Product_Summary
        exclude = ['product', 'benchmark_type', 'desired_level', 'current_level', 'asvs_level_1_benchmark', 'asvs_level_1_score', 'asvs_level_2_benchmark', 'asvs_level_2_score', 'asvs_level_3_benchmark', 'asvs_level_3_score', 'publish']


# class JIRA_ProjectForm(forms.ModelForm):

#     class Meta:
#         model = JIRA_Project
#         exclude = ['product']


class Sonarqube_ProductForm(forms.ModelForm):

    def __init__(self, *args, **kwargs):
        super(Sonarqube_ProductForm, self).__init__(*args, **kwargs)
        Tool_Type.objects.get_or_create(name='SonarQube')

    sonarqube_tool_config = forms.ModelChoiceField(
        label='SonarQube Configuration',
        queryset=Tool_Configuration.objects.filter(tool_type__name="SonarQube").order_by('name'),
        required=False
    )

    class Meta:
        model = Sonarqube_Product
        exclude = ['product']


class DeleteJIRAInstanceForm(forms.ModelForm):
    id = forms.IntegerField(required=True,
                            widget=forms.widgets.HiddenInput())

    class Meta:
        model = JIRA_Instance
        fields = ('id',)


class ToolTypeForm(forms.ModelForm):
    class Meta:
        model = Tool_Type
        exclude = ['product']


class RegulationForm(forms.ModelForm):
    class Meta:
        model = Regulation
        exclude = ['product']


class LanguagesTypeForm(forms.ModelForm):
    class Meta:
        model = Languages
        exclude = ['product']


class Languages_TypeTypeForm(forms.ModelForm):
    class Meta:
        model = Language_Type
        exclude = ['product']


class App_AnalysisTypeForm(forms.ModelForm):
    class Meta:
        model = App_Analysis
        exclude = ['product']


class ToolConfigForm(forms.ModelForm):
    tool_type = forms.ModelChoiceField(queryset=Tool_Type.objects.all(), label='Tool Type')
    ssh = forms.CharField(widget=forms.Textarea(attrs={}), required=False, label='SSH Key')

    class Meta:
        model = Tool_Configuration
        exclude = ['product']

    def clean(self):
        from django.core.validators import URLValidator
        form_data = self.cleaned_data

        try:
            url_validator = URLValidator(schemes=['ssh', 'http', 'https'])
            url_validator(form_data["url"])
        except forms.ValidationError:
            raise forms.ValidationError(
                'It does not appear as though this endpoint is a valid URL/SSH or IP address.',
                code='invalid')

        return form_data


class DeleteObjectsSettingsForm(forms.ModelForm):
    id = forms.IntegerField(required=True,
                            widget=forms.widgets.HiddenInput())

    class Meta:
        model = Objects_Product
        exclude = ['tool_type']


class DeleteToolProductSettingsForm(forms.ModelForm):
    id = forms.IntegerField(required=True,
                            widget=forms.widgets.HiddenInput())

    class Meta:
        model = Tool_Product_Settings
        exclude = ['tool_type']


class ToolProductSettingsForm(forms.ModelForm):
    tool_configuration = forms.ModelChoiceField(queryset=Tool_Configuration.objects.all(), label='Tool Configuration')

    class Meta:
        model = Tool_Product_Settings
        fields = ['name', 'description', 'url', 'tool_configuration', 'tool_project_id']
        exclude = ['tool_type']
        order = ['name']

    def clean(self):
        from django.core.validators import URLValidator
        form_data = self.cleaned_data

        try:
            url_validator = URLValidator(schemes=['ssh', 'http', 'https'])
            url_validator(form_data["url"])
        except forms.ValidationError:
            raise forms.ValidationError(
                'It does not appear as though this endpoint is a valid URL/SSH or IP address.',
                code='invalid')

        return form_data


class ObjectSettingsForm(forms.ModelForm):

    # tags = forms.CharField(widget=forms.SelectMultiple(choices=[]),
    #                        required=False,
    #                        help_text="Add tags that help describe this object.  "
    #                                  "Choose from the list or add new tags.  Press TAB key to add.")

    class Meta:
        model = Objects_Product
        fields = ['path', 'folder', 'artifact', 'name', 'review_status', 'tags']
        exclude = ['product']

    def __init__(self, *args, **kwargs):
        super(ObjectSettingsForm, self).__init__(*args, **kwargs)

    def clean(self):
        form_data = self.cleaned_data

        return form_data


class CredMappingForm(forms.ModelForm):
    cred_user = forms.ModelChoiceField(queryset=Cred_Mapping.objects.all().select_related('cred_id'), required=False,
                                       label='Select a Credential')

    class Meta:
        model = Cred_Mapping
        fields = ['cred_user']
        exclude = ['product', 'finding', 'engagement', 'test', 'url', 'is_authn_provider']


class CredMappingFormProd(forms.ModelForm):
    class Meta:
        model = Cred_Mapping
        fields = ['cred_id', 'url', 'is_authn_provider']
        exclude = ['product', 'finding', 'engagement', 'test']


class EngagementPresetsForm(forms.ModelForm):

    notes = forms.CharField(widget=forms.Textarea(attrs={}),
                                  required=False, help_text="Description of what needs to be tested or setting up environment for testing")

    scope = forms.CharField(widget=forms.Textarea(attrs={}),
                                  required=False, help_text="Scope of Engagement testing, IP's/Resources/URL's)")

    class Meta:
        model = Engagement_Presets
        exclude = ['product']


class DeleteEngagementPresetsForm(forms.ModelForm):
    id = forms.IntegerField(required=True,
                            widget=forms.widgets.HiddenInput())

    class Meta:
        model = Engagement_Presets
        fields = ['id']


class SystemSettingsForm(forms.ModelForm):

    class Meta:
        model = System_Settings
        exclude = ['product_grade', 'credentials', 'column_widths', 'drive_folder_ID', 'enable_google_sheets']


class BenchmarkForm(forms.ModelForm):

    class Meta:
        model = Benchmark_Product
        exclude = ['product', 'control']


class Benchmark_RequirementForm(forms.ModelForm):

    class Meta:
        model = Benchmark_Requirement
        exclude = ['']


class NotificationsForm(forms.ModelForm):

    class Meta:
        model = Notifications
        exclude = ['']


class ProductNotificationsForm(forms.ModelForm):

    def __init__(self, *args, **kwargs):
        super(ProductNotificationsForm, self).__init__(*args, **kwargs)
        if not self.instance.id:
            self.initial['engagement_added'] = ''
            self.initial['test_added'] = ''
            self.initial['scan_added'] = ''
            self.initial['sla_breach'] = ''
            self.initial['risk_acceptance_expiration'] = ''

    class Meta:
        model = Notifications
        fields = ['engagement_added', 'test_added', 'scan_added', 'sla_breach', 'risk_acceptance_expiration']


class AjaxChoiceField(forms.ChoiceField):
    def valid_value(self, value):
        return True


class RuleForm(forms.ModelForm):

    class Meta:
        model = Rule
        exclude = ['key_product']


class ChildRuleForm(forms.ModelForm):

    class Meta:
        model = Child_Rule
        exclude = ['key_product']


RuleFormSet = modelformset_factory(Child_Rule, extra=2, max_num=10, exclude=[''], can_delete=True)


class DeleteRuleForm(forms.ModelForm):
    id = forms.IntegerField(required=True,
                            widget=forms.widgets.HiddenInput())

    class Meta:
        model = Rule
        fields = ('id',)


class CredUserForm(forms.ModelForm):
    # selenium_script = forms.FileField(widget=forms.widgets.FileInput(
    #    attrs={"accept": ".py"}),
    #    label="Select a Selenium Script", required=False)

    class Meta:
        model = Cred_User
        exclude = ['']
        # fields = ['selenium_script']


class GITHUB_Product_Form(forms.ModelForm):
    git_conf = forms.ModelChoiceField(queryset=GITHUB_Conf.objects.all(), label='GITHUB Configuration', required=False)

    class Meta:
        model = GITHUB_PKey
        exclude = ['product']


class JIRAProjectForm(forms.ModelForm):
    jira_instance = forms.ModelChoiceField(queryset=JIRA_Instance.objects.all(), label='JIRA Instance', required=False)

    prefix = 'jira-project-form'

    class Meta:
        model = JIRA_Project
        exclude = ['product', 'engagement']

    def __init__(self, *args, **kwargs):
        # if the form is shown for an engagement, we set a placeholder text around inherited settings from product
        self.target = kwargs.pop('target', 'product')
        self.product = kwargs.pop('product', None)
        self.engagement = kwargs.pop('engagement', None)
        super().__init__(*args, **kwargs)

        # logger.debug('self.target: %s, self.product: %s, self.instance: %s', self.target, self.product, self.instance)
        if self.target == 'engagement':
            product_name = self.product.name if self.product else self.engagement.product.name if self.engagement.product else ''

            self.fields['project_key'].widget = forms.TextInput(attrs={'placeholder': 'JIRA settings inherited from product ''%s''' % product_name})
            self.fields['project_key'].help_text = 'JIRA settings are inherited from product ''%s'', unless configured differently here.' % product_name
            self.fields['jira_instance'].help_text = 'JIRA settings are inherited from product ''%s'' , unless configured differently here.' % product_name

        # if we don't have an instance, django will insert a blank empty one :-(
        # so we have to check for id to make sure we only trigger this when there is a real instance from db
        if self.instance.id:
            self.fields['jira_instance'].required = True
            self.fields['project_key'].required = True

    def clean(self):
        logger.debug('validating jira project form')
        cleaned_data = super().clean()

        project_key = self.cleaned_data.get('project_key')
        jira_instance = self.cleaned_data.get('jira_instance')

        if project_key and jira_instance:
            return cleaned_data

        if not project_key and not jira_instance:
            return cleaned_data

        raise ValidationError('JIRA Project needs a JIRA Instance and JIRA Project Key, or leave both empty')


class GITHUBFindingForm(forms.Form):
    def __init__(self, *args, **kwargs):
        self.enabled = kwargs.pop('enabled')
        super(GITHUBFindingForm, self).__init__(*args, **kwargs)
        self.fields['push_to_github'] = forms.BooleanField()
        self.fields['push_to_github'].required = False
        self.fields['push_to_github'].help_text = "Checking this will overwrite content of your Github issue, or create one."

    push_to_github = forms.BooleanField(required=False)


class JIRAFindingForm(forms.Form):
    def __init__(self, *args, **kwargs):
        self.push_all = kwargs.pop('push_all', False)
        self.instance = kwargs.pop('instance', None)
        self.jira_project = kwargs.pop('jira_project', None)

        if self.instance is None and self.jira_project is None:
            raise ValueError('either and finding instance or jira_project is needed')

        super(JIRAFindingForm, self).__init__(*args, **kwargs)
        self.fields['push_to_jira'] = forms.BooleanField()
        self.fields['push_to_jira'].required = False
        self.fields['push_to_jira'].help_text = "Checking this will overwrite content of your JIRA issue, or create one."
        self.fields['push_to_jira'].label = "Push to JIRA"
        if self.push_all:
            # This will show the checkbox as checked and greyed out, this way the user is aware
            # that issues will be pushed to JIRA, given their product-level settings.
            self.fields['push_to_jira'].help_text = \
                "Push all issues is enabled on this product. If you do not wish to push all issues" \
                " to JIRA, please disable Push all issues on this product."
            self.fields['push_to_jira'].widget.attrs['checked'] = 'checked'
            self.fields['push_to_jira'].disabled = True

        if self.instance:
            if self.instance.has_jira_issue:
                self.initial['jira_issue'] = self.instance.jira_issue.jira_key
                self.fields['push_to_jira'].widget.attrs['checked'] = 'checked'

        self.fields['jira_issue'].widget = forms.TextInput(attrs={'placeholder': 'Leave empty and check push to jira to create a new JIRA issue'})

    def clean(self):
        import dojo.jira_link.helper as jira_helper
        logger.debug('validating jirafindingform')
        cleaned_data = super(JIRAFindingForm, self).clean()
        jira_issue_key_new = self.cleaned_data.get('jira_issue')
        finding = self.instance
        jira_project = self.jira_project
        if jira_issue_key_new:
            if finding:
                # in theory there can multiple jira instances that have similar projects
                # so checking by only the jira issue key can lead to false positives
                # so we check also the jira internal id of the jira issue
                # if the key and id are equal, it is probably the same jira instance and the same issue
                # the database model is lacking some relations to also include the jira config name or url here
                # and I don't want to change too much now. this should cover most usecases.

                jira_issue_need_to_exist = False
                # changing jira link on finding
                if finding.has_jira_issue and jira_issue_key_new != finding.jira_issue.jira_key:
                    jira_issue_need_to_exist = True

                # adding existing jira issue to finding without jira link
                if not finding.has_jira_issue:
                    jira_issue_need_to_exist = True

            else:
                jira_issue_need_to_exist = True

            if jira_issue_need_to_exist:
                jira_issue_new = jira_helper.jira_get_issue(jira_project, jira_issue_key_new)
                if not jira_issue_new:
                    raise ValidationError('JIRA issue ' + jira_issue_key_new + ' does not exist or cannot be retrieved')

                logger.debug('checking if provided jira issue id already is linked to another finding')
                jira_issues = JIRA_Issue.objects.filter(jira_id=jira_issue_new.id, jira_key=jira_issue_key_new).exclude(engagement__isnull=False)

                if self.instance:
                    # just be sure we exclude the finding that is being edited
                    jira_issues = jira_issues.exclude(finding=finding)

                if len(jira_issues) > 0:
                    raise ValidationError('JIRA issue ' + jira_issue_key_new + ' already linked to ' + reverse('view_finding', args=(jira_issues[0].finding_id,)))

    jira_issue = forms.CharField(required=False, label="Linked JIRA Issue",
                validators=[validators.RegexValidator(
                    regex=r'^[A-Z][A-Z_0-9]+-\d+$',
                    message='JIRA issue key must be in XXXX-nnnn format ([A-Z][A-Z_0-9]+-\\d+)')])
    push_to_jira = forms.BooleanField(required=False, label="Push to JIRA")


class JIRAImportScanForm(forms.Form):
    def __init__(self, *args, **kwargs):
        self.push_all = kwargs.pop('push_all', False)

        super(JIRAImportScanForm, self).__init__(*args, **kwargs)
        if self.push_all:
            # This will show the checkbox as checked and greyed out, this way the user is aware
            # that issues will be pushed to JIRA, given their product-level settings.
            self.fields['push_to_jira'].help_text = \
                "Push all issues is enabled on this product. If you do not wish to push all issues" \
                " to JIRA, please disable Push all issues on this product."
            self.fields['push_to_jira'].widget.attrs['checked'] = 'checked'
            self.fields['push_to_jira'].disabled = True

    push_to_jira = forms.BooleanField(required=False, label="Push to JIRA", help_text="Checking this will create a new jira issue for each new finding.")


class JIRAEngagementForm(forms.Form):
    prefix = 'jira-epic-form'

    def __init__(self, *args, **kwargs):
        self.instance = kwargs.pop('instance', None)

        super(JIRAEngagementForm, self).__init__(*args, **kwargs)

        if self.instance:
            if self.instance.has_jira_issue:
                self.fields['push_to_jira'].widget.attrs['checked'] = 'checked'
                self.fields['push_to_jira'].label = 'Update JIRA Epic'
                self.fields['push_to_jira'].help_text = 'Checking this will update the existing EPIC in JIRA.'

    push_to_jira = forms.BooleanField(required=False, label="Create EPIC", help_text="Checking this will create an EPIC in JIRA for this engagement.")


class GoogleSheetFieldsForm(forms.Form):
    cred_file = forms.FileField(widget=forms.widgets.FileInput(
        attrs={"accept": ".json"}),
        label="Google credentials file",
        required=True,
        allow_empty_file=False,
        help_text="Upload the credentials file downloaded from the Google Developer Console")
    drive_folder_ID = forms.CharField(
        required=True,
        label="Google Drive folder ID",
        help_text="Extract the Drive folder ID from the URL and provide it here")
    email_address = forms.EmailField(
        required=True,
        label="Email Address",
        help_text="Enter the same email Address used to create the Service Account")
    enable_service = forms.BooleanField(
        initial=False,
        required=False,
        help_text='Tick this check box to enable Google Sheets Sync feature')

    def __init__(self, *args, **kwargs):
        self.credentials_required = kwargs.pop('credentials_required')
        options = ((0, 'Hide'), (100, 'Small'), (200, 'Medium'), (400, 'Large'))
        protect = ['reporter', 'url', 'numerical_severity', 'endpoint', 'images', 'under_review', 'reviewers',
                   'review_requested_by', 'is_Mitigated', 'jira_creation', 'jira_change', 'sonarqube_issue', 'is_template']
        self.all_fields = kwargs.pop('all_fields')
        super(GoogleSheetFieldsForm, self).__init__(*args, **kwargs)
        if not self.credentials_required:
            self.fields['cred_file'].required = False
        for i in self.all_fields:
            self.fields[i.name] = forms.ChoiceField(choices=options)
            if i.name == 'id' or i.editable is False or i.many_to_one or i.name in protect:
                self.fields['Protect ' + i.name] = forms.BooleanField(initial=True, required=True, disabled=True)
            else:
                self.fields['Protect ' + i.name] = forms.BooleanField(initial=False, required=False)


class LoginBanner(forms.Form):
    banner_enable = forms.BooleanField(
        label="Enable login banner",
        initial=False,
        required=False,
        help_text='Tick this box to enable a text banner on the login page'
    )

    banner_message = forms.CharField(
        required=False,
        label="Message to display on the login page"
    )

    def clean(self):
        cleaned_data = super().clean()
        return cleaned_data


# ==============================
# Defect Dojo Engaegment Surveys
# ==============================

# List of validator_name:func_name
# Show in admin a multichoice list of validator names
# pass this to form using field_name='validator_name' ?
class QuestionForm(forms.Form):
    ''' Base class for a Question
    '''

    def __init__(self, *args, **kwargs):
        self.helper = FormHelper()
        self.helper.form_method = 'post'

        # If true crispy-forms will render a <form>..</form> tags
        self.helper.form_tag = kwargs.get('form_tag', True)

        if 'form_tag' in kwargs:
            del kwargs['form_tag']

        self.engagement_survey = kwargs.get('engagement_survey')

        self.answered_survey = kwargs.get('answered_survey')
        if not self.answered_survey:
            del kwargs['engagement_survey']
        else:
            del kwargs['answered_survey']

        self.helper.form_class = kwargs.get('form_class', '')

        self.question = kwargs.get('question')

        if not self.question:
            raise ValueError('Need a question to render')

        del kwargs['question']
        super(QuestionForm, self).__init__(*args, **kwargs)


class TextQuestionForm(QuestionForm):
    def __init__(self, *args, **kwargs):
        super(TextQuestionForm, self).__init__(*args, **kwargs)

        # work out initial data

        initial_answer = TextAnswer.objects.filter(
            answered_survey=self.answered_survey,
            question=self.question
        )

        if initial_answer.exists():
            initial_answer = initial_answer[0].answer
        else:
            initial_answer = ''

        self.fields['answer'] = forms.CharField(
            label=self.question.text,
            widget=forms.Textarea(attrs={"rows": 3, "cols": 10}),
            required=not self.question.optional,
            initial=initial_answer,
        )

        answer = self.fields['answer']

    def save(self):
        if not self.is_valid():
            raise forms.ValidationError('form is not valid')

        answer = self.cleaned_data.get('answer')

        if not answer:
            if self.fields['answer'].required:
                raise forms.ValidationError('Required')
            return

        text_answer, created = TextAnswer.objects.get_or_create(
            answered_survey=self.answered_survey,
            question=self.question,
        )

        if created:
            text_answer.answered_survey = self.answered_survey
        text_answer.answer = answer
        text_answer.save()


class ChoiceQuestionForm(QuestionForm):
    def __init__(self, *args, **kwargs):
        super(ChoiceQuestionForm, self).__init__(*args, **kwargs)

        choices = [(c.id, c.label) for c in self.question.choices.all()]

        # initial values

        initial_choices = []
        choice_answer = ChoiceAnswer.objects.filter(
            answered_survey=self.answered_survey,
            question=self.question,
        ).annotate(a=Count('answer')).filter(a__gt=0)

        # we have ChoiceAnswer instance
        if choice_answer:
            choice_answer = choice_answer[0]
            initial_choices = choice_answer.answer.all().values_list('id',
                                                                     flat=True)
            if self.question.multichoice is False:
                initial_choices = initial_choices[0]

        # default classes
        widget = forms.RadioSelect
        field_type = forms.ChoiceField
        inline_type = InlineRadios

        if self.question.multichoice:
            field_type = forms.MultipleChoiceField
            widget = forms.CheckboxSelectMultiple
            inline_type = InlineCheckboxes

        field = field_type(
            label=self.question.text,
            required=not self.question.optional,
            choices=choices,
            initial=initial_choices,
            widget=widget
        )

        self.fields['answer'] = field

        # Render choice buttons inline
        self.helper.layout = Layout(
            inline_type('answer')
        )

    def clean_answer(self):
        real_answer = self.cleaned_data.get('answer')

        # for single choice questions, the selected answer is a single string
        if type(real_answer) is not list:
            real_answer = [real_answer]
        return real_answer

    def save(self):
        if not self.is_valid():
            raise forms.ValidationError('Form is not valid')

        real_answer = self.cleaned_data.get('answer')

        if not real_answer:
            if self.fields['answer'].required:
                raise forms.ValidationError('Required')
            return

        choices = Choice.objects.filter(id__in=real_answer)

        # find ChoiceAnswer and filter in answer !
        choice_answer = ChoiceAnswer.objects.filter(
            answered_survey=self.answered_survey,
            question=self.question,
        )

        # we have ChoiceAnswer instance
        if choice_answer:
            choice_answer = choice_answer[0]

        if not choice_answer:
            # create a ChoiceAnswer
            choice_answer = ChoiceAnswer.objects.create(
                answered_survey=self.answered_survey,
                question=self.question
            )

        # re save out the choices
        choice_answer.answered_survey = self.answered_survey
        choice_answer.answer = choices
        choice_answer.save()


class Add_Questionnaire_Form(forms.ModelForm):
    survey = forms.ModelChoiceField(
        queryset=Engagement_Survey.objects.all(),
        required=True,
        widget=forms.widgets.Select(),
        help_text='Select the Questionnaire to add.')

    class Meta:
        model = Answered_Survey
        exclude = ('responder',
                   'completed',
                   'engagement',
                   'answered_on',
                   'assignee')


class AddGeneralQuestionnaireForm(forms.ModelForm):
    survey = forms.ModelChoiceField(
        queryset=Engagement_Survey.objects.all(),
        required=True,
        widget=forms.widgets.Select(),
        help_text='Select the Questionnaire to add.')
    expiration = forms.DateField(widget=forms.TextInput(
        attrs={'class': 'datepicker', 'autocomplete': 'off'}))

    class Meta:
        model = General_Survey
        exclude = ('num_responses', 'generated')


class Delete_Questionnaire_Form(forms.ModelForm):
    id = forms.IntegerField(required=True,
                            widget=forms.widgets.HiddenInput())

    class Meta:
        model = Answered_Survey
        exclude = ('responder',
                   'completed',
                   'engagement',
                   'answered_on',
                   'survey',
                   'assignee')


class DeleteGeneralQuestionnaireForm(forms.ModelForm):
    id = forms.IntegerField(required=True,
                            widget=forms.widgets.HiddenInput())

    class Meta:
        model = General_Survey
        exclude = ('num_responses',
                   'generated',
                   'expiration',
                   'survey')


class Delete_Eng_Survey_Form(forms.ModelForm):
    id = forms.IntegerField(required=True,
                            widget=forms.widgets.HiddenInput())

    class Meta:
        model = Engagement_Survey
        exclude = ('name',
                   'questions',
                   'description',
                   'active')


class CreateQuestionnaireForm(forms.ModelForm):
    class Meta:
        model = Engagement_Survey
        exclude = ['questions']


class EditQuestionnaireQuestionsForm(forms.ModelForm):
    questions = forms.ModelMultipleChoiceField(
        Question.objects.all(),
        required=True,
        help_text="Select questions to include on this questionnaire.  Field can be used to search available questions.",
        widget=MultipleSelectWithPop(attrs={'size': '11'}))

    class Meta:
        model = Engagement_Survey
        exclude = ['name', 'description', 'active']


class CreateQuestionForm(forms.Form):
    type = forms.ChoiceField(choices=(("---", "-----"), ("text", "Text"), ("choice", "Choice")))
    order = forms.IntegerField(min_value=1, widget=forms.TextInput(attrs={'data-type': 'both'}))
    optional = forms.BooleanField(help_text="If selected, user doesn't have to answer this question",
                                  initial=False,
                                  required=False,
                                  widget=forms.CheckboxInput(attrs={'data-type': 'both'}))
    text = forms.CharField(widget=forms.Textarea(attrs={'data-type': 'text'}),
                           label="Question Text",
                           help_text="The actual question.")


class CreateTextQuestionForm(forms.Form):
    class Meta:
        model = TextQuestion
        exclude = ['order', 'optional']


class MultiWidgetBasic(forms.widgets.MultiWidget):
    def __init__(self, attrs=None):
        widgets = [forms.TextInput(attrs={'data-type': 'choice'}),
                   forms.TextInput(attrs={'data-type': 'choice'}),
                   forms.TextInput(attrs={'data-type': 'choice'}),
                   forms.TextInput(attrs={'data-type': 'choice'}),
                   forms.TextInput(attrs={'data-type': 'choice'}),
                   forms.TextInput(attrs={'data-type': 'choice'})]
        super(MultiWidgetBasic, self).__init__(widgets, attrs)

    def decompress(self, value):
        if value:
            return pickle.loads(value)
        else:
            return [None, None, None, None, None, None]

    def format_output(self, rendered_widgets):
        return '<br/>'.join(rendered_widgets)


class MultiExampleField(forms.fields.MultiValueField):
    widget = MultiWidgetBasic

    def __init__(self, *args, **kwargs):
        list_fields = [forms.fields.CharField(required=True),
                       forms.fields.CharField(required=True),
                       forms.fields.CharField(required=False),
                       forms.fields.CharField(required=False),
                       forms.fields.CharField(required=False),
                       forms.fields.CharField(required=False)]
        super(MultiExampleField, self).__init__(list_fields, *args, **kwargs)

    def compress(self, values):
        return pickle.dumps(values)


class CreateChoiceQuestionForm(forms.Form):
    multichoice = forms.BooleanField(required=False,
                                     initial=False,
                                     widget=forms.CheckboxInput(attrs={'data-type': 'choice'}),
                                     help_text="Can more than one choice can be selected?")

    answer_choices = MultiExampleField(required=False, widget=MultiWidgetBasic(attrs={'data-type': 'choice'}))

    class Meta:
        model = ChoiceQuestion
        exclude = ['order', 'optional', 'choices']


class EditQuestionForm(forms.ModelForm):
    class Meta:
        model = Question
        exclude = []


class EditTextQuestionForm(EditQuestionForm):
    class Meta:
        model = TextQuestion
        exclude = []


class EditChoiceQuestionForm(EditQuestionForm):
    choices = forms.ModelMultipleChoiceField(
        Choice.objects.all(),
        required=True,
        help_text="Select choices to include on this question.  Field can be used to search available choices.",
        widget=MultipleSelectWithPop(attrs={'size': '11'}))

    class Meta:
        model = ChoiceQuestion
        exclude = []


class AddChoicesForm(forms.ModelForm):
    class Meta:
        model = Choice
        exclude = []


class AssignUserForm(forms.ModelForm):
    assignee = forms.CharField(required=False,
                                widget=forms.widgets.HiddenInput())

    def __init__(self, *args, **kwargs):
        assignee = None
        if 'assignee' in kwargs:
            assignee = kwargs.pop('asignees')
        super(AssignUserForm, self).__init__(*args, **kwargs)
        if assignee is None:
            self.fields['assignee'] = forms.ModelChoiceField(queryset=User.objects.all(), empty_label='Not Assigned', required=False)
        else:
            self.fields['assignee'].initial = assignee

    class Meta:
        model = Answered_Survey
        exclude = ['engagement', 'survey', 'responder', 'completed', 'answered_on']


class AddEngagementForm(forms.Form):
    product = forms.ModelChoiceField(
        queryset=Product.objects.all(),
        required=True,
        widget=forms.widgets.Select(),
        help_text='Select which product to attach Engagement')
