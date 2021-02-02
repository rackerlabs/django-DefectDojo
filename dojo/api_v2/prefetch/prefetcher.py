from rest_framework.serializers import ModelSerializer
from . import utils
import inspect
import sys

# Reduce the scope of search for serializers.
SERIALIZER_DEFS_MODULE = "dojo.api_v2.serializers"


class _Prefetcher:
    @staticmethod
    def _build_serializers():
        """Returns a map model -> serializer where model is a django model and serializer is the corresponding
        serializer used to serialize the model

        Returns:
            dict[model, serializer]: map of model to their serializer
        """

        def _is_model_serializer(obj):
            return inspect.isclass(obj) and issubclass(obj, ModelSerializer)

        serializers = dict()
        # We process all the serializers found in the module SERIALIZER_DEFS_MODULE. We restrict the scope to avoid
        # processing all the classes in the symbol table
        available_serializers = inspect.getmembers(
            sys.modules[SERIALIZER_DEFS_MODULE], _is_model_serializer
        )

        for _, serializer in available_serializers:
            model = serializer.Meta.model
            serializers[model] = serializer
        # We add object->None to have a more uniform processing later on
        serializers[object] = None

        return serializers

    def __init__(self):
        self._serializers = _Prefetcher._build_serializers()
        self._prefetch_data = dict()

    def _find_serializer(self, field_type):
        """Find the best suited serializer for the given type.

        Args:
            field_type (django.db.models.fields): the field type for which we need to find a serializer

        Returns:
            rest_framework.serializers.ModelSerializer: The serializer if one has been found or None
        """
        # If the type is represented in the map then return the serializer
        if field_type in self._serializers:
            return self._serializers[field_type]

        # Otherwise we get the direct parent class and we recursively call the method
        # Note that this process will always terminate has we have a decreasing measure
        # with a lower bound taking the form of the object class which is referenced
        # in our serializers.
        parent_class = field_type.__mro__[1]
        return self._find_serializer(parent_class)

    def _prefetch(self, entry, fields_to_fetch):
        """Apply prefetching for the given field on the given entry

        Args:
            entry (ModelInstance): Instance of a model as returned by a django queryset
            field_to_fetch (list[string]): fields to prefetch
        """
        for field_to_fetch in fields_to_fetch:
            # Get the field from the instance
            field_value = getattr(entry, field_to_fetch, None)
            if field_value is None:
                continue

            # Get the model related to the field
            model_type = getattr(field_value, "model", type(field_value))
            extra_serializer = self._find_serializer(model_type)
            if extra_serializer is None:
                continue

            # Get the concrete field type
            field_meta = getattr(type(entry), field_to_fetch, None)
            # Check if the field represents a many-to-many relationship as we need to instantiate
            # the serializer accordingly
            many = utils._is_many_to_many_relation(field_meta)
            field_data = extra_serializer(many=many).to_representation(field_value)
            # For convenience in processing we store the field data in a list
            field_data_list = field_data if type(field_data) is list else [field_data]

            if field_to_fetch not in self._prefetch_data:
                self._prefetch_data[field_to_fetch] = dict()

            # Should not fail as django always generate an id field
            for data in field_data_list:
                self._prefetch_data[field_to_fetch][data["id"]] = data

    @property
    def prefetched_data(self):
        return self._prefetch_data
