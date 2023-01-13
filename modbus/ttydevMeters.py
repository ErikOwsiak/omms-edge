
import xml.etree.ElementTree as _et
# -- system --
from core.logutils import logUtils


class ttydevMeters(object):

   """
      <ttydev run="yes" tag="ModbusEdgeA5" alias="modbusPortA" dev="auto" modbusBugID="bugID1">
   """
   def __init__(self, xmlelm: _et.Element):
      self.xml_elm: _et.Element = xmlelm
      self.run = self.xml_elm.attrib["run"]
      self.tag = self.xml_elm.attrib["tag"]
      self.dev = self.xml_elm.attrib["dev"]
      self.alias = self.xml_elm.attrib["alias"]
      self.bud_id = self.xml_elm.attrib["modbusBugID"]
      self.meters: [_et.Element] = None

   def init(self):
      self.meters = self.xml_elm.findall("meter")