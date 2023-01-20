

class meterInfoData(object):

   def __init__(self, mtype="", brand="", model="", tag="n/s"):
      self.red_key: str = "MODEL_INFO"
      self.mtype = mtype
      self.brand = brand
      self.model = model
      self.tag = tag

   def __str__(self):
      return f"type: {self.mtype} | brand: {self.brand} | " \
         f"model: {self.model} | tag: {self.tag}"
