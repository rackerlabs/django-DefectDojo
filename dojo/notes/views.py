# Standard library imports
import logging

# Third party imports
from django.contrib import messages
from django.contrib.auth.decorators import user_passes_test
from django.urls import reverse
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, render
from django.core.exceptions import PermissionDenied
from django.utils import timezone


# Local application/library imports
from dojo.forms import DeleteNoteForm, NoteForm, FindingNoteForm
from dojo.models import Notes, Test, Finding, NoteHistory, Note_Type, CommonNote

logger = logging.getLogger(__name__)


@user_passes_test(lambda u: u.is_staff)
def delete_issue(request, id, page, objid):
    note = get_object_or_404(Notes, id=id)
    reverse_url = None
    object_id = None
    if page == "test":
        object = get_object_or_404(Test, id=objid)
        object_id = object.id
        reverse_url = "view_test"
    elif page == "finding":
        object = get_object_or_404(Finding, id=objid)
        object_id = object.id
        reverse_url = "view_finding"
    elif page == "common_notes":
        object = get_object_or_404(CommonNote, id=objid)
        object_id = object.id
        reverse_url = "view_common_note"
    form = DeleteNoteForm(request.POST, instance=note)

    if page is None or str(request.user) != note.author.username and not request.user.is_staff:
        raise PermissionDenied

    if form.is_valid():
        note.delete()
        messages.add_message(request,
                             messages.SUCCESS,
                             'Note deleted.',
                             extra_tags='alert-success')
    else:
        messages.add_message(request,
                             messages.SUCCESS,
                             'Note was not succesfully deleted.',
                             extra_tags='alert-danger')

    return HttpResponseRedirect(reverse(reverse_url, args=(object_id, )))


def edit_issue(request, id, page, objid):
    note = get_object_or_404(Notes, id=id)
    reverse_url = None
    object_id = None

    if page is None or str(request.user) != note.author.username and not request.user.is_staff:
        raise PermissionDenied

    if page == "test":
        object = get_object_or_404(Test, id=objid)
        object_id = object.id
        reverse_url = "view_test"
        note_type_activation = 0
    elif page == "finding":
        object = get_object_or_404(Finding, id=objid)
        object_id = object.id
        reverse_url = "view_finding"
        note_type_activation = Note_Type.objects.filter(is_active=True).count()
        if note_type_activation:
            available_note_types = find_available_notetypes(object, note)
    elif page == "common_notes":
        object = get_object_or_404(CommonNote, id=objid)
        object_id = object.id
        reverse_url = "view_common_note"
        note_type_activation = Note_Type.objects.filter(is_active=True).count()
        if note_type_activation:
            available_note_types = find_available_notetypes(object, note)

    if request.method == 'POST':
        if page == "finding" and note_type_activation:
            form = FindingNoteForm(request.POST, available_note_types=available_note_types, instance=note)
        elif page == "common_notes" and note_type_activation:
            form = FindingNoteForm(request.POST, available_note_types=available_note_types, instance=note)
        else:
            form = NoteForm(request.POST, instance=note)
        if form.is_valid():
            note = form.save(commit=False)
            note.edited = True
            note.editor = request.user
            note.edit_time = timezone.now()
            if page == "finding" and note_type_activation:
                history = NoteHistory(note_type=note.note_type,
                                      data=note.entry,
                                      time=note.edit_time,
                                      current_editor=note.editor)
            elif page == "common_notes" and note_type_activation:
                history = NoteHistory(note_type=note.note_type,
                                      data=note.entry,
                                      time=note.edit_time,
                                      current_editor=note.editor)
            else:
                history = NoteHistory(data=note.entry,
                                      time=note.edit_time,
                                      current_editor=note.editor)
            history.save()
            note.history.add(history)
            note.save()
            object.last_reviewed = note.date
            object.last_reviewed_by = request.user
            object.save()
            form = NoteForm()
            messages.add_message(request,
                                messages.SUCCESS,
                                'Note edited.',
                                extra_tags='alert-success')
            return HttpResponseRedirect(reverse(reverse_url, args=(object_id, )))
        else:
            messages.add_message(request,
                                messages.SUCCESS,
                                'Note was not succesfully edited.',
                                extra_tags='alert-danger')
    else:
        if page == "finding" and note_type_activation:
            form = FindingNoteForm(available_note_types=available_note_types, instance=note)
        elif page == "common_notes" and note_type_activation:
            form = FindingNoteForm(available_note_types=available_note_types, instance=note)
        else:
            form = NoteForm(instance=note)

    return render(
        request, 'dojo/edit_note.html', {
            'note': note,
            'form': form,
            'page': page,
            'objid': objid,
        })


@user_passes_test(lambda u: u.is_staff)
def note_history(request, id, page, objid):
    note = get_object_or_404(Notes, id=id)
    reverse_url = None
    object_id = None

    if page == "test":
        object = get_object_or_404(Test, id=objid)
        object_id = object.id
        reverse_url = "view_test"
    elif page == "finding":
        object = get_object_or_404(Finding, id=objid)
        object_id = object.id
        reverse_url = "view_finding"
    elif page == "common_notes":
        object = get_object_or_404(CommonNote, id=objid)
        object_id = object.id
        reverse_url = "view_common_note"

    history = note.history.all()

    if request.method == 'POST':
        return HttpResponseRedirect(reverse(reverse_url, args=(object_id, )))

    return render(
        request, 'dojo/view_note_history.html', {
            'history': history,
            'note': note,
            'page': page,
            'objid': objid,
        })


def find_available_notetypes(finding, editing_note):
    notes = finding.notes.all()
    single_note_types = Note_Type.objects.filter(is_single=True, is_active=True).values_list('id', flat=True)
    multiple_note_types = Note_Type.objects.filter(is_single=False, is_active=True).values_list('id', flat=True)
    available_note_types = []
    for note_type_id in multiple_note_types:
        available_note_types.append(note_type_id)
    for note_type_id in single_note_types:
        for note in notes:
            if note_type_id == note.note_type_id:
                break
        else:
            available_note_types.append(note_type_id)
    available_note_types.append(editing_note.note_type_id)
    available_note_types = list(set(available_note_types))
    queryset = Note_Type.objects.filter(id__in=available_note_types).order_by('-id')
    return queryset
