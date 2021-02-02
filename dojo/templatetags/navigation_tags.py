from django import template
from django.utils.safestring import mark_safe as safe
from django.utils.html import escape


register = template.Library()


@register.simple_tag(takes_context=True)
def query_string_as_hidden(context):
    request = context["request"]
    query_string = request.META["QUERY_STRING"]
    inputs = ""
    if query_string:
        parameters = query_string.split("&")
        for param in parameters:
            parts = param.split("=")
            if len(parts) == 2:
                inputs += (
                    "<input type='hidden' name='"
                    + escape(parts[0])
                    + "' value='"
                    + escape(parts[1])
                    + "'/>"
                )
            else:
                inputs += (
                    "<input type='hidden' name='" + escape(parts[0]) + "' value=''/>"
                )
    return safe(inputs)


@register.simple_tag
def url_replace(request, field="page", value=1):
    if field is None or field == "":
        field = "page"
    dict_ = request.GET.copy()
    dict_[field] = value
    return dict_.urlencode()


@register.simple_tag
def dojo_sort(request, display="Name", value="title", default=None):
    field = "o"
    icon = '<i class="fa fa-sort'
    title = "Click to sort "
    if field in request.GET:
        if value in request.GET[field]:
            if request.GET[field].startswith("-"):
                icon += "-desc"
                title += "ascending"
            else:
                value = "-" + value
                icon += "-asc"
                title += "descending"
        else:
            title += "ascending"
    elif default:
        icon += "-" + default
        if default == "asc":
            value = "-" + value
            title += "descending"
        else:
            title += "ascending"
    else:
        title += "ascending"

    icon += ' dd-sort"></i>'
    dict_ = request.GET.copy()
    dict_[field] = value
    link = (
        '<a title="'
        + title
        + '" href="?'
        + dict_.urlencode()
        + '">'
        + display
        + "&nbsp;"
        + icon
        + "</a>"
    )
    return safe(link)


class PaginationNav(object):
    def __init__(self, page_number=None, display=None, is_current=False):
        self.page_number = page_number
        self.is_current = is_current
        self.display = display or page_number or ""


@register.filter
def paginate(page, adjacent=2):
    numpages = page.paginator.num_pages
    # Don't paginate if there is only one page
    if numpages <= 1:
        return []

    chunkstart = page.number - adjacent
    chunkend = page.number + adjacent
    ellipsis_pre = True
    ellipsis_post = True

    if chunkstart <= 2:
        ellipsis_pre = False
        chunkstart = 1
        chunkend = max(chunkend, adjacent * 2)

    if chunkend >= (numpages - 1):
        ellipsis_post = False
        chunkend = numpages
        chunkstart = min(chunkstart, numpages - (adjacent * 2) + 1)
    if chunkstart <= 2:
        ellipsis_pre = False

    chunkstart = max(chunkstart, 1)
    chunkend = min(chunkend, numpages)

    def create_page_nav(page_idx):
        return PaginationNav(page_idx, is_current=page_idx == page.number)

    # create page navs in 'chunk' (i.e. middle range)
    pages = [create_page_nav(page_idx) for page_idx in range(chunkstart, chunkend + 1)]

    # insert first element and ellipsis if applicable
    if ellipsis_pre:
        pages.insert(0, PaginationNav(display="..."))
        pages.insert(0, create_page_nav(1))

    # append last element and ellipsis if applicable
    if ellipsis_post:
        pages.append(PaginationNav(display="..."))
        pages.append(create_page_nav(page.paginator.num_pages))

    # determine whether we need a 'previous' link and build it
    if page.has_previous():
        pages.insert(0, PaginationNav(page.previous_page_number(), safe("Previous")))

    # determine whether we need a 'next' link and build it
    if page.has_next():
        pages.append(PaginationNav(page.next_page_number(), safe("Next")))

    return pages
