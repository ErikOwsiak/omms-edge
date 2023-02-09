
import xml.etree.ElementTree as _et
from modbus.regDataMode import regDataMode
from ommslib.shared.core.elecRegStrEnums import elecRegStrEnumsShort
from core.logutils import logUtils


"""
   <reg type="SerialNum" addr="0x0000" size="2" decpnt="1" mode="" units="" />
"""
class meterReg(object):

   def __init__(self, elm: _et.Element):
      try:
         _hex: int = 16
         self.mtype = elm.attrib["type"]
         self.type: elecRegStrEnumsShort = elecRegStrEnumsShort[self.mtype]
         self.addr_hex: str =  elm.attrib["addr"]
         self.addr_dec: int = int(self.addr_hex, _hex)
         self.size: int = int(elm.attrib["size"])
         self.decpnt: int = int(elm.attrib["decpnt"])
         # -- -- -- --
         self.mode: regDataMode = regDataMode.register
         if "mode" in elm.attrib.keys() and elm.attrib["mode"] != "":
            self.mode = regDataMode[elm.attrib["mode"]]
         # -- -- -- --
         self.units: str = ""
         self.formatter: str = ""
         # -- -- -- --
         if "units" in elm.attrib.keys():
            self.units: str = elm.attrib["units"]
         if "formatter" in elm.attrib.keys():
            self.formatter: str = elm.attrib["formatter"]
      except Exception as e:
         logUtils.log_exp(["meterReg", e])
      finally:
         pass
