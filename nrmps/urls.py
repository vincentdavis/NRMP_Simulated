from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

app_name = "nrmps"

urlpatterns = (
    [
        path("", views.index, name="index"),
        # Auth routes
        path("login/", auth_views.LoginView.as_view(template_name="registration/login.html"), name="login"),
        path("logout/", auth_views.LogoutView.as_view(), name="logout"),
        path("signup/", views.signup, name="signup"),
        # Pages
        path("account/", views.account, name="account"),
        path("contact/", views.contact, name="contact"),
        path("privacy/", views.privacy, name="privacy"),
        path("terms/", views.terms, name="terms"),
        # Simulations CRUD & actions
        path("simulations/", views.simulation_list, name="simulation_list"),
        path("simulations/new/", views.simulation_create, name="simulation_create"),
        path("simulations/<int:pk>/", views.simulation_manage, name="simulation_manage"),
        path("simulations/<int:pk>/delete/", views.simulation_delete, name="simulation_delete"),
        # Actions (HTMX)
        path("simulations/<int:pk>/delete-students/", views.simulation_delete_students, name="simulation_delete_students"),
        path("simulations/<int:pk>/delete-schools/", views.simulation_delete_schools, name="simulation_delete_schools"),
        path("simulations/<int:pk>/upload-students/", views.simulation_upload_students, name="simulation_upload_students"),
        path("simulations/<int:pk>/upload-schools/", views.simulation_upload_schools, name="simulation_upload_schools"),
        # (Re)Create actions
        path("simulations/<int:pk>/create-students/", views.simulation_create_students, name="simulation_create_students"),
        path("simulations/<int:pk>/create-schools/", views.simulation_create_schools, name="simulation_create_schools"),
        # Downloads
        path("simulations/<int:pk>/download-students/", views.simulation_download_students, name="simulation_download_students"),
        path("simulations/<int:pk>/download-schools/", views.simulation_download_schools, name="simulation_download_schools"),
    ]
)
