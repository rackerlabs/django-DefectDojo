from django.db.models import Aggregate, CharField


class Sql_GroupConcat(Aggregate):
    function = "GROUP_CONCAT"
    allow_distinct = True

    def __init__(self, expression, separator, distinct=False, ordering=None, **extra):
        self.separator = separator
        super(Sql_GroupConcat, self).__init__(
            expression,
            distinct="DISTINCT " if distinct else "",
            ordering=" ORDER BY %s" % ordering if ordering is not None else "",
            separator=' SEPARATOR "%s"' % separator,
            output_field=CharField(),
            **extra
        )

    def as_mysql(self, compiler, connection):
        return super().as_sql(
            compiler,
            connection,
            template="%(function)s(%(distinct)s%(expressions)s%(ordering)s%(separator)s)",
            separator=" SEPARATOR '%s'" % self.separator,
        )

    def as_sql(self, compiler, connection, **extra):
        return super().as_sql(
            compiler,
            connection,
            template="%(function)s(%(distinct)s%(expressions)s%(ordering)s)",
            **extra
        )
