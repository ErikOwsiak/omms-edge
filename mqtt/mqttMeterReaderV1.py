import datetime
import os, time
import threading
import typing as t
import configparser as _cp
import xml.etree.ElementTree as et
import paho.mqtt.client as mqtt
import redis

from core.utils import sysUtils as utils
from core.redisOps import redisOps
from mqtt.meter_strucs import regInfo
from core.logutils import logUtils


# noinspection PyTypeChecker
class mqttMeterReaderV1(object):

   def __init__(self, fullpath: str, cp: _cp
         , sys_cp: _cp.ConfigParser
         , redops: redisOps):
      # -- -- -- -- -- -- -- -- -- -- -- --
      self.meters_xml_conf = fullpath
      self.xcp: _cp.ConfigParser = cp
      self.system_cp: _cp.ConfigParser = sys_cp
      self.channel = str(self.xcp["SYSPATH"]["CHANNEL"])
      self.diag_tag: str = str(self.xcp["SYSINFO"]["DIAG_TAG"])
      self.diag_tag = utils.diag_tag_prefix(self.diag_tag)
      self.redops: redisOps = redops
      self.xmldoc: et.ElementTree = None
      self.meter_xml_nodes: t.List[et.Element] = None
      self.regs: t.List[et.Element] = None
      self.report_thread = \
         threading.Thread(target=self.__report_thread__, args=(None,))
      self.clt: mqtt.Client = mqtt.Client()
      self.host: str = ""
      self.port: int = 0
      self.pwd: str = ""
      self.meter_regs_topics: {} = {}
      self.on_msg_lock: threading.Lock = threading.Lock()
      self.last_report: int = 0
      self.report_interval = 120

   def on_connect(self, clt, ud, flags, rc):
      print("\t[ on_connect ]")
      this: mqttMeterReaderV1 = ud
      topics = this.meter_regs_topics.keys()
      for topic in topics:
         this.clt.subscribe(topic=topic)

   def on_msg(self, _, ud, msg: mqtt.MQTTMessage):
      this: mqttMeterReaderV1 = ud
      try:
         # - - - - - - - -
         this.on_msg_lock.acquire()
         print("-- [on_msg] --")
         print(f"\ttopic: {msg.topic}\n\tpayload: {msg.payload}")
         # - - - - - - - -
         reg_info: regInfo = this.meter_regs_topics[msg.topic]
         reg_info.data = round(float(msg.payload), 2)
         reg_info.dts = datetime.datetime.utcnow()
         print(f"\t\tmeter_tag: {reg_info.meter_tag}"
            f"\n\t\treg_type: {reg_info.regtype}\n\t\treading: {reg_info.data}")
         this.meter_regs_topics[msg.topic] = reg_info
         # - - - - - - - -
      except Exception as e:
         print(e)
      finally:
         this.on_msg_lock.release()

   def mqtt_init(self) -> int:
      try:
         self.clt.on_connect = self.on_connect
         self.clt.on_message = self.on_msg
         # -- set user data --
         self.clt.user_data_set(self)
         self.clt.connect(self.host, self.port)
         pub_channel: str = self.xcp["REDIS"]["PUB_READS_CHANNEL"]
         _dict = {"boot_dts_utc": utils.dts_utc(), "dev": "n/a"
            , "lan_ip": utils.lan_ip(), "hostname": utils.HOST
            , "pub_reads_channel": pub_channel}
         self.redops.update_diag_tag(self.diag_tag, mapdct=_dict, restart=True)
         return 0
      except ConnectionRefusedError as e:
         print("Check Redis connection info: host/port")
         logUtils.log_exp(e)
      except Exception as e:
         logUtils.log_exp(e)
         return 1

   def load_xml_conf(self) -> bool:
      try:
         # -- -- -- --
         if not os.path.exists(self.meters_xml_conf):
            print(f"FileNotFound: {self.meters_xml_conf}")
            exit(1)
         # -- hp --
         self.xmldoc: et.ElementTree = et.parse(self.meters_xml_conf)
         self.__init_xml_conf__()
         self.__init_meter_tbl__()
         # -- return --
         return True
      except Exception as e:
         print(e)
         return False

   def start(self) -> bool:
      try:
         self.report_thread.start()
         self.clt.loop_start()
         return True
      except Exception as e:
         logUtils.log_exp(e)
         return False

   def __init_meter_tbl__(self):
      for meter in self.meter_xml_nodes:
         self.__create_meter__(meter)

   def __create_meter__(self, m: et.Element):
      # - - - - - - - - - - - - - - - - - - - -
      def get_type(typ: str) -> [str, None]:
         for r in self.regs:
            if r.attrib["type"] == typ:
               return r
         # -- end --
         return None
      # - - - - - - - - - - - - - - - - - - - -
      meter_tag = m.attrib["tag"]
      mid = m.attrib["id"]
      # dbid = m.attrib["dbid"]
      regs: t.List[et.Element] = m.findall("reg")
      # - - - - - - - - - - - - - - - - - - - -
      for reg in regs:
         reginfo: regInfo = regInfo()
         reginfo.dts = utils.ts_utc()
         reginfo.regtype = reg.attrib["type"]
         # - - - - - - - - - - - - - - -
         treg = get_type(reginfo.regtype)
         tpath = treg.attrib["path"]
         tmpl = reg.attrib["tmpl"]
         topic = tmpl.format(mid=mid, tpath=tpath)
         # events come in per register; so register are stored in reg table with
         # each reg has meter syspath as attribute
         # reginfo.syspath = utils.syspath(self.channel, meter_tag)
         # use meter_tag later to group readings per meter
         reginfo.meter_tag = meter_tag
         self.meter_regs_topics[topic] = reginfo

   def __init_xml_conf__(self):
      root = self.xmldoc.getroot()
      self.host = root.attrib["host"]
      self.port = int(root.attrib["port"])
      self.pwd = root.attrib["pwd"]
      self.meter_xml_nodes: t.List[et.Element] = root.findall("edge_meters/meter")
      # -- add syspath to meter node xml --
      for node in self.meter_xml_nodes:
         node.attrib["syspath"] = utils.syspath(self.channel, node.attrib["tag"])
      self.regs: t.List[et.Element] = root.findall("regtable/reg")

   def __report__(self):
      try:
         # - - - - - - - - - - - - - - - -
         self.on_msg_lock.acquire()
         for m in self.meter_xml_nodes:
            meter_tag = m.attrib["tag"]
            # - - - - - - - - - - - -
            meter_registers: [] = []
            # -- select meter registers --
            for topic in self.meter_regs_topics.keys():
               reginfo: regInfo = self.meter_regs_topics[topic]
               if reginfo.meter_tag == meter_tag:
                  meter_registers.append(reginfo)
            # -- check timestamps; must be within 30 seconds --
            meter_registers.sort(key=lambda r: r.dts)
            # -- here regs should be selected from regs table --
            syspath = m.attrib["syspath"]
            reg_tkwh: regInfo = [r for r in meter_registers if r.regtype == "total_kwh"][0]
            reg_l1_tkwh: regInfo = [r for r in meter_registers if r.regtype == "l1_total_kwh"][0]
            reg_l2_tkwh: regInfo = [r for r in meter_registers if r.regtype == "l2_total_kwh"][0]
            reg_l3_tkwh: regInfo = [r for r in meter_registers if r.regtype == "l3_total_kwh"][0]
            # -- build RPT data buffer --
            # #RPT|DTSUTC:2023-01-07T01:12:50|PATH:/gdn/ck/omms-edge-roof/PZEM6/SS_1
            #     |PZEM:SS_1|F:50.00|V:227.80|A:0.88|W:197.60|kWh:81.87!
            buff = f"#RPT|DTSUTC:{utils.dts_utc()}|PATH:{syspath}|METER_TAG:{meter_tag}|TkWh: {reg_tkwh.data}" \
               f"|L1kWh:{reg_l1_tkwh.data}|L2kWh:{reg_l2_tkwh.data}|L3kWh:{reg_l3_tkwh.data}!"
            print(buff)
            # -- push to redis --
            self.redops.pub_read(buff)
            self.redops.save_read(syspath, buff)
            self.redops.save_heartbeat(syspath, buff)
         # - - - - - - - - - - - - - - - -
      except Exception as e:
         print(e)
      finally:
         self.on_msg_lock.release()

   def __report_thread__(self, args):
      self.mqtt_init()
      LOOP_SLEEP_SECS: float = float(self.xcp["TIMING"]["LOOP_SLEEP_SECS"])
      KWH_REPORT_INTERVAL: int = int(self.xcp["TIMING"]["KWH_REPORT_INTERVAL"])
      # -- hp --
      while True:
         time.sleep(LOOP_SLEEP_SECS)
         epoch_time = int(time.time())
         if (epoch_time - self.last_report) > KWH_REPORT_INTERVAL:
            self.__report__()
            self.last_report = int(time.time())
      # -- end of while --
