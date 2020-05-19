import re
from datetime import datetime, date
from urllib.parse import urlsplit, urlunsplit


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
from tagging.models import Tag
from dojo.models import Finding, Product_Type, Product, Note_Type, ScanSettings, VA, \
    Check_List, User, Engagement, Test, Test_Type, Notes, Risk_Acceptance, \
    Development_Environment, Dojo_User, Scan, Endpoint, Stub_Finding, Finding_Template, Report, FindingImage, \
    JIRA_Issue, JIRA_PKey, JIRA_Conf, GITHUB_Issue, GITHUB_PKey, GITHUB_Conf, UserContactInfo, Tool_Type, Tool_Configuration, Tool_Product_Settings, \
    Cred_User, Cred_Mapping, System_Settings, Notifications, Languages, Language_Type, App_Analysis, Objects, \
    Benchmark_Product, Benchmark_Requirement, Benchmark_Product_Summary, Rule, Child_Rule, Engagement_Presets, \
    DojoMeta, Sonarqube_Product, CommonNote
from dojo.tools import requires_file, SCAN_SONARQUBE_API

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
    class Meta:
        model = Product_Type
        fields = ['name', 'critical_product', 'key_product']


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
    tags = forms.CharField(widget=forms.SelectMultiple(choices=[]),
                           required=False,
                           help_text="Add tags that help describe this product.  "
                                     "Choose from the list or add new tags.  Press TAB key to add.")
    prod_type = forms.ModelChoiceField(label='Product Type',
                                       queryset=Product_Type.objects.all().order_by('name'),
                                       required=True)

    authorized_users = forms.ModelMultipleChoiceField(
        queryset=None,
        required=False, label="Authorized Users")

    product_manager = forms.ModelChoiceField(queryset=Dojo_User.objects.exclude(is_active=False).order_by('first_name', 'last_name'), required=False)
    technical_contact = forms.ModelChoiceField(queryset=Dojo_User.objects.exclude(is_active=False).order_by('first_name', 'last_name'), required=False)
    product_manager = forms.ModelChoiceField(queryset=Dojo_User.objects.exclude(is_active=False).order_by('first_name', 'last_name'), required=False)

    def __init__(self, *args, **kwargs):
        non_staff = Dojo_User.objects.exclude(is_staff=True) \
            .exclude(is_active=False).order_by('first_name', 'last_name')
        tags = Tag.objects.usage_for_model(Product)
        t = [(tag.name, tag.name) for tag in tags]
        super(ProductForm, self).__init__(*args, **kwargs)
        self.fields['authorized_users'].queryset = non_staff
        self.fields['tags'].widget.choices = t

    class Meta:
        model = Product
        fields = ['name', 'description', 'tags', 'product_manager', 'technical_contact', 'team_manager', 'prod_type', 'regulations',
                  'authorized_users', 'business_criticality', 'platform', 'lifecycle', 'origin', 'user_records', 'revenue', 'external_audience', 'internet_accessible']


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
    tags = forms.CharField(widget=forms.SelectMultiple(choices=[]),
                           required=False,
                           help_text="Add tags that help describe this product.  "
                                     "Choose from the list or add new tags.  Press TAB key to add.")
    authorized_users = forms.ModelMultipleChoiceField(
        queryset=None,
        required=False, label="Authorized Users")
    prod_type = forms.ModelChoiceField(label='Product Type',
                                       queryset=Product_Type.objects.all().order_by('name'),
                                       required=True)

    def __init__(self, *args, **kwargs):
        non_staff = User.objects.exclude(is_staff=True) \
            .exclude(is_active=False)
        tags = Tag.objects.usage_for_model(Product)
        t = [(tag.name, tag.name) for tag in tags]
        super(Product_TypeProductForm, self).__init__(*args, **kwargs)
        self.fields['authorized_users'].queryset = non_staff
        self.fields['tags'].widget.choices = t

    class Meta:
        model = Product
        fields = ['name', 'description', 'tags', 'product_manager', 'technical_contact', 'team_manager', 'prod_type', 'regulations',
                  'authorized_users', 'business_criticality', 'platform', 'lifecycle', 'origin', 'user_records', 'revenue', 'external_audience', 'internet_accessible']


class ImportScanForm(forms.Form):
    SCAN_TYPE_CHOICES = (("", "Please Select a Scan Type"),
                         ("Netsparker Scan", "Netsparker Scan"),
                         ("Burp Scan", "Burp Scan"),
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
                         ("GitLab SAST Report", "GitLab SAST Report"))

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
    active = forms.BooleanField(help_text="Select if these findings are currently active.", required=False)
    verified = forms.BooleanField(help_text="Select if these findings have been verified.", required=False)
    scan_type = forms.ChoiceField(required=True, choices=SORTED_SCAN_TYPE_CHOICES)
    endpoints = forms.ModelMultipleChoiceField(Endpoint.objects, required=False, label='Systems / Endpoints',
                                               widget=MultipleSelectWithPopPlusMinus(attrs={'size': '5'}))
    tags = forms.CharField(widget=forms.SelectMultiple(choices=[]),
                           required=False,
                           help_text="Add tags that help describe this scan.  "
                                     "Choose from the list or add new tags.  Press TAB key to add.")
    file = forms.FileField(widget=forms.widgets.FileInput(
        attrs={"accept": ".xml, .csv, .nessus, .json, .html, .js, .zip, .xlsx"}),
        label="Choose report file",
        required=False)

    def __init__(self, *args, **kwargs):
        tags = Tag.objects.usage_for_model(Test)
        t = [(tag.name, tag.name) for tag in tags]
        super(ImportScanForm, self).__init__(*args, **kwargs)
        self.fields['tags'].widget.choices = t

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
    active = forms.BooleanField(help_text="Select if these findings are currently active.", required=False)
    verified = forms.BooleanField(help_text="Select if these findings have been verified.", required=False)
    endpoints = forms.ModelMultipleChoiceField(Endpoint.objects, required=False, label='Systems / Endpoints',
                                               widget=MultipleSelectWithPopPlusMinus(attrs={'size': '5'}))
    tags = forms.CharField(widget=forms.SelectMultiple(choices=[]),
                           required=False,
                           help_text="Add tags that help describe this scan.  "
                                     "Choose from the list or add new tags.  Press TAB key to add.")
    file = forms.FileField(widget=forms.widgets.FileInput(
        attrs={"accept": ".xml, .csv, .nessus, .json, .html, .js, .zip, .xlsx"}),
        label="Choose report file",
        required=False)

    def __init__(self, *args, **kwargs):
        tags = Tag.objects.usage_for_model(Test)
        t = [(tag.name, tag.name) for tag in tags]
        super(ReImportScanForm, self).__init__(*args, **kwargs)
        self.fields['tags'].widget.choices = t

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


class UploadRiskForm(forms.ModelForm):
    path = forms.FileField(label="Select File",
                           required=False,
                           widget=forms.widgets.FileInput(
                               attrs={"accept": ".jpg,.png,.pdf"}))
    accepted_findings = forms.ModelMultipleChoiceField(
        queryset=Finding.objects.all(), required=True,
        widget=forms.widgets.SelectMultiple(attrs={'size': 10}),
        help_text=('Active, verified findings listed, please select to add findings.'))
    reporter = forms.ModelChoiceField(
        queryset=User.objects.exclude(username="root"))
    accepted_by = forms.CharField(help_text="The entity or person that accepts the risk.", required=False)
    expiration_date = forms.DateTimeField(label='Date Risk Exception Expires', required=False, widget=forms.TextInput(attrs={'class': 'datepicker'}))
    compensating_control = forms.CharField(label='Compensating Control', help_text="Compensating control (if applicable) for this risk exception", required=False, max_length=2400, widget=forms.Textarea)
    notes = forms.CharField(required=False, max_length=2400,
                            widget=forms.Textarea,
                            label='Notes')

    class Meta:
        model = Risk_Acceptance
        fields = ['accepted_findings']


class ReplaceRiskAcceptanceForm(forms.ModelForm):
    path = forms.FileField(label="Select File",
                           required=True,
                           widget=forms.widgets.FileInput(
                               attrs={"accept": ".jpg,.png,.pdf"}))

    class Meta:
        model = Risk_Acceptance
        exclude = ('reporter', 'accepted_findings', 'notes')


class AddFindingsRiskAcceptanceForm(forms.ModelForm):
    accepted_findings = forms.ModelMultipleChoiceField(
        queryset=Finding.objects.all(), required=True,
        widget=forms.widgets.SelectMultiple(attrs={'size': 10}),
        help_text=('Select to add findings.'))

    class Meta:
        model = Risk_Acceptance
        exclude = ('reporter', 'path', 'notes', 'accepted_by', 'expiration_date', 'compensating_control')


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
    tags = forms.CharField(widget=forms.SelectMultiple(choices=[]),
                           required=False,
                           help_text="Add tags that help describe this engagement.  "
                                     "Choose from the list or add new tags.  Press TAB key to add.")
    target_start = forms.DateField(widget=forms.TextInput(
        attrs={'class': 'datepicker', 'autocomplete': 'off'}))
    target_end = forms.DateField(widget=forms.TextInput(
        attrs={'class': 'datepicker', 'autocomplete': 'off'}))
    lead = forms.ModelChoiceField(
        queryset=User.objects.exclude(is_staff=False),
        required=True, label="Testing Lead")
    test_strategy = forms.URLField(required=False, label="Test Strategy URL")

    def __init__(self, *args, **kwargs):
        cicd = False
        product = None
        if 'cicd' in kwargs:
            cicd = kwargs.pop('cicd')

        if 'product' in kwargs:
            product = kwargs.pop('product')

        tags = Tag.objects.usage_for_model(Engagement)
        t = [(tag.name, tag.name) for tag in tags]
        super(EngForm, self).__init__(*args, **kwargs)
        self.fields['tags'].widget.choices = t
        if product:
            self.fields['preset'] = forms.ModelChoiceField(help_text="Settings and notes for performing this engagement.", required=False, queryset=Engagement_Presets.objects.filter(product=product))
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


class EngForm2(forms.ModelForm):
    name = forms.CharField(max_length=300,
                           required=False,
                           help_text="Add a descriptive name to identify " +
                                     "this engagement. Without a name the target " +
                                     "start date will be used in listings.")
    description = forms.CharField(widget=forms.Textarea(attrs={}),
                                  required=False)
    tags = forms.CharField(widget=forms.SelectMultiple(choices=[]),
                           required=False,
                           help_text="Add tags that help describe this engagement.  "
                                     "Choose from the list or add new tags.  Press TAB key to add.")
    product = forms.ModelChoiceField(queryset=Product.objects.all())
    target_start = forms.DateField(widget=forms.TextInput(
        attrs={'class': 'datepicker', 'autocomplete': 'off'}))
    target_end = forms.DateField(widget=forms.TextInput(
        attrs={'class': 'datepicker', 'autocomplete': 'off'}))
    test_options = (('API', 'API Test'), ('Static', 'Static Check'),
                    ('Pen', 'Pen Test'), ('Web App', 'Web Application Test'))
    lead = forms.ModelChoiceField(
        queryset=User.objects.exclude(is_staff=False),
        required=True, label="Testing Lead")
    test_strategy = forms.URLField(required=False, label="Test Strategy URL")

    def __init__(self, *args, **kwargs):
        tags = Tag.objects.usage_for_model(Engagement)
        t = [(tag.name, tag.name) for tag in tags]
        super(EngForm2, self).__init__(*args, **kwargs)
        self.fields['tags'].widget.choices = t

    def is_valid(self):
        valid = super(EngForm2, self).is_valid()

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
        exclude = ('first_contacted', 'version', 'eng_type', 'real_start',
                   'real_end', 'requester', 'reason', 'updated', 'report_type')


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
    test_type = forms.ModelChoiceField(queryset=Test_Type.objects.all().order_by('name'))
    environment = forms.ModelChoiceField(
        queryset=Development_Environment.objects.all().order_by('name'))
    # credential = forms.ModelChoiceField(Cred_User.objects.all(), required=False)
    target_start = forms.DateTimeField(widget=forms.TextInput(
        attrs={'class': 'datepicker', 'autocomplete': 'off'}))
    target_end = forms.DateTimeField(widget=forms.TextInput(
        attrs={'class': 'datepicker', 'autocomplete': 'off'}))
    tags = forms.CharField(widget=forms.SelectMultiple(choices=[]),
                           required=False,
                           help_text="Add tags that help describe this test.  "
                                     "Choose from the list or add new tags.  Press TAB key to add.")
    lead = forms.ModelChoiceField(
        queryset=User.objects.exclude(is_staff=False),
        required=False, label="Testing Lead")

    def __init__(self, *args, **kwargs):
        tags = Tag.objects.usage_for_model(Test)
        t = [(tag.name, tag.name) for tag in tags]
        super(TestForm, self).__init__(*args, **kwargs)
        self.fields['tags'].widget.choices = t

    class Meta:
        model = Test
        fields = ['title', 'test_type', 'target_start', 'target_end',
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
    is_template = forms.BooleanField(label="Create Template?", required=False,
                                     help_text="A new finding template will be created from this finding.")

    def clean(self):
        # self.fields['endpoints'].queryset = Endpoint.objects.all()
        cleaned_data = super(AddFindingForm, self).clean()
        if ((cleaned_data['active'] or cleaned_data['verified']) and cleaned_data['duplicate']):
            raise forms.ValidationError('Duplicate findings cannot be'
                                        ' verified or active')
        if cleaned_data['false_p'] and cleaned_data['verified']:
            raise forms.ValidationError('False positive findings cannot '
                                        'be verified.')
        return cleaned_data

    class Meta:
        model = Finding
        order = ('title', 'severity', 'endpoints', 'description', 'impact')
        exclude = ('reporter', 'url', 'numerical_severity', 'endpoint', 'images', 'under_review', 'reviewers',
                   'review_requested_by', 'is_Mitigated', 'jira_creation', 'jira_change')


class AdHocFindingForm(forms.ModelForm):
    title = forms.CharField(max_length=1000)
    date = forms.DateField(required=True,
                           widget=forms.TextInput(attrs={'class': 'datepicker', 'autocomplete': 'off'}))
    cwe = forms.IntegerField(required=False)
    cve = forms.CharField(max_length=28, required=False)
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
    is_template = forms.BooleanField(label="Create Template?", required=False,
                                     help_text="A new finding template will be created from this finding.")

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
        order = ('title', 'severity', 'endpoints', 'description', 'impact')
        exclude = ('reporter', 'url', 'numerical_severity', 'endpoint', 'images', 'under_review', 'reviewers',
                   'review_requested_by', 'is_Mitigated', 'jira_creation', 'jira_change')


class PromoteFindingForm(forms.ModelForm):
    title = forms.CharField(max_length=1000)
    date = forms.DateField(required=True,
                           widget=forms.TextInput(attrs={'class': 'datepicker', 'autocomplete': 'off'}))
    cwe = forms.IntegerField(required=False)
    cve = forms.CharField(max_length=28, required=False)
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
        exclude = ('reporter', 'url', 'numerical_severity', 'endpoint', 'active', 'false_p', 'verified', 'is_template',
                   'duplicate', 'out_of_scope', 'images', 'under_review', 'reviewers', 'review_requested_by', 'is_Mitigated', 'jira_creation', 'jira_change')


class FindingForm(forms.ModelForm):
    title = forms.CharField(max_length=1000)
    date = forms.DateField(required=True,
                           widget=forms.TextInput(attrs={'class': 'datepicker', 'autocomplete': 'off'}))
    cwe = forms.IntegerField(required=False)
    cve = forms.CharField(max_length=28, required=False)
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
    tags = forms.CharField(widget=forms.SelectMultiple(choices=[]),
                           required=False,
                           help_text="Add tags that help describe this finding.  "
                                     "Choose from the list or add new tags.  Press TAB key to add.")
    is_template = forms.BooleanField(label="Create Template?", required=False,
                                     help_text="A new finding template will be created from this finding.")

    def __init__(self, *args, **kwargs):
        template = kwargs.pop('template')
        # Get tags from a template
        if template:
            tags = Tag.objects.usage_for_model(Finding_Template)
        # Get tags from a finding
        else:
            tags = Tag.objects.usage_for_model(Finding)

        t = [(tag.name, tag.name) for tag in tags]
        super(FindingForm, self).__init__(*args, **kwargs)
        self.fields['tags'].widget.choices = t

    def clean(self):
        cleaned_data = super(FindingForm, self).clean()
        if (cleaned_data['active'] or cleaned_data['verified']) and cleaned_data['duplicate']:
            raise forms.ValidationError('Duplicate findings cannot be'
                                        ' verified or active')
        if cleaned_data['false_p'] and cleaned_data['verified']:
            raise forms.ValidationError('False positive findings cannot '
                                        'be verified.')
        return cleaned_data

    class Meta:
        model = Finding
        order = ('title', 'severity', 'endpoints', 'description', 'impact')
        exclude = ('reporter', 'url', 'numerical_severity', 'endpoint', 'images', 'under_review', 'reviewers',
                   'review_requested_by', 'is_Mitigated', 'jira_creation', 'jira_change', 'sonarqube_issue')


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

    severity = forms.ChoiceField(required=False, choices=SEVERITY_CHOICES, error_messages={'required': 'Select valid choice: In Progress, On Hold, Completed', 'invalid_choice': 'Select valid choice: Critical,High,Medium,Low'})

    description = forms.CharField(widget=forms.Textarea)
    mitigation = forms.CharField(widget=forms.Textarea)
    impact = forms.CharField(widget=forms.Textarea)
    references = forms.CharField(widget=forms.Textarea, required=False)
    tags = forms.CharField(widget=forms.SelectMultiple(choices=[]),
                           required=False,
                           help_text="Add tags that help describe this finding template.  "
                                     "Choose from the list or add new tags.  Press TAB key to add.")

    def __init__(self, template=None, *args, **kwargs):
        # django-tagging apparently can not filter for multiple models at once
        tags = Tag.objects.usage_for_model(Finding_Template) + Tag.objects.usage_for_model(Finding)
        t = sorted({(tag.name, tag.name) for tag in tags})
        super(ApplyFindingTemplateForm, self).__init__(*args, **kwargs)
        self.fields['tags'].widget.choices = t
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
        fields = ['title', 'cwe', 'cve', 'severity', 'description', 'mitigation', 'impact', 'references', 'tags']
        order = ('title', 'cwe', 'cve', 'severity', 'description', 'impact', 'is_Mitigated')


class FindingTemplateForm(forms.ModelForm):
    apply_to_findings = forms.BooleanField(required=False, help_text="Apply template to all findings that match this CWE. (Update will overwrite mitigation, impact and references for any active, verified findings.)")
    title = forms.CharField(max_length=1000, required=True)
    tags = forms.CharField(widget=forms.SelectMultiple(choices=[]),
                           required=False,
                           help_text="Add tags that help describe this finding template.  "
                                     "Choose from the list or add new tags.  Press TAB key to add.")
    cwe = forms.IntegerField(label="CWE", required=False)
    cve = forms.CharField(label="CVE", max_length=28, required=False)
    severity = forms.ChoiceField(
        required=False,
        choices=SEVERITY_CHOICES,
        error_messages={
            'required': 'Select valid choice: In Progress, On Hold, Completed',
            'invalid_choice': 'Select valid choice: Critical,High,Medium,Low'})

    field_order = ['title', 'cwe', 'cve', 'severity', 'description', 'mitigation', 'impact', 'references', 'tags', 'template_match', 'template_match_cwe', 'template_match_title', 'apply_to_findings']

    def __init__(self, *args, **kwargs):
        tags = Tag.objects.usage_for_model(Finding_Template)
        t = [(tag.name, tag.name) for tag in tags]
        super(FindingTemplateForm, self).__init__(*args, **kwargs)
        self.fields['tags'].widget.choices = t

    class Meta:
        model = Finding_Template
        order = ('title', 'cwe', 'cve', 'severity', 'description', 'impact')
        exclude = ('numerical_severity', 'is_Mitigated', 'last_used')


class DeleteFindingTemplateForm(forms.ModelForm):
    id = forms.IntegerField(required=True,
                            widget=forms.widgets.HiddenInput())

    class Meta:
        model = Finding_Template
        fields = ('id',)


class FindingBulkUpdateForm(forms.ModelForm):
    status = forms.BooleanField(required=False)
    push_to_jira = forms.BooleanField(required=False)
    push_to_github = forms.BooleanField(required=False)
    tags = forms.CharField(widget=forms.SelectMultiple(choices=[]),
                           required=False)

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
    tags = forms.CharField(widget=forms.SelectMultiple(choices=[]),
                           required=False,
                           help_text="Add tags that help describe this endpoint.  "
                                     "Choose from the list or add new tags.  Press TAB key to add.")

    class Meta:
        model = Endpoint
        exclude = ['product']

    def __init__(self, *args, **kwargs):
        self.product = None
        self.endpoint_instance = None
        tags = Tag.objects.usage_for_model(Endpoint)
        t = [(tag.name, tag.name) for tag in tags]
        super(EditEndpointForm, self).__init__(*args, **kwargs)
        if 'instance' in kwargs:
            self.endpoint_instance = kwargs.pop('instance')
            self.product = self.endpoint_instance.product
            self.fields['tags'].widget.choices = t

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
    tags = forms.CharField(widget=forms.SelectMultiple(choices=[]),
                           required=False,
                           help_text="Add tags that help describe this endpoint.  "
                                     "Choose from the list or add new tags.  Press TAB key to add.")

    def __init__(self, *args, **kwargs):
        product = None
        tags = Tag.objects.usage_for_model(Endpoint)
        t = [(tag.name, tag.name) for tag in tags]
        if 'product' in kwargs:
            product = kwargs.pop('product')
        super(AddEndpointForm, self).__init__(*args, **kwargs)
        if product is None:
            self.fields['product'] = forms.ModelChoiceField(queryset=Product.objects.all())
        else:
            self.fields['product'].initial = product.id

        self.product = product
        self.endpoints_to_process = []
        self.fields['tags'].widget.choices = t

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


class FindingNoteForm(NoteForm):

    def __init__(self, *args, **kwargs):
        queryset = kwargs.pop('available_note_types')
        super(FindingNoteForm, self).__init__(*args, **kwargs)
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
    query = forms.CharField()


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
    report_type = forms.ChoiceField(required=False, choices=(('AsciiDoc', 'AsciiDoc'),))


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

    class Meta:
        model = JIRA_Conf
        exclude = ['product']


class ExpressJIRAForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput, required=True)
    issue_key = forms.CharField(required=True, help_text='A valid issue ID is required to gather the necessary information.')

    class Meta:
        model = JIRA_Conf
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


class JIRA_PKeyForm(forms.ModelForm):

    class Meta:
        model = JIRA_PKey
        exclude = ['product']


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


class DeleteJIRAConfForm(forms.ModelForm):
    id = forms.IntegerField(required=True,
                            widget=forms.widgets.HiddenInput())

    class Meta:
        model = JIRA_Conf
        fields = ('id',)


class ToolTypeForm(forms.ModelForm):
    class Meta:
        model = Tool_Type
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
        model = Objects
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

    tags = forms.CharField(widget=forms.SelectMultiple(choices=[]),
                           required=False,
                           help_text="Add tags that help describe this object.  "
                                     "Choose from the list or add new tags.  Press TAB key to add.")

    class Meta:
        model = Objects
        fields = ['path', 'folder', 'artifact', 'name', 'review_status']
        exclude = ['product']

    def __init__(self, *args, **kwargs):
        tags = Tag.objects.usage_for_model(Objects)
        t = [(tag.name, tag.name) for tag in tags]
        super(ObjectSettingsForm, self).__init__(*args, **kwargs)
        self.fields['tags'].widget.choices = t

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

    class Meta:
        model = Notifications
        fields = ['engagement_added', 'test_added', 'scan_added']


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


class JIRAPKeyForm(forms.ModelForm):
    conf = forms.ModelChoiceField(queryset=JIRA_Conf.objects.all(), label='JIRA Configuration', required=False)

    class Meta:
        model = JIRA_PKey
        exclude = ['product']


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
        self.enabled = kwargs.pop('enabled') or False
        super(JIRAFindingForm, self).__init__(*args, **kwargs)
        self.fields['push_to_jira'] = forms.BooleanField()
        self.fields['push_to_jira'].required = False
        self.fields['push_to_jira'].help_text = "Checking this will overwrite content of your JIRA issue, or create one."
        self.fields['push_to_jira'].label = "Push to JIRA"
        if self.enabled:
            # This will show the checkbox as checked and greyed out, this way the user is aware
            # that issues will be pushed to JIRA, given their product-level settings.
            self.fields['push_to_jira'].help_text = \
                "Push all issues is enabled on this product. If you do not wish to push all issues" \
                " to JIRA, please disable Push all issues on this product."
            self.fields['push_to_jira'].widget.attrs['checked'] = 'checked'
            self.fields['push_to_jira'].disabled = True

    push_to_jira = forms.BooleanField(required=False, label="Push to JIRA")


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


class CommonNoteForm(forms.ModelForm):
    SCAN_TYPE_CHOICES = (("", "Please Select a Scanner Type"),
                         ("Netsparker Scan", "Netsparker Scan"),
                         ("Burp Scan", "Burp Scan"),
                         ("Nessus Scan", "Nessus Scan"),
                         ("Nmap Scan", "Nmap Scan"),
                         ("Nexpose Scan", "Nexpose Scan"),
                         ("AppSpider Scan", "AppSpider Scan"),
                         ("Veracode Scan", "Veracode Scan"),
                         ("Checkmarx Scan", "Checkmarx Scan"),
                         ("Checkmarx Scan detailed", "Checkmarx Scan detailed"),
                         ("Crashtest Security Scan", "Crashtest Security Scan"),
                         ("ZAP Scan", "ZAP Scan"),
                         ("Arachni Scan", "Arachni Scan"),
                         ("VCG Scan", "VCG Scan"),
                         ("Dependency Check Scan", "Dependency Check Scan"),
                         ("Dependency Track Finding Packaging Format (FPF) Export",
                          "Dependency Track Finding Packaging Format (FPF) Export"),
                         ("Retire.js Scan", "Retire.js Scan"),
                         ("Node Security Platform Scan", "Node Security Platform Scan"),
                         ("NPM Audit Scan", "NPM Audit Scan"),
                         ("Qualys Scan", "Qualys Scan"),
                         ("Qualys Webapp Scan", "Qualys Webapp Scan"),
                         ("OpenVAS CSV", "OpenVAS CSV"),
                         ("Snyk Scan", "Snyk Scan"),
                         ("Generic Findings Import", "Generic Findings Import"),
                         ("Trustwave Scan (CSV)", "Trustwave Scan (CSV)"),
                         ("SKF Scan", "SKF Scan"),
                         ("Clair Klar Scan", "Clair Klar Scan"),
                         ("Bandit Scan", "Bandit Scan"),
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
                         ("Testssl Scan", "Testssl Scan"),
                         ("Hadolint Dockerfile check", "Hadolint Dockerfile check"),
                         ("Aqua Scan", "Aqua Scan"),
                         ("HackerOne Cases", "HackerOne Cases"),
                         ("Xanitizer Scan", "Xanitizer Scan"),
                         ("Trivy Scan", "Trivy Scan"))
    SORTED_SCAN_TYPE_CHOICES = sorted(SCAN_TYPE_CHOICES, key=lambda x: x[1])
    title = forms.CharField(max_length=1000)
    scanner = forms.ChoiceField(required=True, choices=SORTED_SCAN_TYPE_CHOICES)
    product = forms.CharField(max_length=100)
    cwe = forms.IntegerField()
    description = forms.CharField(max_length=100)

    class Meta:
        model = CommonNote
        fields = ['title', 'scanner', 'product', 'cwe', 'description']


class EditCommonNoteForm(CommonNoteForm):

    def __init__(self, *args, **kwargs):
        super(EditCommonNoteForm, self).__init__(*args, **kwargs)
