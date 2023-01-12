#!/usr/bin/env python3

import hashlib
import redis, configparser as cp
try:
   from core.utils import sysUtils as utils
   from core.logutils import logUtils
except:
   # -- in package testing --
   from utils import sysUtils as utils
   from logutils import logUtils


class redisOps(object):

   def __init__(self, sys_ini: cp.ConfigParser, CONN_SEC: str = "REDIS_PROD"):
      self.sys_ini = sys_ini
      self.con_ini = self.sys_ini[CONN_SEC]
      self.host = self.con_ini["HOST"]
      self.port: int = int(self.con_ini["PORT"])
      self.red_ini = self.sys_ini["REDIS_CORE"]
      self.pwd = self.red_ini["PWD"]
      self.red: redis.Redis = redis.Redis(host=self.host, port=self.port, password=self.pwd)
      # self.host_ping: bool = self.__ping_host()

   def save_read(self, path: str, buff: str):
      try:
         read_db_idx = int(self.sys_ini["REDIS"]["DB_IDX_READS"])
         self.red.select(read_db_idx)
         md5 = hashlib.md5(bytearray(buff.encode("utf-8")))
         md5str = f"0x{md5.hexdigest().upper()}"
         last_msg_dtsutc = utils.dts_utc()
         _dict = {"dts_utc": last_msg_dtsutc, "msg_md5": md5str, "#RPT": buff}
         rv = self.red.delete(path)
         print(f"rv: {rv}")
         rv = self.red.hset(path, mapping=_dict)
         print(f"rv: {rv}")
      except Exception as e:
         logUtils.log_exp(e)

   def save_meter_data(self, path: str, _dict: {}, delold: bool = False):
      try:
         rv0 = 0
         read_db_idx = int(self.sys_ini["REDIS"]["DB_IDX_READS"])
         self.red.select(read_db_idx)
         if delold:
            rv0 = self.red.delete(path)
         rv1 = self.red.hset(path, mapping=_dict)
         print(f"[ del: {rv0}; hset: {rv1}; ]")
      except Exception as e:
         logUtils.log_exp(e)

   def update_read(self, path: str, key: str, val: str):
      try:
         read_db_idx = int(self.sys_ini["REDIS"]["DB_IDX_READS"])
         self.red.select(read_db_idx)
         rv = self.red.hset(path, mapping={key: val})
         print(f"rv: {rv}")
      except Exception as e:
         logUtils.log_exp(e)

   def pub_diag_debug(self, buff: str):
      channel: str = self.sys_ini["REDIS"]["PUB_DIAG_DEBUG_CHANNEL"]
      rv = self.red.publish(channel, buff)
      print(f"rv: {rv}")

   def pub_read(self, buff: str):
      channel: str = self.sys_ini["REDIS"]["PUB_READS_CHANNEL"]
      rv = self.red.publish(channel, buff)
      print(f"rv: {rv}")

   def save_heartbeat(self, path: str, buff: str):
      try:
         heartbeat_db_idx: int = int(self.sys_ini["REDIS"]["DB_IDX_HEARTBEATS"])
         heartbeat_ttl: int = int(self.sys_ini["REDIS"]["HEARTBEAT_TTL"])
         self.red.select(heartbeat_db_idx)
         md5 = hashlib.md5(bytearray(buff.encode("utf-8")))
         md5str = f"0x{md5.hexdigest().upper()}"
         last_msg_dtsutc = utils.dts_utc()
         _dict = {"last_msg_dts_utc": last_msg_dtsutc, "last_msg_md5": md5str}
         rv = self.red.hset(path, mapping=_dict)
         if heartbeat_ttl not in [None, -1]:
            self.red.expire(path, heartbeat_ttl)
         print(f"rv: {rv}")
      except Exception as e:
         logUtils.log_exp(e)

   def update_diag_tag(self, diag_tag: str, key: str = None
         , val: object = None, mapdct: {} = None, restart: bool = False):
      try:
         diag_db_idx: int = int(self.sys_ini["REDIS_CORE"]["DB_IDX_DIAG"])
         self.red.select(diag_db_idx)
         if restart:
            self.red.delete(diag_tag)
         if mapdct is None:
            rv = self.red.hset(diag_tag, mapping={key: val})
         else:
            rv = self.red.hset(diag_tag, mapping=mapdct)
      except Exception as e:
         logUtils.log_exp(e)

   # def __ping_host(self) -> bool:
   #    try:
   #       return self.red.ping()
   #    except Exception as e:
   #       print(e)
   #       return False
