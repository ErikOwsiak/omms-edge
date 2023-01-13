
import configparser as _cp
import time
import xml.etree.ElementTree as _et
import minimalmodbus as _min_mbus
# -- -- system -- --
from core.logutils import logUtils
from modbus.meterReg import meterReg
from modbus.regDataMode import regDataMode
from modbus.meterSerialConf import meterSerialConf
from modbus.meterReading import meterReading
from system.ports import ports as sys_ports
from ommslib.shared.core.elecRegStream import elecRegStream
from ommslib.shared.core.elecRegStrEnums import elecRegStrEnumsShort


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
      self.model_xml: _et.Element = model_xml
      self.stream_regs: elecRegStream = elec_reg_stream
      self.stream_reads: [meterReading] = []
      # -- set on init call --
      self.serial_info: meterSerialConf = None
      self.model_regs: {} = {}
      self.syspath: str = ""
      self.ports: sys_ports = sys_ports(self.sys_ini)
      self.modbusInst: _min_mbus.Instrument = None

   """
      <comm type="serial" baudrate="9600" parity="E" stopbits="1" timeoutSecs="0.25" />
      <regs>
        <!-- mode="" -> defaults: register; unit="" -> defaults: no unit -->
        <reg type="SerialNum" addr="0x0000" size="2" decpnt="1" mode="" unit="" />
        <reg type="ModbusAddr" addr="0x0002" size="1" decpnt="0" unit="" />
      </regs>
   """
   def init(self):
      try:
         # -- setup serial info --
         elm: _et.Element = self.model_xml.find("comm[@type='serial']")
         self.serial_info = meterSerialConf(elm)
         regs: [_et.Element] = self.model_xml.findall("regs/reg")
         if len(regs) == 0:
            raise Exception("[ ModelRegsNotLoaded ]")
         # -- do --
         self.model_regs = [meterReg(x) for x in regs]
         if len(self.model_regs) == 0:
            raise Exception("ModelRegsNotParsed")
         # -- int ports --
         self.ports.load_serials()
         # -- modbus inst. --
         self.modbusInst: _min_mbus.Instrument = self.__createInstrument()
         return True
      except Exception as e:
         logUtils.log_exp(e)

   def set_syspath(self, syspath: str):
      self.syspath = syspath

   def ping(self) -> (int, str):
      try:
         rval = self.__check_modbus_addr()
         if not rval:
            print(f"\tPING {self.modbus_addr}: NoResponse!")
         else:
            print(f"\tPING {self.modbus_addr}: PONG OK!")
         # -- -- -- --
         return 0, "OK"
      except Exception as e:
         logUtils.log_exp(e)
         return 1, str(e)

   def set_stream_regs(self, regs: elecRegStream):
      self.stream_regs = regs

   def read_stream_regs(self) -> bool:
      if self.stream_regs is None or len(self.stream_regs.reg_arr) == 0:
         pass
      # -- abstract stream regs --
      self.stream_reads.clear()
      for reg in self.stream_regs.reg_arr:
         try:
            # -- remap to meter stream --
            _regs = [mr for mr in self.model_regs if mr.type == reg.regtype]
            if len(_regs) != 1:
               pass
            meter_read: meterReading = self.__read_meter_reg(_regs[0])
            self.stream_reads.append(meter_read)
            time.sleep(0.80)
         except Exception as e:
            logUtils.log_exp(e)
            continue
      # -- -- -- --
      return True

   def reads_to_str(self):
      buff: [] = []
      for mr in self.stream_reads:
         mr: meterReading = mr
         buff.append(f"{mr.regName}:{mr.regVal}")
      s = "|".join(buff)
      return f"[MB: {self.modbus_addr}|{s}]"

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
         if reading is not None:
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

   def __read_meter_reg(self, reg: meterReg) -> [None, meterReading]:
      self.modbusInst.serial.timeout = self.serial_info.timeout
      returnVal = None
      # -- -- -- -- -- -- -- --
      if reg.mode == regDataMode.register:
         if reg.size == 1:
            returnVal = self.modbusInst.read_register(reg.addr_dec, reg.decpnt)
         else:
            returnVal = self.modbusInst.read_registers(reg.addr_dec, reg.size)
      # read float
      if reg.mode == regDataMode.float:
         returnVal = self.modbusInst.read_float(reg.addr_dec, number_of_registers=reg.size)
      # read string
      if reg.mode == regDataMode.string:
         returnVal = self.modbusInst.read_string(reg.addr_dec, number_of_registers=reg.size)
      # read int
      if reg.mode == regDataMode.int:
         returnVal = self.modbusInst.read_long(reg.addr_dec)
      # -- meter was read -> create meter reading output --
      meterRead: meterReading = meterReading(regName=reg.mtype
         , regVal=returnVal, regValUnit=reg.units, formatterName=reg.formatter)
      # -- -- -- -- -- -- -- --
      return meterRead

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
