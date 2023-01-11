
import configparser as _cp
import os.path

import serial, time, typing as t
from serial.tools import list_ports as ser_tools


BAUDRATES = (9600, 19200, 38400, 57600, 115200)
DEVINFO_QRY: str = "#GET|DEVINFO!\n"
DEVSN_QRY: str = "#GET|DEVSN!\n"
RESP_TIMEOUT = 2.0


class ports(object):

   def __init__(self, cp: _cp.ConfigParser = None):
      self.cp: _cp.ConfigParser = cp
      self.serial_ports: [] = []
      self.found: {} = {}

   def load_serials(self) -> int:
      # -- -- -- --
      self.serial_ports = [p.device for p in ser_tools.comports()]
      # -- -- -- --
      path: str = self.cp["SYSINFO"]["OMMS_DEV_PATH"]
      if not os.path.exists(path):
         return 1
      # -- -- -- --
      file_lst = os.listdir(path)
      for fl in file_lst:
         self.serial_ports.append(f"{path}/{fl}")
      # -- -- -- --

   @staticmethod
   def locate_ttydev(tag: str) -> str:
      with open("/run/iotech/omms/ttydev_discovery") as f:
         lns = f.readlines()
      # -- select line --
      return [ln.strip() for ln in lns if f":{tag}::" in ln][0]

   @staticmethod
   def alias_pull_path(alias: str) -> [str, None]:
      path = "/run/iotech/omms/dev"
      flst = os.listdir(path)
      if alias in flst:
         return f"{path}/{alias}"
      else:
         return None

   @staticmethod
   def serial_ports_arr(patt: str):
      arr: [] = [p.device for p in ser_tools.comports() if patt in p.device]
      return arr

   def print(self):
      print("-> system serial_ports")
      if self.serial_ports is None or len(self.serial_ports) == 0:
         self.load_serials()
      for p in self.serial_ports:
         print(f"\tport: {p}")
      print("-> done")

   def scan(self):
      if self.serial_ports is None:
         self.load_serials()
      for port in self.serial_ports:
         if self.probe_port(port.device):
            break
      # -- --
      print("\n\t-- the end --\n")

   def probe_port(self, dev: str) -> bool:
      for bdrate in BAUDRATES:
         print(f"\nprobing device: {dev} @ {bdrate}")
         try:
            ser: serial.Serial = serial.Serial(port=dev, baudrate=bdrate
               , timeout=RESP_TIMEOUT, dsrdtr=False)
            if not ser.isOpen():
               ser.open()
         except serial.SerialException as e:
            print(e)
            continue
         # send dev query
         self.found[dev] = None
         if not self.__read(ser):
            self.found[dev] = {"Status": "NotFound"}
            return False
         else:
            print(f"GotResponse @ {bdrate}")
            self.found[dev] = {"Status": "Found", "Baudrate": bdrate}
            return True
      # - - - - - - - - - - - - - - - - - -
      return False

   def __read(self, _ser: serial.Serial) -> bool:
      try:
         if self.__read_devinfo(_ser):
            self.__read_serialnum(_ser)
            return True
         else:
            print("NoDevInfoFound!")
            return False
      except serial.SerialTimeoutException as e:
         print(e)
         return False
      except Exception as e:
         print(e)
         return False

   def __read_devinfo(self, _ser: serial.Serial) -> bool:
      print(f"sending: {DEVINFO_QRY}")
      _ser.write_timeout = 1.0
      cnt = _ser.write(bytearray(DEVINFO_QRY.encode("ascii")))
      time.sleep(RESP_TIMEOUT)
      if _ser.inWaiting() == 0:
         return False
      else:
         buff: str = _ser.read_all().decode("utf-8")
         pos = buff.find("#DEVINFO|")
         if pos != -1:
            sub = buff[pos:-1]
            print(f"found: {sub}")
         return True

   def __read_serialnum(self, _ser: serial.Serial) -> bool:
      print(f"sending: {DEVSN_QRY}")
      _ser.write_timeout = 1.0
      cnt = _ser.write(bytearray(DEVSN_QRY.encode("ascii")))
      # print(f"bytes sent: {cnt}")
      time.sleep(RESP_TIMEOUT)
      if _ser.inWaiting() == 0:
         return False
      else:
         # print(f"_ser.inWaiting: {_ser.inWaiting()}")
         buff: str = _ser.read_all().decode("utf-8")
         pos = buff.find("#DEVINFO|")
         if pos != -1:
            sub = buff[pos:-1]
            print(f"found: {sub}")
         return True
