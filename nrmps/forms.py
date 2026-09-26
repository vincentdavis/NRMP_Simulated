from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm
from django.core.exceptions import FieldDoesNotExist
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models as db_models

from .limits import market_size_error
from .models import Simulation, SimulationConfig

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
    """Sign-up form: username, a required email address (unique, ignoring case), optional full name, password."""

    full_name = forms.CharField(max_length=255, required=False, label="Full name")
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


class ValidatorLimitsMixin:
    """Give number inputs the `min`, `max` and `step` attributes implied by the model field.

    Browsers then enforce the same limits as the model validators, so the two cannot drift apart.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            try:
                model_field = self._meta.model._meta.get_field(name)
            except FieldDoesNotExist:  # a form-only field
                continue
            if not isinstance(model_field, db_models.IntegerField | db_models.FloatField):
                continue
            attrs = field.widget.attrs
            for validator in model_field.validators:
                if isinstance(validator, MinValueValidator):
                    attrs["min"] = validator.limit_value
                elif isinstance(validator, MaxValueValidator):
                    attrs["max"] = validator.limit_value
            attrs["step"] = "1" if isinstance(model_field, db_models.IntegerField) else "any"


class SimulationForm(forms.ModelForm):
    """Form for creating and updating Simulations."""

    # Fields that have no effect yet (shown with a "Not used yet" badge).
    planned_fields = ("iterations", "public")

    class Meta:
        model = Simulation
        fields = ("name", "public", "description", "iterations")
        widgets = {"description": forms.Textarea(attrs={"rows": 3})}


class StudentsUploadForm(forms.Form):
    """Upload a CSV of applicants; see `population_csv` for the format and validation."""

    file = forms.FileField(
        label="Applicants CSV",
        help_text="CSV with a header row: name, score, and optionally score_meta and meta_preference (JSON objects).",
        widget=forms.FileInput(attrs={"accept": ".csv,text/csv"}),
    )


class SchoolsUploadForm(forms.Form):
    """Upload a CSV of programs; see `population_csv` for the format and validation."""

    file = forms.FileField(
        label="Programs CSV",
        help_text=(
            "CSV with a header row: name, capacity, score, and optionally score_meta and meta_preference "
            "(JSON objects)."
        ),
        widget=forms.FileInput(attrs={"accept": ".csv,text/csv"}),
    )


class SimulationConfigForm(ValidatorLimitsMixin, forms.ModelForm):
    """Form for creating/updating a SimulationConfig associated with a Simulation.

    The simulation FK is set in the view, not editable here. The two attribute lists are posted as JSON arrays by the
    tag editor and validated by the model field validator (`validate_attribute_list`); invalid lists are rejected,
    never silently replaced.
    """

    def clean(self):
        """Reject markets whose applicants x programs product is above the size limit (decision D4)."""
        cleaned = super().clean()
        applicants = cleaned.get("number_of_applicants")
        programs = cleaned.get("number_of_schools")
        if applicants and programs and (message := market_size_error(applicants, programs)):
            self.add_error("number_of_applicants", message)
        return cleaned

    # Parameters the engine does not use yet (shown with a "Not used yet" badge and collapsed on the page).
    planned_fields = (
        "applicant_interview_limit",
        "applicant_post_interview_rating_error",
        "school_interview_limit",
        "school_post_interview_rating_error",
    )

    class Meta:
        model = SimulationConfig
        labels = {
            "number_of_applicants": "Applicants",
            "number_of_schools": "Programs",
            "applicant_score_mean": "Applicant score mean",
            "applicant_score_stddev": "Applicant score SD",
            "applicant_interview_limit": "Max interviews per applicant",
            "applicant_meta_preference_stddev": "Applicant preference diversity",
            "applicant_meta_scores_stddev": "Applicant attribute spread",
            "applicant_pre_interview_rating_error": "Applicant pre-interview noise",
            "applicant_post_interview_rating_error": "Applicant post-interview noise",
            "school_score_mean": "Program score mean",
            "school_score_stddev": "Program score SD",
            "school_capacity_mean": "Positions per program (mean)",
            "school_capacity_stddev": "Positions per program (SD)",
            "school_interview_limit": "Program interview limit",
            "school_meta_preference_stddev": "Program preference diversity",
            "school_meta_scores_stddev": "Program attribute spread",
            "school_pre_interview_rating_error": "Program pre-interview noise",
            "school_post_interview_rating_error": "Program post-interview noise",
        }
        fields = (
            "number_of_applicants",
            "number_of_schools",
            "applicant_score_mean",
            "applicant_score_stddev",
            "applicant_interview_limit",
            "applicant_meta_preference",
            "applicant_meta_preference_stddev",
            "applicant_meta_scores_stddev",
            "applicant_pre_interview_rating_error",
            "applicant_post_interview_rating_error",
            "school_score_mean",
            "school_score_stddev",
            "school_capacity_mean",
            "school_capacity_stddev",
            "school_interview_limit",
            "school_meta_preference",
            "school_meta_preference_stddev",
            "school_meta_scores_stddev",
            "school_pre_interview_rating_error",
            "school_post_interview_rating_error",
        )
