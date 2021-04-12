"""Third stage: Results"""

# Standard library imports
import itertools

# Third party imports
import pandas as pd
import panel as pn
import param
import pyplugs

# Geo:N:G imports
from app import config
from app.assets import panes
from app.assets import state
from geong_common.log import logger

# Find name of app and stage
*_, PACKAGE, APP, STAGE = __name__.split(".")
CFG = config.app[PACKAGE][APP][STAGE]


class Model(param.Parameterized):
    """Data defining this stage"""

    # Values set by previous stage
    report_from_composition = param.Dict()

    # Parameters for the current stage
    headline = param.String(label=CFG.label)
    ready = param.Boolean(default=False)
    net_gross = param.Number(label="Net/Gross", softbounds=(0, 100))
    scenario_name = param.String(label="Scenario Name")

    def __init__(self, report_from_composition, net_gross):
        """Set initial values based on previous stage"""
        super().__init__()
        self._state = state.get_user_state().setdefault(APP, {})
        self._state.setdefault("scenarios", {})
        self._current_scenario_name = None
        self.composition = report_from_composition["building_block_type"]
        self.net_gross = net_gross
        self.scenario_name = f"Scenario {len(self._state['scenarios']) + 1}"

        try:
            session_id = pn.state.curdoc.session_context.id
            logger.insights(f"New result: {self.net_gross}, SessionID: {session_id}")
            logger.insights(
                f"SessionID: {session_id}, Choices: {report_from_composition}"
            )
        except AttributeError as e:
            logger.error(f"SessionID not available: {e}")
            logger.insights(f"New result: {self.net_gross}")
            logger.insights(f"Choices: {report_from_composition}")

    def _store_scenario(self):
        """Store results for the current scenario"""
        scenarios = self._state["scenarios"]

        # Make sure name does not overwrite previous scenarios
        if self.scenario_name in scenarios:
            for suffix in itertools.count(start=2):
                name = f"{self.scenario_name} ({suffix})"
                if name not in scenarios:
                    break
            self.scenario_name = name

        # Get information about scenario
        if self._current_scenario_name in scenarios:
            scenario_info = scenarios.pop(self._current_scenario_name)
        else:
            scenario_info = {"net_gross": self.net_gross}

        # Store scenario information
        scenarios[self.scenario_name] = scenario_info
        self._current_scenario_name = self.scenario_name

    @pn.depends("scenario_name")
    def scenario_table(self):
        """Table showing current scenarios"""
        self._store_scenario()

        scenarios = self._state["scenarios"]
        table_data = pd.DataFrame(
            {
                "Scenario": [s for s in scenarios.keys()],
                "Net/Gross": [round(s["net_gross"]) for s in scenarios.values()],
            }
        ).set_index("Scenario")
        return pn.pane.DataFrame(table_data)

    def new_scenario_button(self):
        """Button for starting new scenario"""

        def restart_scenario(event):
            """Start a new scenario by restarting the workflow"""
            reset_button = self._state["update_view"]["workflow"]
            reset_button.clicks += 1

        button = pn.widgets.Button(name="New Scenario")
        button.on_click(restart_scenario)
        return button

    def finalize_workflow_button(self):
        """Button for finalizing workflow (moving on to final stage)"""

        def next_stage(event):
            """Move to next stage to finish workflow"""
            self.ready = True

        button = pn.widgets.Button(name="Finalize Report")
        button.on_click(next_stage)
        return button

    @param.output(param.List)
    def scenario_names(self):
        """Pass on names of scenarios to next stage"""
        return [sn for sn in self._state["scenarios"].keys()]


class View:
    """Define the look and feel of the stage"""

    def panel(self):
        return pn.Column(
            panes.headline(self.param.headline),
            pn.Row(
                pn.indicators.Number.from_param(
                    self.param.net_gross, format="{value:.0f}%"
                ),
                pn.Column(
                    pn.widgets.TextInput.from_param(self.param.scenario_name),
                    self.scenario_table,
                    pn.Row(self.new_scenario_button, self.finalize_workflow_button),
                    sizing_mode="stretch_width",
                ),
            ),
            sizing_mode="stretch_width",
        )


@pyplugs.register
class StageResult(Model, View):
    """Connect the model and the view"""
