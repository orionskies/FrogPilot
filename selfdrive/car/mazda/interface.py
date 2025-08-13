#!/usr/bin/env python3
from typing import Iterable

from cereal import car, custom
from openpilot.common.conversions import Conversions as CV
from openpilot.selfdrive.car.mazda.values import CAR, LKAS_LIMITS
from openpilot.selfdrive.car import create_button_events, get_safety_config
from openpilot.selfdrive.car.interfaces import CarInterfaceBase

ButtonType = car.CarState.ButtonEvent.Type
FrogPilotButtonType = custom.FrogPilotCarState.ButtonEvent.Type
EventName = car.CarEvent.EventName

# EPS firmware family prefixes for 2022 CX-5 racks
EPS_2022_PREFIXES = (b'KSD5-3210X', b'KBST-3210X')  # add more if needed

def _has_2022_eps(car_fw: Iterable[car.CarParams.CarFw]) -> bool:
  """
  Returns True if EPS FW matches a known 2022 CX-5 rack family.
  """
  for f in car_fw:
    if f.ecu == car.CarParams.Ecu.eps:
      if any(f.fwVersion.startswith(p) for p in EPS_2022_PREFIXES):
        return True
  return False

class CarInterface(CarInterfaceBase):

  @staticmethod
  def _get_params(ret, candidate, fingerprint, car_fw, experimental_long, docs, frogpilot_toggles):
    ret.carName = "mazda"
    ret.safetyConfigs = [get_safety_config(car.CarParams.SafetyModel.mazda)]
    ret.radarUnavailable = True

    ret.steerActuatorDelay = 0.1
    ret.steerLimitTimer = 0.8

    # Detect newer EPS and tune accordingly
    has_new_eps = _has_2022_eps(car_fw)
    if has_new_eps:
      # Apply 2022 CX-5 torque tuning
      CarInterfaceBase.configure_torque_tune(CAR.MAZDA_CX5_2022, ret.lateralTuning)
      ret.minSteerSpeed = 0.0
    else:
      CarInterfaceBase.configure_torque_tune(candidate, ret.lateralTuning)
      if candidate not in (CAR.MAZDA_CX5_2022, ):
        ret.minSteerSpeed = LKAS_LIMITS.DISABLE_SPEED * CV.KPH_TO_MS

    ret.centerToFront = ret.wheelbase * 0.41
    ret.enableBsm = True

    return ret

  # returns a car.CarState
  def _update(self, c, frogpilot_toggles):
    ret, fp_ret = self.CS.update(self.cp, self.cp_cam, frogpilot_toggles)

    # TODO: add button types for inc and dec
    ret.buttonEvents = [
      *create_button_events(self.CS.distance_button, self.CS.prev_distance_button, {1: ButtonType.gapAdjustCruise}),
      *create_button_events(self.CS.lkas_enabled, self.CS.lkas_previously_enabled, {1: FrogPilotButtonType.lkas}),
    ]

    # events
    events = self.create_common_events(ret)

    if self.CS.lkas_disabled:
      events.add(EventName.lkasDisabled)
    elif self.CS.low_speed_alert:
      events.add(EventName.belowSteerSpeed)

    ret.events = events.to_msg()

    return ret, fp_ret