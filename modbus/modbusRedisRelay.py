
import os.path
import typing as _t
import time, threading as _th
import xml.etree.ElementTree as _et
import configparser as _cp
# -- system --
from core.redisOps import redisOps
from core.logutils import logUtils
from core.utils import sysUtils
from modbus.regDataMode import regDataMode
from modbus.modbusMeterV1 import modbusMeterV1
from modbus.ttydevMeters import ttydevMeters
from modbus.modbusEdgeMeters import modbusEdgeMeters
from system.ports import ports
# -- shared --
from ommslib.shared.core.elecRegStream import elecRegStream


class modbusRedisRelay(_th.Thread):

   def __init__(self, cp: _cp.ConfigParser
         , sys_cp: _cp.ConfigParser
         , redops: redisOps
         , dev_meters: [ttydevMeters]
         , reg_streams_xml: _et.ElementTree):
      # -- -- -- -- -- -- -- --
      super().__init__()
      self.cp: _cp.ConfigParser = cp
      self.sys_cp: _cp.ConfigParser = sys_cp
      self.diag_tag: str = str(self.cp["SYSINFO"]["DIAG_TAG"])
      self.diag_tag = sysUtils.diag_tag_prefix(self.diag_tag)
      self.run_iotech_dev: str = str(self.sys_cp["CORE"]["RUN_IOTECH_DEV"])
      self.redops: redisOps = redops
      self.sys_ports: ports = ports(self.cp)
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
      self.__init_meter_pings()
      self.stream_thread: _th.Thread = self.stream_thread
      self.stream_thread.start()
      self.__main_loop()

   def __init_meter_pings(self):
      model_xmls: {} = {}
      for ttydev in self.dev_meters_arr:
         try:
            ttydev: ttydevMeters = ttydev
            alias = ttydev.alias

            for meter_xml in ttydev.meters:
               model_xml = meter_xml.attrib["modelXML"]
               xml_path = f"brands/{model_xml}"
               if model_xml not in model_xmls.keys():
                  model_xmls[model_xml] = _et.parse(xml_path).getroot()
               # -- -- -- --
               xmlelm: _et.Element = model_xmls[model_xml]
               meter: modbusMeterV1 = modbusMeterV1(self.cp, xmlelm)
               meter.clear_reinit(meter.modbus_addr, meter.tty_dev,)
               meter.set_syspath("")

               err, msg = meter.ping()
               # -- -- -- --
         except Exception as e:
            logUtils.log_exp(e)

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
      while True:
         try:
            # -- -- -- -- -- -- -- --
            for stream in self.reg_streams:
               if not stream.is_time_to_run():
                  continue
               if self.__run_stream_frame(stream):
                  stream.update_last_run()
               else:
                  pass
            # -- -- -- -- -- -- -- --
            time.sleep(4.0)
            print("stream_thread")
         except Exception as e:
            logUtils.log_exp(e)

   def __run_stream_frame(self, stream_regs: elecRegStream) -> bool:
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
   def __run_ttydev_meters(self, ers: elecRegStream, dev_meters: ttydevMeters) -> bool:
      if dev_meters.run.lower() not in ["yes", "y", "1"]:
         return True
      # -- -- do -- --
      for meter in dev_meters.meters:
         try:
            alias_path = f"{self.run_iotech_dev}/{dev_meters.alias}"
            tty_dev = ""
            # -- -- -- --
            meter.attrib["alias"] = alias_path if os.path.exists(alias_path) else ""
            meter.attrib["ttydev"] = tty_dev if os.path.exists(tty_dev) else ""
            # -- -- -- --
            err_code, rpt_str = self.__read_meter_regs(ers=ers, _meter=meter)
            if err_code == 0:
               self.redops.pub_read(rpt_str)
               self.redops.save_read(meter.attrib["syspath"], rpt_str)
               self.redops.save_heartbeat(meter.attrib["syspath"], rpt_str)
            else:
               print([err_code, rpt_str])
         except Exception as e:
            logUtils.log_exp(e)
      # -- -- end -- --
      return True

   """
      <meter busAddr="10" modelXML="orno/orno516.xml" />
   """
   def __read_meter_regs(self, ers: elecRegStream, _meter: _et.Element) -> ():
      # -- -- -- -- --
      modbus_addr: int = int(_meter.attrib["busAddr"])
      modelxml: str = _meter.attrib["modelXML"]
      ttydev: str = _meter.attrib["ttydev"]
      devalias: str = _meter.attrib["dev_alias"]
      syspath: str = _meter.attrib["syspath"]
      # -- if not found load xml file for this meter --
      if modelxml not in self.meter_model_xmls.keys():
         path = f"brands/{modelxml}"
         if not os.path.exists(path):
            return ""
         self.meter_model_xmls[modelxml] = _et.parse(path).getroot()
      # -- -- do -- --
      model_xml = self.meter_model_xmls[modelxml]
      mb_meter: modbusMeterV1 = modbusMeterV1(cp=self.cp, modelxml=model_xml)
      mb_meter.init()
      # -- -- do -- --
      error_code = 0
      # model_xml: _et.Element = self.meter_model_xmls[modelxml]
      meter: modbusMeterV1 = self.blank_meters[modelxml]
      ttydev = devalias
      if not meter.clear_reinit(modbus_addr, ttydev, ers=ers):
         error_code = 2
         return error_code, "UnableToReInitModbusMeter"
      # -- -- -- -- -- -- -- --
      meter.set_syspath(syspath)
      # -- try pinging up to 3x --
      for idx in range(0, 3):
         err, msg = meter.ping()
         if err != 0:
            self.redops.pub_diag_debug(f"UnableToPingModbusMeterAddr: {modbus_addr}")
            xdict: {} = {f"Ping_{idx}": msg}
            self.redops.save_meter_data(meter.syspath, _dict=xdict)
            time.sleep(0.480)
            error_code += 1
            continue
         else:
            self.redops.save_read(meter.syspath, f"PingOK: {modbus_addr}")
            return msg
      # -- return rpt string --
      return error_code, "temp_string"

   def __main_loop(self):
      # -- -- report -- --
      pub_channel: str = self.cp["REDIS"]["PUB_READS_CHANNEL"]
      _dict = {"boot_dts_utc": sysUtils.dts_utc(), "dev": "n/a"
         , "lan_ip": sysUtils.lan_ip(), "hostname": sysUtils.HOST
         , "pub_reads_channel": pub_channel}
      self.redops.update_diag_tag(self.diag_tag, mapdct=_dict, restart=True)
      # -- -- run -- --
      while True:
         try:
            print("mainloop")
            time.sleep(4.0)
         except Exception as e:
            logUtils.log_exp(e)
      # -- -- -- --
