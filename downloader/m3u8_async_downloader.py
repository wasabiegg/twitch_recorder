import asyncio
import os

import aiohttp
from aiofile import AIOFile
from tenacity import retry
from tqdm import tqdm


class Downloader(object):
  __slots__ = ["playlists", "directory", "proxy", "headers", "decrypt_method", "file_lists", "timeout",
               "requests_config", "session_config"]

  def __init__(
    self,
    playlists,
    file_lists,
    directory,
    timeout=4,
    proxy=None,
    headers=None,
    decrypt_method=lambda x: x
  ):
    self.playlists = playlists
    self.file_lists = file_lists
    self.directory = directory
    self.timeout = timeout
    self.proxy = proxy
    self.headers = headers
    self.decrypt_method = decrypt_method

    self.__post_init__()

  def __post_init__(self):
    # config headers
    if self.headers is None:
      self.headers = {
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/71.0.3578.80 Safari/537.36",
        "method": "GET"}

    # config request
    if self.proxy:
      self.requests_config = {"proxy": self.proxy, "timeout": self.timeout, "verify_ssl": False}
    else:
      self.requests_config = {"timeout": self.timeout, "verify_ssl": False}

    # config session
    self.session_config = {"headers": self.headers}
    # init project folder
    if not os.path.isdir(self.directory):
      os.mkdir(self.directory)

    self.file_lists = [os.path.join(self.directory, filename) for filename in self.file_lists]

  async def loop(self):
    sem = asyncio.Semaphore(1000)
    tasks = list(zip(self.playlists, self.file_lists))
    with tqdm(total=len(tasks)) as pbar:
      async with aiohttp.ClientSession(**self.session_config) as session:
        result = await asyncio.gather(*[self.download_ts(sem, t[0], t[1], session, pbar) for t in tasks])

  @retry
  async def download_ts(self, sem, url, filepath, session, bar):
    async with sem:
      async with session.get(url=url, **self.requests_config) as resp:
        content = await resp.read()
        if isinstance(content, bytes):
          content = self.decrypt_method(content)
          await self.save_ts(filepath, content)
          bar.update(1)
        else:
          await asyncio.sleep(1)
          await self.download_ts(sem, url, filepath, session)

  async def save_ts(self, filepath, content):
    async with AIOFile(filepath, "wb") as afp:
      await afp.write(content)
      await afp.fsync()

  @staticmethod
  def concat(dir_path, output_path, output):
    import ffmpeg
    try:
      {
        ffmpeg
          .input(os.path.join(dir_path, "filelists.txt"), format="concat", safe=0)
          .output(os.path.join(output_path, output), c="copy", threads=4, loglevel="panic")
          .run()
      }
    except Exception as e:
      raise e

  def run(self):
    # import logging
    # logging.basicConfig(level=logging.DEBUG)
    # asyncio.run(self.loop(), debug=True)

    asyncio.run(self.loop())