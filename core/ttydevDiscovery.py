
import threading as _th
import configparser as _cp
import minimalmodbus as mm
import os, time, typing as t
import xml.etree.ElementTree as et
# -- system --
from system.ports import ports
from core.redisOps import redisOps
from modbus.ttydevMeters import ttydevMeters
from modbus.pingResults import pingResults


class ttyUSBDeviceScanner(_th.Thread):

   AUTO = "AUTO"

   def __init__(self, redops: redisOps
         , ttydev_disco_bot_cp: _cp.ConfigParser
         , modbus_redis_bot_cp: _cp.ConfigParser
         , ttydev_meters_arr):
      # -- -- -- run -- -- --
      super().__init__()
      self.redops: redisOps = redops
      self.cp_ttydev_disco_bot: _cp.ConfigParser = ttydev_disco_bot_cp
      self.cp_modbus_redis_bot: _cp.ConfigParser = modbus_redis_bot_cp
      self.ttydev_meters_arr: [ttydevMeters] = ttydev_meters_arr
      # self.ttyDev = ttyDev
      self.model_xmls: {} = {}
      self.meters: t.List[et.Element] = []
      self.usb_ser_ports: [] = None

   def init(self):
      self.usb_ser_ports = ports.serial_ports_arr("USB")

   def run(self):
      while True:
         if self.__main_loop() == 0:
            break
      # -- end of test loop --
      print("-- [ ping_end ] --")

   def __main_loop(self) -> int:
      # -- per ttydev meters --
      for ttydev_meters in self.ttydev_meters_arr:
         self.__on_ttydev_meters(ttydev_meters)
      # -- -- -- --
      return 0

   def __on_ttydev_meters(self, dev_meters: ttydevMeters):
      # -- per meter in ttydev --
      accu: [] = []
      THRESHOLD_LIMIT: int = int(self.cp_ttydev_disco_bot["SYSINFO"]["THRESHOLD_LIMIT"])
      for meter in dev_meters.meters:
         _meter, _dev = self.__on_meter(meter)
         if _meter and _dev:
            accu.append((_meter, _dev))
         # -- test detection threshold limit --
         if len(accu) >= THRESHOLD_LIMIT:
            print("THRESHOLD_LIMIT_REACHED")
            break
      # -- -- -- --
      if len(accu) < THRESHOLD_LIMIT:
         print("THRESHOLD_LIMIT_NOT_REACHED")
         return
      # -- -- -- --
      dev = dev_meters.dev
      alias = dev_meters.alias
      print(f"create dev link: {dev} -> {alias}")
      time.sleep(2.0)

   def __on_meter(self, meter: et.Element) -> ():
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
      return self.__try_ping_meter_on_usb_ports(meter, comm_xml)

   def __try_ping_meter_on_usb_ports(self, meter: et.Element, com_xml: et.Element) -> (et.Element, str):
      # -- -- -- --
      accu: {} = {}
      model_xml: str = meter.attrib["modelXML"]
      bus_addr: int = int(meter.attrib["busAddr"])
      bus_addr_reg_hex = meter.attrib["modbus_addr_reg"]
      # -- -- -- --
      for usb_dev in self.usb_ser_ports:
         if not os.path.exists(usb_dev):
            continue
         # -- -- --
         print(f"\n[ modelXML: {model_xml} ]")
         modbus_inst: mm.Instrument = self.__get_inst__(usb_dev, com_xml, bus_addr)
         resp: pingResults = self.__do_ping(modbus_inst, bus_addr_reg_hex)
         if resp.err_code != 0:
            accu[usb_dev] = resp
            print("NoPong!")
            continue
         else:
            print("PingOK!")
            return meter, usb_dev
      # -- -- -- --
      return None, None

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
