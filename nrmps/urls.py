from django.contrib.auth import views as auth_views
from django.urls import path, reverse_lazy

from . import account_views, help_views, ops_views, run_views, views

app_name = "nrmps"

urlpatterns = [
    path("", views.index, name="index"),
    path("healthz", views.healthz, name="healthz"),
    # Auth routes
    path("login/", auth_views.LoginView.as_view(template_name="registration/login.html"), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("signup/", account_views.signup, name="signup"),
    path(
        "account/password/",
        auth_views.PasswordChangeView.as_view(
            template_name="registration/password_change_form.html",
            success_url=reverse_lazy("nrmps:password_change_done"),
        ),
        name="password_change",
    ),
    path(
        "account/password/done/",
        auth_views.PasswordChangeDoneView.as_view(template_name="registration/password_change_done.html"),
        name="password_change_done",
    ),
    path(
        "account/password/reset/",
        auth_views.PasswordResetView.as_view(
            template_name="registration/password_reset_form.html",
            email_template_name="registration/password_reset_email.txt",
            subject_template_name="registration/password_reset_subject.txt",
            success_url=reverse_lazy("nrmps:password_reset_done"),
        ),
        name="password_reset",
    ),
    path(
        "account/password/reset/sent/",
        auth_views.PasswordResetDoneView.as_view(template_name="registration/password_reset_done.html"),
        name="password_reset_done",
    ),
    path(
        "account/password/reset/<uidb64>/<token>/",
        auth_views.PasswordResetConfirmView.as_view(
            template_name="registration/password_reset_confirm.html",
            success_url=reverse_lazy("nrmps:password_reset_complete"),
        ),
        name="password_reset_confirm",
    ),
    path(
        "account/password/reset/complete/",
        auth_views.PasswordResetCompleteView.as_view(template_name="registration/password_reset_complete.html"),
        name="password_reset_complete",
    ),
    # Account
    path("account/", account_views.account, name="account"),
    path("account/edit/", account_views.account_edit, name="account_edit"),
    path("account/verify/<str:token>/", account_views.verify_email, name="verify_email"),
    path("account/verify-again/", account_views.resend_verification, name="resend_verification"),
    path("account/export/", account_views.account_export, name="account_export"),
    path("account/delete/", account_views.account_delete, name="account_delete"),
    # Pages
    path("contact/", views.contact, name="contact"),
    path("privacy/", views.privacy, name="privacy"),
    path("terms/", views.terms, name="terms"),
    path("help/", help_views.help_index, name="help"),
    path("help/developer/", help_views.developer_reference, name="developer_reference"),
    path("ops/", ops_views.ops, name="ops"),
    path("documentation/", help_views.documentation_redirect, name="documentation"),
    # Simulations
    path("simulations/", views.simulation_list, name="simulation_list"),
    path("simulations/new/", views.simulation_create, name="simulation_create"),
    path("simulations/<int:pk>/", views.simulation_manage, name="simulation_manage"),
    path("simulations/<int:pk>/delete/", views.simulation_delete, name="simulation_delete"),
    path("simulations/<int:pk>/upload/<str:side>/", views.population_upload, name="population_upload"),
    path(
        "simulations/<int:pk>/upload/<str:side>/remove/",
        views.population_upload_remove,
        name="population_upload_remove",
    ),
    # Runs
    path("simulations/<int:pk>/runs/", views.run_start, name="run_start"),
    path("simulations/<int:pk>/runs/status/", views.run_status, name="run_status"),
    path("simulations/<int:pk>/runs/<int:number>/", run_views.run_detail, name="run_detail"),
    path("simulations/<int:pk>/runs/<int:number>/delete/", run_views.run_delete, name="run_delete"),
    path("simulations/<int:pk>/runs/<int:number>/progress/", run_views.run_progress, name="run_progress"),
    path("simulations/<int:pk>/runs/<int:number>/applicants/", run_views.run_applicants, name="run_applicants"),
    path(
        "simulations/<int:pk>/runs/<int:number>/applicants/<int:index>/",
        run_views.run_applicant,
        name="run_applicant",
    ),
    path("simulations/<int:pk>/runs/<int:number>/programs/", run_views.run_programs, name="run_programs"),
    path("simulations/<int:pk>/runs/<int:number>/programs/<int:index>/", run_views.run_program, name="run_program"),
    path(
        "simulations/<int:pk>/runs/<int:number>/download/<str:name>",
        run_views.run_download,
        name="run_download",
    ),
]
