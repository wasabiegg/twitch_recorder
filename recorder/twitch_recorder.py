import os
import pathlib
import time
from datetime import timezone, datetime
from urllib.parse import urljoin, urlencode

import m3u8
import requests

from downloader import Downloader


def build_session(proxy=None, max_retries=3):
  session = requests.Session()
  adapter = requests.adapters.HTTPAdapter(max_retries=max_retries)
  session.mount("http://", adapter)
  session.mount("https://", adapter)
  if proxy:
    session.proxies = {
      "http": proxy,
      "https": proxy,
    }
  return session


class Twitch(object):
  __slots__ = ["url", "session", "streamer", "sig", "token", "playlists_api", "dir_path", "signal", "proxy",
               "client_id", "timeout", "clean_cache", "output", "update_frequency", "concat_or_not"]

  def __init__(self, url, dir_path=None, proxy=None, timeout=3, clean_cache=True, output="output.mp4",
               update_frequency=0, concat_or_not=True):
    self.url = url
    self.dir_path = dir_path
    self.signal = False
    # client-id is fixed value
    self.client_id = "jzkbprff40iqj646a697cyrvl0zt2m6"
    self.proxy = proxy
    self.timeout = timeout
    self.clean_cache = clean_cache
    self.output = output
    self.update_frequency = update_frequency
    self.concat_or_not = concat_or_not
    self.__post_init__()

  def __post_init__(self):
    # build session
    self.session = build_session(self.proxy, max_retries=3)

    # get streamer name
    self.streamer = self.url.split('/')[-1]
    assert (self.get_status() is not None)

    # get sig and token to access playlists api
    self.sig, self.token = self.get_token()

    # get playlists api, playlists api is for updating segments
    self.playlists_api = self.get_playlists_api()

    # init project folder
    self.__init__dir()

  def __init__dir(self):
    # init project folder
    base_dir = self.dir_path if self.dir_path is not None else os.path.join(
      os.path.abspath(os.path.dirname(__file__)))
    self.dir_path = os.path.join(base_dir, self.streamer, time.strftime("%Y-%m-%d-%H:%M:%S", time.localtime()))
    pathlib.Path(self.dir_path).mkdir(parents=True, exist_ok=True)

  def get_status(self):
    api = urljoin("https://api.twitch.tv/kraken/streams/", self.streamer)
    r = self.session.get(url=api, headers={"Client-ID": self.client_id}, timeout=self.timeout).json()
    if result := r.get("stream"):
      return result
    else:
      return None

  def get_token(self):
    try:
      api = f"https://api.twitch.tv/api/channels/{self.streamer}/access_token?"
      r = self.session.get(api, headers={"Client-ID": self.client_id}, timeout=self.timeout).json()
      return r["sig"], r["token"]
    except Exception as e:
      raise e

  def get_playlists_api(self):
    # default get highest resolution
    params = {
      "allow_source": "true",
      "baking_bread": "false",
      "baking_brownies": "false",
      "baking_brownies_timeout": "1050",
      "fast_bread": "true",
      "p": "5186217",
      "player_backend": "mediaplayer",
      "playlist_include_framerate": "true",
      "reassignments_supported": "true",
      "sig": self.sig,
      "token": self.token,
      "supported_codecs": "avc1",
      "cdm": "wv",
    }
    api = f"https://usher.ttvnw.net/api/channel/hls/{self.streamer}.m3u8?" + urlencode(params)
    r = self.session.get(api, timeout=self.timeout)
    assert r.status_code == 200
    m3u8_obj = m3u8.loads(r.content.decode("utf-8"))
    return m3u8_obj.playlists[0].uri

  def update_playlists(self):
    last_program_date = datetime.now(timezone.utc)

    # loop to keep updating playlists
    while self.signal and self.get_status():
      r = self.session.get(self.playlists_api)
      assert r.status_code == 200

      # track untracked segments
      segments = []
      for segment in m3u8.loads(r.content.decode("utf-8")).segments:
        if segment.program_date_time > last_program_date:
          segments.append(segment)

      # update last_program_date
      if segments:
        last_program_date = segments[-1].program_date_time

        playlists = [i.uri for i in segments]
        file_lists = self.playlists_to_filelists(segments)
        directory = self.dir_path
        timeout = self.timeout

        # start m3u8_async_downloader to download ts file
        downloader = Downloader(playlists, file_lists, directory, timeout=timeout, proxy=self.proxy)
        downloader.run()

        # write tracked ts file to filelists
        self.dump_filelists(segments)
        time.sleep(self.update_frequency)

    # close twitch recorder
    self.close()

  def close(self):
    self.signal = False
    self.concat()
    self.clean()

  def concat(self):
    if self.concat_or_not:
      Downloader.concat(self.dir_path, self.dir_path, self.output)

  def clean(self):
    if self.clean_cache:
      for i in os.listdir(self.dir_path):
        if i.endswith(".ts") or i.endswith(".txt"):
          os.remove(os.path.join(self.dir_path, i))

  def dump_filelists(self, filelists):
    with open(os.path.join(self.dir_path, "filelists.txt"), "a") as f:
      for i in self.playlists_to_filelists(filelists):
        f.write(f"file {i}\n")

  def playlists_to_filelists(self, segments):
    return [(s.program_date_time.strftime("%m-%d-%Y-%H:%M:%S") + ".ts") for s in segments]

  def start(self, signal):
    self.signal = signal
    if signal:
      self.update_playlists()
