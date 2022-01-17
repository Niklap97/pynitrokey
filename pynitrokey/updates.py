# -*- coding: utf-8 -*-
#
# Copyright 2022 Nitrokey Developers
#
# Licensed under the Apache License, Version 2.0, <LICENSE-APACHE or
# http://apache.org/licenses/LICENSE-2.0> or the MIT license <LICENSE-MIT or
# http://opensource.org/licenses/MIT>, at your option. This file may not be
# copied, modified, or distributed except according to those terms.

import os.path
import re
import urllib.parse
from typing import BinaryIO, Dict

import requests

API_BASE_URL = "https://api.github.com"


class FirmwareUpdate:
    def __init__(self, tag: str, url: str) -> None:
        self.tag = tag
        self.url = url

    def download(self, f: BinaryIO) -> None:
        with requests.get(self.url, stream=True) as response:
            response.raise_for_status()
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)

    def download_to_dir(self, d: str, overwrite: bool = False) -> str:
        if not os.path.exists(d):
            raise Exception(f"Cannot download firmware: {d} does not exist")
        if not os.path.isdir(d):
            raise Exception(f"Cannot download firmware: {d} is not a directory")
        url = urllib.parse.urlparse(self.url)
        filename = os.path.basename(url.path)
        path = os.path.join(d, filename)
        if os.path.exists(path) and not overwrite:
            raise Exception(f"File {path} already exists and may not be overwritten")
        with open(path, "wb") as f:
            self.download(f)
        return path

    def __repr__(self) -> str:
        return f"FirmwareUpdate(tag={self.tag}, url={self.url})"

    def __str__(self) -> str:
        return self.tag

    @classmethod
    def _from_release(cls, release: dict, url_pattern: re.Pattern) -> "FirmwareUpdate":
        return cls._from_assets(release["assets"], release["tag_name"], url_pattern)

    @classmethod
    def _from_assets(
        cls, assets: list, tag: str, url_pattern: re.Pattern
    ) -> "FirmwareUpdate":
        urls = []
        for asset in assets:
            url = asset["browser_download_url"]
            if url_pattern.search(url):
                urls.append(url)

        if len(urls) == 1:
            return cls(tag=tag, url=urls[0])
        elif len(urls) == 0:
            raise ValueError(f"Failed to find update file for firmware release {tag}")
        else:
            raise ValueError(f"Found multiple update files for firmware release {tag}")


class Repository:
    def __init__(self, owner: str, name: str, update_pattern: re.Pattern) -> None:
        self.owner = owner
        self.name = name
        self.update_pattern = update_pattern

    def get_latest_update(self) -> FirmwareUpdate:
        release = self._call(f"/repos/{self.owner}/{self.name}/releases/latest")
        return FirmwareUpdate._from_release(release, self.update_pattern)

    def get_update(self, tag: str) -> FirmwareUpdate:
        release = self._call(
            f"/repos/{self.owner}/{self.name}/releases/tags/{tag}",
            {404: f"Failed to find firmware release {tag}"},
        )
        return FirmwareUpdate._from_release(release, self.update_pattern)

    def _call(self, path: str, errors: Dict[int, str] = dict()) -> dict:
        url = self._get_url(path)
        response = requests.get(url)
        for code in errors:
            if response.status_code == code:
                raise ValueError(errors[code])
        response.raise_for_status()
        return response.json()

    def _get_url(self, path: str) -> str:
        return API_BASE_URL + path
