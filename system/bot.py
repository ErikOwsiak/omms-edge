
import psutil, time
import setproctitle
from configparser import SectionProxy as _sp


class bot(object):

   PROC_NAME = ""

   def __init__(self, sec: _sp):
      self.sec_ini: _sp = sec
      bot.PROC_NAME = self.sec_ini["PROC_NAME"]

   def clear_previous_prox(self):
      def __on_proc(pr: psutil.Process):
         try:
            if pr.name() == bot.PROC_NAME:
               print(F"PreviousProcFound | PID: {pr.pid}\n\tkilling...")
               pr.kill()
         except Exception as ex:
            print(ex)
      # -- -- -- --
      for ipr in psutil.process_iter():
         __on_proc(ipr)
      # -- -- -- --

   def set_process_name(self):
      print(f"\n\n\t[ SettingProcessNameTo: {bot.PROC_NAME} ]\n")
      setproctitle.setproctitle(bot.PROC_NAME)
      time.sleep(1.0)
