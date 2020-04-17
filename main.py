import configparser
import os
import sys
from threading import Thread

import platform
from recorder import Twitch


def listen_terminal(application):
  os_type = platform.system()

  if os_type == "Linux":
    import termios
    while application.signal:
      fd = sys.stdin.fileno()
      old_ttyinfo = termios.tcgetattr(fd)
      new_ttfinfo = old_ttyinfo[:]
      new_ttfinfo[3] &= ~termios.ICANON
      new_ttfinfo[3] &= ~termios.ECHO
      termios.tcsetattr(fd, termios.TCSANOW, new_ttfinfo)
      terminal_input = os.read(fd, 7)

      if terminal_input in {b'q', b'Q'}:
        break
  elif os_type == "Windows":
    import msvcrt
    while application.signal:
      input_char = msvcrt.getch()
      if input_char.upper() == "Q":
        break
  else:
    print("didn't support your system")

  print("QUIT")
  application.signal = False


def main():
  config = configparser.ConfigParser()
  config.read("config.ini")

  url = input("streamer_url: ")
  twitch = Twitch(
    url=url, dir_path=config["Paths"]["storage_path"] if config["Paths"]["storage_path"] != "no" else os.path.abspath(os.path.dirname(__file__)),
    proxy=None if config["DEFAULT"]["proxy"] == "no" else config["DEFAULT"]["proxy"],
    concat_or_not=False if config["DEFAULT"]["concat_or_not"] == "no" else True,
    clean_cache=False if config["DEFAULT"]["clean_cache"] == "no" else True,
    output=config["DEFAULT"]["output"],
    update_frequency=int(config["DEFAULT"]["update_frequency"]))

  task1 = Thread(target=twitch.start, args=(True,))
  task1.start()

  listen_terminal(twitch)


if __name__ == "__main__":
  main()
