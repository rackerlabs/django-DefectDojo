"""
Created on Feb 18, 2015

@author: jay7958
"""
import pickle
from datetime import date

from django.contrib import messages
from django.contrib.auth.decorators import user_passes_test
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import PermissionDenied
from django.urls import reverse
from django.http.response import HttpResponseRedirect, HttpResponse, Http404
from django.shortcuts import render, get_object_or_404
from django.utils.html import escape
from pytz import timezone
from datetime import timedelta
from django.utils import timezone as tz

from dojo.filters import QuestionnaireFilter, QuestionFilter
from dojo.models import Engagement, System_Settings
from dojo.utils import add_breadcrumb, get_page_items
from dojo.forms import (
    Add_Questionnaire_Form,
    Delete_Questionnaire_Form,
    CreateQuestionnaireForm,
    Delete_Eng_Survey_Form,
    EditQuestionnaireQuestionsForm,
    CreateQuestionForm,
    CreateTextQuestionForm,
    AssignUserForm,
    CreateChoiceQuestionForm,
    EditTextQuestionForm,
    EditChoiceQuestionForm,
    AddChoicesForm,
    AddEngagementForm,
    AddGeneralQuestionnaireForm,
    DeleteGeneralQuestionnaireForm,
)
from dojo.models import (
    Answered_Survey,
    Engagement_Survey,
    Answer,
    TextQuestion,
    ChoiceQuestion,
    Choice,
    General_Survey,
    Question,
)
from dojo.user.helper import check_auth_users_list

localtz = timezone("America/Chicago")


@user_passes_test(lambda u: u.is_staff)
def delete_engagement_survey(request, eid, sid):
    engagement = get_object_or_404(Engagement, id=eid)
    survey = get_object_or_404(Answered_Survey, id=sid)

    questions = get_answered_questions(survey=survey, read_only=True)

    form = Delete_Questionnaire_Form(instance=survey)

    if request.method == "POST":
        form = Delete_Questionnaire_Form(request.POST, instance=survey)
        if form.is_valid():
            answers = Answer.objects.filter(
                question__in=[
                    question.id for question in survey.survey.questions.all()
                ],
                answered_survey=survey,
            )
            for answer in answers:
                answer.delete()
            survey.delete()
            messages.add_message(
                request,
                messages.SUCCESS,
                "Questionnaire deleted successfully.",
                extra_tags="alert-success",
            )
            return HttpResponseRedirect(
                reverse("view_engagement", args=(engagement.id,))
            )
        else:
            messages.add_message(
                request,
                messages.ERROR,
                "Unable to delete Questionnaire.",
                extra_tags="alert-danger",
            )
    add_breadcrumb(
        title="Delete " + survey.survey.name + " Questionnaire",
        top_level=False,
        request=request,
    )
    return render(
        request,
        "defectDojo-engagement-survey/delete_questionnaire.html",
        {
            "survey": survey,
            "form": form,
            "engagement": engagement,
            "questions": questions,
        },
    )


def answer_questionnaire(request, eid, sid):
    survey = get_object_or_404(Answered_Survey, id=sid)
    engagement = get_object_or_404(Engagement, id=eid)
    prod = engagement.product
    settings = System_Settings.objects.all()[0]

    if not settings.allow_anonymous_survey_repsonse:
        auth = request.user.is_staff or check_auth_users_list(request.user, prod)
        if not auth:
            messages.add_message(
                request,
                messages.ERROR,
                "You must be logged in to answer questionnaire. Otherwise, enable anonymous response in system settings.",
                extra_tags="alert-danger",
            )
            # will render 403
            raise PermissionDenied

    questions = get_answered_questions(survey=survey, read_only=False)

    if request.method == "POST":
        questions = [
            q.get_form()(
                request.POST or None,
                prefix=str(q.id),
                answered_survey=survey,
                question=q,
                form_tag=False,
            )
            for q in survey.survey.questions.all()
        ]

        questions_are_valid = []

        for question in questions:
            valid = question.is_valid()
            questions_are_valid.append(valid)
            if valid:
                question.save()

        questions_are_valid = all(questions_are_valid)
        if questions_are_valid:
            survey.completed = True
            survey.responder = request.user
            survey.answered_on = date.today()
            survey.save()
            messages.add_message(
                request,
                messages.SUCCESS,
                "Successfully answered, all answers valid.",
                extra_tags="alert-success",
            )
            return HttpResponseRedirect(
                reverse("view_engagement", args=(engagement.id,))
            )
        else:
            messages.add_message(
                request,
                messages.ERROR,
                "Questionnaire has errors, please correct.",
                extra_tags="alert-danger",
            )
    add_breadcrumb(
        title="Answer " + survey.survey.name + " Survey",
        top_level=False,
        request=request,
    )
    return render(
        request,
        "defectDojo-engagement-survey/answer_survey.html",
        {
            "survey": survey,
            "engagement": engagement,
            "questions": questions,
        },
    )


@user_passes_test(lambda u: u.is_staff)
def assign_questionnaire(request, eid, sid):
    survey = get_object_or_404(Answered_Survey, id=sid)
    engagement = get_object_or_404(Engagement, id=eid)
    prod = engagement.product
    auth = request.user.is_staff or check_auth_users_list(request.user, prod)
    if not auth:
        # will render 403
        raise PermissionDenied

    form = AssignUserForm(instance=survey)
    if request.method == "POST":
        form = AssignUserForm(request.POST)
        if form.is_valid():
            user = form.cleaned_data["assignee"]
            survey.assignee = user
            survey.save()
            return HttpResponseRedirect(
                reverse("view_engagement", args=(engagement.id,))
            )
    add_breadcrumb(title="Assign Questionnaire", top_level=False, request=request)
    return render(
        request,
        "defectDojo-engagement-survey/assign_survey.html",
        {
            "survey": survey,
            "form": form,
        },
    )


@user_passes_test(lambda u: u.is_staff)
def view_questionnaire(request, eid, sid):
    survey = get_object_or_404(Answered_Survey, id=sid)
    engagement = get_object_or_404(Engagement, id=eid)

    questions = get_answered_questions(survey=survey, read_only=True)
    add_breadcrumb(
        title=survey.survey.name + " Questionnaire Responses",
        top_level=False,
        request=request,
    )
    return render(
        request,
        "defectDojo-engagement-survey/view_survey.html",
        {
            "survey": survey,
            "user": request.user,
            "engagement": engagement,
            "questions": questions,
            "name": survey.survey.name + " Questionnaire Responses",
        },
    )


def get_answered_questions(survey=None, read_only=False):
    if survey is None:
        return None

    questions = [
        q.get_form()(
            prefix=str(q.id), answered_survey=survey, question=q, form_tag=False
        )
        for q in survey.survey.questions.all()
    ]
    if read_only:
        for question in questions:
            question.fields["answer"].widget.attrs = {
                "readonly": "readonly",
                "disabled": "disabled",
            }

    return questions


@user_passes_test(lambda u: u.is_staff)
def add_questionnaire(request, eid):
    user = request.user
    engagement = get_object_or_404(Engagement, id=eid)
    ids = [
        survey.survey.id
        for survey in Answered_Survey.objects.filter(engagement=engagement)
    ]
    surveys = Engagement_Survey.objects.exclude(id__in=ids)
    form = Add_Questionnaire_Form()
    if request.method == "POST":
        form = Add_Questionnaire_Form(request.POST)
        if form.is_valid():
            survey = form.save(commit=False)
            survey.engagement = engagement
            survey.save()
            messages.add_message(
                request,
                messages.SUCCESS,
                "Questionnaire successfully added, answers pending.",
                extra_tags="alert-success",
            )
            if "respond_survey" in request.POST:
                return HttpResponseRedirect(
                    reverse("answer_questionnaire", args=(eid, survey.id))
                )

            return HttpResponseRedirect(reverse("view_engagement", args=(eid,)))
        else:
            messages.add_message(
                request,
                messages.ERROR,
                "Questionnaire could not be added.",
                extra_tags="alert-danger",
            )
    form.fields["survey"].queryset = surveys
    add_breadcrumb(title="Add Questionnaire", top_level=False, request=request)
    return render(
        request,
        "defectDojo-engagement-survey/add_survey.html",
        {"surveys": surveys, "user": user, "form": form, "engagement": engagement},
    )


@user_passes_test(lambda u: u.is_staff)
def edit_questionnaire(request, sid):
    survey = get_object_or_404(Engagement_Survey, id=sid)
    old_name = survey.name
    old_desc = survey.description
    old_active = survey.active

    form = CreateQuestionnaireForm(instance=survey)
    answered = Answered_Survey.objects.filter(survey=survey)
    if len(answered) > 0:
        messages.add_message(
            request,
            messages.ERROR,
            "This questionnaire already has answered instances. If you change it, the responses may no longer"
            " be valid.",
            extra_tags="alert-info",
        )

    if request.method == "POST":
        form = CreateQuestionnaireForm(request.POST, instance=survey)
        if form.is_valid():
            if (
                survey.name != old_name
                or survey.description != old_desc
                or survey.active != old_active
            ):
                survey = form.save()

                messages.add_message(
                    request,
                    messages.SUCCESS,
                    "Questionnaire successfully updated, you may now add/edit questions.",
                    extra_tags="alert-success",
                )
                return HttpResponseRedirect(reverse("questionnaire", args=(survey.id,)))
            else:
                messages.add_message(
                    request,
                    messages.SUCCESS,
                    "No changes detected, questionnaire not updated.",
                    extra_tags="alert-warning",
                )
            if "add_questions" in request.POST:
                return HttpResponseRedirect(
                    reverse("edit_questionnaire_questions", args=(survey.id,))
                )
        else:
            messages.add_message(
                request,
                messages.ERROR,
                "Please correct any errors displayed below.",
                extra_tags="alert-danger",
            )
    add_breadcrumb(title="Edit Questionnaire", top_level=False, request=request)
    return render(
        request,
        "defectDojo-engagement-survey/create_questionnaire.html",
        {
            "survey": survey,
            "form": form,
            "name": "Edit Questionnaire",
        },
    )


@user_passes_test(lambda u: u.is_staff)
def delete_questionnaire(request, sid):
    survey = get_object_or_404(Engagement_Survey, id=sid)
    form = Delete_Eng_Survey_Form(instance=survey)

    from django.contrib.admin.utils import NestedObjects
    from django.db import DEFAULT_DB_ALIAS

    collector = NestedObjects(using=DEFAULT_DB_ALIAS)
    collector.collect([survey])
    rels = collector.nested()

    if request.method == "POST":
        if "id" in request.POST and str(survey.id) == request.POST["id"]:
            form = Delete_Eng_Survey_Form(request.POST, instance=survey)
            if form.is_valid():
                survey.delete()
                messages.add_message(
                    request,
                    messages.SUCCESS,
                    "Questionnaire and relationships removed.",
                    extra_tags="alert-success",
                )
                return HttpResponseRedirect(reverse("questionnaire"))
    add_breadcrumb(title="Delete Questionnaire", top_level=False, request=request)
    return render(
        request,
        "defectDojo-engagement-survey/delete_questionnaire.html",
        {
            "survey": survey,
            "form": form,
            "rels": rels,
        },
    )


@user_passes_test(lambda u: u.is_staff)
def create_questionnaire(request):
    form = CreateQuestionnaireForm()
    survey = None

    if request.method == "POST":
        form = CreateQuestionnaireForm(request.POST)
        if form.is_valid():
            survey = form.save()

            messages.add_message(
                request,
                messages.SUCCESS,
                "Questionnaire successfully created, you may now add questions.",
                extra_tags="alert-success",
            )
            if "add_questions" in request.POST:
                return HttpResponseRedirect(
                    reverse("edit_questionnaire_questions", args=(survey.id,))
                )
            else:
                return HttpResponseRedirect(reverse("questionnaire"))
        else:
            messages.add_message(
                request,
                messages.ERROR,
                "Please correct any errors displayed below.",
                extra_tags="alert-danger",
            )
    add_breadcrumb(title="Create Questionnaire", top_level=False, request=request)
    return render(
        request,
        "defectDojo-engagement-survey/create_questionnaire.html",
        {
            "survey": survey,
            "form": form,
            "name": "Create Survey",
        },
    )


@user_passes_test(lambda u: u.is_staff)
def edit_questionnaire_questions(request, sid):
    survey = get_object_or_404(Engagement_Survey, id=sid)

    answered_surveys = Answered_Survey.objects.filter(survey=survey)
    reverted = False

    form = EditQuestionnaireQuestionsForm(instance=survey)

    if request.method == "POST":
        form = EditQuestionnaireQuestionsForm(request.POST, instance=survey)

        if form.is_valid():
            form.save()
            for answered_survey in answered_surveys:
                answered_survey.completed = False
                answered_survey.answered_on = None
                answered_survey.save()
                reverted = True

            if reverted:
                messages.add_message(
                    request,
                    messages.SUCCESS,
                    "Answered questionnaires associated with this survey have been set to uncompleted.",
                    extra_tags="alert-warning",
                )
            messages.add_message(
                request,
                messages.SUCCESS,
                "Questionnaire questions successfully saved.",
                extra_tags="alert-success",
            )
            return HttpResponseRedirect(reverse("questionnaire"))
        else:
            messages.add_message(
                request,
                messages.ERROR,
                "Questionnaire questions not saved, please correct any errors displayed below.",
                extra_tags="alert-success",
            )
    add_breadcrumb(
        title="Update Questionnaire Questions", top_level=False, request=request
    )
    return render(
        request,
        "defectDojo-engagement-survey/edit_survey_questions.html",
        {
            "survey": survey,
            "form": form,
            "name": "Update Survey Questions",
        },
    )


@user_passes_test(lambda u: u.is_staff)
def questionnaire(request):
    user = request.user
    surveys = Engagement_Survey.objects.all()
    surveys = QuestionnaireFilter(request.GET, queryset=surveys)
    paged_surveys = get_page_items(request, surveys.qs, 25)
    general_surveys = General_Survey.objects.all()
    for survey in general_surveys:
        survey_exp = survey.expiration
        if survey.expiration < tz.now():
            survey.delete()
    messages.add_message(
        request,
        messages.INFO,
        "Surveys have migrated to core DefectDojo! Please run python3 manage.py migrate_surveys to retrieve data. "
        + "For docker-compose, run `docker ps -a` to find the uwsgi container name then `docker exec -it <conainter_name> ./manage.py migrate_sruveys`",
        extra_tags="alert-info",
    )

    add_breadcrumb(title="All Questionnaires", top_level=True, request=request)
    return render(
        request,
        "defectDojo-engagement-survey/list_surveys.html",
        {
            "surveys": paged_surveys,
            "filtered": surveys,
            "general": general_surveys,
            "name": "All Surveys",
        },
    )


@user_passes_test(lambda u: u.is_staff)
def questions(request):
    user = request.user
    questions = Question.objects.all()
    questions = QuestionFilter(request.GET, queryset=questions)
    paged_questions = get_page_items(request, questions.qs, 25)
    add_breadcrumb(title="All Questions", top_level=False, request=request)
    return render(
        request,
        "defectDojo-engagement-survey/list_questions.html",
        {
            "questions": paged_questions,
            "filtered": questions,
            "name": "All Questions",
        },
    )


@user_passes_test(lambda u: u.is_staff)
def create_question(request):
    error = False
    form = CreateQuestionForm()
    textQuestionForm = CreateTextQuestionForm()
    choiceQuestionFrom = CreateChoiceQuestionForm()
    created_question = None

    if "return" in request.GET:
        return HttpResponseRedirect(reverse("questionnaire"))

    if request.method == "POST":
        form = CreateQuestionForm(request.POST)
        textQuestionForm = CreateTextQuestionForm(request.POST)
        choiceQuestionFrom = CreateChoiceQuestionForm(request.POST)

        if form.is_valid():
            type = form.cleaned_data["type"]

            if type == "text":

                if textQuestionForm.is_valid():
                    created_question = TextQuestion.objects.create(
                        optional=form.cleaned_data["optional"],
                        order=form.cleaned_data["order"],
                        text=form.cleaned_data["text"],
                    )
                    messages.add_message(
                        request,
                        messages.SUCCESS,
                        "Text Question added successfully.",
                        extra_tags="alert-success",
                    )
                else:
                    error = True

            elif type == "choice":

                if choiceQuestionFrom.is_valid():

                    created_question = ChoiceQuestion.objects.create(
                        optional=form.cleaned_data["optional"],
                        order=form.cleaned_data["order"],
                        text=form.cleaned_data["text"],
                        multichoice=choiceQuestionFrom.cleaned_data["multichoice"],
                    )

                    choices_to_process = pickle.loads(
                        choiceQuestionFrom.cleaned_data["answer_choices"]
                    )

                    for c in choices_to_process:
                        if c is not None and len(c) > 0:
                            created_question.choices.add(
                                Choice.objects.get_or_create(label=c)[0]
                            )

                    created_question.save()

                    messages.add_message(
                        request,
                        messages.SUCCESS,
                        "Choice Question added successfully.",
                        extra_tags="alert-success",
                    )
                else:
                    error = True

            if "_popup" in request.GET and not error:
                resp = (
                    '<script type="text/javascript">opener.dismissAddAnotherPopupDojo(window, "%s", "%s");</script>'
                    % (
                        escape(created_question._get_pk_val()),
                        escape(created_question.text),
                    )
                )
                resp += '<script type="text/javascript">window.close();</script>'
                return HttpResponse(resp)
    add_breadcrumb(title="Add Question", top_level=False, request=request)
    return render(
        request,
        "defectDojo-engagement-survey/create_related_question.html",
        {
            "name": "Add Question",
            "form": form,
            "textForm": textQuestionForm,
            "choiceForm": choiceQuestionFrom,
        },
    )


@user_passes_test(lambda u: u.is_staff)
def edit_question(request, qid):
    error = False

    question = get_object_or_404(Question, id=qid)
    survey = Engagement_Survey.objects.filter(questions__in=[question])
    reverted = False

    if survey:
        answered = Answered_Survey.objects.filter(survey__in=survey)
        if answered.count() > 0:
            messages.add_message(
                request,
                messages.ERROR,
                "This question is part of an already answered survey. If you change it, the responses "
                "may no longer be valid.",
                extra_tags="alert-info",
            )

    type = str(ContentType.objects.get_for_model(question))

    if type == "text question":
        form = EditTextQuestionForm(instance=question)
    elif type == "choice question":
        form = EditChoiceQuestionForm(instance=question)
    else:
        raise Http404()

    if request.method == "POST":
        if type == "text question":
            form = EditTextQuestionForm(request.POST, instance=question)
        elif type == "choice question":
            form = EditChoiceQuestionForm(request.POST, instance=question)
        else:
            raise Http404()

        if form.is_valid():
            form.save()

            for answered_survey in answered:
                answered_survey.completed = False
                answered_survey.answered_on = None
                answered_survey.save()
                reverted = True

            if reverted:
                messages.add_message(
                    request,
                    messages.SUCCESS,
                    "Answered surveys associated with this survey have been set to uncompleted.",
                    extra_tags="alert-warning",
                )

            messages.add_message(
                request,
                messages.SUCCESS,
                "Question updated successfully.",
                extra_tags="alert-success",
            )
            return HttpResponseRedirect(reverse("questions"))
    add_breadcrumb(title="Edit Question", top_level=False, request=request)
    return render(
        request,
        "defectDojo-engagement-survey/edit_question.html",
        {"name": "Edit Question", "question": question, "form": form},
    )


@user_passes_test(lambda u: u.is_staff)
def add_choices(request):
    form = AddChoicesForm()
    if request.method == "POST":
        form = AddChoicesForm(request.POST)
        if form.is_valid():
            choice, created = Choice.objects.get_or_create(**form.cleaned_data)
            if created:
                messages.add_message(
                    request,
                    messages.SUCCESS,
                    "Choice added successfully.",
                    extra_tags="alert-success",
                )
            if "_popup" in request.GET:
                resp = ""
                if created:
                    resp = (
                        '<script type="text/javascript">opener.dismissAddAnotherPopupDojo(window, "%s", "%s");</script>'
                        % (escape(choice._get_pk_val()), escape(choice.label))
                    )
                resp += '<script type="text/javascript">window.close();</script>'
                return HttpResponse(resp)
    add_breadcrumb(title="Add Choice", top_level=False, request=request)
    return render(
        request,
        "defectDojo-engagement-survey/add_choices.html",
        {"name": "Add Choice", "form": form},
    )


# Empty questionnaire functions
@user_passes_test(lambda u: u.is_staff)
def add_empty_questionnaire(request):
    user = request.user
    surveys = Engagement_Survey.objects.all()
    form = AddGeneralQuestionnaireForm()
    engagement = None
    if request.method == "POST":
        form = AddGeneralQuestionnaireForm(request.POST)
        if form.is_valid():
            survey = form.save(commit=False)
            survey.generated = tz.now()
            survey.save()
            messages.add_message(
                request,
                messages.SUCCESS,
                "Engagement Created, Questionnaire successfully added, answers pending.",
                extra_tags="alert-success",
            )
            if "respond_survey" in request.POST:
                return HttpResponseRedirect(reverse("dashboard"))

            return HttpResponseRedirect(reverse("questionnaire"))
        else:
            messages.add_message(
                request,
                messages.ERROR,
                "Questionnaire could not be added.",
                extra_tags="alert-danger",
            )
    form.fields["survey"].queryset = surveys
    add_breadcrumb(title="Add Empty Questionnaire", top_level=False, request=request)
    return render(
        request,
        "defectDojo-engagement-survey/add_survey.html",
        {"surveys": surveys, "user": user, "form": form, "engagement": engagement},
    )


@user_passes_test(lambda u: u.is_staff)
def view_empty_survey(request, esid):
    survey = get_object_or_404(Answered_Survey, id=esid)
    engagement = None

    questions = get_answered_questions(survey=survey, read_only=True)
    add_breadcrumb(
        title=survey.survey.name + " Questionnaire Responses",
        top_level=False,
        request=request,
    )
    return render(
        request,
        "defectDojo-engagement-survey/view_survey.html",
        {
            "survey": survey,
            "user": request.user,
            "engagement": engagement,
            "questions": questions,
            "name": survey.survey.name + " Questionnaire Responses",
        },
    )


@user_passes_test(lambda u: u.is_staff)
def delete_empty_questionnaire(request, esid):
    engagement = None
    survey = get_object_or_404(Answered_Survey, id=esid)

    questions = get_answered_questions(survey=survey, read_only=True)

    form = Delete_Questionnaire_Form(instance=survey)

    if request.method == "POST":
        form = Delete_Questionnaire_Form(request.POST, instance=survey)
        if form.is_valid():
            answers = Answer.objects.filter(
                question__in=[
                    question.id for question in survey.survey.questions.all()
                ],
                answered_survey=survey,
            )
            for answer in answers:
                answer.delete()
            survey.delete()
            messages.add_message(
                request,
                messages.SUCCESS,
                "Questionnaire deleted successfully.",
                extra_tags="alert-success",
            )
            return HttpResponseRedirect(reverse("survey"))
        else:
            messages.add_message(
                request,
                messages.ERROR,
                "Unable to delete Questionnaire.",
                extra_tags="alert-danger",
            )
    add_breadcrumb(
        title="Delete " + survey.survey.name + " Questionnaire",
        top_level=False,
        request=request,
    )
    return render(
        request,
        "defectDojo-engagement-survey/delete_questionnaire.html",
        {
            "survey": survey,
            "form": form,
            "engagement": engagement,
            "questions": questions,
        },
    )


@user_passes_test(lambda u: u.is_staff)
def delete_general_questionnaire(request, esid):
    engagement = None
    questions = None
    survey = get_object_or_404(General_Survey, id=esid)

    form = DeleteGeneralQuestionnaireForm(instance=survey)

    if request.method == "POST":
        form = DeleteGeneralQuestionnaireForm(request.POST, instance=survey)
        if form.is_valid():
            survey.delete()
            messages.add_message(
                request,
                messages.SUCCESS,
                "Questionnaire deleted successfully.",
                extra_tags="alert-success",
            )
            return HttpResponseRedirect(reverse("questionnaire"))
        else:
            messages.add_message(
                request,
                messages.ERROR,
                "Unable to delete questionnaire.",
                extra_tags="alert-danger",
            )
    add_breadcrumb(
        title="Delete " + survey.survey.name + " Questionnaire",
        top_level=False,
        request=request,
    )
    return render(
        request,
        "defectDojo-engagement-survey/delete_questionnaire.html",
        {
            "survey": survey,
            "form": form,
            "engagement": engagement,
            "questions": questions,
        },
    )


def answer_empty_survey(request, esid):
    general_survey = get_object_or_404(General_Survey, id=esid)
    engagement_survey = get_object_or_404(
        Engagement_Survey, id=general_survey.survey_id
    )
    engagement, survey = None, None

    settings = System_Settings.objects.all()[0]

    if not settings.allow_anonymous_survey_repsonse:
        auth = request.user.is_staff
        if not auth:
            messages.add_message(
                request,
                messages.ERROR,
                "You must be logged in to answer questionnaire. Otherwise, enable anonymous response in system settings.",
                extra_tags="alert-danger",
            )
            # will render 403
            raise PermissionDenied

    questions = [
        q.get_form()(
            prefix=str(q.id),
            engagement_survey=engagement_survey,
            question=q,
            form_tag=False,
        )
        for q in engagement_survey.questions.all()
    ]

    if request.method == "POST":
        survey = Answered_Survey(survey=engagement_survey)
        survey.save()
        questions = [
            q.get_form()(
                request.POST or None,
                prefix=str(q.id),
                answered_survey=survey,
                question=q,
                form_tag=False,
            )
            for q in survey.survey.questions.all()
        ]

        questions_are_valid = []

        for question in questions:
            valid = question.is_valid()
            questions_are_valid.append(valid)
            if valid:
                question.save()

        questions_are_valid = all(questions_are_valid)
        if questions_are_valid:
            survey.completed = True
            survey.responder = request.user if not request.user.is_anonymous else None
            survey.answered_on = date.today()
            survey.save()
            general_survey.num_responses = general_survey.num_responses + 1
            general_survey.save()
            if request.user.is_anonymous:
                message = "Your responses have been recorded."
            else:
                message = "Successfully answered, all answers valid."

            messages.add_message(
                request, messages.SUCCESS, message, extra_tags="alert-success"
            )
            return HttpResponseRedirect(reverse("dashboard"))
        else:
            messages.add_message(
                request,
                messages.ERROR,
                "Questionnaire has errors, please correct.",
                extra_tags="alert-danger",
            )
    add_breadcrumb(
        title="Answer Empty " + engagement_survey.name + " Questionnaire",
        top_level=False,
        request=request,
    )
    if survey is None:
        survey = engagement_survey
    return render(
        request,
        "defectDojo-engagement-survey/answer_survey.html",
        {
            "survey": survey,
            "engagement": engagement,
            "questions": questions,
        },
    )


def engagement_empty_survey(request, esid):
    survey = get_object_or_404(Answered_Survey, id=esid)
    engagement = None
    settings = System_Settings.objects.all()[0]
    form = AddEngagementForm()

    if not settings.allow_anonymous_survey_repsonse:
        auth = request.user.is_staff
        if not auth:
            messages.add_message(
                request,
                messages.ERROR,
                "You must be logged in to answer questionnaire. Otherwise, enable anonymous response in system settings.",
                extra_tags="alert-danger",
            )
            # will render 403
            raise PermissionDenied

    if request.method == "POST":
        form = AddEngagementForm(request.POST)
        if form.is_valid():
            product = form.cleaned_data.get("product")
            engagement = Engagement(
                product_id=product.id,
                target_start=tz.now().date(),
                target_end=tz.now().date() + timedelta(days=7),
            )
            engagement.save()
            survey.engagement = engagement
            survey.save()
            messages.add_message(
                request,
                messages.SUCCESS,
                "Engagement created and questionnaire successfully linked.",
                extra_tags="alert-success",
            )
            return HttpResponseRedirect(
                reverse("edit_engagement", args=(engagement.id,))
            )
        else:
            messages.add_message(
                request,
                messages.ERROR,
                "Questionnaire could not be added.",
                extra_tags="alert-danger",
            )
    add_breadcrumb(title="Add Empty Questionnaire", top_level=False, request=request)
    return render(
        request, "defectDojo-engagement-survey/add_engagement.html", {"form": form}
    )
