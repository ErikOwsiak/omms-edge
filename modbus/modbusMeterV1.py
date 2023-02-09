
import configparser as _cp
import time
import xml.etree.ElementTree as _et
import minimalmodbus as _min_mbus
from termcolor import colored
# -- -- system -- --
from core.logutils import logUtils
from core.utils import sysUtils as utils
from modbus.meterReg import meterReg
from modbus.regDataMode import regDataMode
from modbus.meterSerialConf import meterSerialConf
from modbus.meterReading import meterReading
from system.ports import ports as sys_ports
from ommslib.shared.core.elecRegStream import elecRegStream
from ommslib.shared.core.elecRegStrEnums import elecRegStrEnumsShort
from core.meterInfoData import meterInfoData


"""
   1. load model xml registers 
   2. set modbus addr
   3. set stream frame
   4. per stream frame reg -> lookup address in model xml
   5. send to the meter -> get response 
   6. update stream frame reg
   7. create #RPT string 
   8. push to redis
   9. clear meter 
"""


NULL = "null"


class modbusMeterV1(object):
   """
      meter needs:
         1. modbus address
         2. serial info
         3. model registers -> actual register address as define by the model
         4. stream registers -> generic register defs used as lookups into the above
   """
   def __init__(self, sys_ini: _cp.ConfigParser
         , bus_addr: int
         , tty_dev_path: str
         , model_xml: _et.Element
         , elec_reg_stream: elecRegStream = None):
      # -- -- -- --
      self.sys_ini: _cp.ConfigParser = sys_ini
      self.modbus_addr: int = bus_addr
      self.tty_dev_path: str = tty_dev_path
      # <meter type="e1" tag="orno504 / single phase" brand="orno" model="orno504">
      # <meter type="e3" tag="orno516 / 3 phase" brand="orno" model="orno516">
      self.model_xml: _et.Element = model_xml
      self.mtype = self.model_xml.attrib["type"]
      self.model_brand: str = self.model_xml.attrib["brand"]
      self.model_model: str = self.model_xml.attrib["model"]
      self.model_tag: str = self.model_xml.attrib["tag"]
      # -- -- -- --
      self.m_info: meterInfoData \
         = meterInfoData(self.mtype, brand=self.model_brand
            , model=self.model_model, tag=self.model_tag)
      # -- -- -- --
      self.stream_regs: elecRegStream = elec_reg_stream
      self.stream_reads: [meterReading] = []
      # -- set on init call --
      self.serial_info: meterSerialConf = None
      self.model_regs: {} = {}
      self.syspath: str = ""
      self.ports: sys_ports = sys_ports(self.sys_ini)
      self.modbusInst: _min_mbus.Instrument = None
      self.read_error_count = 0

   """
      <comm type="serial" baudrate="9600" parity="E" stopbits="1" timeoutSecs="0.25" />
      <global_register_table>
        <!-- mode="" -> defaults: register; unit="" -> defaults: no unit -->
        <reg type="SerialNum" addr="0x0000" size="2" decpnt="1" mode="" unit="" />
        <reg type="ModbusAddr" addr="0x0002" size="1" decpnt="0" unit="" />
      </global_register_table>
   """
   def init(self):
      try:
         print(f"\n[ MB: {self.modbus_addr} | {self.model_model} ]")
         # -- setup serial info --
         elm: _et.Element = self.model_xml.find("comm[@type='serial']")
         self.serial_info = meterSerialConf(elm)
         regs: [_et.Element] = self.model_xml.findall("regs/reg")
         if len(regs) == 0:
            raise Exception("[ ModelRegsNotLoaded ]")
         # -- do --
         print(["loading regs:", regs])
         self.model_regs = [meterReg(x) for x in regs]
         if len(self.model_regs) == 0:
            raise Exception("ModelRegsNotParsed")
         # -- int ports --
         self.ports.load_serials()
         # -- modbus inst. --
         self.modbusInst: _min_mbus.Instrument = self.__createInstrument()
         return True
      except Exception as e:
         logUtils.log_exp(["modbusMeterV.init", e])
         return False

   def set_syspath(self, syspath: str):
      self.syspath = syspath

   def ping(self) -> (int, str):
      try:
         rval = self.__check_modbus_addr()
         if not rval:
            print(colored(f"\n\t[ PING {self.modbus_addr}: NoResponse! ]", "light_red"))
            time.sleep(1.0)
         else:
            print(colored(f"\n\t[ PING {self.modbus_addr}: PONG OK! ]", "light_green"))
            time.sleep(0.48)
         # -- -- -- --
         return 0, "OK"
      except Exception as e:
         logUtils.log_exp(e)
         return 1, str(e)

   def set_stream_regs(self, regs: elecRegStream):
      self.stream_regs = regs

   def read_stream_frame_registers(self) -> bool:
      # -- do --
      if self.stream_regs is None or len(self.stream_regs.reg_arr) == 0:
         print(colored("NoStreamRegisters", "yellow"))
         return False
      # -- abstract stream global_register_table --
      error_counter: int = 0
      self.stream_reads.clear()
      # -- for each register in stream registers --
      for reg in self.stream_regs.reg_arr:
         try:
            print(f"\t[ reading reg: {reg.regtype.name}]")
            _regs = [mr for mr in self.model_regs if mr.type == reg.regtype]
            if len(_regs) != 1:
               # if reg not listed in the model xml ... set to default value
               meter_read: meterReading = meterReading(regName=reg.regtype.name
                  , regVal=NULL, regValUnit="", formatterName="")
               self.stream_reads.append(meter_read)
               continue
            # -- -- run -- --
            meter_reg: meterReg = _regs[0]
            meter_read: meterReading = self.__read_meter_reg(meter_reg)
            if not meter_read.hasError:
               self.stream_reads.append(meter_read)
            else:
               # -- retry 2 more times --
               error_counter += 1
               for i in range(0, 2):
                  print(f"\t\t[ retrying reading reg: {reg.regtype.name} ]")
                  time.sleep(0.040)
                  meter_read: meterReading = self.__read_meter_reg(meter_reg)
                  if not meter_read.hasError:
                     print(colored(f"\t\t -> GoodRetry: {reg.regtype.name}", "magenta"))
                     error_counter -= 1
                     break
                  error_counter += 1
               # -- outside of for --
               self.stream_reads.append(meter_read)
            # -- small delay --
            time.sleep(0.020)
         except Exception as e:
            logUtils.log_exp(e)
            continue
      # -- -- end for reg in registers -- --
      ret_val: bool = True
      if error_counter == 0:
         print(colored(f"\n\t[ GoodMeterRead: addr: {self.modbus_addr} ]\n", "green"))
      else:
         print(colored(f"\n\t[ BadMeterRead: addr: {self.modbus_addr} ]\n", "red"))
         ret_val = False
      # -- -- -- --
      return ret_val

   def reads_str_arr(self) -> []:
      # -- -- -- --
      buff: [] = []
      if len(self.stream_reads) == 0:
         return buff
      # -- -- -- --
      for mr in self.stream_reads:
         mr: meterReading = mr
         buff.append(f"{mr.regName}:{mr.regVal}")
      # -- -- -- --
      return buff
      # -- -- -- --

   """
      private ... kinda
   """

   def __check_modbus_addr(self) -> bool:
      print("__check_modbus_addr")
      if self.modbus_addr in [None, 0]:
         raise Exception(f"BadModbusAddress: {self.modbus_addr}")
      # -- -- -- run -- -- -- --
      lst = [mr for mr in self.model_regs if mr.type == elecRegStrEnumsShort.ModbusAddr]
      if len(lst) != 1:
         raise Exception("MeterRegSearchError")
      reg: meterReg = lst[0]
      # -- -- -- -- -- --
      reading: meterReading = None
      for i in range(0, 3):
         reading: meterReading = self.__read_meter_reg(reg)
         if not reading.hasError:
            break
      # -- -- -- --
      if (reading is None) or (reading.regVal is None):
         print("UnableToRead")
         return False
      # -- -- -- --
      if not reading.hasError:
         return self.modbus_addr == int(str(reading.regVal), 0)
      else:
         return False

   def __read_meter_reg(self, reg: meterReg) -> meterReading:
      try:
         returnVal = None
         self.modbusInst.serial.timeout = self.serial_info.timeout
         # -- -- -- -- -- -- -- --
         if reg.mode == regDataMode.register:
            if reg.size == 1:
               returnVal = self.modbusInst.read_register(reg.addr_dec, reg.decpnt)
            else:
               returnVal = self.modbusInst.read_registers(reg.addr_dec, reg.size)
         # -- read float --
         if reg.mode == regDataMode.float:
            returnVal = self.modbusInst.read_float(reg.addr_dec, number_of_registers=reg.size)
         # -- read string --
         if reg.mode == regDataMode.string:
            returnVal = self.modbusInst.read_string(reg.addr_dec, number_of_registers=reg.size)
         # -- read int --
         if reg.mode == regDataMode.int:
            returnVal = self.modbusInst.read_long(reg.addr_dec)
         # -- meter was read -> create meter reading output --
         meterRead: meterReading = meterReading(regName=reg.mtype
            , errorReading=False, regVal=returnVal, regValUnit=reg.units
            , formatterName=reg.formatter)
         # -- -- -- -- -- -- -- --
         return meterRead
      except Exception as e:
         self.read_error_count += 1
         logUtils.log_exp(f"\t\t\t{e}")
         return meterReading(regName=reg.mtype, regVal=NULL
            , regValUnit=reg.units, formatterName="", errorReading=True)

   def __createInstrument(self) -> _min_mbus.Instrument:
      # - - - - - - - - - -
      if self.tty_dev_path not in self.ports.serial_ports:
         raise Exception(f"CommPortNotFound: {self.tty_dev_path}")
      # - - - - -
      meterInst: _min_mbus.Instrument = \
         _min_mbus.Instrument(port=self.tty_dev_path, slaveaddress=self.modbus_addr
            , mode=_min_mbus.MODE_RTU, debug=False)
      # - - - - -
      if meterInst is None:
         raise Exception("unable to create instrument")
      # - - - - -
      meterInst.serial.baudrate = self.serial_info.baudrate
      meterInst.serial.stopbits = self.serial_info.stopbits
      meterInst.serial.parity = self.serial_info.parity
      meterInst.serial.timeout = self.serial_info.timeout
      meterInst.clear_buffers_before_each_transaction = True
      # - - - -
      if not meterInst.serial.is_open:
         meterInst.serial.open()
      # self.modbusInst.precalculate_read_size = True
      # self.modbusInst.close_port_after_each_call = True
      return meterInst
