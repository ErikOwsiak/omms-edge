
import os.path, typing as _t
import time, threading as _th
import xml.etree.ElementTree as _et
import configparser as _cp
from termcolor import colored
# -- system --
from core.redisOps import redisOps
from core.logutils import logUtils
from core.utils import sysUtils
from modbus.modbusMeterV1 import modbusMeterV1
from modbus.ttydevMeters import ttydevMeters
from system.ports import ports
# -- shared --
from ommslib.shared.core.elecRegStream import elecRegStream
from ommslib.shared.core.datatypes import readStatus


class modbusRedisRelay(_th.Thread):

   def __init__(self, sys_ini: _cp.ConfigParser
         , redops: redisOps
         , dev_meters: [ttydevMeters]
         , reg_streams_xml: _et.ElementTree):
      # -- -- -- -- -- -- -- --
      super().__init__()
      self.sys_ini: _cp.ConfigParser = sys_ini
      self.sec_ini = self.sys_ini["MODBUS"]
      self.diag_tag: str = str(self.sec_ini["DIAG_TAG"])
      self.diag_tag = sysUtils.set_systag(self.diag_tag)
      self.run_iotech_dev: str = str(self.sys_ini["CORE"]["RUN_IOTECH_DEV"])
      self.channel = self.sec_ini["SYSPATH_CHANNEL"]
      self.red_pub_channel: str = self.sec_ini["REDIS_PUB_CHNL"]
      self.red_pub_channel = sysUtils.set_systag(self.red_pub_channel)
      self.redops: redisOps = redops
      self.sys_ports: ports = ports(self.sys_ini)
      # -- edge modbus edge_meters --
      self.dev_meters_arr: [ttydevMeters] = dev_meters
      # -- register reg_streams --
      self.reg_streams_xml: _et.Element = reg_streams_xml.getroot()
      self.reg_streams: _t.List[elecRegStream] = []
      self.stream_thread = None
      self.meter_model_xmls: {} = {}
      self.blank_meters: {} = {}

   def init(self):
      try:
         if self.__load_rs_xml():
            self.stream_thread: _th.Thread = _th.Thread(target=self.__stream_thread)
         else:
            pass
      except Exception as e:
         logUtils.log_exp(e)

   def run(self) -> None:
      if self.__on_init_ping_meters():
         if self.stream_thread is not None:
            self.stream_thread.start()
         else:
            raise Exception("SteamThreadIsNone")
      # -- run main dumb loop --
      self.__main_loop()

   def __on_init_ping_meters(self) -> bool:
      # -- -- -- -- --
      rval: bool = True
      print("[ __on_init_ping_meters ]")
      try:
         for item in self.dev_meters_arr:
            item: ttydevMeters = item
            print(f"\n[ ttydevMeters:: tag: {item.tag} ]")
            exp_counter, no_pong_counter, pong_counter = self.__on_ttydev(item)
            msg = "exp_counter: %s, no_pong_counter: %s, pong_counter: %s" % \
               (exp_counter, no_pong_counter, pong_counter)
            print(msg)
            time.sleep(0.480)
      except Exception as e:
         logUtils.log_exp(e)
         rval = False
      finally:
         return rval

   def __on_ttydev(self, _ttydev: ttydevMeters) -> (int, int, int):
      # -- -- -- --
      if _ttydev.dev == "auto":
         full_dev_path = ports.alias_full_path(_ttydev.alias)
      else:
         full_dev_path = _ttydev.dev
      # -- -- -- --
      exp_counter = 0
      pong_counter = 0
      no_pong_counter = 0
      # -- -- -- --
      for meter_xml in _ttydev.meters:
         try:
            meter_xml.attrib["full_dev_path"] = full_dev_path
            err, meter = self.__create_modbus_meter(meter_xml)
            if err != 0:
               raise Exception(f"UnableToCreateMeter: {err}")
            # -- update syspath to meter_xml --
            meter_xml.attrib["syspath"] = meter.syspath
            # -- ping meter --
            meter: modbusMeterV1 = meter
            err, msg = meter.ping()
            if err == 0:
               pong_counter += 1
            else:
               no_pong_counter += 1
            # -- -- -- -- -- -- -- --
            minfo: str = str(meter.m_info)
            _d = {"INIT_PING": f"{msg} | {sysUtils.dts_utc(with_tz=True)}"
               , meter.m_info.red_key: minfo}
            self.redops.save_meter_data(meter.syspath, _dict=_d, delold=True)
            # -- -- -- -- -- -- -- --
         except Exception as e:
            logUtils.log_exp(e)
            exp_counter += 1
            continue
      # -- --
      return exp_counter, no_pong_counter, pong_counter

   def __create_modbus_meter(self, meter_xml: _et.Element) -> (int, modbusMeterV1):
      # basic data
      model_xml = meter_xml.attrib["modelXML"]
      dev_path: str = meter_xml.attrib["full_dev_path"]
      # -- -- -- --
      model_xml_path = f"brands/{model_xml}"
      if model_xml_path not in self.meter_model_xmls.keys():
         if not os.path.exists(model_xml_path):
            raise FileNotFoundError(model_xml_path)
         # -- add meter xml to cache --
         self.meter_model_xmls[model_xml_path] = _et.parse(model_xml_path).getroot()
      # -- -- -- --
      model_xmlelm: _et.Element = self.meter_model_xmls[model_xml_path]
      bus_addr = meter_xml.attrib["busAddr"]
      meter: modbusMeterV1 = modbusMeterV1(self.sys_ini, int(bus_addr), dev_path, model_xmlelm)
      # -- build unique:constant syspath for this meter --
      meter.set_syspath(sysUtils.syspath(self.channel, bus_addr))
      # -- -- -- --
      if meter.init():
         print(f"UnableToInitMeter: {model_xml}")
         return 0, meter
      else:
         return 1, meter

   def __load_rs_xml(self) -> bool:
      xpath = "stream[@enabled='1']"
      stream_lst: _t.List[_et.Element] = self.reg_streams_xml.findall(xpath)
      if len(stream_lst) == 0:
         return False
      # -- convert xml to register stream objects --
      for s_item in stream_lst:
         reg_stream: elecRegStream = elecRegStream(s_item)
         self.reg_streams.append(reg_stream)
      # -- sort --
      self.reg_streams.sort(key=lambda x: x.run_index, reverse=False)
      # -- return state --
      return len(self.reg_streams) > 0

   def __stream_thread(self):
      # -- -- -- -- -- -- -- --
      print("\n[ __stream_thread ]\n")
      time.sleep(1.0)
      # -- -- -- -- -- -- -- --
      while True:
         try:
            # -- -- -- -- -- --
            for stream in self.reg_streams:
               diff: int = stream.time_to_run()
               print(f"next run in: {diff}s : {stream.name}")
               if diff > 0:
                  continue
               # -- run stream frame --
               if self.__run_stream_frame(stream):
                  stream.update_last_run()
               else:
                  pass
            # -- -- -- -- -- --
            time.sleep(4.0)
            print("stream_thread")
         except Exception as e:
            logUtils.log_exp(e)
            time.sleep(8.0)

   def __run_stream_frame(self, stream_regs: elecRegStream) -> bool:
      print(f"[ __run_stream_frame: {stream_regs.name} ]")
      accu_buff: bool = True
      for meters in self.dev_meters_arr:
         accu_buff &= self.__run_ttydev_meters(stream_regs, meters)
      return True

   """
      <edge hostname="3cpo" pubChannel="MODBUS_DEVLAB_READS">
         <ttydev run="yes" tag="ModbusEdgeA5" alias="modbusPortA" dev="auto" modbusBugID="bugID1">
               ; if dev="auto" and alias is set use look for it in OMMS_DEV_PATH; it should be created there
               ; by ttyDiscovery bot; if dev="auto" and no alias then 
            <meter busAddr="10" modelXML="orno/orno516.xml" />
            ...
         </ttydev>
      </edge>
   """
   def __run_ttydev_meters(self, stream_regs: elecRegStream, dev_meters: ttydevMeters) -> bool:
      if dev_meters.run.lower() not in ["yes", "y", "1"]:
         return True
      # -- publish to redis channel --
      def redis_publish(stream_name: str, _arr: []):
         INI_SEC = "MODBUS"
         _arr.insert(1, f"DTSUTC:{sysUtils.dts_utc()}")
         _arr.insert(2, f"EPOCH:{sysUtils.dts_epoch()}")
         _arr.insert(3, f"PATH:{meter.syspath}")
         self.redops.pub_read_on_sec(INI_SEC, _arr=_arr)
      # -- save to redis as a lost data read --
      def redis_save(stream_name, _arr: [], read_status: str = None):
         CHNL_TYPE = "MODBUS"
         rpt_key: str = f"#RPT_{stream_name}"
         s = "|".join(_arr)
         rpt_stat_key = f"{rpt_key}_STATUS"
         dtsutc, epoch = sysUtils.dtsutc_epoch()
         d = {rpt_key: f"[{s}]"
            , rpt_stat_key: f"{dtsutc} | {epoch} | {read_status}"
            , "CHANNEL_TYPE": CHNL_TYPE
            , "LAST_READ": f"{rpt_key} | {read_status} | {sysUtils.dts_utc(with_tz=True)}"}
         self.redops.save_meter_data(meter.syspath, _dict=d)
      # -- -- do -- --
      for meter_xml in dev_meters.meters:
         try:
            full_dev_path = meter_xml.attrib["full_dev_path"]
            if not os.path.exists(full_dev_path):
               raise FileNotFoundError(full_dev_path)
            # -- -- -- --
            err, meter = self.__create_modbus_meter(meter_xml=meter_xml)
            if err != 0:
               raise Exception(f"CreateModbusMeterNotZero: {err}")
            meter: modbusMeterV1 = meter
            meter.set_stream_regs(stream_regs)
            if meter.read_stream_frame_registers():
               arr: [] = meter.reads_str_arr()
               arr.insert(0, f"#RPT:{stream_regs.name}")
               status = readStatus.READ_OK
            else:
               arr = [f"#RPT:ERROR|MSG:UnableToReadStreamFrame|ModbusAddr:{meter.modbus_addr}"]
               status = readStatus.READ_FAILED
            # -- -- -- --
            redis_save(stream_regs.name, arr, read_status=status)
            redis_publish(stream_regs.name, arr)
            # -- -- -- --
         except Exception as e:
            logUtils.log_exp(e)
            continue
      # -- -- end -- --
      return True

   def __main_loop(self):
      # -- -- report -- --
      _dict = {"boot_dts_utc": sysUtils.dts_utc(), "lan_ip": sysUtils.lan_ip()
         , "hostname": sysUtils.HOST, "pub_reads_channel": self.red_pub_channel}
      self.redops.update_edge_diag(self.diag_tag, mapdct=_dict, restart=True)
      # -- -- run -- --
      while True:
         try:
            print("mainloop")
            time.sleep(4.0)
         except Exception as e:
            logUtils.log_exp(e)
      # -- -- -- --
