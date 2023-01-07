
import datetime
from core.utils import sysUtils as utils


class regInfo(object):

   def __init__(self):
      self.regtype: str = ""
      self.data: float = 0.0
      self.dts: datetime.datetime = utils.min_dts()
      self.syspath: str = ""
      self.meter_tag: str = ""
      # self.last_reading: datetime.datetime = utils.min_dts()

   def to_str(self) -> str:
      return f"syspath: {self.syspath} | rtype: {self.regtype} |" \
         f" data: {self.data} | dts: {self.dts}"


# - - test - -
if __name__ == "__main__":
   mi: regInfo = regInfo()
   mi.data = "xxx"
   mi.regtype = "type"
   mi.dts = "dta"
   print(mi.to_str())
