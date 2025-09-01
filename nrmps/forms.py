from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm

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
            "description": forms.Textarea(attrs={"rows": 3}),
        }


class StudentsUploadForm(forms.Form):
    """Upload CSV for students: expects headers name,score."""

    file = forms.FileField(label="Students CSV", help_text="CSV with columns: name, score")


class SchoolsUploadForm(forms.Form):
    """Upload CSV for schools: expects headers name,capacity,score."""

    file = forms.FileField(label="Schools CSV", help_text="CSV with columns: name, capacity, score")


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
        if isinstance(val, str):
            s = val.strip()
            if s.startswith("[") or s.startswith("{"):
                import json
                try:
                    return json.loads(s)
                except Exception:
                    return []
            if "," in s or s:
                return [x.strip() for x in s.split(",") if x.strip()]
        return val


    def clean_school_meta_preference(self):
        val = self.cleaned_data.get("school_meta_preference")
        if isinstance(val, str):
            s = val.strip()
            if s.startswith("[") or s.startswith("{"):
                import json
                try:
                    return json.loads(s)
                except Exception:
                    return []
            if "," in s or s:
                return [x.strip() for x in s.split(",") if x.strip()]
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
            "school_score_mean",
            "school_score_stddev",
            "school_capacity_mean",
            "school_capacity_stddev",
            "school_interview_limit",
            "school_meta_preference",
        )
        widgets = {
            "number_of_applicants": forms.NumberInput(attrs={"min": 0}),
            "number_of_schools": forms.NumberInput(attrs={"min": 0}),
            "applicant_score_mean": forms.NumberInput(attrs={"step": "any"}),
            "applicant_score_stddev": forms.NumberInput(attrs={"step": "any", "min": 0}),
            "applicant_interview_limit": forms.NumberInput(attrs={"step": "any", "min": 0}),
            "applicant_meta_preference": forms.Textarea(attrs={"rows": 2, "placeholder": "program_size, prestige"}),
            "school_score_mean": forms.NumberInput(attrs={"step": "any"}),
            "school_score_stddev": forms.NumberInput(attrs={"step": "any", "min": 0}),
            "school_capacity_mean": forms.NumberInput(attrs={"step": "any", "min": 0}),
            "school_capacity_stddev": forms.NumberInput(attrs={"step": "any", "min": 0}),
            "school_interview_limit": forms.NumberInput(attrs={"step": "any", "min": 0}),
            "school_meta_preference": forms.Textarea(attrs={"rows": 2, "placeholder": "board_scores, research"}),
        }
