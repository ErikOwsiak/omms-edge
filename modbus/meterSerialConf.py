
import xml.etree.ElementTree as et


# <serial baudrate="9600" parity="N" stopbits="1" timeoutSecs="0.15" />
class meterSerialConf(object):

   def __init__(self, serXml: et.Element):
      print("[ c-tor: meterSerial ]")
      self.serXml = serXml
      self.parity: str = self.serXml.attrib["parity"]
      self.baudrate: int = int(self.serXml.attrib["baudrate"])
      self.stopbits: int = int(self.serXml.attrib["stopbits"])
      self.timeout: float = float(self.serXml.attrib["timeoutSecs"])
