
import time
import threading as _th
import configparser as _cp
import xml.etree.ElementTree as et
import paho.mqtt.client as mqtt
# -- -- system  -- --
from core.utils import sysUtils as utils
from core.redisOps import redisOps
from mqtt.meter_strucs import regInfo
from core.logutils import logUtils
from ommslib.shared.core.datatypes import mqttMeterInfo
from core.meterInfoData import meterInfoData
from ommslib.shared.core.elecRegStrEnums import elecRegStrEnumsShort as _erses


"""
   [MQTT]
   REDIS_PUB_CHNL: CK_READS_MQTT_???
   DIAG_TAG: ???_MQTT_RELAY
   PROC_NAME: omms-mqtt
   MAIN_LOOP_SECS: 20
   SYSPATH_CHANNEL: MQTT
"""

# noinspection PyTypeChecker
class mqttMeterReaderV1(object):

   def __init__(self, xmldoc: et.Element
         , sys_ini: _cp.ConfigParser
         , mqtt_core_ini: _cp.SectionProxy
         , mqtt_info_ini: _cp.SectionProxy
         , redops: redisOps):
      # -- -- -- -- -- -- -- -- -- -- -- --
      self.meters_xml: et.Element = xmldoc
      self.sys_ini: _cp.ConfigParser = sys_ini
      self.mqtt_core_ini: _cp.SectionProxy = mqtt_core_ini
      self.mqtt_info_ini: _cp.SectionProxy = mqtt_info_ini
      # -- -- -- --
      self.syspath_channel = self.mqtt_core_ini.get("SYSPATH_CHANNEL")
      # REDIS_PUB_CHNL
      tmp: str = self.mqtt_core_ini.get("REDIS_PUB_CHNL")
      self.reads_pub_channel = utils.set_systag(tmp)
      # -- -- -- --
      self.diag_tag: str = str(self.mqtt_core_ini["DIAG_TAG"])
      self.diag_tag = utils.set_systag(self.diag_tag)
      self.redops: redisOps = redops
      self.kwh_report_interval: int = self.mqtt_core_ini.getint("KWH_REPORT_INTERVAL", 120)
      self.report_loop_intv: float = self.mqtt_core_ini.getfloat("LOOP_SLEEP_SECS", 4)
      self.running_meters: [et.Element] = []
      self.global_register_table: {str, mqttMeterInfo} = {}
      self.report_thread = _th.Thread(target=self.__report_thread__, args=(None,))
      self.clt: mqtt.Client = mqtt.Client()
      self.host: str = self.mqtt_info_ini.get("HOST", "")
      self.port: int = self.mqtt_info_ini.getint("PORT", 0)
      self.pwd: str = self.mqtt_info_ini.get("PWD", "")
      self.on_msg_lock: _th.Lock = _th.Lock()
      self.last_report: int = 0
      self.m_info: meterInfoData = meterInfoData("e3", "ZAMEL", "MEW1")

   def on_connect(self, clt, ud, flags, rc):
      print("\t[ on_connect ]")
      this: mqttMeterReaderV1 = ud
      topics = this.global_register_table.keys()
      for topic in topics:
         this.clt.subscribe(topic=topic)

   def on_msg(self, _, ud, msg: mqtt.MQTTMessage):
      this: mqttMeterReaderV1 = ud
      try:
         this.on_msg_lock.acquire()
         reg: regInfo = this.global_register_table[msg.topic]
         reg.update_data(msg.payload)
         print(reg)
      except Exception as e:
         logUtils.log_exp(e)
      finally:
         this.on_msg_lock.release()

   def mqtt_init(self) -> int:
      try:
         self.clt.on_connect = self.on_connect
         self.clt.on_message = self.on_msg
         # -- set user data --
         self.clt.user_data_set(self)
         self.clt.connect(self.host, self.port)
         # -- -- report to redis -- --
         _dict = {"mqtt_reader_dts_utc": utils.dts_utc()
            , "lan_ip": utils.lan_ip(), "hostname": utils.HOST
            , "pub_reads_channel": self.reads_pub_channel}
         self.redops.update_edge_diag(self.diag_tag, mapdct=_dict)
         return 0
      except ConnectionRefusedError as e:
         print("Check Redis connection info: host/port")
         logUtils.log_exp(e)
      except Exception as e:
         logUtils.log_exp(e)
         return 1

   def load_xml_conf(self) -> bool:
      try:
         self.__build_global_register_table__()
         return True
      except Exception as e:
         logUtils.log_exp(e)
         return False

   def start(self) -> bool:
      try:
         self.report_thread.start()
         self.clt.loop_start()
         return True
      except Exception as e:
         logUtils.log_exp(e)
         return False

   def __build_global_register_table__(self):
      # -- load register table --
      self.regtable: et.Element = self.meters_xml.find("regtable")
      if len(self.regtable.findall("reg")) == 0:
         raise Exception("NoRegLookUpTableFound")
      # -- -- -- -- -- --
      xpath = f"omms_edge[@hostname='{utils.HOST}']/meter"
      host_meters: [et.Element] = self.meters_xml.findall(xpath)
      # -- -- -- -- -- --
      def __per_reg(mmi: mqttMeterInfo, met: et.Element, reg: et.Element):
         try:
            mid = met.attrib["mid"].strip("/")
            reg_type = reg.attrib["type"]
            # -- -- -- --
            reg_xml: et.Element = self.regtable.find(f"reg[@type='{reg_type}']")
            if reg_xml is None:
               raise Exception("RegXmlIsNone")
            # -- -- -- --
            key = reg_xml.attrib["key"]
            topic_templ = reg.attrib["topic_template"]
            topic = topic_templ.replace("$mid", mid).replace("$key", key)
            reg_info: regInfo = regInfo(reg_type, mmi.tag)
            self.global_register_table[topic] = reg_info
            print(reg_info)
         except Exception as e:
            logUtils.log_exp(e)
      # -- -- -- -- -- --
      def __per_meter(meter: et.Element) -> mqttMeterInfo:
         met_tag = meter.attrib["tag"]
         syspath: str = utils.syspath(self.syspath_channel, met_tag)
         meter_info: mqttMeterInfo = mqttMeterInfo(met_tag, syspath)
         regs = meter.findall("reg")
         for reg_item in regs:
            __per_reg(meter_info, meter, reg_item)
         return meter_info
      # -- -- -- -- -- --
      for meter_item in host_meters:
         mi: mqttMeterInfo = __per_meter(meter_item)
         self.running_meters.append(mi)
      # -- -- -- -- -- --

   def __report__(self):
      try:
         # - - - - - - - - - - - - - - - -
         self.on_msg_lock.acquire()
         # -- redis save --
         def redis_save(syspath: str, s_name: str, _buff: str):
            CHNL_TYPE = "MQTT"
            rpt_key: str = f"#RPT_{s_name}"
            dts_key = f"{rpt_key}_dtsutc_epoch"
            dtsutc_epoch = utils.dtsutc_epoch()
            d = {rpt_key: f"[{_buff}]", dts_key: dtsutc_epoch
               , "CHANNEL_TYPE": CHNL_TYPE, "LAST_READ": utils.dts_utc()}
            self.redops.save_meter_data(syspath, _dict=d)
         # -- -- -- -- -- -- -- --
         stream_name = "kWhrs"
         for m in self.running_meters:
            m: mqttMeterInfo = m
            # -- select meter registers --
            meter_regs = [v for v in self.global_register_table.values() if v.meter_tag == m.tag]
            # -- check timestamps; must be within 30 seconds --
            # -- here global_register_table should be selected from global_register_table table --
            reg_tkwh: regInfo = [r for r in meter_regs if r.regtype == _erses.tl_kwh][0]
            reg_l1_tkwh: regInfo = [r for r in meter_regs if r.regtype == _erses.l1_kwh][0]
            reg_l2_tkwh: regInfo = [r for r in meter_regs if r.regtype == _erses.l2_kwh][0]
            reg_l3_tkwh: regInfo = [r for r in meter_regs if r.regtype == _erses.l3_kwh][0]
            # -- build RPT data buffer --
            buff = f"#RPT:{stream_name}|DTSUTC:{utils.dts_utc()}|EPOCH:{utils.dts_epoch()}" \
               f"|PATH:{m.syspath}|METER_TAG:{m.tag}" \
               f"|tl_kwh:{reg_tkwh.data}|l1_kwh:{reg_l1_tkwh.data}|" \
               f"|l2_kwh:{reg_l2_tkwh.data}|l3_kwh:{reg_l3_tkwh.data}"
            # -- publish to redis --
            self.redops.pub_read_on_sec("MQTT_CORE", _buff=f"({buff})")
            # -- -- -- save -- -- --
            redis_save(m.syspath, stream_name, buff)
         # - - - - - - - - - - - - - - - -
      except Exception as e:
         logUtils.log_exp(e)
      finally:
         self.on_msg_lock.release()

   def __report_thread__(self, args):
      while True:
         try:
            time.sleep(self.report_loop_intv)
            epoch_time = int(time.time())
            if (epoch_time - self.last_report) > self.kwh_report_interval:
               self.__report__()
               self.last_report = int(time.time())
         # -- end of while --
         except Exception as e:
            logUtils.log_exp(e)
