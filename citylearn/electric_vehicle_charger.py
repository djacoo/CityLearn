import inspect
from typing import List, Dict
from citylearn.base import Environment

from citylearn.electric_vehicle import electric_vehicle

ZERO_DIVISION_CAPACITY = 0.00001


class Charger(Environment):
    def __init__(
            self,
            nominal_power: float,
            efficiency: float = None,
            charger_id: str = None,
            charger_type: int = None,
            max_charging_power: float = 50.0,
            min_charging_power: float = 0.0,
            max_discharging_power: float = 50.0,
            min_discharging_power: float = 0.0,
            charge_efficiency_curve: Dict[float, float] = None,
            discharge_efficiency_curve: Dict[float, float] = None,
            image_path: str = None,
            connected_ev: electric_vehicle = None, incoming_ev: electric_vehicle = None,
            **kwargs
    ):
        r"""Initializes the `Electric Vehicle Charger` class with the given attributes.

        Parameters
        ----------
        charger_id: str
            Id through which the charger is uniquely identified in the system
        charger_type: int
            Either private (0) or public (1) charger
        max_charging_power : float, default 50
            Maximum charging power in kW.
        min_charging_power : float, default 0
            Minimum charging power in kW.
        max_discharging_power : float, default 50
            Maximum discharging power in kW.
        min_discharging_power : float, default 0
            Minimum discharging power in kW.
        charge_efficiency_curve : dict, default {3.6: 0.95, 7.2: 0.97, 22: 0.98, 50: 0.98}
            Efficiency curve for charging containing power levels and corresponding efficiency values.
        discharge_efficiency_curve : dict, default {3.6: 0.95, 7.2: 0.97, 22: 0.98, 50: 0.98}
            Efficiency curve for discharging containing power levels and corresponding efficiency values.
        max_connected_cars : int, default 1
            Maximum number of cars that can be connected to the charger simultaneously.

        Other Parameters
        ----------------
        **kwargs : dict
            Other keyword arguments used to initialize super classes.
        """

        self.nominal_power = nominal_power
        self.efficiency = efficiency
        self.charger_id = charger_id
        self.charger_type = charger_type
        self.max_charging_power = max_charging_power
        self.min_charging_power = min_charging_power
        self.max_discharging_power = max_discharging_power
        self.min_discharging_power = min_discharging_power
        self.charge_efficiency_curve = charge_efficiency_curve or {3.6: 0.95, 7.2: 0.97, 22: 0.98, 50: 0.98}
        self.discharge_efficiency_curve = discharge_efficiency_curve or {3.6: 0.95, 7.2: 0.97, 22: 0.98, 50: 0.98}
        self.image_path = image_path
        self.connected_ev = connected_ev or None
        self.incoming_ev = incoming_ev or None

        arg_spec = inspect.getfullargspec(super().__init__)
        kwargs = {
            key: value for (key, value) in kwargs.items()
            if (key in arg_spec.args or (arg_spec.varkw is not None))
        }
        super().__init__(**kwargs)

    @property
    def charger_id(self) -> str:
        """ID of the charger."""
        return self.__charger_id

    @property
    def charger_type(self) -> int:
        """Type of the charger."""
        return self.__charger_type

    @property
    def max_charging_power(self) -> float:
        """Maximum charging power in kW."""
        return self.__max_charging_power

    @property
    def image_path(self) -> str:
        """Unique building name."""

        return self.__image_path

    @image_path.setter
    def image_path(self, image_path: str):
        self.__image_path = image_path

    @property
    def min_charging_power(self) -> float:
        """Minimum charging power in kW."""
        return self.__min_charging_power

    @property
    def max_discharging_power(self) -> float:
        """Maximum discharging power in kW."""
        return self.__max_discharging_power

    @property
    def min_discharging_power(self) -> float:
        """Minimum discharging power in kW."""
        return self.__min_discharging_power

    @property
    def charge_efficiency_curve(self) -> dict:
        """Efficiency curve for charging containing power levels and corresponding efficiency values."""
        return self.__charge_efficiency_curve

    @property
    def discharge_efficiency_curve(self) -> dict:
        """Efficiency curve for discharging containing power levels and corresponding efficiency values."""
        return self.__discharge_efficiency_curve

    @property
    def connected_ev(self) -> electric_vehicle:
        """electric_vehicle currently connected to charger"""
        return self.__connected_ev

    @property
    def incoming_ev(self) -> electric_vehicle:
        """electric_vehicle incoming to charger"""
        return self.__incoming_ev

    @charger_id.setter
    def charger_id(self, charger_id: str):
        self.__charger_id = charger_id

    @property
    def efficiency(self) -> float:
        """Technical efficiency."""

        return self.__efficiency

    @efficiency.setter
    def efficiency(self, efficiency: float):
        if efficiency is None:
            self.__efficiency = 1.0
        else:
            assert efficiency > 0, 'efficiency must be > 0.'
            self.__efficiency = efficiency

    @property
    def nominal_power(self) -> float:
        r"""Nominal power."""

        return self.__nominal_power

    @property
    def past_connected_evs(self) -> List[electric_vehicle]:
        r"""Each timestep with the list of Past connected Evs or None in the case no car was connected """

        return self.__past_connected_evs

    @property
    def past_charging_action_values(self) -> List[float]:
        r"""Actions given to charge/discharge in [kWh]. Different from the electricity consumption as in this an action can be given but no car being connect it will not consume such energy"""

        return self.__past_charging_action_values

    @property
    def electricity_consumption(self) -> List[float]:
        r"""Electricity consumption time series."""

        return self.__electricity_consumption

    @property
    def electricity_consumption_without_partial_load(self) -> List[float]:
        r"""Electricity consumption time series in the case of EVs are not being controlled by an algorithm"""

        return self.__electricity_consumption_without_partial_load

    @property
    def available_nominal_power(self) -> float:
        r"""Difference between `nominal_power` and `electricity_consumption` at current `time_step`."""

        return None if self.nominal_power is None else self.nominal_power - self.electricity_consumption[self.time_step]

    @nominal_power.setter
    def nominal_power(self, nominal_power: float):
        if nominal_power is None or nominal_power == 0:
            self.__nominal_power = ZERO_DIVISION_CAPACITY
        else:
            assert nominal_power >= 0, 'nominal_power must be >= 0.'
            self.__nominal_power = nominal_power

    def update_electricity_consumption(self, electricity_consumption: float):
        r"""Updates `electricity_consumption` at current `time_step`.

        Parameters
        ----------
        electricity_consumption : float
            value to add to current `time_step` `electricity_consumption`. Must be >= 0.
        """

        assert electricity_consumption >= 0, 'electricity_consumption must be >= 0.'
        self.__electricity_consumption[self.time_step] += electricity_consumption

    @charger_type.setter
    def charger_type(self, charger_type: str):
        self.__charger_type = charger_type

    @max_charging_power.setter
    def max_charging_power(self, max_charging_power: float):
        self.__max_charging_power = max_charging_power

    @min_charging_power.setter
    def min_charging_power(self, min_charging_power: float):
        self.__min_charging_power = min_charging_power

    @max_discharging_power.setter
    def max_discharging_power(self, max_discharging_power: float):
        self.__max_discharging_power = max_discharging_power

    @min_discharging_power.setter
    def min_discharging_power(self, min_discharging_power: float):
        self.__min_discharging_power = min_discharging_power

    @charge_efficiency_curve.setter
    def charge_efficiency_curve(self, charge_efficiency_curve: dict):
        self.__charge_efficiency_curve = charge_efficiency_curve

    @discharge_efficiency_curve.setter
    def discharge_efficiency_curve(self, discharge_efficiency_curve: dict):
        self.__discharge_efficiency_curve = discharge_efficiency_curve

    @connected_ev.setter
    def connected_ev(self, ev: electric_vehicle):
        self.__connected_ev = ev

    @incoming_ev.setter
    def incoming_ev(self, ev: electric_vehicle):
        self.__incoming_ev = ev

    def plug_car(self, car: electric_vehicle):
        """
        Connects a car to the charger.

        Parameters
        ----------
        car : object
            Car instance to be connected to the charger.

        Raises
        ------
        ValueError
            If the charger has reached its maximum connected cars' capacity.
        """
        self.__past_connected_evs[self.time_step] = car
        self.connected_ev = car

    def unplug_car(self):
        """
        Disconnects a car from the charger.

        Parameters
        ----------
        car : object
            Car instance to be disconnected from the charger.
        """
        self.connected_ev = None

    def associate_incoming_car(self, car: electric_vehicle):
        """
        Associates incoming car to the charger.

        Parameters
        ----------
        car : object
            Car instance to be connected to the charger.

        Raises
        ------
        ValueError
            If the charger has reached its maximum associated cars' capacity.
        """
        self.incoming_ev = car

        # else:
        #    raise ValueError("Charger has reached its maximum associated cars capacity")

    def disassociate_incoming_car(self):
        """
        Disassociates incoming car from the charger.

        Parameters
        ----------
        car : object
            Car instance to be disconnected from the charger.
        """
        self.incoming_ev = None

    def update_connected_ev_soc(self, action_value: float):
        self.__past_charging_action_values[self.time_step] = action_value
        if self.connected_ev and action_value != 0:
            car = self.connected_ev
            if action_value > 0:
                energy = action_value * self.max_charging_power
            else:
                energy = action_value * self.max_discharging_power

            charging = energy >= 0

            if charging:
                # make sure we do not charge beyond the maximum capacity
                energy = min(energy, car.battery.capacity - car.battery.soc[self.time_step])
            else:
                # make sure we do not discharge beyond the minimum level (assuming it's zero)
                max_discharge = - (car.battery.soc[self.time_step] - 0.10 * car.battery.capacity)
                energy = max(energy, max_discharge)


            energy_kwh = energy * self.efficiency

            # Here we call the car's battery's charge method directly, passing the energy (positive for charging,
            # negative for discharging)
            car.battery.charge(energy_kwh)
            self.__electricity_consumption[self.time_step] = car.battery.electricity_consumption[-1]

            #charge for maintaining the case of no partial load, this is just for result comparison and is done to a no partial load battery

            energy_aux = min(self.max_charging_power, (car.aux_battery.capacity * car.ev_simulation.ev_required_soc_departure[self.time_step]) - car.aux_battery.soc[self.time_step])
            car.aux_battery.charge(energy_aux)
            self.__electricity_consumption_without_partial_load[self.time_step] = car.aux_battery.electricity_consumption[-1]
        else:
            self.__electricity_consumption[self.time_step] = 0
            self.__electricity_consumption_without_partial_load[self.time_step] = 0

    def next_time_step(self):
        r"""Advance to next `time_step` and set `electricity_consumption` at new `time_step` to 0.0."""

        self.__electricity_consumption.append(0.0)
        self.__electricity_consumption_without_partial_load.append(0.0)
        self.__past_connected_evs.append(None)
        self.__past_charging_action_values.append(0.0)
        self.connected_ev = None
        self.incoming_ev = None
        super().next_time_step()

    def reset(self):
        """
        Resets the Charger to its initial state by disconnecting all cars.
        """
        super().reset()
        self.connected_ev = None
        self.incoming_ev = None
        self.__electricity_consumption = [0.0]
        self.__electricity_consumption_without_partial_load = [0.0]
        self.__past_connected_evs = [None]
        self.__past_charging_action_values = [0.0]

    def __str__(self):
       return (
            f"Charger ID: {self.charger_id}\n"
            f"electricity consumption: {self.electricity_consumption} kW\n"
            f"electricity_consumption_without_partial_load: {self.electricity_consumption_without_partial_load} kW\n"
            f"past_connected_evs: {self.past_connected_evs} kW\n"
            f"past_charging_action_values: {self.past_charging_action_values} kW\n"
            f"Currently Connected Car: {self.connected_ev}\n"
            f"Incoming electric_vehicle: {self.incoming_ev}\n"
       )
#
