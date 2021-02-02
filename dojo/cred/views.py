import logging
import os
from django.contrib import messages
from django.contrib.auth.decorators import user_passes_test
from django.urls import reverse
from django.http import HttpResponseRedirect, StreamingHttpResponse
from django.shortcuts import render, get_object_or_404
from django.utils import timezone
from dojo.models import Finding, Product, Engagement, Cred_User, Cred_Mapping, Test
from dojo.utils import add_breadcrumb, Product_Tab
from dojo.forms import CredUserForm, NoteForm, CredMappingFormProd, CredMappingForm

from dojo.utils import dojo_crypto_encrypt, prepare_for_view, FileIterWrapper


logger = logging.getLogger(__name__)


@user_passes_test(lambda u: u.is_staff)
def new_cred(request):
    if request.method == "POST":
        tform = CredUserForm(request.POST)
        if tform.is_valid():
            form_copy = tform.save(commit=False)
            form_copy.password = dojo_crypto_encrypt(tform.cleaned_data["password"])
            form_copy.save()
            messages.add_message(
                request,
                messages.SUCCESS,
                "Credential Successfully Created.",
                extra_tags="alert-success",
            )
            return HttpResponseRedirect(
                reverse(
                    "cred",
                )
            )
    else:
        tform = CredUserForm()
        add_breadcrumb(title="New Credential", top_level=False, request=request)
    return render(request, "dojo/new_cred.html", {"tform": tform})


@user_passes_test(lambda u: u.is_staff)
def all_cred_product(request, pid):
    prod = get_object_or_404(Product, id=pid)
    creds = Cred_Mapping.objects.filter(product=prod).order_by("cred_id__name")

    product_tab = Product_Tab(prod.id, title="Credentials", tab="settings")
    return render(
        request,
        "dojo/view_cred_prod.html",
        {"product_tab": product_tab, "creds": creds, "prod": prod},
    )


@user_passes_test(lambda u: u.is_staff)
def edit_cred(request, ttid):
    tool_config = Cred_User.objects.get(pk=ttid)
    if request.method == "POST":
        tform = CredUserForm(request.POST, request.FILES, instance=tool_config)
        if tform.is_valid():
            form_copy = tform.save(commit=False)
            form_copy.password = dojo_crypto_encrypt(tform.cleaned_data["password"])
            # handle_uploaded_selenium(request.FILES['selenium_script'], tool_config)
            form_copy.save()

            messages.add_message(
                request,
                messages.SUCCESS,
                "Credential Successfully Updated.",
                extra_tags="alert-success",
            )
            return HttpResponseRedirect(
                reverse(
                    "cred",
                )
            )
    else:
        tool_config.password = prepare_for_view(tool_config.password)

        tform = CredUserForm(instance=tool_config)
    add_breadcrumb(
        title="Edit Credential Configuration", top_level=False, request=request
    )

    return render(
        request,
        "dojo/edit_cred.html",
        {
            "tform": tform,
        },
    )


@user_passes_test(lambda u: u.is_staff)
def view_cred_details(request, ttid):
    cred = Cred_User.objects.get(pk=ttid)
    notes = cred.notes.all()
    cred_products = (
        Cred_Mapping.objects.select_related("product")
        .filter(product_id__isnull=False, cred_id=ttid)
        .order_by("product__name")
    )

    if request.method == "POST":
        form = NoteForm(request.POST)

        if form.is_valid():
            new_note = form.save(commit=False)
            new_note.author = request.user
            new_note.date = timezone.now()
            new_note.save()
            cred.notes.add(new_note)
            form = NoteForm()

            messages.add_message(
                request,
                messages.SUCCESS,
                "Note added successfully.",
                extra_tags="alert-success",
            )
    else:
        form = NoteForm()

    add_breadcrumb(title="View", top_level=False, request=request)

    return render(
        request,
        "dojo/view_cred_details.html",
        {"cred": cred, "form": form, "notes": notes, "cred_products": cred_products},
    )


@user_passes_test(lambda u: u.is_staff)
def cred(request):
    confs = Cred_User.objects.all().order_by("name", "environment", "username")
    add_breadcrumb(title="Credential Manager", top_level=True, request=request)
    return render(
        request,
        "dojo/view_cred.html",
        {
            "confs": confs,
        },
    )


@user_passes_test(lambda u: u.is_staff)
def view_cred_product(request, pid, ttid):
    cred = get_object_or_404(Cred_Mapping.objects.select_related("cred_id"), id=ttid)
    notes = cred.cred_id.notes.all()

    if request.method == "POST":
        form = NoteForm(request.POST)

        if form.is_valid():
            new_note = form.save(commit=False)
            new_note.author = request.user
            new_note.date = timezone.now()
            new_note.save()
            cred.cred_id.notes.add(new_note)
            form = NoteForm()
            messages.add_message(
                request,
                messages.SUCCESS,
                "Note added successfully.",
                extra_tags="alert-success",
            )
    else:
        form = NoteForm()

    add_breadcrumb(title="Credential Manager", top_level=False, request=request)
    cred_type = "Product"
    view_link = reverse(
        "view_cred_product",
        args=(
            cred.product.id,
            cred.id,
        ),
    )
    edit_link = reverse(
        "edit_cred_product",
        args=(
            cred.product.id,
            cred.id,
        ),
    )
    delete_link = reverse(
        "delete_cred_product",
        args=(
            cred.product.id,
            cred.id,
        ),
    )

    return render(
        request,
        "dojo/view_cred_all_details.html",
        {
            "cred": cred,
            "form": form,
            "notes": notes,
            "cred_type": cred_type,
            "edit_link": edit_link,
            "delete_link": delete_link,
            "view_link": view_link,
        },
    )


@user_passes_test(lambda u: u.is_staff)
def view_cred_product_engagement(request, eid, ttid):
    cred = get_object_or_404(Cred_Mapping.objects.select_related("cred_id"), id=ttid)
    cred_product = Cred_Mapping.objects.filter(
        cred_id=cred.cred_id.id, product=cred.engagement.product.id
    ).first()
    notes = cred.cred_id.notes.all()

    if request.method == "POST":
        form = NoteForm(request.POST)

        if form.is_valid():
            new_note = form.save(commit=False)
            new_note.author = request.user
            new_note.date = timezone.now()
            new_note.save()
            cred.cred_id.notes.add(new_note)
            form = NoteForm()
            messages.add_message(
                request,
                messages.SUCCESS,
                "Note added successfully.",
                extra_tags="alert-success",
            )
    else:
        form = NoteForm()

    add_breadcrumb(title="Credential Manager", top_level=False, request=request)
    cred_type = "Engagement"
    edit_link = ""
    view_link = reverse(
        "view_cred_product_engagement",
        args=(
            eid,
            cred.id,
        ),
    )
    delete_link = reverse(
        "delete_cred_engagement",
        args=(
            eid,
            cred.id,
        ),
    )

    return render(
        request,
        "dojo/view_cred_all_details.html",
        {
            "cred": cred,
            "form": form,
            "notes": notes,
            "cred_type": cred_type,
            "edit_link": edit_link,
            "delete_link": delete_link,
            "cred_product": cred_product,
        },
    )


@user_passes_test(lambda u: u.is_staff)
def view_cred_engagement_test(request, tid, ttid):
    cred = get_object_or_404(Cred_Mapping.objects.select_related("cred_id"), id=ttid)
    cred_product = Cred_Mapping.objects.filter(
        cred_id=cred.cred_id.id, product=cred.test.engagement.product.id
    ).first()

    notes = cred.cred_id.notes.all()

    if request.method == "POST":
        form = NoteForm(request.POST)

        if form.is_valid():
            new_note = form.save(commit=False)
            new_note.author = request.user
            new_note.date = timezone.now()
            new_note.save()
            cred.cred_id.notes.add(new_note)
            form = NoteForm()
            messages.add_message(
                request,
                messages.SUCCESS,
                "Note added successfully.",
                extra_tags="alert-success",
            )
    else:
        form = NoteForm()

    add_breadcrumb(title="Credential Manager", top_level=False, request=request)
    cred_type = "Test"
    edit_link = None
    view_link = reverse(
        "view_cred_engagement_test",
        args=(
            tid,
            cred.id,
        ),
    )
    delete_link = reverse(
        "delete_cred_test",
        args=(
            tid,
            cred.id,
        ),
    )

    return render(
        request,
        "dojo/view_cred_all_details.html",
        {
            "cred": cred,
            "form": form,
            "notes": notes,
            "cred_type": cred_type,
            "edit_link": edit_link,
            "delete_link": delete_link,
            "cred_product": cred_product,
        },
    )


@user_passes_test(lambda u: u.is_staff)
def view_cred_finding(request, fid, ttid):
    cred = get_object_or_404(Cred_Mapping.objects.select_related("cred_id"), id=ttid)
    cred_product = Cred_Mapping.objects.filter(
        cred_id=cred.cred_id.id, product=cred.finding.test.engagement.product.id
    ).first()

    notes = cred.cred_id.notes.all()

    if request.method == "POST":
        form = NoteForm(request.POST)

        if form.is_valid():
            new_note = form.save(commit=False)
            new_note.author = request.user
            new_note.date = timezone.now()
            new_note.save()
            cred.cred_id.notes.add(new_note)
            form = NoteForm()
            messages.add_message(
                request,
                messages.SUCCESS,
                "Note added successfully.",
                extra_tags="alert-success",
            )
    else:
        form = NoteForm()

    add_breadcrumb(title="Credential Manager", top_level=False, request=request)
    cred_type = "Finding"
    edit_link = None
    view_link = reverse(
        "view_cred_finding",
        args=(
            fid,
            cred.id,
        ),
    )
    delete_link = reverse(
        "delete_cred_finding",
        args=(
            fid,
            cred.id,
        ),
    )

    return render(
        request,
        "dojo/view_cred_all_details.html",
        {
            "cred": cred,
            "form": form,
            "notes": notes,
            "cred_type": cred_type,
            "edit_link": edit_link,
            "delete_link": delete_link,
            "cred_product": cred_product,
        },
    )


@user_passes_test(lambda u: u.is_staff)
def edit_cred_product(request, pid, ttid):
    cred = get_object_or_404(Cred_Mapping.objects.select_related("cred_id"), id=ttid)

    prod = get_object_or_404(Product, pk=pid)
    if request.method == "POST":
        tform = CredMappingFormProd(request.POST, instance=cred)
        if tform.is_valid():
            tform.save()
            messages.add_message(
                request,
                messages.SUCCESS,
                "Credential Successfully Updated.",
                extra_tags="alert-success",
            )
            return HttpResponseRedirect(reverse("all_cred_product", args=(pid,)))
    else:
        tform = CredMappingFormProd(instance=cred)

    product_tab = Product_Tab(prod.id, title="Edit Product Credential", tab="settings")
    return render(
        request,
        "dojo/edit_cred_all.html",
        {"tform": tform, "product_tab": product_tab, "cred_type": "Product"},
    )


@user_passes_test(lambda u: u.is_staff)
def edit_cred_product_engagement(request, eid, ttid):
    cred = get_object_or_404(Cred_Mapping.objects.select_related("cred_id"), id=ttid)
    eng = get_object_or_404(Engagement, pk=eid)

    if request.method == "POST":
        tform = CredMappingForm(request.POST, instance=cred)
        if tform.is_valid():
            tform.save()
            messages.add_message(
                request,
                messages.SUCCESS,
                "Credential Successfully Updated.",
                extra_tags="alert-success",
            )
            return HttpResponseRedirect(reverse("view_engagement", args=(eid,)))
    else:
        tform = CredMappingFormProd(instance=cred)
        tform.fields["cred_id"].queryset = Cred_Mapping.objects.filter(
            product=eng.product
        ).order_by("cred_id")

    add_breadcrumb(
        title="Edit Credential Configuration", top_level=False, request=request
    )

    return render(
        request, "dojo/edit_cred_all.html", {"tform": tform, "cred_type": "Engagement"}
    )


@user_passes_test(lambda u: u.is_staff)
def new_cred_product(request, pid):
    prod = get_object_or_404(Product, pk=pid)
    if request.method == "POST":
        tform = CredMappingFormProd(request.POST)
        if tform.is_valid():
            # Select the credential mapping object from the selected list and only allow if the credential is associated with the product
            cred_user = Cred_Mapping.objects.filter(
                cred_id=tform.cleaned_data["cred_id"].id, product=pid
            ).first()
            message = "Credential already associated."
            status_tag = "alert-danger"

            if cred_user is None:
                prod = Product.objects.get(id=pid)
                new_f = tform.save(commit=False)
                new_f.product = prod
                new_f.save()
                message = "Credential Successfully Updated."
                status_tag = "alert-success"

            messages.add_message(
                request, messages.SUCCESS, message, extra_tags=status_tag
            )
            return HttpResponseRedirect(reverse("all_cred_product", args=(pid,)))
    else:
        tform = CredMappingFormProd()

    product_tab = Product_Tab(pid, title="Add Credential Configuration", tab="settings")

    return render(
        request,
        "dojo/new_cred_product.html",
        {"tform": tform, "pid": pid, "product_tab": product_tab},
    )


@user_passes_test(lambda u: u.is_staff)
def new_cred_product_engagement(request, eid):
    eng = get_object_or_404(Engagement, pk=eid)

    if request.method == "POST":
        tform = CredMappingForm(request.POST)
        tform.fields["cred_user"].queryset = Cred_Mapping.objects.filter(
            product=eng.product
        ).order_by("cred_id")
        if tform.is_valid() and tform.cleaned_data["cred_user"]:
            # Select the credential mapping object from the selected list and only allow if the credential is associated with the product
            cred_user = (
                Cred_Mapping.objects.filter(
                    pk=tform.cleaned_data["cred_user"].id, product=eng.product.id
                )
                .order_by("cred_id")
                .first()
            )
            # search for cred_user and engagement id
            cred_lookup = Cred_Mapping.objects.filter(
                cred_id=cred_user.cred_id, engagement=eng.id
            )

            message = "Credential already associated."
            status_tag = "alert-danger"

            if not cred_user:
                message = "Credential must first be associated with this product."

            if not cred_lookup and cred_user:
                new_f = tform.save(commit=False)
                new_f.engagement = eng
                new_f.cred_id = cred_user.cred_id
                new_f.save()
                message = "Credential Successfully Updated."
                status_tag = "alert-success"

            messages.add_message(
                request, messages.SUCCESS, message, extra_tags=status_tag
            )
            return HttpResponseRedirect(reverse("view_engagement", args=(eid,)))
    else:
        tform = CredMappingForm()
        tform.fields["cred_user"].queryset = Cred_Mapping.objects.filter(
            product=eng.product
        ).order_by("cred_id")

    add_breadcrumb(
        title="Add Credential Configuration", top_level=False, request=request
    )

    return render(
        request,
        "dojo/new_cred_mapping.html",
        {
            "tform": tform,
            "eid": eid,
            "formlink": reverse("new_cred_product_engagement", args=(eid,)),
        },
    )


@user_passes_test(lambda u: u.is_staff)
def new_cred_engagement_test(request, tid):
    test = get_object_or_404(Test, pk=tid)

    if request.method == "POST":
        tform = CredMappingForm(request.POST)
        tform.fields["cred_user"].queryset = Cred_Mapping.objects.filter(
            engagement=test.engagement
        ).order_by("cred_id")
        if tform.is_valid() and tform.cleaned_data["cred_user"]:
            # Select the credential mapping object from the selected list and only allow if the credential is associated with the product
            cred_user = Cred_Mapping.objects.filter(
                pk=tform.cleaned_data["cred_user"].id, engagement=test.engagement.id
            ).first()
            # search for cred_user and test id
            cred_lookup = Cred_Mapping.objects.filter(
                cred_id=cred_user.cred_id, test=test.id
            )

            message = "Credential already associated."
            status_tag = "alert-danger"

            if not cred_user:
                message = "Credential must first be associated with this product."

            if not cred_lookup and cred_user:
                new_f = tform.save(commit=False)
                new_f.test = test
                new_f.cred_id = cred_user.cred_id
                new_f.save()
                message = "Credential Successfully Updated."
                status_tag = "alert-success"

            messages.add_message(
                request, messages.SUCCESS, message, extra_tags=status_tag
            )
            return HttpResponseRedirect(reverse("view_test", args=(tid,)))
    else:
        tform = CredMappingForm()
        tform.fields["cred_user"].queryset = Cred_Mapping.objects.filter(
            engagement=test.engagement
        ).order_by("cred_id")

    add_breadcrumb(
        title="Add Credential Configuration", top_level=False, request=request
    )

    return render(
        request,
        "dojo/new_cred_mapping.html",
        {
            "tform": tform,
            "eid": tid,
            "formlink": reverse("new_cred_engagement_test", args=(tid,)),
        },
    )


@user_passes_test(lambda u: u.is_staff)
def new_cred_finding(request, fid):
    finding = get_object_or_404(Finding, pk=fid)

    if request.method == "POST":
        tform = CredMappingForm(request.POST)
        tform.fields["cred_user"].queryset = Cred_Mapping.objects.filter(
            engagement=finding.test.engagement
        ).order_by("cred_id")

        if tform.is_valid() and tform.cleaned_data["cred_user"]:
            # Select the credential mapping object from the selected list and only allow if the credential is associated with the product
            cred_user = Cred_Mapping.objects.filter(
                pk=tform.cleaned_data["cred_user"].id,
                engagement=finding.test.engagement.id,
            ).first()
            # search for cred_user and test id
            cred_lookup = Cred_Mapping.objects.filter(
                cred_id=cred_user.cred_id, finding=finding.id
            )

            message = "Credential already associated."
            status_tag = "alert-danger"

            if not cred_user:
                message = "Credential must first be associated with this product."

            if not cred_lookup and cred_user:
                new_f = tform.save(commit=False)
                new_f.finding = finding
                new_f.cred_id = cred_user.cred_id
                new_f.save()
                message = "Credential Successfully Updated."
                status_tag = "alert-success"

            messages.add_message(
                request, messages.SUCCESS, message, extra_tags=status_tag
            )
            return HttpResponseRedirect(reverse("view_finding", args=(fid,)))
    else:
        tform = CredMappingForm()
        tform.fields["cred_user"].queryset = Cred_Mapping.objects.filter(
            engagement=finding.test.engagement
        ).order_by("cred_id")

    add_breadcrumb(
        title="Add Credential Configuration", top_level=False, request=request
    )

    return render(
        request,
        "dojo/new_cred_mapping.html",
        {
            "tform": tform,
            "eid": fid,
            "formlink": reverse("new_cred_finding", args=(fid,)),
        },
    )


def delete_cred_controller(request, destination_url, id, ttid):
    cred = None
    try:
        cred = Cred_Mapping.objects.get(pk=ttid)
    except:
        pass
    if request.method == "POST":
        tform = CredMappingForm(request.POST, instance=cred)
        message = ""
        status_tag = ""
        delete_cred = False

        # Determine if the credential can be deleted
        if destination_url == "cred":
            if cred is None:
                delete_cred = True
            else:
                cred_lookup = Cred_Mapping.objects.filter(cred_id=cred.cred_id).exclude(
                    product__isnull=True
                )
                message = "Credential is associated with product(s). Remove the credential from the product(s) before this credential can be deleted."
                if cred_lookup.exists() is False:
                    delete_cred = True
        elif destination_url == "all_cred_product":
            cred_lookup = Cred_Mapping.objects.filter(cred_id=cred.cred_id).exclude(
                engagement__isnull=True
            )
            message = "Credential is associated with engagement(s). Remove the credential from the engagement(s) before this credential can be deleted."
            if cred_lookup.exists() is False:
                delete_cred = True
        elif destination_url == "view_engagement":
            cred_lookup = Cred_Mapping.objects.filter(cred_id=cred.cred_id).exclude(
                test__isnull=True
            )
            message = "Credential is associated with test(s). Remove the test(s) before this credential can be deleted."
            if cred_lookup.exists() is False:
                cred_lookup = Cred_Mapping.objects.filter(cred_id=cred.cred_id).exclude(
                    finding__isnull=True
                )
                message = "Credential is associated with finding(s). Remove the finding(s) before this credential can be deleted."
                if cred_lookup.exists() is False:
                    delete_cred = True
            else:
                if cred_lookup.exists() is False:
                    delete_cred = True
        elif destination_url == "view_test" or destination_url == "view_finding":
            delete_cred = True

        # Allow deletion if no credentials are associated
        if delete_cred is True:
            message = "Credential Successfully Deleted."
            status_tag = "alert-success"
            # check if main cred delete
            if destination_url == "cred":
                cred = Cred_User.objects.get(pk=ttid)
                cred.delete()
            else:
                cred.delete()
        else:
            status_tag = "alert-danger"

        messages.add_message(request, messages.SUCCESS, message, extra_tags=status_tag)

        if destination_url == "cred":
            return HttpResponseRedirect(reverse(destination_url))
        else:
            return HttpResponseRedirect(reverse(destination_url, args=(id,)))
    else:
        tform = CredMappingForm(instance=cred)

    add_breadcrumb(title="Delete Credential", top_level=False, request=request)
    product_tab = None
    if id:
        product_tab = Product_Tab(id, title="Delete Credential Mapping", tab="settings")
    return render(
        request,
        "dojo/delete_cred_all.html",
        {"tform": tform, "product_tab": product_tab},
    )


@user_passes_test(lambda u: u.is_staff)
def delete_cred(request, ttid):
    return delete_cred_controller(request, "cred", 0, ttid)


@user_passes_test(lambda u: u.is_staff)
def delete_cred_product(request, pid, ttid):
    return delete_cred_controller(request, "all_cred_product", pid, ttid)


@user_passes_test(lambda u: u.is_staff)
def delete_cred_engagement(request, eid, ttid):
    return delete_cred_controller(request, "view_engagement", eid, ttid)


@user_passes_test(lambda u: u.is_staff)
def delete_cred_test(request, tid, ttid):
    return delete_cred_controller(request, "view_test", tid, ttid)


@user_passes_test(lambda u: u.is_staff)
def delete_cred_finding(request, fid, ttid):
    return delete_cred_controller(request, "view_finding", fid, ttid)


@user_passes_test(lambda u: u.is_staff)
def view_selenium(request, ttid):
    import mimetypes

    mimetypes.init()
    cred = Cred_Mapping.objects.get(pk=ttid)
    # print(cred.cred_id.selenium_script)
    # mimetype, encoding = mimetypes.guess_type(cred.cred_id.selenium_script)
    response = StreamingHttpResponse(
        FileIterWrapper(open(cred.cred_id.selenium_script))
    )
    fileName, fileExtension = os.path.splitext(cred.cred_id.selenium_script)
    response["Content-Disposition"] = (
        "attachment; filename=selenium_script" + fileExtension
    )
    response["Content-Type"] = mimetypes

    return response
