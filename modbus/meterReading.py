
import json
from modbus.meterRegFormatter import meterRegFormatter as rf


class meterReading(object):

   def __init__(self, regName: str, regVal: object, regValUnit: str
         , fldRegMapped: bool = True, errorReading: bool = False
         , formatterName: str = None):
      # - - - - - -
      self.regName: str = regName
      self.regVal: object = regVal
      self.regValUnit: str = regValUnit
      self.fldRegMapped: bool = fldRegMapped
      self.hasError: bool = errorReading
      self.formatter: str = formatterName
      # - - - - - -
      if self.formatter not in ("", "n/s", "None", None):
         func = getattr(rf, self.formatter)
         self.regVal = func(self.regVal)

   def __str__(self) -> str:
      buff = "regName: %s; regVal: %s; regValUnit: %s; fldRegMapped: %s; hasError: %s" \
             % (self.regName, self.regVal, self.regValUnit, self.fldRegMapped, self.hasError)
      return buff

   def toJson(self) -> str:
      return json.dumps(self, default=lambda o: o.__dict__)

   def toDict(self) -> dict:
      return self.__dict__

   def __repr__(self) -> str:
      return json.dumps(self.__dict__)
