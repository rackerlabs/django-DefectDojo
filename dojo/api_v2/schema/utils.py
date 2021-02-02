from drf_yasg2.openapi import SchemaRef, Schema


class LazySchemaRef:
    """Utility class to support SchemaRef definition without knowing the resolver.
    The reference can be evaluated later in the context of a swagger generator
    """

    def __init__(self, schema_name, ignore_unresolved=False):
        # Bind curried version of the SchemaRef init
        self.schema_ref = lambda resolver: SchemaRef(
            resolver, schema_name, ignore_unresolved
        )

    def apply(self, resolver):
        """Resolve the LazySchemaRef with the given resolver

        Args:
            resolver (ReferenceResolver): resolver containing the schema refs

        Returns:
            SchemaRef: the corresponding SchemaRef
        """
        return self.schema_ref(resolver)


def try_apply(obj, resolver):
    """Try to resolve a LazySchemaRef

    Args:
        obj (object): the object to resolve
        resolver (resolver): the resolver to use

    Returns:
        object: the original object if it was not resolve otherwise the resolved LazySchemaRef
    """
    if type(obj) is LazySchemaRef:
        return obj.apply(resolver)
    else:
        return obj


def resolve_lazy_ref(schema, resolver):
    """Recursively evaluate the schema to unbox LazySchemaRef based on the underlying resolvers.

    Args:
        schema (object): the schema to evaluate

    Returns:
        object: the schema without LazySchemaRef
    """
    if type(schema) is not Schema:
        return try_apply(schema, resolver)

    if "properties" in schema:
        for prop_name, prop in schema["properties"].items():
            schema["properties"][prop_name] = resolve_lazy_ref(prop, resolver)
    if "additionalProperties" in schema:
        schema["additionalProperties"] = resolve_lazy_ref(
            schema["additionalProperties"], resolver
        )

    return schema
