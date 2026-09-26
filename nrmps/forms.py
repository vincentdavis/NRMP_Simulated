from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm

from .models import Simulation
from .presets import DEFAULT_PRESET, preset_choices

User = get_user_model()


def _check_email_available(email: str, exclude_user=None) -> str:
    """Return the email, or raise ValidationError if another account uses it (ignoring case)."""
    others = User.objects.filter(email__iexact=email)
    if exclude_user is not None:
        others = others.exclude(pk=exclude_user.pk)
    if others.exists():
        raise forms.ValidationError("Another account already uses this email address.", code="email_taken")
    return email


class SignupForm(UserCreationForm):
    """Sign-up form: username, a required email address (unique, ignoring case), optional full name, password.

    `website` is a honeypot: people never see it (the template hides it), so a value means a bot filled in the form.
    """

    full_name = forms.CharField(max_length=255, required=False, label="Full name")
    website = forms.CharField(
        required=False,
        label="Leave this field empty",
        widget=forms.TextInput(attrs={"autocomplete": "off", "tabindex": "-1"}),
    )
    email = forms.EmailField(
        label="Email",
        help_text="Used to confirm your account and to reset your password. Never shown to other users.",
    )

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "full_name", "email")

    def clean_email(self) -> str:
        """Reject an address another account already uses."""
        return _check_email_available(self.cleaned_data["email"])

    def clean_website(self) -> str:
        """Reject the form if the honeypot field was filled in (without saying why)."""
        if self.cleaned_data.get("website"):
            raise forms.ValidationError("The account could not be created.", code="honeypot")
        return ""

    def save(self, commit: bool = True):
        """Save the user, including the optional full name and email."""
        user = super().save(commit=False)
        user.full_name = self.cleaned_data.get("full_name", "")
        user.email = self.cleaned_data["email"]
        if commit:
            user.save()
        return user


class ProfileForm(forms.ModelForm):
    """Edit the full name and email address. A new address has to be confirmed again."""

    email = forms.EmailField(label="Email", help_text="Changing it sends a new confirmation link.")

    class Meta:
        model = User
        fields = ("full_name", "email")

    def clean_email(self) -> str:
        """Reject an address another account already uses."""
        return _check_email_available(self.cleaned_data["email"], exclude_user=self.instance)


class DeleteAccountForm(forms.Form):
    """Confirm account deletion with the current password."""

    password = forms.CharField(
        label="Your password",
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "current-password"}),
        help_text="Deleting your account also deletes all your simulations. This cannot be undone.",
    )

    def __init__(self, user, *args, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

    def clean_password(self) -> str:
        """Require the account's current password."""
        password = self.cleaned_data["password"]
        if not self.user.check_password(password):
            raise forms.ValidationError("The password is not correct.", code="wrong_password")
        return password


class SimulationForm(forms.ModelForm):
    """Form for creating and updating a simulation's name, description and visibility."""

    # Fields that have no effect yet (shown with a "Not used yet" badge).
    planned_fields = ("public",)

    class Meta:
        model = Simulation
        fields = ("name", "public", "description")
        widgets = {"description": forms.Textarea(attrs={"rows": 3})}


class NewSimulationForm(SimulationForm):
    """The new-simulation form: the simulation's details and the preset its parameters start from."""

    preset = forms.ChoiceField(
        label="Start from",
        choices=preset_choices,
        initial=DEFAULT_PRESET,
        required=False,
        help_text="Every parameter can be changed afterwards.",
        widget=forms.RadioSelect,
    )

    def clean_preset(self) -> str:
        """Return the chosen preset, or the default one when none was chosen."""
        return self.cleaned_data.get("preset") or DEFAULT_PRESET


class PopulationUploadForm(forms.Form):
    """Upload a CSV of applicants or programs; see `population_csv` for the format and validation."""

    file = forms.FileField(
        label="CSV file",
        help_text="A CSV file with a header row, in the format of the sample file.",
        widget=forms.FileInput(attrs={"accept": ".csv,text/csv"}),
    )
