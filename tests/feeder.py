#!/usr/bin/env python3

import time
import serial


port = "/dev/pts/11"


def main():
   ser: serial.Serial = serial.Serial(port=port)
   with open("reads.txt", "r") as f:
      lns = f.readlines()
   while True:
      print("top of while...")
      for ln in lns:
         cnt = ser.write(ln.encode("utf-8"))
         print(f"bytes sent: {cnt}")
         time.sleep(4.0)
      time.sleep(8.0)


# -- -- -- -- run -- -- -- --
if __name__ == "__main__":
    main()
