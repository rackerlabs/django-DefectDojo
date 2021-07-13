#  engagements
import logging
from datetime import datetime
import operator
from django.contrib.auth.models import User
from django.conf import settings
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.urls import reverse
from django.db.models import Q, Count
from django.http import HttpResponseRedirect, StreamingHttpResponse, Http404, HttpResponse, FileResponse
from django.shortcuts import render, get_object_or_404
from django.views.decorators.cache import cache_page
from django.utils import timezone
from time import strftime
from django.contrib.admin.utils import NestedObjects
from django.db import DEFAULT_DB_ALIAS

from dojo.engagement.services import close_engagement, reopen_engagement
from dojo.filters import EngagementFilter, EngagementDirectFilter, EngagementTestFilter
from dojo.forms import CheckForm, \
    UploadThreatForm, RiskAcceptanceForm, NoteForm, DoneForm, \
    EngForm, TestForm, ReplaceRiskAcceptanceProofForm, AddFindingsRiskAcceptanceForm, DeleteEngagementForm, ImportScanForm, \
    CredMappingForm, JIRAEngagementForm, JIRAImportScanForm, TypedNoteForm, JIRAProjectForm, \
    EditRiskAcceptanceForm

from dojo.models import Finding, Product, Engagement, Test, \
    Check_List, Test_Import, Notes, \
    Risk_Acceptance, Development_Environment, Endpoint, \
    Cred_Mapping, Dojo_User, System_Settings, Note_Type, Sonarqube_Product
from dojo.tools.factory import get_choices
from dojo.utils import add_error_message_to_response, add_success_message_to_response, get_page_items, add_breadcrumb, handle_uploaded_threat, \
    FileIterWrapper, get_cal_event, Product_Tab, is_scan_file_too_large, \
    get_system_setting, redirect_to_return_url_or_else, get_return_url
from dojo.notifications.helper import create_notification
from dojo.finding.views import find_available_notetypes
from functools import reduce
from django.db.models.query import Prefetch, QuerySet
import dojo.jira_link.helper as jira_helper
import dojo.risk_acceptance.helper as ra_helper
from dojo.risk_acceptance.helper import prefetch_for_expiration
from dojo.finding.helper import NOT_ACCEPTED_FINDINGS_QUERY
from django.views.decorators.vary import vary_on_cookie
from dojo.authorization.authorization import user_has_permission_or_403
from dojo.authorization.roles_permissions import Permissions
from dojo.product.queries import get_authorized_products
from dojo.engagement.queries import get_authorized_engagements
from dojo.authorization.authorization_decorators import user_is_authorized
from dojo.importers.importer.importer import DojoDefaultImporter as Importer
import dojo.notifications.helper as notifications_helper


logger = logging.getLogger(__name__)


@cache_page(60 * 5)  # cache for 5 minutes
@vary_on_cookie
def engagement_calendar(request):
    if 'lead' not in request.GET or '0' in request.GET.getlist('lead'):
        engagements = get_authorized_engagements(Permissions.Engagement_View)
    else:
        filters = []
        leads = request.GET.getlist('lead', '')
        if '-1' in request.GET.getlist('lead'):
            leads.remove('-1')
            filters.append(Q(lead__isnull=True))
        filters.append(Q(lead__in=leads))
        engagements = get_authorized_engagements(Permissions.Engagement_View).filter(reduce(operator.or_, filters))

    engagements = engagements.select_related('lead')
    engagements = engagements.prefetch_related('product')

    add_breadcrumb(
        title="Engagement Calendar", top_level=True, request=request)
    return render(
        request, 'dojo/calendar.html', {
            'caltype': 'engagements',
            'leads': request.GET.getlist('lead', ''),
            'engagements': engagements,
            'users': Dojo_User.objects.all()
        })


def engagement(request):
    products = get_authorized_products(Permissions.Engagement_View).distinct()
    engagements = Engagement.objects.filter(
        product__in=products
    ).select_related(
        'product',
        'product__prod_type',
    ).prefetch_related(
        'lead',
        'tags',
        'product__tags',
    )

    # Get the test counts per engagments. As a separate query, this is much
    # faster than annotating the above `engagements` query.
    engagement_test_counts = {
        test['engagement']: test['test_count']
        for test in Test.objects.filter(
            engagement__in=engagements
        ).values(
            'engagement'
        ).annotate(
            test_count=Count('engagement')
        )
    }

    if System_Settings.objects.get().enable_jira:
        engagements = engagements.prefetch_related(
            'jira_project__jira_instance',
            'product__jira_project_set__jira_instance'
        )

    filtered_engagements = EngagementDirectFilter(
        request.GET,
        queryset=engagements
    )

    engs = get_page_items(request, filtered_engagements.qs, 25)
    product_name_words = sorted(products.values_list('name', flat=True))
    engagement_name_words = sorted(engagements.values_list('name', flat=True).distinct())

    add_breadcrumb(
        title="Active Engagements",
        top_level=not len(request.GET),
        request=request)

    return render(
        request, 'dojo/engagement.html', {
            'engagements': engs,
            'engagement_test_counts': engagement_test_counts,
            'filter_form': filtered_engagements.form,
            'product_name_words': product_name_words,
            'engagement_name_words': engagement_name_words,
        })


def engagements_all(request):

    products_with_engagements = get_authorized_products(Permissions.Engagement_View)
    products_with_engagements = products_with_engagements.filter(~Q(engagement=None)).distinct()

    # count using prefetch instead of just using 'engagement__set_test_test` to avoid loading all test in memory just to count them
    filter_qs = products_with_engagements.prefetch_related(
        Prefetch('engagement_set', queryset=Engagement.objects.all().annotate(test_count=Count('test__id')))
    )

    filter_qs = filter_qs.prefetch_related(
        'engagement_set__tags',
        'prod_type',
        'engagement_set__lead',
        'tags',
    )
    if System_Settings.objects.get().enable_jira:
        filter_qs = filter_qs.prefetch_related(
            'engagement_set__jira_project__jira_instance',
            'jira_project_set__jira_instance'
        )

    filtered = EngagementFilter(
        request.GET,
        queryset=filter_qs
    )

    prods = get_page_items(request, filtered.qs, 25)

    name_words = products_with_engagements.values_list('name', flat=True)
    eng_words = get_authorized_engagements(Permissions.Engagement_View).values_list('name', flat=True).distinct()

    add_breadcrumb(
        title="All Engagements",
        top_level=not len(request.GET),
        request=request)

    return render(
        request, 'dojo/engagements_all.html', {
            'products': prods,
            'filter_form': filtered.form,
            'name_words': sorted(set(name_words)),
            'eng_words': sorted(set(eng_words)),
        })


@user_is_authorized(Engagement, Permissions.Engagement_Edit, 'eid', 'change')
def edit_engagement(request, eid):
    engagement = Engagement.objects.get(pk=eid)
    is_ci_cd = engagement.engagement_type == "CI/CD"
    jira_project_form = None
    jira_epic_form = None
    jira_project = None
    jira_error = False

    if request.method == 'POST':
        form = EngForm(request.POST, instance=engagement, cicd=is_ci_cd, product=engagement.product, user=request.user)
        jira_project = jira_helper.get_jira_project(engagement, use_inheritance=False)

        if form.is_valid():
            # first save engagement details
            new_status = form.cleaned_data.get('status')
            engagement = form.save(commit=False)
            if (new_status == "Cancelled" or new_status == "Completed"):
                engagement.active = False
                create_notification(event='close_engagement',
                        title='Closure of %s' % engagement.name,
                        description='The engagement "%s" was closed' % (engagement.name),
                        engagement=engagement, url=reverse('engagment_all_findings', args=(engagement.id, ))),
            else:
                engagement.active = True
            engagement.save()
            form.save_m2m()

            messages.add_message(
                request,
                messages.SUCCESS,
                'Engagement updated successfully.',
                extra_tags='alert-success')

            success, jira_project_form = jira_helper.process_jira_project_form(request, instance=jira_project, target='engagement', engagement=engagement, product=engagement.product)
            error = not success

            success, jira_epic_form = jira_helper.process_jira_epic_form(request, engagement=engagement)
            error = error or not success

            if not error:
                if '_Add Tests' in request.POST:
                    return HttpResponseRedirect(
                        reverse('add_tests', args=(engagement.id, )))
                else:
                    return HttpResponseRedirect(
                        reverse('view_engagement', args=(engagement.id, )))
        else:
            logger.debug(form.errors)

    else:
        form = EngForm(initial={'product': engagement.product}, instance=engagement, cicd=is_ci_cd, product=engagement.product, user=request.user)

        jira_epic_form = None
        if get_system_setting('enable_jira'):
            jira_project = jira_helper.get_jira_project(engagement, use_inheritance=False)
            jira_project_form = JIRAProjectForm(instance=jira_project, target='engagement', product=engagement.product)
            logger.debug('showing jira-epic-form')
            jira_epic_form = JIRAEngagementForm(instance=engagement)

    if is_ci_cd:
        title = 'Edit CI/CD Engagement'
    else:
        title = 'Edit Interactive Engagement'

    product_tab = Product_Tab(engagement.product.id, title=title, tab="engagements")
    product_tab.setEngagement(engagement)
    return render(request, 'dojo/new_eng.html', {
        'product_tab': product_tab,
        'title': title,
        'form': form,
        'edit': True,
        'jira_epic_form': jira_epic_form,
        'jira_project_form': jira_project_form,
        'engagement': engagement,
    })


@user_is_authorized(Engagement, Permissions.Engagement_Delete, 'eid', 'delete')
def delete_engagement(request, eid):
    engagement = get_object_or_404(Engagement, pk=eid)
    product = engagement.product
    form = DeleteEngagementForm(instance=engagement)

    if request.method == 'POST':
        if 'id' in request.POST and str(engagement.id) == request.POST['id']:
            form = DeleteEngagementForm(request.POST, instance=engagement)
            if form.is_valid():
                product = engagement.product
                engagement.delete()
                messages.add_message(
                    request,
                    messages.SUCCESS,
                    'Engagement and relationships removed.',
                    extra_tags='alert-success')
                create_notification(event='other',
                                    title='Deletion of %s' % engagement.name,
                                    product=product,
                                    description='The engagement "%s" was deleted by %s' % (engagement.name, request.user),
                                    url=request.build_absolute_uri(reverse('view_engagements', args=(product.id, ))),
                                    recipients=[engagement.lead],
                                    icon="exclamation-triangle")

                return HttpResponseRedirect(reverse("view_engagements", args=(product.id, )))

    collector = NestedObjects(using=DEFAULT_DB_ALIAS)
    collector.collect([engagement])
    rels = collector.nested()

    product_tab = Product_Tab(product.id, title="Delete Engagement", tab="engagements")
    product_tab.setEngagement(engagement)
    return render(request, 'dojo/delete_engagement.html', {
        'product_tab': product_tab,
        'engagement': engagement,
        'form': form,
        'rels': rels,
    })


@user_is_authorized(Engagement, Permissions.Engagement_View, 'eid', 'view')
def view_engagement(request, eid):
    eng = get_object_or_404(Engagement, id=eid)
    tests = eng.test_set.all().order_by('test_type__name', '-updated')

    default_page_num = 10

    tests_filter = EngagementTestFilter(request.GET, queryset=tests, engagement=eng)
    paged_tests = get_page_items(request, tests_filter.qs, default_page_num)
    # prefetch only after creating the filters to avoid https://code.djangoproject.com/ticket/23771 and https://code.djangoproject.com/ticket/25375
    paged_tests.object_list = prefetch_for_view_tests(paged_tests.object_list)

    prod = eng.product
    risks_accepted = eng.risk_acceptance.all().select_related('owner').annotate(accepted_findings_count=Count('accepted_findings__id'))
    preset_test_type = None
    network = None
    if eng.preset:
        preset_test_type = eng.preset.test_type.all()
        network = eng.preset.network_locations.all()
    system_settings = System_Settings.objects.get()

    jissue = jira_helper.get_jira_issue(eng)
    jira_project = jira_helper.get_jira_project(eng)

    try:
        check = Check_List.objects.get(engagement=eng)
    except:
        check = None
        pass
    notes = eng.notes.all()
    note_type_activation = Note_Type.objects.filter(is_active=True).count()
    if note_type_activation:
        available_note_types = find_available_notetypes(notes)
    form = DoneForm()
    files = eng.files.all()
    if request.method == 'POST':
        if settings.FEATURE_AUTHORIZATION_V2:
            user_has_permission_or_403(request.user, eng, Permissions.Note_Add)
        else:
            if not request.user.is_staff:
                raise PermissionDenied
        eng.progress = 'check_list'
        eng.save()

        if note_type_activation:
            form = TypedNoteForm(request.POST, available_note_types=available_note_types)
        else:
            form = NoteForm(request.POST)
        if form.is_valid():
            new_note = form.save(commit=False)
            new_note.author = request.user
            new_note.date = timezone.now()
            new_note.save()
            eng.notes.add(new_note)
            if note_type_activation:
                form = TypedNoteForm(available_note_types=available_note_types)
            else:
                form = NoteForm()
            url = request.build_absolute_uri(reverse("view_engagement", args=(eng.id,)))
            title = "Engagement: %s on %s" % (eng.name, eng.product.name)
            messages.add_message(request,
                                 messages.SUCCESS,
                                 'Note added successfully.',
                                 extra_tags='alert-success')
    else:
        if note_type_activation:
            form = TypedNoteForm(available_note_types=available_note_types)
        else:
            form = NoteForm()

    creds = Cred_Mapping.objects.filter(
        product=eng.product).select_related('cred_id').order_by('cred_id')
    cred_eng = Cred_Mapping.objects.filter(
        engagement=eng.id).select_related('cred_id').order_by('cred_id')

    add_breadcrumb(parent=eng, top_level=False, request=request)

    title = ""
    if eng.engagement_type == "CI/CD":
        title = " CI/CD"
    product_tab = Product_Tab(prod.id, title="View" + title + " Engagement", tab="engagements")
    product_tab.setEngagement(eng)
    return render(
        request, 'dojo/view_eng.html', {
            'eng': eng,
            'product_tab': product_tab,
            'system_settings': system_settings,
            'tests': paged_tests,
            'filter': tests_filter,
            'check': check,
            'threat': eng.tmodel_path,
            'form': form,
            'notes': notes,
            'files': files,
            'risks_accepted': risks_accepted,
            'jissue': jissue,
            'jira_project': jira_project,
            'creds': creds,
            'cred_eng': cred_eng,
            'network': network,
            'preset_test_type': preset_test_type
        })


def prefetch_for_view_tests(tests):
    prefetched = tests
    if isinstance(tests,
                  QuerySet):  # old code can arrive here with prods being a list because the query was already executed

        prefetched = prefetched.select_related('lead')
        prefetched = prefetched.prefetch_related('tags', 'test_type', 'notes')
        prefetched = prefetched.annotate(count_findings_test_all=Count('finding__id', distinct=True))
        prefetched = prefetched.annotate(count_findings_test_active=Count('finding__id', filter=Q(finding__active=True), distinct=True))
        prefetched = prefetched.annotate(count_findings_test_active_verified=Count('finding__id', filter=Q(finding__active=True) & Q(finding__verified=True), distinct=True))
        prefetched = prefetched.annotate(count_findings_test_mitigated=Count('finding__id', filter=Q(finding__is_mitigated=True), distinct=True))
        prefetched = prefetched.annotate(count_findings_test_dups=Count('finding__id', filter=Q(finding__duplicate=True), distinct=True))
        prefetched = prefetched.annotate(total_reimport_count=Count('test_import__id', filter=Q(test_import__type=Test_Import.REIMPORT_TYPE), distinct=True))

    else:
        logger.warn('unable to prefetch because query was already executed')

    return prefetched


@user_is_authorized(Engagement, Permissions.Test_Add, 'eid', 'staff')
def add_tests(request, eid):
    eng = Engagement.objects.get(id=eid)
    cred_form = CredMappingForm()
    cred_form.fields["cred_user"].queryset = Cred_Mapping.objects.filter(
        engagement=eng).order_by('cred_id')

    if request.method == 'POST':
        form = TestForm(request.POST, engagement=eng)
        cred_form = CredMappingForm(request.POST)
        cred_form.fields["cred_user"].queryset = Cred_Mapping.objects.filter(
            engagement=eng).order_by('cred_id')
        if form.is_valid():
            new_test = form.save(commit=False)
            new_test.engagement = eng
            try:
                new_test.lead = User.objects.get(id=form['lead'].value())
            except:
                new_test.lead = None
                pass

            # Set status to in progress if a test is added
            if eng.status != "In Progress" and eng.active is True:
                eng.status = "In Progress"
                eng.save()

            new_test.save()

            # Save the credential to the test
            if cred_form.is_valid():
                if cred_form.cleaned_data['cred_user']:
                    # Select the credential mapping object from the selected list and only allow if the credential is associated with the product
                    cred_user = Cred_Mapping.objects.filter(
                        pk=cred_form.cleaned_data['cred_user'].id,
                        engagement=eid).first()

                    new_f = cred_form.save(commit=False)
                    new_f.test = new_test
                    new_f.cred_id = cred_user.cred_id
                    new_f.save()

            messages.add_message(
                request,
                messages.SUCCESS,
                'Test added successfully.',
                extra_tags='alert-success')

            notifications_helper.notify_test_created(new_test)

            if '_Add Another Test' in request.POST:
                return HttpResponseRedirect(
                    reverse('add_tests', args=(eng.id, )))
            elif '_Add Findings' in request.POST:
                return HttpResponseRedirect(
                    reverse('add_findings', args=(new_test.id, )))
            elif '_Finished' in request.POST:
                return HttpResponseRedirect(
                    reverse('view_engagement', args=(eng.id, )))
    else:
        form = TestForm(engagement=eng)
        form.initial['target_start'] = eng.target_start
        form.initial['target_end'] = eng.target_end
        form.initial['lead'] = request.user
    add_breadcrumb(
        parent=eng, title="Add Tests", top_level=False, request=request)
    product_tab = Product_Tab(eng.product.id, title="Add Tests", tab="engagements")
    product_tab.setEngagement(eng)
    return render(request, 'dojo/add_tests.html', {
        'product_tab': product_tab,
        'form': form,
        'cred_form': cred_form,
        'eid': eid,
        'eng': eng
    })


# Cant use the easy decorator because of the potential for either eid/pid being used
def import_scan_results(request, eid=None, pid=None):
    engagement = None
    form = ImportScanForm()
    cred_form = CredMappingForm()
    finding_count = 0
    jform = None
    user = request.user

    if eid:
        engagement = get_object_or_404(Engagement, id=eid)
        engagement_or_product = engagement
        cred_form.fields["cred_user"].queryset = Cred_Mapping.objects.filter(engagement=engagement).order_by('cred_id')
    elif pid:
        product = get_object_or_404(Product, id=pid)
        engagement_or_product = product
    elif not user.is_staff:
        raise PermissionDenied

    if settings.FEATURE_AUTHORIZATION_V2:
        user_has_permission_or_403(user, engagement_or_product, Permissions.Import_Scan_Result)
    else:
        if not user_is_authorized(user, 'staff', engagement_or_product):
            raise PermissionDenied

    push_all_jira_issues = jira_helper.is_push_all_issues(engagement_or_product)

    if request.method == "POST":
        form = ImportScanForm(request.POST, request.FILES)
        cred_form = CredMappingForm(request.POST)
        cred_form.fields["cred_user"].queryset = Cred_Mapping.objects.filter(
            engagement=engagement).order_by('cred_id')

        if jira_helper.get_jira_project(engagement_or_product):
            jform = JIRAImportScanForm(request.POST, push_all=push_all_jira_issues, prefix='jiraform')
            logger.debug('jform valid: %s', jform.is_valid())
            logger.debug('jform errors: %s', jform.errors)

        if form.is_valid() and (jform is None or jform.is_valid()):
            scan = request.FILES.get('file', None)
            scan_date = form.cleaned_data['scan_date']
            minimum_severity = form.cleaned_data['minimum_severity']
            active = form.cleaned_data['active']
            verified = form.cleaned_data['verified']
            scan_type = request.POST['scan_type']
            tags = form.cleaned_data['tags']
            version = form.cleaned_data['version']
            branch_tag = form.cleaned_data.get('branch_tag', None)
            build_id = form.cleaned_data.get('build_id', None)
            commit_hash = form.cleaned_data.get('commit_hash', None)
            sonarqube_config = form.cleaned_data.get('sonarqube_config', None)
            close_old_findings = form.cleaned_data.get('close_old_findings', None)
            # Will save in the provided environment or in the `Development` one if absent
            environment_id = request.POST.get('environment', 'Development')
            environment = Development_Environment.objects.get(id=environment_id)

            group_by = form.cleaned_data.get('group_by', None)

            # TODO move to form validation?
            if not any(scan_type in code
                       for code in ImportScanForm.SORTED_SCAN_TYPE_CHOICES):
                raise Http404()

            # TODO move to form validation?
            if scan and is_scan_file_too_large(scan):
                messages.add_message(request,
                                     messages.ERROR,
                                     "Report file is too large. Maximum supported size is {} MB".format(settings.SCAN_FILE_MAX_SIZE),
                                     extra_tags='alert-danger')
                return HttpResponseRedirect(reverse('import_scan_results', args=(engagement,)))

            # Allows for a test to be imported with an engagement created on the fly
            if engagement is None:
                engagement = Engagement()
                engagement.name = "AdHoc Import - " + strftime("%a, %d %b %Y %X", timezone.now().timetuple())
                engagement.threat_model = False
                engagement.api_test = False
                engagement.pen_test = False
                engagement.check_list = False
                engagement.target_start = timezone.now().date()
                engagement.target_end = timezone.now().date()
                engagement.product = product
                engagement.active = True
                engagement.status = 'In Progress'
                engagement.version = version
                engagement.branch_tag = branch_tag
                engagement.build_id = build_id
                engagement.commit_hash = commit_hash
                engagement.save()

            # can't use helper as when push_all_jira_issues is True, the checkbox gets disabled and is always false
            # push_to_jira = jira_helper.is_push_to_jira(new_finding, jform.cleaned_data.get('push_to_jira'))
            push_to_jira = push_all_jira_issues or (jform and jform.cleaned_data.get('push_to_jira'))
            error = False

            try:
                importer = Importer()
                test, finding_count, closed_finding_count = importer.import_scan(scan, scan_type, engagement, user, environment, active=active, verified=verified, tags=tags,
                            minimum_severity=minimum_severity, endpoints_to_add=form.cleaned_data['endpoints'], scan_date=scan_date,
                            version=version, branch_tag=branch_tag, build_id=build_id, commit_hash=commit_hash, push_to_jira=push_to_jira,
                            close_old_findings=close_old_findings, group_by=group_by, sonarqube_config=sonarqube_config)

                message = f'{scan_type} processed a total of {finding_count} findings'

                if close_old_findings:
                    message = message + ' and closed %d findings' % (closed_finding_count)

                message = message + "."

                add_success_message_to_response(message)

            except Exception as e:
                logger.exception(e)
                add_error_message_to_response('An exception error occurred during the report import:%s' % str(e))
                error = True

            # Save the credential to the test
            if cred_form.is_valid():
                if cred_form.cleaned_data['cred_user']:
                    # Select the credential mapping object from the selected list and only allow if the credential is associated with the product
                    cred_user = Cred_Mapping.objects.filter(
                        pk=cred_form.cleaned_data['cred_user'].id,
                        engagement=eid).first()

                    new_f = cred_form.save(commit=False)
                    new_f.test = test
                    new_f.cred_id = cred_user.cred_id
                    new_f.save()

            if not error:
                return HttpResponseRedirect(
                    reverse('view_test', args=(test.id, )))

    prod_id = None
    custom_breadcrumb = None
    title = "Import Scan Results"
    if engagement:
        prod_id = engagement.product.id
        product_tab = Product_Tab(prod_id, title=title, tab="engagements")
        product_tab.setEngagement(engagement)
    else:
        prod_id = pid
        custom_breadcrumb = {"", ""}
        product_tab = Product_Tab(prod_id, title=title, tab="findings")

    if jira_helper.get_jira_project(engagement_or_product):
        jform = JIRAImportScanForm(push_all=push_all_jira_issues, prefix='jiraform')

    form.fields['endpoints'].queryset = Endpoint.objects.filter(product__id=product_tab.product.id)
    form.fields['sonarqube_config'].queryset = Sonarqube_Product.objects.filter(product=product_tab.product)
    return render(request,
        'dojo/import_scan_results.html',
        {'form': form,
         'product_tab': product_tab,
         'engagement_or_product': engagement_or_product,
         'custom_breadcrumb': custom_breadcrumb,
         'title': title,
         'cred_form': cred_form,
         'jform': jform,
         'scan_types': get_choices(),
         })


@user_is_authorized(Engagement, Permissions.Engagement_Edit, 'eid', 'staff')
def close_eng(request, eid):
    eng = Engagement.objects.get(id=eid)
    close_engagement(eng)
    messages.add_message(
        request,
        messages.SUCCESS,
        'Engagement closed successfully.',
        extra_tags='alert-success')
    create_notification(event='close_engagement',
                        title='Closure of %s' % eng.name,
                        description='The engagement "%s" was closed' % (eng.name),
                        engagement=eng, url=reverse('engagment_all_findings', args=(eng.id, ))),
    return HttpResponseRedirect(reverse("view_engagements", args=(eng.product.id, )))


@user_is_authorized(Engagement, Permissions.Engagement_Edit, 'eid', 'staff')
def reopen_eng(request, eid):
    eng = Engagement.objects.get(id=eid)
    reopen_engagement(eng)
    messages.add_message(
        request,
        messages.SUCCESS,
        'Engagement reopened successfully.',
        extra_tags='alert-success')
    create_notification(event='other',
                        title='Reopening of %s' % eng.name,
                        engagement=eng,
                        description='The engagement "%s" was reopened' % (eng.name),
                        url=reverse('view_engagement', args=(eng.id, ))),
    return HttpResponseRedirect(reverse("view_engagements", args=(eng.product.id, )))


"""
Greg:
status: in production
method to complete checklists from the engagement view
"""


@user_is_authorized(Engagement, Permissions.Engagement_Edit, 'eid', 'staff')
def complete_checklist(request, eid):
    eng = get_object_or_404(Engagement, id=eid)
    try:
        checklist = Check_List.objects.get(engagement=eng)
    except:
        checklist = None
        pass

    add_breadcrumb(
        parent=eng,
        title="Complete checklist",
        top_level=False,
        request=request)
    if request.method == 'POST':
        tests = Test.objects.filter(engagement=eng)
        findings = Finding.objects.filter(test__in=tests).all()
        form = CheckForm(request.POST, instance=checklist, findings=findings)
        if form.is_valid():
            cl = form.save(commit=False)
            try:
                check_l = Check_List.objects.get(engagement=eng)
                cl.id = check_l.id
                cl.save()
                form.save_m2m()
            except:
                cl.engagement = eng
                cl.save()
                form.save_m2m()
                pass
            messages.add_message(
                request,
                messages.SUCCESS,
                'Checklist saved.',
                extra_tags='alert-success')
            return HttpResponseRedirect(
                reverse('view_engagement', args=(eid, )))
    else:
        tests = Test.objects.filter(engagement=eng)
        findings = Finding.objects.filter(test__in=tests).all()
        form = CheckForm(instance=checklist, findings=findings)

    product_tab = Product_Tab(eng.product.id, title="Checklist", tab="engagements")
    product_tab.setEngagement(eng)
    return render(request, 'dojo/checklist.html', {
        'form': form,
        'product_tab': product_tab,
        'eid': eng.id,
        'findings': findings,
    })


@user_is_authorized(Engagement, Permissions.Risk_Acceptance, 'eid', 'staff')
def add_risk_acceptance(request, eid, fid=None):
    eng = get_object_or_404(Engagement, id=eid)
    finding = None
    if fid:
        finding = get_object_or_404(Finding, id=fid)

    if not eng.product.enable_full_risk_acceptance:
        raise PermissionDenied()

    if request.method == 'POST':
        form = RiskAcceptanceForm(request.POST, request.FILES)
        if form.is_valid():
            # first capture notes param as it cannot be saved directly as m2m
            notes = None
            if form.cleaned_data['notes']:
                notes = Notes(
                    entry=form.cleaned_data['notes'],
                    author=request.user,
                    date=timezone.now())
                notes.save()

            del form.cleaned_data['notes']

            try:
                # we sometimes see a weird exception here, but are unable to reproduce.
                # we add some logging in case it happens
                risk_acceptance = form.save()
            except Exception as e:
                logger.debug(vars(request.POST))
                logger.error(vars(form))
                logger.exception(e)
                raise

            # attach note to risk acceptance object now in database
            if notes:
                risk_acceptance.notes.add(notes)

            eng.risk_acceptance.add(risk_acceptance)

            findings = form.cleaned_data['accepted_findings']

            risk_acceptance = ra_helper.add_findings_to_risk_acceptance(risk_acceptance, findings)

            messages.add_message(
                request,
                messages.SUCCESS,
                'Risk acceptance saved.',
                extra_tags='alert-success')

            return redirect_to_return_url_or_else(request, reverse('view_engagement', args=(eid, )))
    else:
        risk_acceptance_title_suggestion = 'Accept: %s' % finding
        form = RiskAcceptanceForm(initial={'owner': request.user, 'name': risk_acceptance_title_suggestion})

    finding_choices = Finding.objects.filter(duplicate=False, test__engagement=eng).filter(NOT_ACCEPTED_FINDINGS_QUERY).order_by('title')

    form.fields['accepted_findings'].queryset = finding_choices
    if fid:
        form.fields['accepted_findings'].initial = {fid}
    product_tab = Product_Tab(eng.product.id, title="Risk Acceptance", tab="engagements")
    product_tab.setEngagement(eng)

    return render(request, 'dojo/add_risk_acceptance.html', {
                  'eng': eng,
                  'product_tab': product_tab,
                  'form': form
                  })


@user_is_authorized(Engagement, Permissions.Engagement_View, 'eid', 'view')
def view_risk_acceptance(request, eid, raid):
    return view_edit_risk_acceptance(request, eid=eid, raid=raid, edit_mode=False)


@user_is_authorized(Engagement, Permissions.Risk_Acceptance, 'eid', 'staff')
def edit_risk_acceptance(request, eid, raid):
    return view_edit_risk_acceptance(request, eid=eid, raid=raid, edit_mode=True)


# will only be called by view_risk_acceptance and edit_risk_acceptance
def view_edit_risk_acceptance(request, eid, raid, edit_mode=False):
    risk_acceptance = get_object_or_404(Risk_Acceptance, pk=raid)
    eng = get_object_or_404(Engagement, pk=eid)

    if edit_mode and not eng.product.enable_full_risk_acceptance:
        raise PermissionDenied()

    risk_acceptance_form = None
    errors = False

    if request.method == 'POST':
        # deleting before instantiating the form otherwise django messes up and we end up with an empty path value
        if len(request.FILES) > 0:
            logger.debug('new proof uploaded')
            risk_acceptance.path.delete()

        if 'decision' in request.POST:
            old_expiration_date = risk_acceptance.expiration_date
            risk_acceptance_form = EditRiskAcceptanceForm(request.POST, request.FILES, instance=risk_acceptance)
            errors = errors or not risk_acceptance_form.is_valid()
            if not errors:
                logger.debug('path: %s', risk_acceptance_form.cleaned_data['path'])

                risk_acceptance_form.save()

                if risk_acceptance.expiration_date != old_expiration_date:
                    # risk acceptance was changed, check if risk acceptance needs to be reinstated and findings made accepted again
                    ra_helper.reinstate(risk_acceptance, old_expiration_date)

                messages.add_message(
                    request,
                    messages.SUCCESS,
                    'Risk Acceptance saved successfully.',
                    extra_tags='alert-success')

        if 'entry' in request.POST:
            note_form = NoteForm(request.POST)
            errors = errors or not note_form.is_valid()
            if not errors:
                new_note = note_form.save(commit=False)
                new_note.author = request.user
                new_note.date = timezone.now()
                new_note.save()
                risk_acceptance.notes.add(new_note)
                messages.add_message(
                    request,
                    messages.SUCCESS,
                    'Note added successfully.',
                    extra_tags='alert-success')

        if 'delete_note' in request.POST:
            note = get_object_or_404(Notes, pk=request.POST['delete_note_id'])
            if note.author.username == request.user.username:
                risk_acceptance.notes.remove(note)
                note.delete()
                messages.add_message(
                    request,
                    messages.SUCCESS,
                    'Note deleted successfully.',
                    extra_tags='alert-success')
            else:
                messages.add_message(
                    request,
                    messages.ERROR,
                    "Since you are not the note's author, it was not deleted.",
                    extra_tags='alert-danger')

        if 'remove_finding' in request.POST:
            finding = get_object_or_404(
                Finding, pk=request.POST['remove_finding_id'])

            ra_helper.remove_finding_from_risk_acceptance(risk_acceptance, finding)

            messages.add_message(
                request,
                messages.SUCCESS,
                'Finding removed successfully from risk acceptance.',
                extra_tags='alert-success')

        if 'replace_file' in request.POST:
            replace_form = ReplaceRiskAcceptanceProofForm(
                request.POST, request.FILES, instance=risk_acceptance)

            errors = errors or not replace_form.is_valid()
            if not errors:
                replace_form.save()

                messages.add_message(
                    request,
                    messages.SUCCESS,
                    'New Proof uploaded successfully.',
                    extra_tags='alert-success')
            else:
                logger.error(replace_form.errors)

        if 'add_findings' in request.POST:
            add_findings_form = AddFindingsRiskAcceptanceForm(
                request.POST, request.FILES, instance=risk_acceptance)

            errors = errors or not add_findings_form.is_valid()
            if not errors:
                findings = add_findings_form.cleaned_data['accepted_findings']

                ra_helper.add_findings_to_risk_acceptance(risk_acceptance, findings)

                messages.add_message(
                    request,
                    messages.SUCCESS,
                    'Finding%s added successfully.' % ('s' if len(findings) > 1
                                                       else ''),
                    extra_tags='alert-success')

        if not errors:
            logger.debug('redirecting to return_url')
            return redirect_to_return_url_or_else(request, reverse("view_risk_acceptance", args=(eid, raid)))
        else:
            logger.error('errors found')

    else:
        if edit_mode:
            risk_acceptance_form = EditRiskAcceptanceForm(instance=risk_acceptance)

    note_form = NoteForm()
    replace_form = ReplaceRiskAcceptanceProofForm(instance=risk_acceptance)
    add_findings_form = AddFindingsRiskAcceptanceForm(instance=risk_acceptance)

    accepted_findings = risk_acceptance.accepted_findings.order_by('numerical_severity')
    fpage = get_page_items(request, accepted_findings, 15)

    unaccepted_findings = Finding.objects.filter(test__in=eng.test_set.all()) \
        .exclude(id__in=accepted_findings).order_by("title")
    add_fpage = get_page_items(request, unaccepted_findings, 10, 'apage')
    # on this page we need to add unaccepted findings as possible findings to add as accepted
    add_findings_form.fields[
        "accepted_findings"].queryset = add_fpage.object_list

    product_tab = Product_Tab(eng.product.id, title="Risk Acceptance", tab="engagements")
    product_tab.setEngagement(eng)
    return render(
        request, 'dojo/view_risk_acceptance.html', {
            'risk_acceptance': risk_acceptance,
            'engagement': eng,
            'product_tab': product_tab,
            'accepted_findings': fpage,
            'notes': risk_acceptance.notes.all(),
            'eng': eng,
            'edit_mode': edit_mode,
            'risk_acceptance_form': risk_acceptance_form,
            'note_form': note_form,
            'replace_form': replace_form,
            'add_findings_form': add_findings_form,
            # 'show_add_findings_form': len(unaccepted_findings),
            'request': request,
            'add_findings': add_fpage,
            'return_url': get_return_url(request),
        })


@user_is_authorized(Engagement, Permissions.Risk_Acceptance, 'eid', 'staff')
def expire_risk_acceptance(request, eid, raid):
    risk_acceptance = get_object_or_404(prefetch_for_expiration(Risk_Acceptance.objects.all()), pk=raid)
    eng = get_object_or_404(Engagement, pk=eid)

    ra_helper.expire_now(risk_acceptance)

    return redirect_to_return_url_or_else(request, reverse("view_risk_acceptance", args=(eid, raid)))


@user_is_authorized(Engagement, Permissions.Risk_Acceptance, 'eid', 'staff')
def reinstate_risk_acceptance(request, eid, raid):
    risk_acceptance = get_object_or_404(prefetch_for_expiration(Risk_Acceptance.objects.all()), pk=raid)
    eng = get_object_or_404(Engagement, pk=eid)

    if not eng.product.enable_full_risk_acceptance:
        raise PermissionDenied()

    ra_helper.reinstate(risk_acceptance, risk_acceptance.expiration_date)

    return redirect_to_return_url_or_else(request, reverse("view_risk_acceptance", args=(eid, raid)))


@user_is_authorized(Engagement, Permissions.Risk_Acceptance, 'eid', 'staff')
def delete_risk_acceptance(request, eid, raid):
    risk_acceptance = get_object_or_404(Risk_Acceptance, pk=raid)
    eng = get_object_or_404(Engagement, pk=eid)

    ra_helper.delete(eng, risk_acceptance)

    messages.add_message(
        request,
        messages.SUCCESS,
        'Risk acceptance deleted successfully.',
        extra_tags='alert-success')
    return HttpResponseRedirect(reverse("view_engagement", args=(eng.id, )))


@user_is_authorized(Engagement, Permissions.Engagement_View, 'eid', 'view')
def download_risk_acceptance(request, eid, raid):
    import mimetypes

    mimetypes.init()

    risk_acceptance = get_object_or_404(Risk_Acceptance, pk=raid)

    response = StreamingHttpResponse(
        FileIterWrapper(
            open(settings.MEDIA_ROOT + "/" + risk_acceptance.path.name, mode='rb')))
    response['Content-Disposition'] = 'attachment; filename="%s"' \
                                      % risk_acceptance.filename()
    mimetype, encoding = mimetypes.guess_type(risk_acceptance.path.name)
    response['Content-Type'] = mimetype
    return response


"""
Greg
status: in production
Upload a threat model at the engagement level. Threat models are stored
under media folder
"""


@user_is_authorized(Engagement, Permissions.Engagement_Edit, 'eid', 'staff')
def upload_threatmodel(request, eid):
    eng = Engagement.objects.get(id=eid)
    add_breadcrumb(
        parent=eng,
        title="Upload a threat model",
        top_level=False,
        request=request)

    if request.method == 'POST':
        form = UploadThreatForm(request.POST, request.FILES)
        if form.is_valid():
            handle_uploaded_threat(request.FILES['file'], eng)
            eng.progress = 'other'
            eng.threat_model = True
            eng.save()
            messages.add_message(
                request,
                messages.SUCCESS,
                'Threat model saved.',
                extra_tags='alert-success')
            return HttpResponseRedirect(
                reverse('view_engagement', args=(eid, )))
    else:
        form = UploadThreatForm()
    product_tab = Product_Tab(eng.product.id, title="Upload Threat Model", tab="engagements")
    return render(request, 'dojo/up_threat.html', {
        'form': form,
        'product_tab': product_tab,
        'eng': eng,
    })


@user_is_authorized(Engagement, Permissions.Engagement_View, 'eid', 'staff')
def view_threatmodel(request, eid):
    eng = get_object_or_404(Engagement, pk=eid)
    response = FileResponse(open(eng.tmodel_path, 'rb'))
    return response


@user_is_authorized(Engagement, Permissions.Engagement_View, 'eid', 'staff')
def engagement_ics(request, eid):
    eng = get_object_or_404(Engagement, id=eid)
    start_date = datetime.combine(eng.target_start, datetime.min.time())
    end_date = datetime.combine(eng.target_end, datetime.max.time())
    uid = "dojo_eng_%d_%d" % (eng.id, eng.product.id)
    cal = get_cal_event(
        start_date, end_date,
        "Engagement: %s (%s)" % (eng.name, eng.product.name),
        "Set aside for engagement %s, on product %s.  Additional detail can be found at %s"
        % (eng.name, eng.product.name,
           request.build_absolute_uri(
               (reverse("view_engagement", args=(eng.id, ))))), uid)
    output = cal.serialize()
    response = HttpResponse(content=output)
    response['Content-Type'] = 'text/calendar'
    response['Content-Disposition'] = 'attachment; filename=%s.ics' % eng.name
    return response
