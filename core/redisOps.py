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

   # def update_edge_diag(self, key: str, _d: {}, del_prev: bool = False):
   #    """
   #       :param key: hostname, process name & etc
   #       :param _d:
   #       :param del_prev: if True remove old key
   #       :return:
   #    """
   #    try:
   #       rv0 = 0
   #       # -- db_idx: int = int(self.sys_ini["REDIS_CORE"]["DB_IDX_DIAG"])
   #       self.red.select(redisDBIdx.DB_IDX_EDGE_DIAG)
   #       if del_prev:
   #          rv0 = self.red.delete(key)
   #       rv1 = self.red.hset(key, mapping=_d)
   #       print(f"rv0: {rv0}; rv1: {rv1};")
   #    except Exception as e:
   #       logUtils.log_exp(e)

   # def save_read(self, path: str, buff: str):
   #    try:
   #       path = path.lower()
   #       read_db_idx = int(self.sys_ini["REDIS_CORE"]["DB_IDX_READS"])
   #       self.red.select(read_db_idx)
   #       last_msg_dtsutc = utils.dts_utc()
   #       _dict = {"#rpt_kWhrs_dts_utc": last_msg_dtsutc, "#rpt_kWhrs": buff}
   #       rv0 = self.red.delete(path)
   #       rv1 = self.red.hset(path, mapping=_dict)
   #       print(f"rv0: {rv0}; rv1: {rv1};")
   #    except Exception as e:
   #       logUtils.log_exp(e)

   def save_meter_data(self, path: str
         , _dict: {}, delold: bool = False):
      try:
         rv0 = 0
         path = path.lower()
         self.red.select(redisDBIdx.DB_IDX_READS.value)
         if delold:
            rv0 = self.red.delete(path)
         rv1 = self.red.hset(path, mapping=_dict)
         print(f"[ del: {rv0}; hset: {rv1}; ]")
      except Exception as e:
         logUtils.log_exp(e)

   # def update_read(self, path: str, key: str, val: str):
   #    try:
   #       path = path.lower()
   #       self.red.select(redisDBIdx.DB_IDX_READS)
   #       rv = self.red.hset(path, mapping={key: val})
   #       print(f"rv: {rv}")
   #    except Exception as e:
   #       logUtils.log_exp(e)

   # def pub_diag_debug(self, buff: str):
   #    channel: str = self.sys_ini["REDIS"]["PUB_DIAG_DEBUG_CHANNEL"]
   #    rv = self.red.publish(channel, buff)
   #    print(f"rv: {rv}")

   # def pub_read(self, buff: str):
   #    channel: str = self.sys_ini["REDIS"]["PUB_READS_CHANNEL"]
   #    rv = self.red.publish(channel, buff)
   #    print(f"rv: {rv}")

   def pub_read_on_sec(self, ini_sec: str, buff: str):
      pub_chnl: str = self.sys_ini[ini_sec]["REDIS_PUB_CHNL"]
      pub_chnl = utils.set_systag(pub_chnl)
      rv = self.red.publish(pub_chnl, buff)
      print(f"\t-- [ rv: {rv}] --")

   # def save_heartbeat(self, path: str, buff: str):
   #    try:
   #       path = path.lower()
   #       heartbeat_ttl: int = int(self.sys_ini["REDIS"]["HEARTBEAT_TTL"])
   #       self.red.select(redisDBIdx.DB_IDX_HEARTBEATS)
   #       md5 = hashlib.md5(bytearray(buff.encode("utf-8")))
   #       md5str = f"0x{md5.hexdigest().upper()}"
   #       last_msg_dtsutc = utils.dts_utc()
   #       _dict = {"last_msg_dts_utc": last_msg_dtsutc, "last_msg_md5": md5str}
   #       rv = self.red.hset(path, mapping=_dict)
   #       if heartbeat_ttl not in [None, -1]:
   #          self.red.expire(path, heartbeat_ttl)
   #       print(f"rv: {rv}")
   #    except Exception as e:
   #       logUtils.log_exp(e)

   def update_edge_diag_tag(self, diag_tag: str
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
