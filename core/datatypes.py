
import datetime


class mqttInfo(object):

   def __init__(self, host: str, port: int, pwd: str):
      self.host: str = host
      self.port: int = port
      self.pwd: str = pwd


class mqttMeterInfo(object):

   def __init__(self, tag: str, syspath: str):
      self.tag: str = tag
      self.syspath = syspath
