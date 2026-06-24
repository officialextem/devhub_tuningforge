from __future__ import annotations

from core.executor import build_winget_command
from core.models import ActionPlan, Package, PlannedAction, Profile


def build_action_plan(profile: Profile, packages: list[Package], selected_package_ids: set[str]) -> ActionPlan:
    selected = [package for package in packages if package.id in selected_package_ids]
    actions = [
        PlannedAction(package=package, command=build_winget_command(package.winget_id))
        for package in selected
    ]
    return ActionPlan(profile=profile, actions=actions, folders=list(profile.folders))
