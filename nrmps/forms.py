from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm
from django.core.exceptions import FieldDoesNotExist
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models as db_models

from .limits import market_size_error
from .models import Simulation, SimulationConfig

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
        """Save the user, including the optional full name and email."""
        user = super().save(commit=False)
        user.full_name = self.cleaned_data.get("full_name", "")
        email = self.cleaned_data.get("email")
        if email is not None:
            user.email = email
        if commit:
            user.save()
        return user


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

    class Meta:
        model = Simulation
        fields = ("name", "public", "description", "iterations")
        widgets = {
            "name": forms.TextInput(attrs={"class": "input input-bordered w-full"}),
            "description": forms.Textarea(attrs={"class": "textarea textarea-bordered w-full", "rows": 3}),
            "iterations": forms.NumberInput(attrs={"class": "input input-bordered w-full", "min": 1}),
            "public": forms.CheckboxInput(attrs={"class": "checkbox"}),
        }


class StudentsUploadForm(forms.Form):
    """Upload a CSV of applicants; see `population_csv` for the format and validation."""

    file = forms.FileField(
        label="Students CSV",
        help_text="CSV with a header row: name, score, and optionally score_meta and meta_preference (JSON objects).",
        widget=forms.FileInput(attrs={"class": "file-input file-input-bordered w-full"}),
    )


class SchoolsUploadForm(forms.Form):
    """Upload a CSV of programs; see `population_csv` for the format and validation."""

    file = forms.FileField(
        label="Schools CSV",
        help_text=(
            "CSV with a header row: name, capacity, score, and optionally score_meta and meta_preference "
            "(JSON objects)."
        ),
        widget=forms.FileInput(attrs={"class": "file-input file-input-bordered w-full"}),
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

    class Meta:
        model = SimulationConfig
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
        widgets = {
            "applicant_meta_preference": forms.Textarea(
                attrs={"class": "textarea textarea-bordered w-full", "rows": 2, "placeholder": "program_size, prestige"}
            ),
            "school_meta_preference": forms.Textarea(
                attrs={"class": "textarea textarea-bordered w-full", "rows": 2, "placeholder": "board_scores, research"}
            ),
        } | {
            name: forms.NumberInput(attrs={"class": "input input-bordered w-full"})
            for name in (
                "number_of_applicants",
                "number_of_schools",
                "applicant_score_mean",
                "applicant_score_stddev",
                "applicant_interview_limit",
                "applicant_meta_preference_stddev",
                "applicant_meta_scores_stddev",
                "applicant_pre_interview_rating_error",
                "applicant_post_interview_rating_error",
                "school_score_mean",
                "school_score_stddev",
                "school_capacity_mean",
                "school_capacity_stddev",
                "school_interview_limit",
                "school_meta_preference_stddev",
                "school_meta_scores_stddev",
                "school_pre_interview_rating_error",
                "school_post_interview_rating_error",
            )
        }
