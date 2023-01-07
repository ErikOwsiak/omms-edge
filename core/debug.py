
import os


class debug(object):

   @staticmethod
   def is_dev_box() -> bool:
      hn = os.uname()[1]
      return hn in ["3cpo", ""]
