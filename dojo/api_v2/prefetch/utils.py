from django.db.models.fields import related


def _is_many_to_many_relation(field):
    """Check if a field specified a many-to-many relationship as defined by django.
    This is the case if the field is an instance of the ManyToManyDescriptor as generated
    by the django framework

    Args:
        field (django.db.models.fields): The field to check

    Returns:
        bool: true if the field is a many-to-many relationship
    """
    return isinstance(field, related.ManyToManyDescriptor)


def _is_one_to_one_relation(field):
    """Check if a field specified a one-to-one relationship as defined by django.
    This is the case if the field is an instance of the ForwardManyToOne as generated
    by the django framework

    Args:
        field (django.db.models.fields): The field to check

    Returns:
        bool: true if the field is a one-to-one relationship
    """
    return isinstance(field, related.ForwardManyToOneDescriptor)


def _get_prefetchable_fields(serializer):
    """Get the fields that are prefetchable according to the serializer description.
    Method mainly used by for automatic schema generation.

    Args:
        serializer (Serializer): [description]
    """

    def _is_field_prefetchable(field):
        return _is_one_to_one_relation(field) or _is_many_to_many_relation(field)

    meta = getattr(serializer, "Meta", None)
    if meta is None:
        return []

    model = getattr(meta, "model", None)
    if model is None:
        return []

    fields = []
    for field_name in dir(model):
        field = getattr(model, field_name)
        if _is_field_prefetchable(field):
            fields.append((field_name, field.field.related_model))

    return fields
