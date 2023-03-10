#!/usr/bin/env python3

import time, serial
import threading as th
import configparser as cp
# -- system --
from core.utils import sysUtils
from core.redisOps import redisOps
from core.logutils import logUtils
from core.meterInfoData import meterInfoData
from ommslib.shared.core.datatypes import redisDBIdx, readStatus


class pzemRedisBot(th.Thread):

   def __init__(self, SYS_INI: cp.ConfigParser, redops: redisOps):
      super().__init__()
      self.sys_ini: cp.ConfigParser = SYS_INI
      self.sec: cp.SectionProxy = self.sys_ini["PZEM"]
      self.dev: str = self.sec.get("SERIAL_DEV", "/dev/ttyUSB0")
      self.baudrate: int = self.sec.getint("SERIAL_BAUDRATE", 19200)
      self.syspath_channel = self.sec.get("SYSPATH_CHANNEL")
      tmp: str = self.sec.get("DIAG_TAG")
      self.diag_tag = sysUtils.set_systag(tmp)
      self.ser: serial.Serial = serial.Serial(port=self.dev, baudrate=self.baudrate)
      self.redops: redisOps = redops
      self.start_dts_dts_utc = sysUtils.dts_utc()
      self.last_msg_dts_utc = ""
      self.m_info: meterInfoData = \
         meterInfoData("e1", "Peacefair", "PZEM-004T AC 100A")
      self.first_reads: [] = []

   def run(self):
      pub_channel: str = self.sec.get("REDIS_PUB_CHNL")
      pub_channel = sysUtils.set_systag(pub_channel)
      _dict = {"boot_dts_utc": sysUtils.dts_utc(), "dev": self.dev
         , "lan_ip": sysUtils.lan_ip(), "hostname": sysUtils.HOST
         , "pub_reads_channel": pub_channel}
      self.redops.update_edge_diag(self.diag_tag, mapdct=_dict, restart=True)
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
         CHANNEL = "PZEM"
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
            self.redops.update_edge_diag(diag_tag=self.diag_tag, mapdct=__dict)
         # -- -- -- -- -- -- -- -- -- -- -- --
         print(buff)
         if not buff.startswith("#RPT|PZEM:SS_"):
            return
         # -- -- -- -- -- -- -- -- -- -- -- --
         arr: [] = buff.split("|")
         arr[0] = "#RPT:kWhrs"
         pzem_ss = arr[1].split(":")[1]
         arr.insert(1, f"DTSUTC:{sysUtils.dts_utc()}")
         arr.insert(2, f"EPOCH:{sysUtils.dts_epoch()}")
         syspath: str = sysUtils.syspath(self.syspath_channel, pzem_ss)
         arr.insert(3, f"PATH:{syspath}")
         buff = "|".join(arr)
         # -- -- publish & set -- --
         dtsutc, epoch = sysUtils.dtsutc_epoch()
         _d: {} = {"#RPT_kWhrs_STATUS": f"{dtsutc} | {epoch} | {readStatus.READ_OK}"
            , "#RPT_kWhrs": f"[{buff[:-1]}]"
            , "CHANNEL_TYPE": CHANNEL
            , "LAST_READ": f"#RPT_kWhrs | {readStatus.READ_OK} | {sysUtils.dts_utc(with_tz=True)}"
            , self.m_info.red_key: str(self.m_info)}
         # -- -- -- -- -- -- -- --
         if syspath not in self.first_reads:
            self.redops.red.select(redisDBIdx.DB_IDX_READS.value)
            self.redops.red.delete(syspath)
            self.first_reads.append(syspath)
         # -- -- -- -- -- -- -- --
         self.redops.save_meter_data(syspath, _dict=_d)
         self.redops.pub_read_on_sec("PZEM", _buff=f"({buff[:-1]})")
         # -- -- -- -- -- -- -- -- -- -- -- --
      except Exception as e:
         logUtils.log_exp(e)
         time.sleep(2.0)
