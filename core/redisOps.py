#!/usr/bin/env python3


import redis, configparser as cp
try:
   from core.utils import sysUtils as utils
   from core.logutils import logUtils
   from ommslib.shared.core.datatypes import redisDBIdx
except:
   # -- in package testing --
   from utils import sysUtils as utils
   from logutils import logUtils
   from ommslib.shared.core.datatypes import redisDBIdx


class redisOps(object):

   def __init__(self, sys_ini: cp.ConfigParser
         , CONN_SEC: str = "REDIS_PROD"):
      # -- -- -- -- -- --
      self.sys_ini = sys_ini
      self.con_ini = self.sys_ini[CONN_SEC]
      self.host = self.con_ini["HOST"]
      self.port: int = int(self.con_ini["PORT"])
      self.red_ini = self.sys_ini["REDIS_CORE"]
      self.pwd: str = self.red_ini["PWD"]
      self.red: redis.Redis = \
         redis.Redis(host=self.host, port=self.port, password=self.pwd)

   def save_meter_data(self, path: str
         , _dict: {}
         , delold: bool = False):
      try:
         rv0 = 0
         path = path.lower()
         self.red.select(redisDBIdx.DB_IDX_READS.value)
         # -- -- -- --
         if delold:
            rv0 = self.red.delete(path)
         # -- -- -- --
         _dict["LAST_READ"] = utils.dts_utc()
         rv1 = self.red.hset(path, mapping=_dict)
         print(f"[ del: {rv0}; hset: {rv1}; ]")
      except Exception as e:
         logUtils.log_exp(e)

   def pub_read_on_sec(self, ini_sec: str, _arr: [] = None, _buff: str = None):
      pub_chnl: str = self.sys_ini[ini_sec]["REDIS_PUB_CHNL"]
      pub_chnl = utils.set_systag(pub_chnl)
      if _arr is not None:
         msg = "|".join(_arr)
         msg_out = f"({msg})"
      elif _buff is not None:
         msg_out = _buff
      else:
         msg_out = "Bad|_arr|_buff"
      # -- -- -- --
      rv = self.red.publish(pub_chnl, msg_out)
      print(f"\t-- [ rv: {rv}] --")

   def update_edge_diag(self, diag_tag: str
         , key: str = None
         , val: object = None
         , mapdct: {} = None
         , restart: bool = False):
      try:
         self.red.select(redisDBIdx.DB_IDX_EDGE_DIAG.value)
         if restart:
            self.red.delete(diag_tag)
         if mapdct is None:
            rv = self.red.hset(diag_tag, mapping={key: val})
         else:
            rv = self.red.hset(diag_tag, mapping=mapdct)
      except Exception as e:
         logUtils.log_exp(e)

   def update_server_diag(self, diag_tag: str
         , key: str = None
         , val: object = None
         , mapdct: {} = None
         , restart: bool = False):
      try:
         self.red.select(redisDBIdx.DB_IDX_ONPREM_DIAG.value)
         if restart:
            self.red.delete(diag_tag)
         if mapdct is None:
            rv = self.red.hset(diag_tag, mapping={key: val})
         else:
            rv = self.red.hset(diag_tag, mapping=mapdct)
         print(f"rv:{rv}")
      except Exception as e:
         logUtils.log_exp(e)
