from django.contrib.auth import views as auth_views
from django.urls import path, reverse_lazy

from . import views

app_name = "nrmps"

urlpatterns = [
    path("", views.index, name="index"),
    path("healthz", views.healthz, name="healthz"),
    # Auth routes
    path("login/", auth_views.LoginView.as_view(template_name="registration/login.html"), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("signup/", views.signup, name="signup"),
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
    # Pages
    path("account/", views.account, name="account"),
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
    path("simulations/<int:pk>/upload-students/", views.simulation_upload_students, name="simulation_upload_students"),
    path("simulations/<int:pk>/upload-schools/", views.simulation_upload_schools, name="simulation_upload_schools"),
    # (Re)Create actions
    # Downloads
    path(
        "simulations/<int:pk>/download-students/",
        views.simulation_download_students,
        name="simulation_download_students",
    ),
    path(
        "simulations/<int:pk>/download-schools/", views.simulation_download_schools, name="simulation_download_schools"
    ),
    path(
        "simulations/<int:pk>/download-interviews/",
        views.simulation_download_interviews,
        name="simulation_download_interviews",
    ),
    # Lists
    path("simulations/<int:pk>/students/", views.simulation_students, name="simulation_students"),
    path("simulations/<int:pk>/schools/", views.simulation_schools, name="simulation_schools"),
    path("simulations/<int:pk>/interviews/", views.simulation_interviews, name="simulation_interviews"),
    # Interview actions
]
