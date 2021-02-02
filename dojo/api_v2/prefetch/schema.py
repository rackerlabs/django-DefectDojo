from drf_yasg2 import openapi, utils
from .prefetcher import _Prefetcher
from .utils import _get_prefetchable_fields
from ..schema import extra_schema
from ..schema.utils import LazySchemaRef


def get_prefetch_schema(methods, serializer):
    """Return a composable swagger schema that contains in the query the fields that can be prefetch from the model
    supported by the serializer and in the reponse the structure of these fields in a new top-level attribute
    named prefetch.

    Returns:
        ComposableSchema: A swagger schema
    """
    prefetcher = _Prefetcher()
    fields = _get_prefetchable_fields(serializer())

    field_to_serializer = dict(
        [(name, prefetcher._find_serializer(field)) for name, field in fields]
    )
    fields_to_refname = dict(
        [
            (name, utils.get_serializer_ref_name(serializer()))
            for name, serializer in field_to_serializer.items()
        ]
    )
    fields_name = [name for name, _ in fields]

    # New openapi parameter corresponding to the prefetchable fields
    prefetch_params = [
        openapi.Parameter(
            "prefetch",
            in_=openapi.IN_QUERY,
            required=False,
            type=openapi.TYPE_ARRAY,
            items=openapi.Items(type=openapi.TYPE_STRING, enum=fields_name),
        )
    ]

    additional_props = dict(
        [
            (
                name,
                openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    read_only=True,
                    additional_properties=LazySchemaRef(fields_to_refname[name], True),
                ),
            )
            for name in fields_name
        ]
    )
    prefetch_response = {
        "200": {
            "prefetch": openapi.Schema(
                type=openapi.TYPE_OBJECT, properties=additional_props
            )
        }
    }

    schema = extra_schema.IdentitySchema()
    for method in methods:
        schema = schema.composeWith(
            extra_schema.ExtraParameters(method, prefetch_params)
        )
        schema = schema.composeWith(
            extra_schema.ExtraResponseField(method, prefetch_response)
        )

    return schema
