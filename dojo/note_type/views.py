import logging

from django.contrib.auth.decorators import user_passes_test
from django.shortcuts import render, get_object_or_404
from django.contrib import messages
from django.urls import reverse
from django.http import HttpResponseRedirect

from dojo.forms import NoteTypeForm, EditNoteTypeForm, DisableOrEnableNoteTypeForm
from dojo.models import Note_Type
from dojo.filters import NoteTypesFilter
from dojo.utils import get_page_items, add_breadcrumb

logger = logging.getLogger(__name__)


@user_passes_test(lambda u: u.is_superuser)
def note_type(request):
    initial_queryset = Note_Type.objects.all().order_by("name")
    name_words = initial_queryset.values_list("name", flat=True)
    ntl = NoteTypesFilter(request.GET, queryset=initial_queryset)
    nts = get_page_items(request, ntl.qs, 25)
    add_breadcrumb(title="Note Type List", top_level=True, request=request)
    return render(
        request,
        "dojo/note_type.html",
        {
            "name": "Note Type List",
            "metric": False,
            "user": request.user,
            "nts": nts,
            "ntl": ntl,
            "name_words": name_words,
        },
    )


@user_passes_test(lambda u: u.is_superuser)
def edit_note_type(request, ntid):
    nt = get_object_or_404(Note_Type, pk=ntid)
    is_single = nt.is_single
    nt_form = EditNoteTypeForm(instance=nt, is_single=is_single)
    if request.method == "POST" and request.POST.get("edit_note_type"):
        nt_form = EditNoteTypeForm(request.POST, instance=nt, is_single=is_single)
        if nt_form.is_valid():
            nt = nt_form.save()
            messages.add_message(
                request,
                messages.SUCCESS,
                "Note type updated successfully.",
                extra_tags="alert-success",
            )
            return HttpResponseRedirect(reverse("note_type"))

    add_breadcrumb(title="Edit Note Type", top_level=False, request=request)
    return render(
        request,
        "dojo/edit_note_type.html",
        {
            "name": "Edit Note Type",
            "metric": False,
            "user": request.user,
            "nt_form": nt_form,
            "nt": nt,
        },
    )


@user_passes_test(lambda u: u.is_superuser)
def disable_note_type(request, ntid):
    nt = get_object_or_404(Note_Type, pk=ntid)
    nt_form = DisableOrEnableNoteTypeForm(instance=nt)
    if request.method == "POST":
        nt_form = DisableOrEnableNoteTypeForm(request.POST, instance=nt)
        nt.is_active = False
        nt.save()
        messages.add_message(
            request,
            messages.SUCCESS,
            "Note type Disabled successfully.",
            extra_tags="alert-success",
        )
        return HttpResponseRedirect(reverse("note_type"))

    add_breadcrumb(title="Disable Note Type", top_level=False, request=request)
    return render(
        request,
        "dojo/disable_note_type.html",
        {
            "name": "Disable Note Type",
            "metric": False,
            "user": request.user,
            "nt_form": nt_form,
            "nt": nt,
        },
    )


@user_passes_test(lambda u: u.is_superuser)
def enable_note_type(request, ntid):
    nt = get_object_or_404(Note_Type, pk=ntid)
    nt_form = DisableOrEnableNoteTypeForm(instance=nt)
    if request.method == "POST":
        nt_form = DisableOrEnableNoteTypeForm(request.POST, instance=nt)
        nt.is_active = True
        nt.save()
        messages.add_message(
            request,
            messages.SUCCESS,
            "Note type Enabled successfully.",
            extra_tags="alert-success",
        )
        return HttpResponseRedirect(reverse("note_type"))
    add_breadcrumb(title="Enable Note Type", top_level=False, request=request)
    return render(
        request,
        "dojo/enable_note_type.html",
        {
            "name": "Enable Note Type",
            "metric": False,
            "user": request.user,
            "nt_form": nt_form,
            "nt": nt,
        },
    )


@user_passes_test(lambda u: u.is_superuser)
def add_note_type(request):
    form = NoteTypeForm()
    if request.method == "POST":
        form = NoteTypeForm(request.POST)
        if form.is_valid():
            note_type = form.save()
            messages.add_message(
                request,
                messages.SUCCESS,
                "Note Type added successfully.",
                extra_tags="alert-success",
            )
            return HttpResponseRedirect(reverse("note_type"))
    add_breadcrumb(title="Add Note Type", top_level=False, request=request)
    return render(
        request,
        "dojo/add_note_type.html",
        {
            "name": "Add Note Type",
            "metric": False,
            "user": request.user,
            "form": form,
        },
    )
