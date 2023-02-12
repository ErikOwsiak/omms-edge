
import datetime
import socket
import os, time, re
import serial, typing as t


class sysUtils(object):

   with open("/etc/hostname") as f:
      HOST = f.read().strip()
   with open("/etc/iotech/geoloc") as f:
      GEOLOC = f.read().strip()
   with open("/etc/iotech/building") as f:
      BUILDING = f.read().strip()
   with open("/etc/iotech/systag") as f:
      SYSTAG = f.read().strip()

   def __init__(self):
      pass

   @staticmethod
   def set_systag(buff: str, PATT="???"):
      return buff.replace(PATT, sysUtils.SYSTAG).strip()

   @staticmethod
   def lan_ip():
      try:
         s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
         s.connect(("8.8.8.8", 80))
         lanip = s.getsockname()[0]
         s.close()
         return lanip
      except Exception as e:
         print(e)

   @staticmethod
   def dts_utc(with_tz: bool = False):
      d = datetime.datetime.utcnow()
      _t: str = f"{d.year}-{d.month:02d}-{d.day:02d}T" \
         f"{d.hour:02d}:{d.minute:02d}:{d.second:02d}"
      return f"{_t} UTC" if with_tz else _t

   @staticmethod
   def ts_utc():
      _t = datetime.datetime.utcnow()
      return f"{_t.hour:02d}:{_t.minute:02d}:{_t.second:02d}"

   @staticmethod
   def dts_epoch() -> int:
     return int(time.time())

   @staticmethod
   def dtsutc_epoch() -> str:
      d = sysUtils.dts_utc()
      e = sysUtils.dts_epoch()
      return f"{d} | {e}"

   @staticmethod
   def syspath(channel: str, ep: str):
      try:
         if sysUtils.GEOLOC == "":
            with open("/etc/iotech/geoloc") as f:
               sysUtils.GEOLOC = f.read().strip()
         if sysUtils.BUILDING == "":
            with open("/etc/iotech/building") as f:
               sysUtils.BUILDING = f.read().strip()
         if sysUtils.HOST == "":
            with open("/etc/hostname") as f:
               sysUtils.HOST = f.read().strip()
         # -- -- -- --
         syspath: str = f"/{sysUtils.GEOLOC}/{sysUtils.BUILDING}/{sysUtils.HOST}/{channel}/{ep}"
         return syspath.lower()
      except Exception as e:
         print(e)
         exit(1)

   @staticmethod
   def min_dts() -> datetime.datetime:
      return datetime.datetime.fromisoformat("0001-01-01T01:01:01")
