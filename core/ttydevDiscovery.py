
import threading as _th
import configparser as _cp
import minimalmodbus as mm
import os, time, typing as t
import xml.etree.ElementTree as et
# -- system --
from system.ports import ports
from core.redisOps import redisOps
from core.utils import sysUtils as utils
from modbus.ttydevMeters import ttydevMeters
from modbus.pingResults import pingResults


class ttyUSBDeviceScanner(_th.Thread):

   def __init__(self, redops: redisOps, sys_ini: _cp.ConfigParser, ttydev_meters_arr):
      # -- -- -- run -- -- --
      super().__init__()
      self.redops: redisOps = redops
      self.sys_ini: _cp.ConfigParser = sys_ini
      self.sec_ini = self.sys_ini["TTYDEV_DISCO"]
      # -- -- -- --
      self.diag_tag = self.sec_ini["DIAG_TAG"]
      self.diag_tag = utils.set_systag(self.diag_tag)
      # -- -- -- --
      self.ttydev_meters_arr: [ttydevMeters] = ttydev_meters_arr
      self.model_xmls: {} = {}
      self.meters: t.List[et.Element] = []
      self.usb_ser_ports: [] = None
      self.is_done: bool = False
      self.located_ports: [] = []
      self.located_map: [] = []

   def init(self):
      self.usb_ser_ports = ports.serial_ports_arr("USB")
      _d = {"start_dts_utc": utils.dts_utc()
         , "usb_ser_ports": " | ".join(self.usb_ser_ports)}
      self.redops.update_diag_tag(self.diag_tag, mapdct=_d, restart=True)

   def run(self):
      while True:
         if self.__main_loop() == 0:
            break
      # -- end of test loop --
      self.is_done = True
      print("\n[ usb dev ports mappings ]")
      for d, a, _ in self.located_map:
         print(f" -> {d} | {a}")
      # -- create ttydev aliases in
      self.__create_dev_aliases()
      _d = {"end_dts_utc": utils.dts_utc()}
      self.redops.update_diag_tag(self.diag_tag, mapdct=_d)
      print("\n\t-- [ pinging_end ] --\n")

   def __main_loop(self) -> int:
      # -- per ttydev meters --
      self.located_ports.clear()
      for ttydev_meters in self.ttydev_meters_arr:
         self.__on_ttydev_meters(ttydev_meters)
      # -- -- -- --
      return 0

   def __create_dev_aliases(self):
      # -- -- -- -- -- -- -- --
      dev_path = self.sys_ini["CORE"]["RUN_IOTECH_DEV"]
      if not os.path.exists(dev_path):
         print(f"PathNotFound: {dev_path}")
         return
      # -- -- -- -- -- -- -- --
      for d, a, _ in self.located_map:
         if os.path.exists(d):
            a_path = f"{dev_path}/{a}"
            if not os.path.exists(a_path):
               os.system(f"ln -s {d} {a_path}")
            if os.path.exists(a_path):
               print(f"\tDEVLINK_OK!: {a_path}")
            else:
               print(f"\tDEVLINK_ERROR: {a_path}")
      # -- -- -- -- -- -- -- --
      # -- test dev links --
      for d, a, m in self.located_map:
         a_path = f"{dev_path}/{a}"
         _meter, _dev = self.__on_meter(m, a_path)
         if (_meter is not None) and (_dev is not None):
            b0, b1 = f"DEV: {d}", f"DEV_LINK_TESTED_OK: {a_path}"
         else:
            b0, b1 = f"DEV: {d}", f"DEV_LINK_TESTED_ERR: {a_path}"
         # -- -- -- -- --
         print([b0, b1])
         self.redops.update_diag_tag(self.diag_tag, mapdct={d: b1})

   def __on_ttydev_meters(self, dev_meters: ttydevMeters):
      # -- inner method --
      def __on_usb_ser_port(usb_ser):
         accu: [] = []
         print(f"\n\n\t--[ testing usb_port: {usb_ser} ]--\n")
         for meter in dev_meters.meters:
            _meter, _dev = self.__on_meter(meter, usb_ser)
            if (_meter is not None) and (_dev is not None):
               accu.append((_meter, _dev))
            # -- test detection threshold limit --
            if (len(accu) == 1 and len(dev_meters.meters) == 1) \
                  or (len(accu) >= THRESHOLD_LIMIT and len(dev_meters.meters) > 1):
               # -- -- -- -- --
               self.located_map.append((usb_ser, dev_meters.alias, _meter))
               self.located_ports.append(usb_ser)
               _dict = {"_dev": _dev, "dev": dev_meters.dev
                  , "alias": dev_meters.alias, "tag": dev_meters.tag}
               self.__on_threshold_reached(_dict)
               break
            else:
               pass
         return
      # -- -- -- --
      THRESHOLD_LIMIT: int = int(self.sec_ini["THRESHOLD_LIMIT"])
      for usb_ser_port in self.usb_ser_ports:
         if usb_ser_port not in self.located_ports:
            __on_usb_ser_port(usb_ser_port)
         else:
            print(f"\n\t[ dev_located: {usb_ser_port} ]\n")
      # -- -- -- --

   def __on_threshold_reached(self, _dict: {}):
      print("__on_threshold_reached")
      print(_dict)

   def __on_meter(self, meter: et.Element, dev_port: str) -> ():
      # -- load meter xml file --
      model_xml = meter.attrib["modelXML"]
      path = f"brands/{model_xml}"
      if path not in self.model_xmls.keys():
         if os.path.exists(path):
            print(os.getcwd())
            self.model_xmls[path] = et.parse(path).getroot()
         else:
            pass
      # -- -- found -- --
      # <comm type="serial" baudrate="9600" parity="E" stopbits="1" timeoutSecs="0.25" />
      model_xmldoc: et.Element = self.model_xmls[path]
      comm_xml: et.Element = model_xmldoc.find("comm[@type='serial']")
      reg_xml: et.Element = model_xmldoc.find("regs/reg[@type='ModbusAddr']")
      if reg_xml is None:
         pass
      meter.attrib["modbus_addr_reg"] = reg_xml.attrib["addr"]
      if comm_xml is None:
         pass
      # -- -- run -- --
      return self.__try_ping_meter_on_usb_port(dev_port, meter, comm_xml)

   def __try_ping_meter_on_usb_port(self
         , usb_dev_port: str
         , meter: et.Element
         , com_xml: et.Element) -> (et.Element, str):
      # -- -- -- --
      model_xml: str = meter.attrib["modelXML"]
      bus_addr: int = int(meter.attrib["busAddr"])
      bus_addr_reg_hex = meter.attrib["modbus_addr_reg"]
      # -- -- -- --
      if not os.path.exists(usb_dev_port):
         return None, None
      # -- -- --
      print(f"\n[ modelXML: {model_xml} ]")
      modbus_inst: mm.Instrument = self.__get_inst__(usb_dev_port, com_xml, bus_addr)
      resp: pingResults = self.__do_ping(modbus_inst, bus_addr_reg_hex)
      if resp.err_code != 0:
         print("NoPong!")
         return None, None
      else:
         print("PingOK!")
         return meter, usb_dev_port

   def __do_ping(self, inst: mm.Instrument, bus_addr_reg_hex: str) -> pingResults:
      HEX = 16
      err_code: int = 0
      err_msg: str = "OK"
      try:
         time.sleep(0.480)
         reg_loc = int(bus_addr_reg_hex, HEX)
         print(f"ping :: bus_addr: {inst.address} | on_dev: {inst.serial.name} | on_reg: {reg_loc}")
         val = inst.read_register(reg_loc)
         err_code = 1
         if int(inst.address) == int(val):
            err_code = 0
      except Exception as e:
         err_code = 2
         err_msg = str(e)
         print(err_code)
      finally:
         pingRes: pingResults = pingResults(err_code, err_msg)
         return pingRes

   def __get_inst__(self, usb_dev: str, ser: et.Element, bus_addr) -> mm.Instrument:
      inst = mm.Instrument(usb_dev, bus_addr)
      inst.serial.baudrate = int(ser.attrib["baudrate"])
      inst.serial.parity = ser.attrib["parity"]
      inst.serial.stopbits = int(ser.attrib["stopbits"])
      inst.serial.timeout = float(ser.attrib["timeoutSecs"])
      inst.debug = False
      return inst
