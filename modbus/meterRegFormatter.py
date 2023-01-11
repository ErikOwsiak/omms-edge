

class meterRegFormatter(object):

   @staticmethod
   def divide1000r2(num):
      print(f"divide1000r2: {num}")
      return round((num / 1000), 2)

   @staticmethod
   def divide1000r3(num):
      return round((num / 1000), 3)

   @staticmethod
   def divide1000r4(num):
      return round((num / 1000), 4)

   @staticmethod
   def round2(num):
      return round(num, 2)

   @staticmethod
   def round3(num):
      return round(num, 3)

   @staticmethod
   def round4(num):
      return round(num, 4)

   @staticmethod
   def times1000r2(num):
      return round((num * 1000), 2)
