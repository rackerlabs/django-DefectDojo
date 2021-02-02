from django import template

register = template.Library()


@register.filter(name="get_notetype_notes_count")
def get_notetype_notes_count(notes):
    notes_without_type = notes.filter(note_type=None).count()
    notes_count = notes.count()
    notes_with_type = notes_count - notes_without_type

    return notes_with_type
