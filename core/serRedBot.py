#!/usr/bin/env python3

import threading as th
import configparser as cp
import time, serial
from core.utils import sysUtils
from core.redisOps import redisOps
from core.logutils import logUtils


class serRedBot(th.Thread):

   def __init__(self, _cp: cp.ConfigParser, redops: redisOps):
      super().__init__()
      self.cp = _cp
      self.dev: str = str(self.cp["SERIAL"]["DEV"])
      self.baudrate: int = int(self.cp["SERIAL"]["BAUDRATE"])
      self.channel = str(self.cp["SYSPATH"]["CHANNEL"])
      self.diag_tag: str = str(self.cp["SYSINFO"]["DIAG_TAG"])
      self.ser: serial.Serial = serial.Serial(port=self.dev, baudrate=self.baudrate)
      self.redops: redisOps = redops
      self.start_dts_dts_utc = sysUtils.dts_utc()
      self.last_msg_dts_utc = ""

   def run(self):
      pub_channel: str = self.cp["REDIS"]["PUB_READS_CHANNEL"]
      _dict = {"boot_dts_utc": sysUtils.dts_utc(), "dev": self.dev
         , "lan_ip": sysUtils.lan_ip(), "hostname": sysUtils.HOST
         , "pub_reads_channel": pub_channel}
      self.redops.update_diag_tag(self.diag_tag, mapdct=_dict, restart=True)
      while True:
         self.__run_loop()

   def __read_string(self) -> str:
      barr: bytearray = bytearray()
      while True:
         __char = self.ser.read()
         # -- start char --
         if chr(__char[0]) == '#':
            barr.clear()
         barr.extend(__char)
         # -- test end --
         if chr(__char[0]) == '!':
            break
      # -- --
      return barr.decode("utf-8")

   def __run_loop(self):
      try:
         # -- -- -- -- -- -- -- -- -- -- -- --
         buff = None
         time.sleep(0.48)
         if self.ser.inWaiting():
            buff = self.__read_string()
         # -- -- -- -- -- -- -- -- -- -- -- --
         if buff is None:
            return
         # -- -- -- -- -- -- -- -- -- -- -- --
         if buff.startswith("#") and buff.endswith("!"):
            __dict = {"last_msg_dts_utc": sysUtils.dts_utc(), "last_msg": buff}
            self.redops.update_diag_tag(diag_tag=self.diag_tag, mapdct=__dict)
         # -- -- -- -- -- -- -- -- -- -- -- --
         print(buff)
         self.redops.pub_diag_debug(buff)
         if not buff.startswith("#RPT|PZEM:SS_"):
            return
         # -- -- -- -- -- -- -- -- -- -- -- --
         arr: [] = buff.split("|")
         pzem_ss = arr[1].split(":")[1]
         arr.insert(1, f"DTSUTC:{sysUtils.dts_utc()}")
         syspath: str = sysUtils.syspath(self.channel, pzem_ss)
         arr.insert(2, f"PATH:{syspath}")
         buff = "|".join(arr)
         # -- -- publish & set -- --
         self.redops.pub_read(buff)
         self.redops.save_read(syspath, buff)
         self.redops.save_heartbeat(syspath, buff)
         # -- -- -- -- -- -- -- -- -- -- -- --
      except Exception as e:
         logUtils.log_exp(e)
         time.sleep(2.0)

   def __monitor_thread(self):
      pass
