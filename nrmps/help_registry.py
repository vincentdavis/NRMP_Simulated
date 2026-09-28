"""The help registry (plan step 4.3): what every action, table column and page means, in one place.

Parameters are described by the typed schema (`nrmps.params`: title, description, unit, range, default), so the
registry covers the rest: ACTIONS (buttons that change something), COLUMNS (table columns, keyed "table.column"),
PAGES (the Help panel of each page) and CHARTS (the chart catalog, plan step 5.1: what each chart shows and how to
read it). The "?" popovers, the Help panels and the guide's chart section read it (`nrmps.templatetags.help_tags`,
`nrmps.guide`), and `nrmps.checks` verifies it at start-up: every parameter has a description, every page lists only
known actions and columns, every chart is fully described, and every "Learn more" link points at a section of the
help. Strings are marked for translation.
"""

from dataclasses import dataclass, field

from django.utils.functional import Promise
from django.utils.text import format_lazy
from django.utils.translation import gettext_lazy as _

from .params import ParamField
from .params_forms import choice_label

# "Learn more" targets are guide pages (nrmps/help_content/<slug>.md), optionally with "#anchor"; nrmps.checks
# verifies that each exists.

Text = str | Promise


@dataclass(frozen=True)
class HelpEntry:
    """Help for one action or column: a title, what it means, and the help section to learn more."""

    title: Text
    text: Text
    more: str = ""  # a guide page, optionally with "#anchor" ("model", "index#quick-start"), or ""


@dataclass(frozen=True)
class PageHelp:
    """The Help panel of a page: what it is, what to do next, and its actions and columns."""

    title: Text
    what: Text
    next_steps: tuple[Text, ...] = ()
    actions: tuple[str, ...] = ()
    columns: tuple[str, ...] = ()
    more: str = ""
    notes: tuple[Text, ...] = field(default=())


ACTIONS: dict[str, HelpEntry] = {
    "run": HelpEntry(
        _("Run"),
        _(
            "Runs every stage, from the population to the match, with the saved parameters and seed. The same "
            "parameters and seed always give the same results. Earlier runs stay until you delete them."
        ),
        "index#quick-start",
    ),
    "notify": HelpEntry(
        _("Email me when it finishes"),
        _("Sends one email when a queued run finishes or fails. Needs a confirmed email address."),
    ),
    "save_params": HelpEntry(
        _("Save"),
        _("Saves the parameters without running. The pipeline then shows which stages the change makes out of date."),
        "parameters",
    ),
    "save_and_run": HelpEntry(
        _("Save and run"),
        _("Saves the parameters and starts a run with them, then opens the run."),
        "parameters",
    ),
    "apply_preset": HelpEntry(
        _("Apply preset"),
        _(
            "Replaces every parameter with the preset's (the seed stays, so the same preset gives the same "
            "market). Parameters you changed without saving are lost."
        ),
        "parameters",
    ),
    "save_preset": HelpEntry(
        _("Save as preset"),
        _(
            "Saves the simulation's saved parameters (not changes you have not saved, and not the seed) as a preset "
            "of yours: new simulations and Apply preset can then start from it."
        ),
        "parameters",
    ),
    "load_params": HelpEntry(
        _("Load parameters from a file"),
        _(
            "Replaces every parameter with a JSON file's: a parameters download from any simulation, or a run's "
            "parameters. The file's seed is used when it has one; otherwise the simulation keeps its seed."
        ),
        "parameters",
    ),
    "duplicate": HelpEntry(
        _("Duplicate"),
        _("Copies the simulation with its parameters, seed and uploaded files, but not its runs."),
    ),
    "upload": HelpEntry(
        _("Upload"),
        _(
            "Uses your CSV file for this side instead of generating it. The whole file is checked first; if any "
            "row has a problem, nothing changes and the problems are listed."
        ),
        "csv",
    ),
    "remove_upload": HelpEntry(
        _("Remove"),
        _("Deletes the uploaded file; runs generate this side from the parameters again. Past runs keep theirs."),
        "csv",
    ),
    "delete_run": HelpEntry(
        _("Delete run"),
        _(
            "Deletes the run and its results. It can be repeated: its parameters and seed are on its summary "
            "page and in its downloads."
        ),
    ),
    "delete_simulation": HelpEntry(
        _("Delete simulation"),
        _("Deletes the simulation with its parameters, uploaded files and every run. This cannot be undone."),
    ),
    "download_csv": HelpEntry(
        _("Download CSV"),
        _(
            "Downloads this side of the population in the upload format: uploading it to a simulation reproduces "
            "the same applicants or programs."
        ),
        "csv",
    ),
}


def _column(title: Text, text: Text, more: str = "results") -> HelpEntry:
    return HelpEntry(title, text, more)


RANK_1 = _("1 is the favourite.")

COLUMNS: dict[str, HelpEntry] = {
    # The applicants of a run.
    "applicants.index": _column(_("#"), _("The applicant's number in the population.")),
    "applicants.name": _column(
        _("Name"), _("Open the applicant's page: every program they applied to, stage by stage.")
    ),
    "applicants.group": _column(_("Group"), _("The applicant group (for example US MD seniors)."), "model"),
    "applicants.strength": _column(
        _("Strength"), _("Latent strength on the z-scale: 0 is average, 1 is one standard deviation above."), "model"
    ),
    "applicants.percentile": _column(_("Percentile"), _("Where the applicant's strength ranks among all applicants.")),
    "applicants.applications": _column(_("Applications"), _("How many programs the applicant applied to.")),
    "applicants.interviews": _column(_("Interviews"), _("How many interviews the applicant attended.")),
    "applicants.match": _column(
        _("Matched to"), _("The program of the match, and where the applicant had put it on their list.")
    ),
    "applicants.attributes": _column(
        _("Attributes"), _("The applicant's attributes that programs evaluate, on the z-scale."), "model"
    ),
    "applicants.weights": _column(
        _("Weights"), _("How much the applicant values each program attribute; the weights add up to 1."), "model"
    ),
    "applicants.first_choice": _column(
        _("First choice"), _("The program the applicant would rank first before interviews.")
    ),
    "applicants.fidelity": _column(
        _("Fidelity"),
        _("Rank correlation of the applicant's true and pre-interview orderings of programs (1 = no mistakes)."),
    ),
    "applicants.popularity": _column(
        _("Ranked first by"), _("How many programs would rank this applicant first before interviews.")
    ),
    # The programs of a run.
    "programs.index": _column(_("#"), _("The program's number in the population.")),
    "programs.name": _column(_("Name"), _("Open the program's page: every applicant who applied, stage by stage.")),
    "programs.tier": _column(_("Tier"), _("The program tier, if the parameters define tiers."), "model"),
    "programs.quality": _column(
        _("Quality"), _("Latent quality on the z-scale: 0 is average, 1 is one standard deviation above."), "model"
    ),
    "programs.percentile": _column(_("Percentile"), _("Where the program's quality ranks among all programs.")),
    "programs.capacity": _column(_("Positions"), _("The program's number of positions.")),
    "programs.applications": _column(_("Applications"), _("How many applicants applied to the program.")),
    "programs.interviews": _column(_("Interviews"), _("How many applicants the program interviewed.")),
    "programs.fill": _column(_("Filled"), _("Positions filled in the match, of the program's positions.")),
    "programs.attributes": _column(
        _("Attributes"), _("The program's attributes that applicants evaluate, on the z-scale."), "model"
    ),
    "programs.weights": _column(
        _("Weights"), _("How much the program values each applicant attribute; the weights add up to 1."), "model"
    ),
    "programs.first_choice": _column(
        _("First choice"), _("The applicant the program would rank first before interviews.")
    ),
    "programs.fidelity": _column(
        _("Fidelity"),
        _("Rank correlation of the program's true and pre-interview orderings of applicants (1 = no mistakes)."),
    ),
    "programs.popularity": _column(
        _("Ranked first by"), _("How many applicants would rank this program first before interviews.")
    ),
    # One agent's page: the stages.
    "agent_stages.pre_rank": _column(
        _("Pre-interview rank"),
        format_lazy("{}{}", _("Where this agent ranks the other before interviews, among everyone. "), RANK_1),
    ),
    "agent_stages.signal": _column(_("Signal"), _("The tier of the preference signal sent with the application.")),
    "agent_stages.wave": _column(_("Invited"), _("The invitation wave in which the program invited the applicant.")),
    "agent_stages.interview": _column(
        _("Interview"), _("Yes if the interview took place; Declined if the applicant was invited but did not go.")
    ),
    "agent_stages.post": _column(
        _("Post-interview view"), _("This agent's view of the other after the interview, in SD units."), "model"
    ),
    "agent_stages.their_post": _column(
        _("Their post-interview view"), _("The other's view of this agent after the interview."), "model"
    ),
    "agent_stages.list_rank": _column(
        _("List rank"),
        format_lazy("{}{}", _("Where this agent put the other on its rank order list (blank: not on it). "), RANK_1),
    ),
    "agent_stages.their_list_rank": _column(
        _("Their list rank of it"), _("Where the other put this agent on its rank order list.")
    ),
    "agent_stages.match": _column(_("Match"), _("Marks the pair the match joined.")),
    # One agent's page: before interviews.
    "agent_pre.true": _column(_("True utility"), _("How much this agent values the other, in SD units."), "model"),
    "agent_pre.observed": _column(
        _("Pre-interview view"), _("The true utility plus the pre-interview error: what the agent sees."), "model"
    ),
    "agent_pre.true_rank": _column(_("True rank"), format_lazy("{}{}", _("The rank by true utility. "), RANK_1)),
    "agent_pre.pre_rank": _column(
        _("Pre-interview rank"), format_lazy("{}{}", _("The rank by the pre-interview view. "), RANK_1)
    ),
    "agent_pre.their_true": _column(_("Their true utility"), _("How much the other values this agent.")),
    "agent_pre.their_observed": _column(
        _("Their pre-interview view"), _("The other's pre-interview view of this agent.")
    ),
    "agent_pre.their_true_rank": _column(
        _("Their true rank of it"), _("Where the other ranks this agent by true utility.")
    ),
    "agent_pre.their_pre_rank": _column(
        _("Their pre-interview rank of it"), _("Where the other ranks this agent before interviews.")
    ),
    # Every application of a run.
    "applications.applicant": _column(_("Applicant"), _("The applicant; the link opens their page.")),
    "applications.program": _column(_("Program"), _("The program applied to; the link opens its page.")),
    "applications.pre_rank": _column(
        _("Applicant's pre-interview rank"),
        format_lazy("{}{}", _("Where the applicant ranked the program before interviews. "), RANK_1),
    ),
    "applications.signal": _column(_("Signal"), _("The tier of the signal the applicant sent, if any.")),
    "applications.invited": _column(_("Invited"), _("The wave in which the program invited the applicant.")),
    "applications.interview": _column(
        _("Interview"), _("Yes if the interview took place; Declined if the applicant was invited but did not go.")
    ),
    "applications.applicant_rank": _column(
        _("Applicant's list rank"), _("Where the applicant put the program on their rank order list.")
    ),
    "applications.program_rank": _column(
        _("Program's list rank"), _("Where the program put the applicant on its rank order list.")
    ),
    "applications.match": _column(_("Match"), _("Marks the applications that ended in the match.")),
}

_RUN_TABS = _(
    "The tabs above lead to the population, the views before interviews, the applications, the match, "
    "and the lists of applicants and programs."
)

PAGES: dict[str, PageHelp] = {
    "simulation_list": PageHelp(
        _("Your simulations"),
        _("Every simulation you created, with its latest run. A simulation holds parameters and runs."),
        (_("Open a simulation to change its parameters and run it."), _("Or create a new one from a preset.")),
        more="index#quick-start",
    ),
    "simulation_create": PageHelp(
        _("New simulation"),
        _("Name the simulation and pick the preset its parameters start from. Every parameter can change later."),
        (_("Press Create; the simulation page opens with the preset's parameters."),),
        more="index#quick-start",
    ),
    "simulation_manage": PageHelp(
        _("The simulation page"),
        _(
            "The parameters, the populations and the runs of one simulation. The pipeline at the top shows each "
            "stage's state; a stage with results links to them."
        ),
        (
            _("Adjust the parameters; the panel beside them shows what they give."),
            _("Press Save and run, or Run to use the saved parameters."),
            _("Open a run to see its results."),
        ),
        actions=(
            "run",
            "save_params",
            "save_and_run",
            "apply_preset",
            "save_preset",
            "load_params",
            "upload",
            "duplicate",
            "delete_simulation",
        ),
        more="parameters",
    ),
    "run_summary": PageHelp(
        _("A run's summary"),
        _(
            "The key numbers of the run, its checks, downloads, stages, version stamps and parameters. While the run "
            "is queued or running, the stages show which have finished and which are still waiting."
        ),
        (_RUN_TABS,),
        actions=("delete_run",),
        more="results",
    ),
    "run_population": PageHelp(
        _("The population"),
        _(
            "The applicants and programs as generated, next to what the parameters asked for, and their "
            "distributions. A line over a histogram is the requested distribution."
        ),
        (_RUN_TABS,),
        more="model",
    ),
    "run_pre_interview": PageHelp(
        _("Before interviews"),
        _(
            "How much the agents agree, how well each side sees the other before interviews, and how concentrated "
            "the first choices are."
        ),
        (_RUN_TABS,),
        more="results",
    ),
    "run_applications": PageHelp(
        _("Applications and interviews"),
        _(
            "The funnel from applications to rank order lists, the signals, what interviews revealed, and every "
            "application with filters."
        ),
        (_("Filter the applications by the stage they reached, by signal or by name."), _RUN_TABS),
        columns=tuple(key for key in COLUMNS if key.startswith("applications.")),
        more="results",
    ),
    "run_match": PageHelp(
        _("The match"),
        _(
            "The match rate, the positions filled, where applicants matched on their lists, the checks of the "
            "match, and who matched by group and strength."
        ),
        (_RUN_TABS,),
        more="results",
    ),
    "run_applicants": PageHelp(
        _("The applicants of a run"),
        _("Every applicant with their attributes, weights, pre-interview results and outcome."),
        (_("Sort by a column, or open an applicant's page."),),
        actions=("download_csv",),
        columns=tuple(key for key in COLUMNS if key.startswith("applicants.")),
        more="results",
    ),
    "run_programs": PageHelp(
        _("The programs of a run"),
        _("Every program with its attributes, weights, positions, pre-interview results and fill."),
        (_("Sort by a column, or open a program's page."),),
        actions=("download_csv",),
        columns=tuple(key for key in COLUMNS if key.startswith("programs.")),
        more="results",
    ),
    "run_agent": PageHelp(
        _("One applicant or program"),
        _(
            "Its path through the stages (applications, signals, invitations, interviews, rank order lists, the "
            "match) and, on the second tab, how it sees everyone before interviews and how everyone sees it."
        ),
        (_("Follow a link to the other side's page."),),
        columns=tuple(key for key in COLUMNS if key.startswith(("agent_stages.", "agent_pre."))),
        more="results",
    ),
}


@dataclass(frozen=True)
class ChartHelp:
    """One chart of the catalog (VIZ-19, HELP-25): the question it answers, what it shows, how to read it."""

    title: Text  # the question the chart answers, also its caption
    what: Text
    how: Text
    caveats: Text = ""
    tab: str = ""  # where it appears: a key of CHART_PLACES
    side: str = "applicant"  # the colour of a one-sided chart: "applicant" or "program"
    switch: str = ""  # an option a switch beside the chart turns on (nrmp-charts.js reads data-<switch>="on")
    switch_label: Text = ""  # the switch's label

    @property
    def text(self) -> str:
        """Return the popover text: what the chart shows, how to read it and its caveats."""
        return " ".join(str(part) for part in (self.what, self.how, self.caveats) if part)


# Where the charts appear, in the order the guide lists them.
CHART_PLACES: dict[str, Text] = {
    "population": _("Population tab"),
    "pre_interview": _("Before interviews tab"),
    "applications": _("Applications and interviews tab"),
    "agent": _("One applicant's or program's page"),
}

CHARTS: dict[str, ChartHelp] = {
    "strength": ChartHelp(
        _("Did the generator produce the applicants asked for?"),
        _(
            "A histogram of applicant strength (z-scores) in this run. When the applicants were generated, a line "
            "shows the counts the parameters ask for: the mixture of the applicant groups' normal distributions."
        ),
        _(
            "Bars that follow the line mean the population is what the parameters describe. The summary gives the "
            "largest deviation in standard errors; above 4, the generator did not produce what was asked."
        ),
        _("Uploaded applicants have no line: their strengths are given, not drawn."),
        tab="population",
    ),
    "quality": ChartHelp(
        _("Did the generator produce the programs asked for?"),
        _(
            "A histogram of program quality (z-scores) in this run, with the counts the parameters ask for (the "
            "tiers' normal distributions, or one normal distribution without tiers) when the programs were generated."
        ),
        _("Bars that follow the line mean the programs are what the parameters describe."),
        _("Uploaded programs have no line: their qualities are given, not drawn."),
        tab="population",
        side="program",
    ),
    "capacity": ChartHelp(
        _("How are the positions spread over programs?"),
        _("How many programs have each number of positions."),
        _(
            "A long right tail means a few large programs hold many of the positions. The key numbers above give the "
            "median and the range."
        ),
        tab="population",
        side="program",
    ),
    "applicant_fidelity": ChartHelp(
        _("How well does each applicant know their true order?"),
        _(
            "For each applicant, the rank correlation (Spearman) between their true ordering of every program and "
            "their view of it before interviews."
        ),
        _(
            "1 is a perfect view; values near 0 mean the pre-interview view says little about the truth. The spread "
            "shows how unevenly information falls among applicants."
        ),
        _("Before interviews only: interviews reveal more, as the Applications and interviews tab shows."),
        tab="pre_interview",
    ),
    "program_fidelity": ChartHelp(
        _("How well does each program know its true order?"),
        _(
            "For each program, the rank correlation (Spearman) between its true ordering of every applicant and its "
            "view of it before interviews."
        ),
        _("1 is a perfect view; values near 0 mean the pre-interview view says little about the truth."),
        _("Before interviews only: interviews reveal more, as the Applications and interviews tab shows."),
        tab="pre_interview",
        side="program",
    ),
    "perception_applicants": ChartHelp(
        _("How accurately do applicants see programs?"),
        _(
            "True against observed utility for a sample of applicant\u2013program pairs: before interviews, the true "
            "utility against the pre-interview view; after interviews, for a sample of interviews, the realised "
            "utility against the view after the interview."
        ),
        _(
            "Points on the dashed line are seen exactly; the wider the cloud around it, the noisier the view. The "
            "summary gives each cloud's correlation."
        ),
        _("A sample of at most 1,500 points per series, the same on every visit (drawn from the run's seed)."),
        tab="pre_interview",
    ),
    "perception_programs": ChartHelp(
        _("How accurately do programs see applicants?"),
        _(
            "True against observed utility for a sample of program\u2013applicant pairs, before interviews and (for a "
            "sample of interviews) after them."
        ),
        _(
            "Points on the dashed line are seen exactly; the wider the cloud around it, the noisier the view. The "
            "summary gives each cloud's correlation."
        ),
        _("A sample of at most 1,500 points per series, the same on every visit (drawn from the run's seed)."),
        tab="pre_interview",
        side="program",
    ),
    "demand": ChartHelp(
        _("Is demand concentrated on a few programs?"),
        _(
            "How many applicants rank each program first before interviews, most wanted first, with each program's "
            "number of positions as a mark."
        ),
        _(
            "Bars far above their mark are programs many more applicants want than they can take. With many "
            "programs, zoom with the slider under the chart."
        ),
        _("First choices before interviews, not the final rank order lists."),
        tab="pre_interview",
        side="program",
    ),
    "lorenz": ChartHelp(
        _("How unequal is first-choice demand?"),
        _(
            "The Lorenz curve of first-choice demand: programs from the least to the most wanted, against their "
            "cumulative share of first choices."
        ),
        _(
            "The dashed diagonal is equal demand; the further the curve sags below it, the more concentrated demand "
            "is. The Gini coefficient in the summary is twice the area between them (0 = equal, 1 = everyone wants "
            "the same program)."
        ),
        tab="pre_interview",
        side="program",
    ),
    "funnel": ChartHelp(
        _("Where do applications drop out?"),
        _(
            "Every application through the stages: invited to interview or not, interviewed or not (declined, or "
            "over the applicant's interview cap), on the applicant's rank order list or not, matched or not."
        ),
        _("Each band's width is a number of applications; hover a band for its count and share. Grey marks drop-offs."),
        _("It counts applications (applicant\u2013program pairs), not applicants."),
        tab="applications",
    ),
    "applicant_flow": ChartHelp(
        _("Which applicants get an interview and a match?"),
        _(
            "Every applicant counted once: whether they had at least one interview, and whether they matched. With "
            "Colour by strength on, each stage splits into fifths of applicant strength (applicants of equal strength "
            "stay in the same fifth), in shades of blue from the weakest fifth to the strongest, so the quality of the "
            "applicants can be followed through the stages."
        ),
        _(
            "Each band's width is a number of applicants. Hover a stage or a band for its count and its share of all "
            "applicants (with the switch on, of its fifth); a band after the first stage also gives its share of the "
            "stage it leaves. No interview splits into never invited and invited without an interview. With the "
            "switch on, a grey drop-off lists each fifth's count and the share of that fifth it holds: a fifth that "
            "loses a larger share of its applicants to the drop-offs does worse."
        ),
        _(
            "Strength is the applicant's latent strength. The view all programs share is mostly strength, mixed with "
            "the applicant's attributes, and each program sees it only through its own noisy view. The funnel above "
            "counts applications instead: strong applicants hold many interviews but match only once."
        ),
        tab="applications",
        switch="bands",
        switch_label=_("Colour by strength"),
    ),
    "ego_applicant": ChartHelp(
        _("How far did each of this applicant's applications get?"),
        _(
            "Every program the applicant applied to, on rings by how far the application got: applied only on the "
            "outer ring, then invited, interviewed and ranked, and the match in the middle."
        ),
        _("Hover a program for its name. The table below lists every application with its details."),
        _("Ranked means the applicant ranked the program; whether the program ranked them is in the table."),
        tab="agent",
    ),
    "ego_program": ChartHelp(
        _("How far did each application to this program get?"),
        _(
            "Every applicant who applied to the program, on rings by how far the application got: applied only on "
            "the outer ring, then invited, interviewed and ranked, and the matches in the middle."
        ),
        _("Hover an applicant for their name. The table below lists every application with its details."),
        _("Ranked means the program ranked the applicant; whether the applicant ranked it is in the table."),
        tab="agent",
        side="program",
    ),
    "funnel_applicant": ChartHelp(
        _("Where did this applicant's applications drop out?"),
        _(
            "The applicant's applications through the stages: invited to interview or not, interviewed or not "
            "(declined, or over the applicant's interview cap), on the applicant's rank order list or not, matched or "
            "not."
        ),
        _("Each band's width is a number of applications; hover a band for its count and share. Grey marks drop-offs."),
        _("Ranked means the applicant ranked the program."),
        tab="agent",
    ),
    "funnel_program": ChartHelp(
        _("Where did the applications to this program drop out?"),
        _(
            "The applications the program received, through the stages: invited to interview or not, interviewed or "
            "not (the applicant declined, or was over their interview cap), on the program's rank order list or not, "
            "matched or not."
        ),
        _("Each band's width is a number of applications; hover a band for its count and share. Grey marks drop-offs."),
        _("Ranked means the program ranked the applicant; an applicant it ranked may have matched elsewhere."),
        tab="agent",
        side="program",
    ),
}


def chart(key: str) -> ChartHelp:
    """Return a chart's catalog entry; raise KeyError for a chart the catalog does not describe."""
    return CHARTS[key]


def chart_anchor(key: str) -> str:
    """Return the id of a chart's entry in the guide's chart section."""
    return "chart-" + key.replace("_", "-")


def chart_target(key: str) -> str:
    """Return the help target of a chart's entry in the guide."""
    return f"results#{chart_anchor(key)}"


def column(key: str) -> HelpEntry:
    """Return the help of a table column; raise KeyError for a column the registry does not describe."""
    return COLUMNS[key]


def action(key: str) -> HelpEntry:
    """Return the help of an action; raise KeyError for an action the registry does not describe."""
    return ACTIONS[key]


def param_anchor(path: str) -> str:
    """Return the id of a parameter's row in the guide's parameter reference."""
    return "param-" + path.replace(".", "-")


def param_target(path: str) -> str:
    """Return the help target of a parameter's row in the parameter reference."""
    return f"parameters#{param_anchor(path)}"


def param_limits(spec: ParamField) -> str:
    """Return a parameter's range (low, an en dash, high; ">" marks an exclusive minimum) or its choices."""
    if spec.minimum is not None or spec.maximum is not None:
        low = "" if spec.minimum is None else f"{'>' if spec.exclusive_minimum else ''}{spec.minimum:g}"
        high = "" if spec.maximum is None else f"{spec.maximum:g}"
        return f"{low}\u2013{high}"  # en dash
    if spec.choices:
        return ", ".join(choice_label(choice) for choice in spec.choices)
    return ""


def param_value(value: object) -> str:
    """Return a parameter value (a default) as text."""
    if value is None:
        return "blank"
    if isinstance(value, bool):
        return "on" if value else "off"
    if isinstance(value, str):
        return choice_label(value)
    if isinstance(value, float):
        return f"{value:g}"
    return str(value)
