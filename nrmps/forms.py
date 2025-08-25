from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import get_user_model


User = get_user_model()


class SignupForm(UserCreationForm):
    """Signup form for the custom User model.

    Includes optional full_name field in addition to the standard username and password fields.
    """

    full_name = forms.CharField(max_length=255, required=False, label="Full name")
    email = forms.EmailField(required=False, label="Email")

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "full_name", "email")

    def save(self, commit: bool = True):
        user = super().save(commit=False)
        user.full_name = self.cleaned_data.get("full_name", "")
        email = self.cleaned_data.get("email")
        if email is not None:
            user.email = email
        if commit:
            user.save()
        return user
