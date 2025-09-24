import logging
from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm

from .models import Simulation, SimulationConfig

logger = logging.getLogger(__name__)

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
    """Upload CSV for students: expects headers name,score and optional meta fields.

    Optional columns:
    - score_meta: JSON object mapping meta names to values
    """

    file = forms.FileField(
        label="Students CSV",
        help_text="CSV: name, score, [score_meta]",
        widget=forms.FileInput(attrs={"class": "file-input file-input-bordered w-full"})
    )


class SchoolsUploadForm(forms.Form):
    """Upload CSV for schools: expects headers name,capacity,score and optional meta fields.

    Optional columns:
    - score_meta: JSON object mapping meta names to values
    """

    file = forms.FileField(
        label="Schools CSV",
        help_text="CSV: name, capacity, score, [score_meta]",
        widget=forms.FileInput(attrs={"class": "file-input file-input-bordered w-full"})
    )


class SimulationConfigForm(forms.ModelForm):
    """Form for creating/updating a SimulationConfig associated with a Simulation.

    The simulation FK is set in the view, not editable here.

    Notes on JSON/list fields:
    - For list fields, you can enter a JSON array (e.g., ["research", "leadership"]) or a comma-separated list.
    - For dict fields, enter valid JSON (e.g., {"research": 0.2, "leadership": 0.1}).
    """

    # Optional helpers to accept comma-separated values for list JSONFields

    def clean_applicant_meta_preference(self):
        val = self.cleaned_data.get("applicant_meta_preference")
        logger.debug("clean_applicant_meta_preference input", extra={"type": type(val).__name__, "value_preview": str(val)[:200]})
        # Coerce empty/None to empty list for robustness
        if val is None or val == "":
            return []
        if isinstance(val, str):
            s = val.strip()
            if s.startswith("[") or s.startswith("{"):
                import json
                try:
                    parsed = json.loads(s)
                    logger.debug("clean_applicant_meta_preference parsed JSON", extra={"parsed_type": type(parsed).__name__, "len": len(parsed) if hasattr(parsed, "__len__") else None})
                    return parsed
                except Exception as e:
                    logger.warning("clean_applicant_meta_preference JSON parse failed; defaulting to []", extra={"error": str(e)})
                    return []
            if "," in s or s:
                out = [x.strip() for x in s.split(",") if x.strip()]
                logger.debug("clean_applicant_meta_preference parsed CSV", extra={"count": len(out)})
                return out
        return val


    def clean_school_meta_preference(self):
        val = self.cleaned_data.get("school_meta_preference")
        logger.debug("clean_school_meta_preference input", extra={"type": type(val).__name__, "value_preview": str(val)[:200]})
        # Coerce empty/None to empty list for robustness
        if val is None or val == "":
            return []
        if isinstance(val, str):
            s = val.strip()
            if s.startswith("[") or s.startswith("{"):
                import json
                try:
                    parsed = json.loads(s)
                    logger.debug("clean_school_meta_preference parsed JSON", extra={"parsed_type": type(parsed).__name__, "len": len(parsed) if hasattr(parsed, "__len__") else None})
                    return parsed
                except Exception as e:
                    logger.warning("clean_school_meta_preference JSON parse failed; defaulting to []", extra={"error": str(e)})
                    return []
            if "," in s or s:
                out = [x.strip() for x in s.split(",") if x.strip()]
                logger.debug("clean_school_meta_preference parsed CSV", extra={"count": len(out)})
                return out
        return val

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
            "number_of_applicants": forms.NumberInput(attrs={"class": "input input-bordered w-full", "min": 0}),
            "number_of_schools": forms.NumberInput(attrs={"class": "input input-bordered w-full", "min": 0}),
            "applicant_score_mean": forms.NumberInput(attrs={"class": "input input-bordered w-full", "step": "any"}),
            "applicant_score_stddev": forms.NumberInput(attrs={"class": "input input-bordered w-full", "step": "any", "min": 0}),
            "applicant_interview_limit": forms.NumberInput(attrs={"class": "input input-bordered w-full", "step": "any", "min": 0}),
            "applicant_meta_preference": forms.Textarea(attrs={"class": "textarea textarea-bordered w-full", "rows": 2, "placeholder": "program_size, prestige"}),
            "applicant_meta_preference_stddev": forms.NumberInput(attrs={"class": "input input-bordered w-full", "step": "any", "min": 0}),
            "applicant_meta_scores_stddev": forms.NumberInput(attrs={"class": "input input-bordered w-full", "step": "any", "min": 0}),
            "applicant_pre_interview_rating_error": forms.NumberInput(attrs={"class": "input input-bordered w-full", "step": "any", "min": 0}),
            "applicant_post_interview_rating_error": forms.NumberInput(attrs={"class": "input input-bordered w-full", "step": "any", "min": 0}),
            "school_score_mean": forms.NumberInput(attrs={"class": "input input-bordered w-full", "step": "any"}),
            "school_score_stddev": forms.NumberInput(attrs={"class": "input input-bordered w-full", "step": "any", "min": 0}),
            "school_capacity_mean": forms.NumberInput(attrs={"class": "input input-bordered w-full", "step": "any", "min": 0}),
            "school_capacity_stddev": forms.NumberInput(attrs={"class": "input input-bordered w-full", "step": "any", "min": 0}),
            "school_interview_limit": forms.NumberInput(attrs={"class": "input input-bordered w-full", "step": "any", "min": 0}),
            "school_meta_preference": forms.Textarea(attrs={"class": "textarea textarea-bordered w-full", "rows": 2, "placeholder": "board_scores, research"}),
            "school_meta_preference_stddev": forms.NumberInput(attrs={"class": "input input-bordered w-full", "step": "any", "min": 0}),
            "school_meta_scores_stddev": forms.NumberInput(attrs={"class": "input input-bordered w-full", "step": "any", "min": 0}),
            "school_pre_interview_rating_error": forms.NumberInput(attrs={"class": "input input-bordered w-full", "step": "any", "min": 0}),
            "school_post_interview_rating_error": forms.NumberInput(attrs={"class": "input input-bordered w-full", "step": "any", "min": 0}),
        }
