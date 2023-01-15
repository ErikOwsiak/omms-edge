
import datetime
from ommslib.shared.core.elecRegStrEnums import elecRegStrEnumsShort


class regInfo(object):

   def __init__(self, rtype: str, mtag: str):
      self.regtype: elecRegStrEnumsShort = elecRegStrEnumsShort[rtype]
      self.meter_tag: str = mtag
      self.data: float = 0.0
      self.last_update_dts_utc: datetime.datetime = datetime.datetime.min

   def __str__(self) -> str:
      return f"meter_tag: {self.meter_tag} | rtype: {self.regtype.name} |" \
         f" data: {self.data} | last_update_dts_utc: {self.last_update_dts_utc}"

   def update_data(self, d: str):
      self.data = round(float(d), 3)
      self.last_update_dts_utc = datetime.datetime.utcnow().replace(second=0, microsecond=0)
