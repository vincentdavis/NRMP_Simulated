"""Admin site registrations.

Users and simulations can be edited. Runs, their stages and artifacts, uploaded populations and saved presets are
produced by the application, so staff can view and delete them but not add or change them.
"""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import PopulationUpload, RunArtifact, SavedPreset, Simulation, SimulationRun, StageRun, User


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    """The custom user, with its full name."""

    fieldsets = (*(DjangoUserAdmin.fieldsets or ()), ("Profile", {"fields": ("full_name",)}))
    list_display = ("username", "email", "full_name", "is_staff", "is_active", "date_joined")


@admin.register(Simulation)
class SimulationAdmin(admin.ModelAdmin):
    """Simulations with their owner and runs."""

    list_display = ("name", "owner", "n_runs", "latest_run_status", "created_at")
    list_filter = ("public",)
    search_fields = ("name", "owner__username")
    list_select_related = ("owner",)
    readonly_fields = ("created_at", "updated_at")

    def get_queryset(self, request):
        """Annotate the run summary (one subquery each)."""
        return super().get_queryset(request).with_run_summary()

    @admin.display(description="Runs", ordering="n_runs")
    def n_runs(self, obj) -> int:
        """Return the number of runs."""
        return obj.n_runs

    @admin.display(description="Latest run")
    def latest_run_status(self, obj) -> str:
        """Return the latest run's status."""
        return obj.latest_run_status or "-"


class ReadOnlyAdmin(admin.ModelAdmin):
    """Rows the application produces: viewable and deletable, not editable."""

    show_full_result_count = False
    list_per_page = 100

    def has_add_permission(self, request) -> bool:
        """Produced rows are not added by hand."""
        return False

    def has_change_permission(self, request, obj=None) -> bool:
        """Produced rows are not edited by hand."""
        return False


class StageRunInline(admin.TabularInline):
    """The stages of a run."""

    model = StageRun
    extra = 0
    can_delete = False
    fields = ("stage", "status", "duration_ms", "fingerprint", "counts", "error")
    readonly_fields = fields

    def has_add_permission(self, request, obj=None) -> bool:
        """Stages are recorded by the run."""
        return False


@admin.register(SimulationRun)
class SimulationRunAdmin(ReadOnlyAdmin):
    """Runs: status, size, duration, seed and versions."""

    list_display = ("__str__", "status", "n_applicants", "n_programs", "duration_ms", "seed", "created_at")
    list_filter = ("status", "model_version")
    list_select_related = ("simulation",)
    search_fields = ("simulation__name", "simulation__owner__username")
    raw_id_fields = ("simulation", "created_by")
    inlines = (StageRunInline,)


@admin.register(RunArtifact)
class RunArtifactAdmin(ReadOnlyAdmin):
    """Array artifacts (their bytes are not shown)."""

    list_display = ("run", "kind", "size", "created_at")
    list_filter = ("kind",)
    list_select_related = ("run__simulation",)
    exclude = ("data",)

    def get_queryset(self, request):
        """Never load the bytes for the list."""
        return super().get_queryset(request).defer("data")


@admin.register(PopulationUpload)
class PopulationUploadAdmin(ReadOnlyAdmin):
    """Uploaded populations (their bytes are not shown)."""

    list_display = ("simulation", "side", "filename", "rows", "uploaded_at")
    list_filter = ("side",)
    list_select_related = ("simulation",)
    exclude = ("data",)

    def get_queryset(self, request):
        """Never load the bytes for the list."""
        return super().get_queryset(request).defer("data")


@admin.register(SavedPreset)
class SavedPresetAdmin(ReadOnlyAdmin):
    """Presets users saved from their simulations' parameters."""

    list_display = ("name", "owner", "created_at")
    list_select_related = ("owner",)
    search_fields = ("name", "owner__username")
