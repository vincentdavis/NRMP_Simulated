"""Template filters for simulation workflow stage rendering."""

from django import template

from nrmps.models import STAGE_ORDER

register = template.Library()


@register.filter
def stage_complete(simulation, stage_key):
    """Return True if *stage_key* is behind the simulation's current status."""
    try:
        return STAGE_ORDER.index(stage_key) < simulation.stage_index()
    except ValueError:
        return False


@register.filter
def stage_active(simulation, stage_key):
    """Return True if *stage_key* is the simulation's current status."""
    return simulation.status == stage_key


@register.filter
def stage_locked(simulation, stage_key):
    """Return True if *stage_key* is ahead of the simulation's current status."""
    try:
        return STAGE_ORDER.index(stage_key) > simulation.stage_index()
    except ValueError:
        return True


@register.filter
def stage_reached(simulation, stage_key):
    """Return True if the simulation's current status is *stage_key* or a later stage.

    A step's controls are enabled once the stage it depends on has been reached.
    """
    try:
        return simulation.stage_index() >= STAGE_ORDER.index(stage_key)
    except ValueError:
        return False
