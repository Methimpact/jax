# Copyright 2020 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import contextlib
import itertools
import os.path
import threading
from typing import Any, Optional, Iterator

import jax.version
from jax.lib import xla_client

from jax._src import traceback_util
traceback_util.register_exclusion(__file__)


Traceback = Any  # xla_client.Traceback
Frame = Any  # xla_client.Traceback::Frame

_exclude_paths = [os.path.dirname(jax.version.__file__)]

def register_exclusion(path):
  _exclude_paths.append(path)

def user_frames(source_info: Optional[Traceback]) -> Iterator[Frame]:
  """Heuristic that guesses the identity of the user's code in a stack trace."""
  # Guess the user's frame is the innermost frame not in the jax source tree
  # We don't use traceback_util.path_starts_with because that incurs filesystem
  # access, which may be slow; we call this function when e.g. adding source
  # provenance annotations to XLA lowerings, so we don't want to incur the cost.
  return (x for x in (source_info.frames if source_info else [])
          if not any(x.file_name.startswith(p) for p in _exclude_paths))

def user_frame(source_info: Optional[Traceback]) -> Optional[Frame]:
  return next(user_frames(source_info), None)

def summarize(source_info: Optional[Traceback], num_frames=1) -> str:
  frames = itertools.islice(user_frames(source_info), num_frames)
  frame_strs = [f"{frame.file_name}:{frame.line_num} ({frame.function_name})"
                if frame else "unknown" for frame in frames]
  return '\n'.join(reversed(frame_strs))


class _SourceInfoContext(threading.local):
  context: Optional[Traceback]

  def __init__(self):
    self.context = None

_source_info_context = _SourceInfoContext()


def current() -> Optional[Traceback]:
  return _source_info_context.context or xla_client.Traceback.get_traceback()

@contextlib.contextmanager
def user_context(c):
  prev = _source_info_context.context
  _source_info_context.context = c or _source_info_context.context
  try:
    yield
  finally:
    _source_info_context.context = prev