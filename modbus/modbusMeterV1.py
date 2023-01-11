
import configparser as _cp
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

   def __init__(self, cp: _cp.ConfigParser, modelxml: _et.Element):
      self.cp: _cp.ConfigParser = cp
      self.modelxml: _et.Element = modelxml
      self.serial_info: meterSerialConf = None
      self.modbus_addr: int = 0
      self.stream_frame_regs: _et.Element = None
      self.model_regs: {} = {}
      self.ers: elecRegStream = None
      self.syspath: str = ""
      self.ports: sys_ports = sys_ports()
      self.tty_dev: str = ""
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
         # load model regs into a dictionary
         elm: _et.Element = self.modelxml.find("comm[@type='serial']")
         self.serial_info = meterSerialConf(elm)
         regs: [_et.Element] = self.modelxml.findall("regs/reg")
         if len(regs) == 0:
            raise Exception("[ ModelRegsNotLoaded ]")
         # -- do --
         self.model_regs = [meterReg(x) for x in regs]
         if len(self.model_regs) == 0:
            raise Exception("ModelRegsNotParsed")
         # -- int ports --
         self.ports.load_serials(cp=self.cp)
      except Exception as e:
         logUtils.log_exp(e)

   def set_syspath(self, syspath: str):
      self.syspath = syspath

   def clear_reinit(self, addr: int, ttydev: str, ers: elecRegStream) -> bool:
      try:
         self.modbus_addr = addr
         self.tty_dev = ttydev
         self.stream_frame_regs = ers
         # -- new modbus inst --
         if self.modbusInst is None:
            self.modbusInst: _min_mbus.Instrument = self.__createInstrument()
         else:
            if self.modbusInst.serial.isOpen():
               self.modbusInst.serial.close()
            self.modbusInst.address = addr
            self.modbusInst.serial.port = self.tty_dev
            if not self.modbusInst.serial.isOpen():
               self.modbusInst.serial.open()
         return True
      except Exception as e:
         logUtils.log_exp(e)
         return False

   def ping(self) -> (int, str):
      try:
         rval = self.__checkModbusAddr()
         if not rval:
            print(f"\tPING {self.modbus_addr}: NoResponse!")
         else:
            print(f"\tPING {self.modbus_addr}: PONG OK!")
         # -- -- -- --
         return 0, "OK"
      except Exception as e:
         logUtils.log_exp(e)
         return 1, str(e)

   """
      private ... kinda
   """

   def __checkModbusAddr(self) -> bool:
      print("_checkModbusAddr")
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
      if self.tty_dev not in self.ports.serial_ports:
         raise Exception(f"CommPortNotFound: {self.tty_dev}")
      # - - - - -
      meterInst: _min_mbus.Instrument = \
         _min_mbus.Instrument(port=self.tty_dev, slaveaddress=self.modbus_addr
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
