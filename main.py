import configparser
import os
import sys
import termios
from threading import Thread

from recorder import Twitch


def main():
  config = configparser.ConfigParser()
  config.read("config.ini")

  url = input("streamer_url: ")
  twitch = Twitch(
    url=url, dir_path=config["Paths"]["storage_path"] if config["Paths"]["storage_path"] != "no" else None,
    proxy=None if config["DEFAULT"]["proxy"] == "no" else config["DEFAULT"]["proxy"],
    concat_or_not=False if config["DEFAULT"]["concat_or_not"] == "no" else True,
    clean_cache=False if config["DEFAULT"]["clean_cache"] == "no" else True,
    output=config["DEFAULT"]["output"],
    update_frequency=int(config["DEFAULT"]["update_frequency"]))

  task1 = Thread(target=twitch.start, args=(True,))
  task1.start()

  while twitch.signal:
    fd = sys.stdin.fileno()
    old_ttyinfo = termios.tcgetattr(fd)
    new_ttfinfo = old_ttyinfo[:]
    new_ttfinfo[3] &= ~termios.ICANON
    new_ttfinfo[3] &= ~termios.ECHO
    termios.tcsetattr(fd, termios.TCSANOW, new_ttfinfo)
    terminal_input = os.read(fd, 7)

    if terminal_input in {b'q', b'Q'}:
      print("QUIT")
      twitch.signal = False


if __name__ == "__main__":
  main()
