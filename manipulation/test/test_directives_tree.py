import typing
import unittest
from functools import cache

from pydrake.all import (
    AddFrame,
    AddModel,
    AddWeld,
    IiwaDriver,
    ModelDirective,
    MultibodyPlant,
    RobotDiagram,
    Rotation,
    Transform,
)

from manipulation.directives_tree import DirectivesTree
from manipulation.station import MakeHardwareStation, MakeMultibodyPlant, Scenario


class DirectivesTreeTest(unittest.TestCase):
    @cache
    def get_flattened_directives(self) -> typing.List[ModelDirective]:
        return [
            ModelDirective(
                add_model=AddModel(
                    name="iiwa",
                    file="package://drake_models/iiwa_description/urdf/iiwa14_no_collision.urdf",
                )
            ),
            ModelDirective(
                add_frame=AddFrame(
                    name="iiwa_origin",
                    X_PF=Transform(
                        base_frame="world",
                        translation=[0, 0.765, 0],
                    ),
                )
            ),
            ModelDirective(
                add_weld=AddWeld(
                    parent="iiwa_origin",
                    child="iiwa::base",
                )
            ),
            ModelDirective(
                add_model=AddModel(
                    name="wsg",
                    file="package://drake_models/wsg_50_description/sdf/schunk_wsg_50_with_tip.sdf",
                )
            ),
            ModelDirective(
                add_frame=AddFrame(
                    name="iiwa::wsg_attach",
                    X_PF=Transform(
                        base_frame="iiwa::iiwa_link_7",
                        translation=[0, 0, 0.114],
                        rotation=Rotation.Rpy(deg=[90.0, 0.0, 68.0]),
                    ),
                )
            ),
            ModelDirective(
                add_weld=AddWeld(
                    parent="iiwa::wsg_attach",
                    child="wsg::body",
                )
            ),
            ModelDirective(
                add_model=AddModel(
                    name="table",
                    file="package://drake_models/manipulation_station/table_wide.sdf",
                )
            ),
            ModelDirective(
                add_frame=AddFrame(
                    name="table_origin",
                    X_PF=Transform(
                        base_frame="world",
                        translation=[0.4, 0.3825, 0.0],
                        rotation=Rotation.Rpy(deg=[0.0, 0.0, 0.0]),
                    ),
                )
            ),
            ModelDirective(
                add_weld=AddWeld(
                    parent="table_origin",
                    child="table::table_body",
                )
            ),
        ]

    def test_get_welded_descendants_and_directives(self):
        directives = self.get_flattened_directives()
        tree = DirectivesTree(directives)

        children, wsg_directives = tree.GetWeldedDescendantsAndDirectives(["iiwa"])
        self.assertEqual(children, {"wsg"})
        sorted_wsg_directives = tree.TopologicallySortDirectives(wsg_directives)
        self.assertEqual(
            sorted_wsg_directives, directives[3:6]
        )  # wsg-related directives

    def test_get_weld_to_world_directives(self):
        directives = self.get_flattened_directives()
        tree = DirectivesTree(directives)

        iiwa_directives = tree.GetDirectivesFromRootToModels(["iiwa"])
        sorted_iiwa_directives = tree.TopologicallySortDirectives(iiwa_directives)
        self.assertEqual(
            sorted_iiwa_directives, directives[:3]
        )  # iiwa-related directives

        iiwa_wsg_directives = tree.GetDirectivesFromRootToModels(["iiwa", "wsg"])
        sorted_iiwa_wsg_directives = tree.TopologicallySortDirectives(
            iiwa_wsg_directives
        )
        self.assertEqual(sorted_iiwa_wsg_directives, directives[:6])

    def test_make_multibody_plant(self):
        scenario = Scenario()
        scenario.directives = self.get_flattened_directives()
        scenario.model_drivers = {
            "iiwa": IiwaDriver(
                control_mode="position_only",
                hand_model_name="wsg",
            )
        }

        # Test with all model instances.
        plant: MultibodyPlant = MakeMultibodyPlant(scenario)
        self.assertTrue(plant.HasModelInstanceNamed("iiwa"))
        self.assertTrue(plant.HasModelInstanceNamed("wsg"))
        self.assertTrue(plant.HasModelInstanceNamed("table"))

        # Test with only "iiwa" and "wsg".
        plant: MultibodyPlant = MakeMultibodyPlant(
            scenario, model_instance_names=["iiwa", "wsg"]
        )
        self.assertTrue(plant.HasModelInstanceNamed("iiwa"))
        self.assertTrue(plant.HasModelInstanceNamed("wsg"))
        self.assertFalse(plant.HasModelInstanceNamed("table"))

        # Test with only "iiwa".
        plant: MultibodyPlant = MakeMultibodyPlant(
            scenario, model_instance_names=["iiwa"]
        )
        self.assertTrue(plant.HasModelInstanceNamed("iiwa"))
        self.assertFalse(plant.HasModelInstanceNamed("wsg"))
        self.assertFalse(plant.HasModelInstanceNamed("table"))

        # Test with only "iiwa" and "add_frozen_child_instances=True"
        plant: MultibodyPlant = MakeMultibodyPlant(
            scenario,
            model_instance_names=["iiwa"],
            add_frozen_child_instances=True,
        )
        self.assertTrue(plant.HasModelInstanceNamed("iiwa"))
        self.assertTrue(plant.HasModelInstanceNamed("wsg"))
        self.assertFalse(plant.HasModelInstanceNamed("table"))

    def test_load_scenario(self):
        scenario = Scenario()
        scenario.directives = self.get_flattened_directives()
        scenario.model_drivers = {
            "iiwa": IiwaDriver(
                control_mode="position_only",
                hand_model_name="wsg",
            )
        }
        station: RobotDiagram = MakeHardwareStation(scenario, hardware=False)
        controller_plant: MultibodyPlant = station.GetSubsystemByName(
            "iiwa_controller_plant_pointer_system"
        ).get()

        # Check that the controller plant contains "iiwa" and "wsg" but not "table".
        self.assertTrue(controller_plant.HasModelInstanceNamed("iiwa"))
        self.assertTrue(controller_plant.HasModelInstanceNamed("wsg"))
        self.assertFalse(controller_plant.HasModelInstanceNamed("table"))


if __name__ == "__main__":
    unittest.main()
