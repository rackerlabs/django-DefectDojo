import re

from django import template
from django import forms


register = template.Library()


def _process_field_attributes(field, attr, process):
    # split attribute name and value from 'attr:value' string
    params = attr.split(":", 1)
    attribute = params[0]
    value = params[1] if len(params) == 2 else ""

    # decorate field.as_widget method with updated attributes
    old_as_widget = field.as_widget

    def as_widget(self, widget=None, attrs=None, only_initial=False):
        attrs = attrs or {}
        process(widget or self.field.widget, attrs, attribute, value)
        return old_as_widget(widget, attrs, only_initial)

    bound_method = type(old_as_widget)
    try:
        field.as_widget = bound_method(as_widget, field, field.__class__)
    except TypeError:  # python 3
        field.as_widget = bound_method(as_widget, field)
    return field


@register.filter
def addcss(field, attr):
    def process(widget, attrs, attribute, value):
        if attrs.get(attribute):
            attrs[attribute] += " " + value
        elif widget.attrs.get(attribute):
            attrs[attribute] = widget.attrs[attribute] + " " + value
        else:
            attrs[attribute] = value

    return _process_field_attributes(field, attr, process)


@register.filter
def is_checkbox(field):
    return isinstance(field.field.widget, forms.CheckboxInput)


@register.filter
def is_multiple_checkbox(field):
    return isinstance(field.field.widget, forms.CheckboxSelectMultiple)


@register.filter
def is_radio(field):
    return isinstance(field.field.widget, forms.RadioSelect)


@register.filter
def is_file(field):
    return isinstance(field.field.widget, forms.FileInput) or isinstance(
        field, forms.ClearableFileInput
    )


@register.filter
def is_text(field):
    return isinstance(field.field.widget, forms.TextInput) or isinstance(
        field.field.widget, forms.Textarea
    )


@register.filter
def sum_dict(d):
    total = 0
    for key, value in list(d.items()):
        total += value
    return total


@register.filter
def nice_title(title):
    pat = re.compile(r"Finding [0-9][0-9][0-9]:*")
    s = pat.split(title, 2)
    try:
        ret = s[1]
        return ret
    except:
        return title
