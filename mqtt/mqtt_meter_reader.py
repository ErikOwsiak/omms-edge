
import paho.mqtt.client as mqtt
import xml.etree.cElementTree as et


class mqttMeterReader(object):

   def __init__(self, node: et.Element):
      self.node: et.Element = node
      self.meter_dbid = self.node.attrib["dbid"]
      self.meter_sn = self.node.attrib["sn"]
      self.clt: mqtt.Client = mqtt.Client()

   def init(self, broker: str, port: int):
      # -- callbacks --
      self.clt.on_connect = self.on_connect
      self.clt.on_message = self.on_msg
      # -- set user data --
      self.clt.user_data_set(self.node)
      self.clt.connect(broker, port)

   def start(self):
      self.clt.loop_start()

   """ <meter dbid="" sn="supla/devices/zamel-mew-01-11d2be">
          <reg type="total_kwh" name="channels/0/state/total_forward_active_energy" />
      </meter> """
   def on_connect(self, client, ud_node, flags, rc):
      self_clt: mqtt.Client = client
      self_node: et.Element = ud_node
      sn = self_node.attrib["sn"]
      dbid = self_node.attrib["dbid"]
      # -- subscribe all regs --
      for reg in self_node.findall("reg"):
         reg_key = reg.attrib["name"]
         topic = f"{sn}/{reg_key}"
         print(f"subscribing: {topic}")
         self_clt.subscribe(topic)

   def on_msg(self, client, ud_node, msg):
      ud_node: et.Element = ud_node
      dbid = ud_node.attrib["dbid"]
      meter_sn = ud_node.attrib["sn"]
      msg: mqtt.MQTTMessage = msg
      topic = msg.topic.replace(meter_sn, "")
      val = round(float(msg.payload), 2)
      buff = f"\n\t--- [ {meter_sn} ] ---\n\t  topic: {topic}" \
         f"\n\t  value: {val}\n\t  dbid: {dbid}"
      print(buff)
