
import configparser as _cp
import xml.etree.ElementTree as _et
from core.utils import sysUtils as utils
from core.redisOps import redisOps
from system.ports import ports
from core.logutils import logUtils


class modbusEdgeMeters(object):

   def __init__(self, cp: _cp.ConfigParser, redops: redisOps, edge_xml: _et.Element):
      self.cp: _cp.ConfigParser = cp
      self.redops: redisOps = redops
      self.edge_xml: _et.Element = edge_xml
      self.pub_channel = self.edge_xml.attrib["pubChannel"]
      # -- -- edge_meters -- --
      self.ttydev_meters: [_et.Element] = self.edge_xml.findall("ttydev")

   def init(self):
      if len(self.ttydev_meters) == 0:
         raise Exception("NoEdgeMetersFound")
      # -- add syspath & etc... to each meter --
      # <ttydev run="yes" tag="ModbusEdgeA5" alias="modbusPortA" dev="auto" modbusBugID="bugID1">
      for meter_arr in self.ttydev_meters:
         tag = meter_arr.attrib["tag"]
         dev = meter_arr.attrib["dev"]
         alias = meter_arr.attrib["alias"]
         # -- -- -- -- -- -- -- --
         _ttydisc, _dev, _alias = self.__remap_ttydisc_dev_alias(tag, dev, alias)
         for m in meter_arr:
            try:
               m.attrib["ttydev"] = dev
               modbus_addr = m.attrib["busAddr"]
               syspath: str = utils.syspath("MODBUS", modbus_addr)
               m.attrib["syspath"] = syspath
               xdict: {} = {"init_dts_utc": utils.dts_utc(), "ttydev": dev, "bus_addr": modbus_addr}
               self.redops.save_meter_data(syspath, _dict=xdict, delold=True)
            except Exception as e:
               logUtils.log_exp(e)
         # -- -- -- -- -- -- -- --

   def push_to_redis(self, redops: redisOps):
      # -- -- -- -- -- --
      if redops is None:
         raise Exception("RedOpsIsNone")
      # -- -- -- -- -- --
      for _ttydev_meters in self.ttydev_meters:
         for _meter in _ttydev_meters:
            pass

   def __remap_ttydisc_dev_alias(self, tag: str, dev: str, alias: str) -> (str, str, str):
      # -- lookup dev in: OMMS_DEV_PATH/ttydev_discovery
      ttydisc = ""; dev_alias = ""
      _ports: ports = ports()
      _ports.load_serials(self.cp)
      if dev == "auto" and alias == "":
         ttydisc = ports.locate_ttydev(tag)
         patt = "|located:"
         pos = ttydisc.find(patt)
         dev = ttydisc[(pos + len(patt)):].strip(")")
      # -- use dev in: OMMS_DEV_PATH/dev/alias
      elif dev == "auto" and alias != "":
         dev_alias = ports.alias_pull_path(alias)
         if dev_alias:
            pass
         else:
            ttydev = dev
      # -- return --
      return ttydisc, dev, dev_alias
