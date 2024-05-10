# SPDX-License-Identifier: Apache-2.0
# Copyright 2024 momtchil@momtchev.com
# Inspired by the python.py module

from __future__ import annotations

import json, subprocess, os, sys, tarfile
import urllib.request, urllib.error, urllib.parse
from pathlib import Path
import typing as T

from . import ExtensionModule, ModuleInfo
from .. import mesonlib
from .. import mlog
from .. import mparser
from ..build import known_shmod_kwargs, CustomTarget, CustomTargetIndex, BuildTarget, GeneratedList, StructuredSources, ExtractedObjects, SharedModule
from ..interpreter.type_checking import SHARED_MOD_KWS
from ..interpreterbase import (
    permittedKwargs, typed_pos_args, typed_kwargs
)

if T.TYPE_CHECKING:
    from ..interpreter import Interpreter
    from ..interpreter.interpreter import BuildTargetSource
    from ..interpreter.kwargs import SharedModule as SharedModuleKw


mod_kwargs = {'subdir', 'limited_api'}
mod_kwargs.update(known_shmod_kwargs)
mod_kwargs -= {'name_prefix', 'name_suffix'}

_MOD_KWARGS = [k for k in SHARED_MOD_KWS if k.name not in {'name_prefix', 'name_suffix'}]

class NapiModule(ExtensionModule):

    INFO = ModuleInfo('node_api', '2.0.0')

    def __init__(self, interpreter: 'Interpreter') -> None:
        super().__init__(interpreter)
        self.methods.update({
            'extension_module': self.extension_module_method,
        })

    def download_item(self, url: str, dest: Path) -> None:
        remote = urllib.request.urlopen(url)
        if url.endswith('.tar.gz'):
            if not os.path.exists(dest):
                mlog.log(f'Downloading {url} to {dest}')
                strip1 = lambda member, path: member.replace(name=Path(*Path(member.path).parts[1:]))
                with tarfile.open(fileobj=remote, mode='r:gz') as input:
                    input.extractall(path=dest, filter=strip1)
        else:
            if not os.path.exists(dest):
                file = urllib.parse(url)
                input = Path(dest, os.path.basename(file.path))
                mlog.log(f'Downloading {url} to {str(input)}')
                with file.open('wb') as output:
                    output.write(url.read())

    def download_headers(self) -> None:
        try:
            node_json = subprocess.Popen(['node', '-p', 'JSON.stringify(process)'], shell=False, stdout=subprocess.PIPE)
            node_json.wait()
            data, err = node_json.communicate()
            node_process = json.loads(data)
        except Exception as e:
            raise mesonlib.MesonException(f'Failed spawning node: {str(e)}')
        destination: Path = None
        if sys.platform == 'linux' or sys.platform == 'darwin':
            home = os.environ['HOME'] if 'HOME' in os.environ else '/tmp'
            destination = Path(home) / '.cache' / 'node-hadron' / node_process['release']['name'] / node_process['version']
        elif sys.platform == 'darwin':
            home = os.environ['HOME'] if 'HOME' in os.environ else '/tmp'
            destination = Path(home) / 'Library' / 'Caches' / 'node-hadron' / node_process['release']['name'] / node_process['version']
        elif sys.platform == 'win32':
            home = os.environ['LOCALAPPDATA'] if 'LOCALAPPDATA' in os.environ else 'C:\\'
            destination = Path(home) / 'node-hadron' / node_process['release']['name'] / node_process['version']

        if 'headersUrl' in node_process['release']:
            self.download_item(node_process['release']['headersUrl'], destination)
        if 'libUrl' in node_process['release']:
            self.download_item(node_process['release']['libUrl'], destination)

        mlog.log(f'Node.js library distribution is in {str(destination)}')
        return None

    @permittedKwargs(mod_kwargs)
    @typed_pos_args('node_api.extension_module', str, varargs=(str, mesonlib.File, CustomTarget, CustomTargetIndex, GeneratedList, StructuredSources, ExtractedObjects, BuildTarget))
    @typed_kwargs('node_api.extension_module', *_MOD_KWARGS)
    def extension_module_method(self, node: mparser.BaseNode, args: T.Tuple[str, T.List[BuildTargetSource]], kwargs: SharedModuleKw) -> 'SharedModule':
        self.download_headers()
        return self.interpreter.build_target(node, args, kwargs, SharedModule)

def initialize(interpreter: 'Interpreter') -> NapiModule:
    mod = NapiModule(interpreter)
    return mod
