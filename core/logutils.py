
from termcolor import colored


class logUtils(object):

   @staticmethod
   def print_info(msg):
      pass

   @staticmethod
   def log_err(err):
      print(err)

   @staticmethod
   def log_exp(ex):
      print(colored(str(ex), "red"))
