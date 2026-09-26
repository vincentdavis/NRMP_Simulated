from django.contrib.auth import views as auth_views
from django.urls import path, reverse_lazy

from . import account_views, views

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
    path("documentation/", views.documentation, name="documentation"),
    # Simulations CRUD & actions
    path("simulations/", views.simulation_list, name="simulation_list"),
    path("simulations/new/", views.simulation_create, name="simulation_create"),
    path("simulations/<int:pk>/", views.simulation_manage, name="simulation_manage"),
    path("simulations/<int:pk>/delete/", views.simulation_delete, name="simulation_delete"),
    # Steps (HTMX): create/delete populations, initialize interviews, compute ratings (see views.STEPS)
    path("simulations/<int:pk>/steps/<slug:step>/", views.simulation_step, name="simulation_step"),
    # Actions (HTMX)
    path(
        "simulations/<int:pk>/upload-applicants/", views.simulation_upload_students, name="simulation_upload_students"
    ),
    path("simulations/<int:pk>/upload-programs/", views.simulation_upload_schools, name="simulation_upload_schools"),
    # (Re)Create actions
    # Downloads
    path(
        "simulations/<int:pk>/download-applicants/",
        views.simulation_download_students,
        name="simulation_download_students",
    ),
    path(
        "simulations/<int:pk>/download-programs/", views.simulation_download_schools, name="simulation_download_schools"
    ),
    path(
        "simulations/<int:pk>/download-interviews/",
        views.simulation_download_interviews,
        name="simulation_download_interviews",
    ),
    # Lists
    path("simulations/<int:pk>/applicants/", views.simulation_students, name="simulation_students"),
    path("simulations/<int:pk>/programs/", views.simulation_schools, name="simulation_schools"),
    path("simulations/<int:pk>/interviews/", views.simulation_interviews, name="simulation_interviews"),
    # Interview actions
]
