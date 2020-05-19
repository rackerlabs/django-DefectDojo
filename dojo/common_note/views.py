import logging

from django.contrib.auth.decorators import user_passes_test
from django.shortcuts import render, get_object_or_404
from django.contrib import messages
from django.urls import reverse
from django.http import HttpResponseRedirect

from dojo.finding.views import find_available_notetypes
from dojo.forms import CommonNoteForm, NoteForm, FindingNoteForm
from dojo.models import Note_Type, CommonNote, Dojo_User, NoteHistory
from dojo.filters import NoteTypesFilter
from dojo.utils import get_page_items, add_breadcrumb, process_notifications

logger = logging.getLogger(__name__)
deduplicationLogger = logging.getLogger("dojo.specific-loggers.deduplication")


@user_passes_test(lambda u: u.is_superuser)
def common_note(request):
    initial_queryset = CommonNote.objects.all().order_by('id')
    name_words = [common_note1.scanner for common_note1 in
                  initial_queryset]
    cnl = NoteTypesFilter(request.GET, queryset=initial_queryset)
    cns = get_page_items(request, cnl.qs, 25)

    add_breadcrumb(title="Common Note List", top_level=True, request=request)

    return render(request, 'dojo/common_note.html', {
        'name': 'Common Note List',
        'metric': False,
        'user': request.user,
        'cns': cns,
        'cnl': cnl,
        'name_words': name_words})


@user_passes_test(lambda u: u.is_superuser)
def add_common_note(request):
    form = CommonNoteForm()

    if request.method == 'POST':
        form = CommonNoteForm(request.POST)

        if form.is_valid():
            common_note_form = form.save(commit=False)
            common_note_form.save()
            messages.add_message(request,
                                 messages.SUCCESS,
                                 'Common Note added successfully.',
                                 extra_tags='alert-success')
            return HttpResponseRedirect(reverse('add_common_note_comment', args=(common_note_form.id,)))

    add_breadcrumb(title="Add Common Note", top_level=False, request=request)

    return render(request, 'dojo/add_common_note.html', {
        'name': 'Add Common Note',
        'metric': False,
        'user': request.user,
        'form': form,
    })


@user_passes_test(lambda u: u.is_superuser)
def add_common_note_comment(request, cnid):
    cn = get_object_or_404(CommonNote, pk=cnid)

    notes = cn.notes.all()
    note_type_activation = Note_Type.objects.filter(is_active=True).count()

    if note_type_activation:
        available_note_types = find_available_notetypes(notes)

    if request.method == 'POST':
        if note_type_activation:
            form = FindingNoteForm(request.POST, available_note_types=available_note_types)
        else:
            form = NoteForm(request.POST)
        if form.is_valid():
            new_note = form.save(commit=False)
            new_note.author = request.user
            new_note.save()
            history = NoteHistory(data=new_note.entry,
                                  time=new_note.date,
                                  current_editor=new_note.author)
            history.save()
            new_note.history.add(history)
            cn.notes.add(new_note)
            cn.save()

            url = request.build_absolute_uri(
                reverse("add_common_note_comment", args=(cn.id,)))
            title = "Common Note: " + cn.title
            process_notifications(request, new_note, url, title)
            messages.add_message(request,
                                 messages.SUCCESS,
                                 'Note saved successfully.',
                                 extra_tags='alert-success')
            return HttpResponseRedirect(
                reverse('add_common_note_comment', args=(cn.id,)))

    else:
        if note_type_activation:
            form = FindingNoteForm(available_note_types=available_note_types)
        else:
            form = NoteForm()

    add_breadcrumb(title="Add Note", top_level=False, request=request)

    return render(request, 'dojo/add_common_note_comment.html', {
        'name': 'Add Common Note',
        'metric': False,
        'user': request.user,
        'form': form,
        'cn': cn,
        'notes': notes
    })


def find_available_common_notes():
    single_note_types = Note_Type.objects.filter(is_single=True, is_active=True).values_list('id', flat=True)
    multiple_note_types = Note_Type.objects.filter(is_single=False, is_active=True).values_list('id', flat=True)
    available_note_types = []

    for note_type_id in multiple_note_types:
        available_note_types.append(note_type_id)

    for note_type_id in single_note_types:
        available_note_types.append(note_type_id)

    queryset = Note_Type.objects.filter(id__in=available_note_types).order_by('-id')
    return queryset


@user_passes_test(lambda u: u.is_superuser)
def edit_common_note(request, cnid):
    cn = get_object_or_404(CommonNote, pk=cnid)
    form = CommonNoteForm(instance=cn)
    notes = cn.notes.all()

    if request.method == 'POST':
        form = CommonNoteForm(request.POST, instance=cn)
        if form.is_valid():
            new_common_note = form.save(commit=False)
            new_common_note.save()

            messages.add_message(request,
                                 messages.SUCCESS,
                                 'Common Note saved successfully.',
                                 extra_tags='alert-success')
            return HttpResponseRedirect(reverse('common_note'))

    add_breadcrumb(title="Edit Common Note", top_level=False, request=request)
    return render(request, 'dojo/edit_common_note.html', {
        'name': 'Edit Common Note',
        'metric': False,
        'user': request.user,
        'form': form,
        'notes': notes,
        'cn': cn})


@user_passes_test(lambda u: u.is_superuser)
def view_common_note(request, cnid):
    common_note1 = get_object_or_404(CommonNote, id=cnid)
    user = request.user
    dojo_user = get_object_or_404(Dojo_User, id=user.id)
    cn_form = CommonNoteForm(request.POST)
    notes = common_note1.notes.all()
    note_type_activation = Note_Type.objects.filter(is_active=True).count()

    if note_type_activation:
        available_note_types = find_available_notetypes(notes)

    form = FindingNoteForm(available_note_types=available_note_types)

    if request.method == 'POST':
        if note_type_activation:
            form = FindingNoteForm(request.POST, available_note_types=available_note_types)
        else:
            form = NoteForm(request.POST)
        if form.is_valid():
            new_note = form.save(commit=False)
            new_note.author = request.user
            new_note.save()
            history = NoteHistory(data=new_note.entry,
                                  time=new_note.date,
                                  current_editor=new_note.author)
            history.save()
            new_note.history.add(history)
            common_note1.notes.add(new_note)
            common_note1.save()

            messages.add_message(
                request,
                messages.SUCCESS,
                'Note saved.',
                extra_tags='alert-success')

            return HttpResponseRedirect(
                reverse('view_common_note', args=(common_note1.id,)))

    add_breadcrumb(title="View Common Note", top_level=False, request=request)

    return render(
        request, 'dojo/view_common_note.html', {
            'dojo_user': dojo_user,
            'user': user,
            'notes': notes,
            'form': cn_form,
            'cn': common_note1,
            'common_note_form': form
        })
