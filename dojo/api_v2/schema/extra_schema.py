from drf_yasg2.inspectors.view import SwaggerAutoSchema
from drf_yasg2.openapi import resolve_ref, Schema
from .utils import resolve_lazy_ref
import copy


class ComposableSchema:
    """A composable schema defines a transformation on drf_yasg2 Operation. These
    schema can then be composed with another composable schema using the composeWith method
    yielding a new composable schema whose transformation is defined as the function composition
    of the transformation of the two source schema.
    """

    def transform_operation(self, operation, resolver):
        """Defines an operation transformation

        Args:
            operation (Operation): the operation to transform
            resolver (Resolver): the schema refs resolver
        """
        pass

    def composeWith(self, schema):
        """Allow two schema to be composed into a new schema.
        Given the caller schema 'self' and another schema 'schema',
        this operation yields a new composable schema whose transform_operation
        if defined as
            transform_operation(op, res) = schema.transform_operation(self.transform_operation(op, res), res)

        Args:
            schema (ComposableSchema): The schema to compose with

        Returns:
            ComposableSchema: the newly composed schema
        """
        op = self.transform_operation

        class _Wrapper(ComposableSchema):
            def transform_operation(self, operation, resolver):
                return schema.transform_operation(op(operation, resolver), resolver)

        return _Wrapper()

    def to_schema(self):
        """Convert the composable schema into a SwaggerAutoSchema that
        can be used with the drf_yasg library code

        Returns:
            SwaggerAutoSchema: the swagger auto schema derived from the composable schema
        """
        op = self.transform_operation

        class _Schema(SwaggerAutoSchema):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)

            def get_operation(self, operation_keys):
                operation = super().get_operation(operation_keys)
                return op(operation, self.components)

        return _Schema


class IdentitySchema(ComposableSchema):
    def transform_operation(self, operation, resolver):
        return operation


class ExtraParameters(ComposableSchema):
    """Define a schema that can add parameters to the operation"""

    def __init__(self, operation_name, extra_parameters, *args, **kwargs):
        """Initialize the schema

        Args:
            operation_name (string): the name of the operation to transform
            extra_parameters (list[Parameter]): list of openapi parameters to add
        """
        super().__init__(*args, **kwargs)
        self._extra_parameters = extra_parameters
        self._operation_name = operation_name

    def transform_operation(self, operation, resolver):
        operation_id = operation["operationId"]
        if not operation_id.endswith(self._operation_name):
            return operation

        for param in self._extra_parameters:
            operation["parameters"].append(resolve_lazy_ref(param, resolver))
        return operation


class ExtraResponseField(ComposableSchema):
    """Define a schema that can add fields to the responses of the operation"""

    def __init__(self, operation_name, extra_fields, *args, **kwargs):
        """Initialize the schema

        Args:
            operation_name (string): the name of the operation to transform
            extra_fields (dict()): description of the fields to add to the responses. The format is
            {
                parameters: list[openapi.Parameter](params1, params2, ...),
                responses: {
                    code1: {
                        field1: openapi.Schema,
                        field2: openapi.Schema,
                        ...
                    },
                    code2: ...
                }
            }
        """
        super().__init__(*args, **kwargs)
        self._extra_fields = extra_fields
        self._operation_name = operation_name

    def transform_operation(self, operation, resolver):
        operation_id = operation["operationId"]
        if not operation_id.endswith(self._operation_name):
            return operation

        responses = operation["responses"]
        for code, params in self._extra_fields.items():
            if code in responses:
                original_schema = responses[code]["schema"]
                schema = (
                    original_schema
                    if type(original_schema) is Schema
                    else resolve_ref(original_schema, resolver)
                )
                schema = copy.deepcopy(schema)

                for name, param in params.items():
                    schema["properties"][name] = resolve_lazy_ref(param, resolver)
                responses[code]["schema"] = schema
        return operation
