import inspect
import math
from typing import List, Mapping, Tuple, Union, Dict
from gym import spaces
import numpy as np
from citylearn.base import Environment, EpisodeTracker
from citylearn.data import EnergySimulation, CarbonIntensity, Pricing, Weather, EVSimulation
from citylearn.energy_model import Battery, ElectricHeater, HeatPump, PV, StorageTank
from citylearn.preprocessing import Normalize, PeriodicNormalization
import random
import copy

class electric_vehicle(Environment):

    def __init__(self, ev_simulation: EVSimulation,episode_tracker: EpisodeTracker, observation_metadata: Mapping[str, bool],
                 action_metadata: Mapping[str, bool], battery: Battery = None, auxBattery: Battery = None, min_battery_soc: int = 20,
                 image_path: str = None, name: str = None, **kwargs):
        """
        Initialize the EVCar class.

        Parameters
        ----------
        ev_simulation : EVSimulation
            Temporal features, locations, predicted SOCs and more.
        battery : Battery
            An instance of the Battery class.
        observation_metadata : dict
            Mapping of active and inactive observations.
        action_metadata : dict
            Mapping od active and inactive actions.
        name : str, optional
            Unique electric_vehicle name.

        Other Parameters
        ----------------
        **kwargs : dict
            Other keyword arguments used to initialize super class.
        """

        self.ev_simulation = ev_simulation
        self.name = name

        super().__init__(
            seconds_per_time_step=kwargs.get('seconds_per_time_step'),
            random_seed=kwargs.get('random_seed'),
            episode_tracker=episode_tracker
        )

        self.battery = battery
        self.aux_battery = auxBattery
        self.observation_metadata = observation_metadata
        self.action_metadata = action_metadata
        self.non_periodic_normalized_observation_space_limits = None
        self.periodic_normalized_observation_space_limits = None
        self.observation_space = self.estimate_observation_space()
        self.action_space = self.estimate_action_space()
        self.min_battery_soc = min_battery_soc
        self.image_path = image_path
        self.__observation_epsilon = 0.0  # to avoid out of bound observations



    @property
    def ev_simulation(self) -> EVSimulation:
        """Return the electric_vehicle simulation data."""
        return self.__ev_simulation

    @ev_simulation.setter
    def ev_simulation(self, ev_simulation: EVSimulation):
        self.__ev_simulation = ev_simulation

    @property
    def name(self) -> str:
        """Unique building name."""

        return self.__name

    @name.setter
    def name(self, name: str):
        self.__name = name    \

    @property
    def min_battery_soc(self) -> int:
        """min battery soc percentage."""

        return self.__min_battery_soc

    @min_battery_soc.setter
    def min_battery_soc(self, min_battery_soc: str):
        self.__min_battery_soc = min_battery_soc

    @property
    def image_path(self) -> str:
        """Unique building name."""

        return self.__image_path

    @image_path.setter
    def image_path(self, image_path: str):
        self.__image_path = image_path

    @property
    def observation_metadata(self) -> Mapping[str, bool]:
        """Mapping of active and inactive observations."""

        return self.__observation_metadata

    @property
    def action_metadata(self) -> Mapping[str, bool]:
        """Mapping od active and inactive actions."""

        return self.__action_metadata

    @observation_metadata.setter
    def observation_metadata(self, observation_metadata: Mapping[str, bool]):
        self.__observation_metadata = observation_metadata

    @action_metadata.setter
    def action_metadata(self, action_metadata: Mapping[str, bool]):
        self.__action_metadata = action_metadata

    @property
    def battery(self) -> Battery:
        """Battery for electric_vehicle."""
        return self.__battery

    @property
    def aux_battery(self) -> Battery:
        """Battery for electric_vehicle."""
        return self.__aux_battery

    @battery.setter
    def battery(self, battery: Battery):
        self.__battery = Battery(0.0, 0.0) if battery is None else battery

    @aux_battery.setter
    def aux_battery(self, auxBattery: Battery):
        self.__aux_battery = Battery(0.0, 0.0) if auxBattery is None else auxBattery

    @property
    def observation_space(self) -> spaces.Box:
        """Agent observation space."""

        return self.__observation_space

    @property
    def action_space(self) -> spaces.Box:
        """Agent action spaces."""

        return self.__action_space

    @property
    def active_observations(self) -> List[str]:
        """Observations in `observation_metadata` with True value i.e. obeservable."""

        return [k for k, v in self.observation_metadata.items() if v]

    @property
    def active_actions(self) -> List[str]:
        """Actions in `action_metadata` with True value i.e.
        indicates which storage systems are to be controlled during simulation."""

        return [k for k, v in self.action_metadata.items() if v]

    @observation_space.setter
    def observation_space(self, observation_space: spaces.Box):
        self.__observation_space = observation_space
        self.non_periodic_normalized_observation_space_limits = self.estimate_observation_space_limits(
            include_all=True, periodic_normalization=False
        )
        self.periodic_normalized_observation_space_limits = self.estimate_observation_space_limits(
            include_all=True, periodic_normalization=True
        )

    @action_space.setter
    def action_space(self, action_space: spaces.Box):
        self.__action_space = action_space

    def adjust_ev_soc_on_system_connection(self, soc_system_connection):
        """
        Adjusts the state of charge (SoC) of an electric vehicle's (electric_vehicle's) battery upon connection to the system.

        When an electric_vehicle is in transit, the system "loses" the connection and does not know how much battery
        has been used during travel. As such, when an electric_vehicle enters an incoming or connected state, its battery
        SoC is updated to be close to the predicted SoC at arrival present in the electric_vehicle dataset.

        However, predictions sometimes fail, so this method introduces variability for the simulation by
        randomly creating a discrepancy between the predicted value and a "real-world inspired" value. This discrepancy
        is generated using a normal (Gaussian) distribution, which is more likely to produce values near 0 and less
        likely to produce extreme values.

        The range of potential variation is between -30% to +30% of the predicted SoC, with most of the values
        being close to 0 (i.e., the prediction). The exact amount of variation is calculated by taking a random
        value from the normal distribution and scaling it by the predicted SoC. This value is then added to the
        predicted SoC to get the actual SoC, which can be higher or lower than the prediction.

        The difference between the actual SoC and the initial SoC (before the adjustment) is passed to the
        battery's charge method. If the difference is positive, the battery is charged; if the difference is negative,
        the battery is discharged.

        For example, if the electric_vehicle dataset has a predicted SoC at arrival of 20% (of the battery's total capacity),
        this method can randomly adjust the electric_vehicle's battery to 22% or 19%, or even by a larger margin such as 40%.

        Args:
        soc_system_connection (float): The predicted SoC at system connection, expressed as a percentage of the
        battery's total capacity.
        """

        # Get the SoC in kWh from the battery
        soc_init_kwh = self.battery.initial_soc
        aux_soc_init_kwh = self.aux_battery.initial_soc

        # Calculate the system connection SoC in kWh
        soc_system_connection_kwh = self.battery.capacity * (soc_system_connection / 100)
        aux_soc_system_connection_kwh = self.aux_battery.capacity * (soc_system_connection / 100)

        # Determine the range for random variation.
        # Here we use a normal distribution centered at 0 and a standard deviation of 0.1.
        # We also make sure that the values are truncated at -20% and +20%.
        variation_percentage = np.clip(np.random.normal(0, 0.1), -0.2, 0.2)

        # Apply the variation
        variation_kwh = variation_percentage * soc_system_connection_kwh
        aux_variation_kwh = variation_percentage * aux_soc_system_connection_kwh

        # Calculate the final SoC in kWh
        soc_final_kwh = soc_system_connection_kwh + variation_kwh
        aux_soc_final_kwh = aux_soc_system_connection_kwh + aux_variation_kwh

        # Charge or discharge the battery to the new SoC.
        self.battery.set_ad_hoc_charge(soc_final_kwh - soc_init_kwh)
        self.aux_battery.set_ad_hoc_charge(aux_soc_final_kwh - aux_soc_init_kwh)

    def next_time_step(self) -> Mapping[int, str]:

        """
        Advance electric_vehicle to the next `time_step` by
        """

        self.battery.next_time_step()
        self.aux_battery.next_time_step()
        super().next_time_step()

        if self.ev_simulation.ev_charger_state[self.time_step] == 2:
            self.adjust_ev_soc_on_system_connection(self.ev_simulation.ev_estimated_soc_arrival[self.time_step])

        elif self.ev_simulation.ev_charger_state[self.time_step] == 3:
            self.adjust_ev_soc_on_system_connection((self.battery.soc[-1] / self.battery.capacity)*100)


    def reset(self):
        """
        Reset the EVCar to its initial state.
        """
        super().reset()

        #object reset
        #ToDO Problem Here

        self.battery.reset()
        self.aux_battery.reset()



    def observations(self, include_all: bool = None, normalize: bool = None, periodic_normalization: bool = None) -> \
            Mapping[str, float]:
        r"""Observations at current time step.

        Parameters
        ----------
        include_all: bool, default: False,
            Whether to estimate for all observations as listed in `observation_metadata` or only those that are active.
        normalize : bool, default: False
            Whether to apply min-max normalization bounded between [0, 1].
        periodic_normalization: bool, default: False
            Whether to apply sine-cosine normalization to cyclic observations.

        Returns
        -------
        observation_space : spaces.Box
            Observation low and high limits.
        """

        unwanted_keys = ['month', 'hour', 'day_type', "ev_charger_state", "charger"]

        normalize = False if normalize is None else normalize
        periodic_normalization = False if periodic_normalization is None else periodic_normalization
        include_all = False if include_all is None else include_all

        data = {
            **{
                k.lstrip('_'): self.ev_simulation.__getattr__(k.lstrip('_'))[self.time_step]
                for k, v in vars(self.ev_simulation).items() if isinstance(v, np.ndarray) and k not in unwanted_keys
            },
            'ev_soc': self.battery.soc[self.time_step] / self.battery.capacity
        }


        if include_all:
            valid_observations = list(self.observation_metadata.keys())
        else:
            valid_observations = self.active_observations

        observations = {k: data[k] for k in valid_observations if k in data.keys()}
        unknown_observations = list(set(valid_observations).difference(observations.keys()))
        assert len(unknown_observations) == 0, f'Unknown observations: {unknown_observations}'

        low_limit, high_limit = self.periodic_normalized_observation_space_limits
        periodic_observations = self.get_periodic_observation_metadata()

        if periodic_normalization:
            observations_copy = {k: v for k, v in observations.items()}
            observations = {}
            pn = PeriodicNormalization(x_max=0)

            for k, v in observations_copy.items():
                if k in periodic_observations:
                    pn.x_max = max(periodic_observations[k])
                    sin_x, cos_x = v * pn
                    observations[f'{k}_cos'] = cos_x
                    observations[f'{k}_sin'] = sin_x
                else:
                    observations[k] = v
        else:
            pass

        if normalize:
            nm = Normalize(0.0, 1.0)

            for k, v in observations.items():
                nm.x_min = low_limit[k]
                nm.x_max = high_limit[k]
                observations[k] = v * nm
        else:
            pass
        return observations


    @staticmethod
    def get_periodic_observation_metadata() -> dict[str, range]:
        r"""Get periodic observation names and their minimum and maximum values for periodic/cyclic normalization.

        Returns
        -------
        periodic_observation_metadata: Mapping[str, int]
            Observation low and high limits.
        """

        return {
            'hour': range(1, 25),
            'day_type': range(1, 9),
            'month': range(1, 13)
        }

    def estimate_observation_space(self, include_all: bool = None, normalize: bool = None,
                                   periodic_normalization: bool = None) -> spaces.Box:
        r"""Get estimate of observation spaces.
        Parameters
        ----------
        include_all: bool, default: False,
            Whether to estimate for all observations as listed in `observation_metadata` or only those that are active.
        normalize : bool, default: False
            Whether to apply min-max normalization bounded between [0, 1].
        periodic_normalization: bool, default: False
            Whether to apply sine-cosine normalization to cyclic observations including hour, day_type and month.
        Returns
        -------
        observation_space : spaces.Box
            Observation low and high limits.
        """
        normalize = False if normalize is None else normalize
        normalized_observation_space_limits = self.estimate_observation_space_limits(
            include_all=include_all, periodic_normalization=True
        )
        unnormalized_observation_space_limits = self.estimate_observation_space_limits(
            include_all=include_all, periodic_normalization=False
        )
        if normalize:
            low_limit, high_limit = normalized_observation_space_limits
            low_limit = [0.0] * len(low_limit)
            high_limit = [1.0] * len(high_limit)
        else:
            low_limit, high_limit = unnormalized_observation_space_limits
            low_limit = list(low_limit.values())
            high_limit = list(high_limit.values())
        return spaces.Box(low=np.array(low_limit, dtype='float32'), high=np.array(high_limit, dtype='float32'))

    def estimate_observation_space_limits(self, include_all: bool = None, periodic_normalization: bool = None) -> Tuple[
        Mapping[str, float], Mapping[str, float]]:
        r"""Get estimate of observation space limits.
        Find minimum and maximum possible values of all the observations, which can then be used by the RL agent to scale the observations and train any function approximators more effectively.
        Parameters
        ----------
        include_all: bool, default: False,
            Whether to estimate for all observations as listed in `observation_metadata` or only those that are active.
        periodic_normalization: bool, default: False
            Whether to apply sine-cosine normalization to cyclic observations including hour, day_type and month.
        Returns
        -------
        observation_space_limits : Tuple[Mapping[str, float], Mapping[str, float]]
            Observation low and high limits.
        Notes
        -----
        Lower and upper bounds of net electricity consumption are rough estimates and may not be completely accurate hence,
        scaling this observation-variable using these bounds may result in normalized values above 1 or below 0.
        """
        include_all = False if include_all is None else include_all
        observation_names = list(self.observation_metadata.keys()) if include_all else self.active_observations
        periodic_normalization = False if periodic_normalization is None else periodic_normalization
        periodic_observations = self.get_periodic_observation_metadata()
        low_limit, high_limit = {}, {}
        for key in observation_names:
            if key in "ev_estimated_departure_time" or key in "ev_estimated_arrival_time":
                    low_limit[key] = 0
                    high_limit[key] = 24
            elif key in "ev_required_soc_departure" or key in "ev_estimated_soc_arrival"  or key in "ev_soc":
                    low_limit[key] = 0.0
                    high_limit[key] = 1.0
        low_limit = {k: v - 0.05 for k, v in low_limit.items()}
        high_limit = {k: v + 0.05 for k, v in high_limit.items()}
        return low_limit, high_limit

    def estimate_action_space(self) -> spaces.Box:
        r"""Get estimate of action spaces.
        Find minimum and maximum possible values of all the actions, which can then be used by the RL agent to scale the selected actions.
        Returns
        -------
        action_space : spaces.Box
            Action low and high limits.
        Notes
        -----
        The lower and upper bounds for the `cooling_storage`, `heating_storage` and `dhw_storage` actions are set to (+/-) 1/maximum_demand for each respective end use,
        as the energy storage device can't provide the building with more energy than it will ever need for a given time step. .
        For example, if `cooling_storage` capacity is 20 kWh and the maximum `cooling_demand` is 5 kWh, its actions will be bounded between -5/20 and 5/20.
        These boundaries should speed up the learning process of the agents and make them more stable compared to setting them to -1 and 1.
        """
        low_limit, high_limit = [], []
        for key in self.active_actions:
            if key == 'ev_storage':
                limit = self.battery.nominal_power / self.battery.capacity
                low_limit.append(-limit)
                high_limit.append(limit)
        return spaces.Box(low=np.array(low_limit, dtype='float32'), high=np.array(high_limit, dtype='float32'))

    def autosize_battery(self, **kwargs):
        """Autosize `Battery` for a typical electric_vehicle.

        Other Parameters
        ----------------
        **kwargs : dict
            Other keyword arguments parsed to `electrical_storage` `autosize` function.
        """

        self.battery.autosize_for_EV()

    @staticmethod
    def observations_length() -> Mapping[str, int]:
        r"""Get periodic observation names and their minimum and maximum values for periodic/cyclic normalization.

        Returns
        -------
        periodic_observation_metadata: Mapping[str, int]
            Observation low and high limits.
        """

        return {
            'hour': range(1, 25),
            'day_type': range(1, 9),
            'month': range(1, 13)
        }

    def __str__(self):
        ev_simulation_attrs = [
            f"electric_vehicle simulation (time_step={self.time_step}):",
            f"Month: {self.ev_simulation.month[self.time_step]}",
            f"Hour: {self.ev_simulation.hour[self.time_step]}",
            f"Day Type: {self.ev_simulation.day_type[self.time_step]}",
            f"State: {self.ev_simulation.ev_charger_state[self.time_step]}",
            f"Estimated Departure Time: {self.ev_simulation.ev_estimated_departure_time[self.time_step]}",
            f"Required Soc At Departure: {self.ev_simulation.ev_required_soc_departure[self.time_step]}",
            f"Estimated Arrival Time: {self.ev_simulation.ev_estimated_arrival_time[self.time_step]}",
            f"Estimated Soc Arrival: {self.ev_simulation.ev_estimated_soc_arrival[self.time_step]}"
        ]

        ev_simulation_str = '\n'.join(ev_simulation_attrs)

        return (
            f"electric_vehicle {self.name}:\n"
            f"  Battery: {self.battery}\n\n"
            f"Simulation details:\n"
            f"  {ev_simulation_str}"
        )

