
import gc, time, setproctitle
import multiprocessing as mp


class classAsProcRunner(object):

   def __init__(self, procname: str, obj: object, method2run: str):
      self.procname = procname
      self.obj = obj
      self.method2run = method2run
      self.proc = None
      self._target = None

   def init(self):
      self._target = getattr(self.obj, self.method2run)
      if self._target is None:
         raise Exception(f"MethodNotFound: {self.method2run}")

   def run_main_loop(self):
      # -- -- -- -- -- -- -- --
      setproctitle.setproctitle(self.procname)
      # -- main loop -- -- --
      while True:
         try:
            if self.proc is None:
               self.proc: mp.Process = mp.Process(target=self._target)
            if not self.proc.is_alive():
               if self.proc.exitcode:
                  try:
                     self.proc.kill()
                     self.proc.terminate()
                     self.proc = None
                     gc.collect()
                  finally:
                     time.sleep(30.0)
                  # -- re do new proc --
                  self.proc: mp.Process = mp.Process(target=self._target)
               # -- start proc --
               self.proc.start()
            else:
               pass
            # -- dump info --
            print(f"run_main_loop: {self.proc.name}")
            time.sleep(8.0)
         except Exception as e:
            print(e)
            continue
