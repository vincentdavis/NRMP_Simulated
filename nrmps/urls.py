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
    ]
)
