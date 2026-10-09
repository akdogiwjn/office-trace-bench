"""Passive Linux filesystem revision capture during Agent execution.

This adds no Agent tool, changes no Skill and executes no helper. Captured versions
are evidence, not proof that a particular process read a particular revision.
"""
import ctypes
import hashlib
import os
from pathlib import Path
import select
import struct
import threading
import time

from .contracts import write_json

CREATE = 0x100; CLOSE_WRITE = 0x8; MOVED_TO = 0x80; DELETE = 0x200
ISDIR = 0x40000000; OVERFLOW = 0x4000


class ArtifactCapture:
    def __init__(self, workspace, destination, temporary_root=Path('/tmp')):
        self.workspace = Path(workspace).resolve()
        self.destination = Path(destination)
        self.temporary_root = Path(temporary_root).resolve()
        self.events = []; self.gaps = []; self.watches = {}
        self.stop_event = threading.Event()
        self.libc = ctypes.CDLL(None, use_errno=True)

    def start(self):
        self.destination.mkdir(parents=True, exist_ok=True)
        (self.destination/'objects').mkdir(exist_ok=True)
        self.fd = self.libc.inotify_init1(os.O_NONBLOCK | os.O_CLOEXEC)
        if self.fd < 0: raise OSError(ctypes.get_errno(), 'inotify_init1 failed')
        for root in (self.workspace, self.temporary_root):
            self.watch(root)
            for folder in root.rglob('*'):
                if folder.is_dir() and not folder.is_symlink(): self.watch(folder)
        self.thread = threading.Thread(target=self.listen, daemon=True)
        self.thread.start()
        return self

    def watch(self, path):
        if path.is_relative_to(self.destination.resolve()): return
        descriptor = self.libc.inotify_add_watch(self.fd, os.fsencode(path), CREATE | CLOSE_WRITE | MOVED_TO | DELETE)
        if descriptor >= 0: self.watches[descriptor] = path
        else: self.gaps.append(dict(path=str(path), reason='watch_failed'))

    def capture(self, path, action):
        if path.is_symlink() or not path.is_file(): return
        if path.is_relative_to(self.workspace):
            relative = 'workspace/' + path.relative_to(self.workspace).as_posix()
            # Frozen inputs are already bound separately, not generated artifacts.
            if relative.startswith('workspace/input/'): return
        elif path.is_relative_to(self.temporary_root):
            if path.suffix.lower() not in ('.py','.sh','.json','.csv','.tsv','.yaml','.yml','.cfg','.ini','.toml','.conf','.txt',
                                           '.xlsx','.xls','.pdf','.xml','.rels','.parquet','.arrow','.feather'):
                return
            relative = 'temporary/' + path.relative_to(self.temporary_root).as_posix()
        else: return
        try:
            before = path.stat()
            if before.st_size > 128*1024*1024:
                self.gaps.append(dict(path=relative,reason='over_128MiB')); return
            data = path.read_bytes(); after = path.stat()
            if before.st_mtime_ns != after.st_mtime_ns or before.st_size != after.st_size:
                self.gaps.append(dict(path=relative, reason='changed_during_capture'))
                return
            digest = hashlib.sha256(data).hexdigest()
            target = self.destination/'objects'/digest
            if not target.exists(): target.write_bytes(data)
            self.events.append(dict(path=relative, sha256=digest, size=len(data), event=action,
                                    captured_at_ns=time.time_ns(), source_mtime_ns=after.st_mtime_ns))
        except OSError as exc:
            self.gaps.append(dict(path=relative, reason=type(exc).__name__))

    def listen(self):
        while not self.stop_event.is_set():
            readable, _, _ = select.select([self.fd], [], [], .05)
            if not readable: continue
            try: data = os.read(self.fd, 1024*1024)
            except BlockingIOError: continue
            offset = 0
            while offset < len(data):
                wd, mask, _, length = struct.unpack_from('iIII',data,offset)
                name = data[offset+16:offset+16+length].split(b'\0')[0]
                offset += 16+length
                if mask & OVERFLOW:
                    self.gaps.append(dict(reason='inotify_queue_overflow')); continue
                if wd not in self.watches: continue
                path = self.watches[wd]/os.fsdecode(name)
                if mask & ISDIR:
                    if mask & (CREATE|MOVED_TO):
                        self.watch(path)
                        if path.exists():
                            for child in path.rglob('*'):
                                if child.is_dir(): self.watch(child)
                                elif child.is_file(): self.capture(child,'new_directory_inventory')
                elif mask & (CLOSE_WRITE|MOVED_TO): self.capture(path,'close_write' if mask & CLOSE_WRITE else 'moved_to')
                elif mask & DELETE:
                    self.events.append(dict(path=str(path), event='deleted', captured_at_ns=time.time_ns()))

    def finish(self):
        # Drain the event queue before final inventory; remaining final files also get captured.
        time.sleep(.1)
        self.stop_event.set(); self.thread.join(timeout=5); os.close(self.fd)
        for path in self.workspace.rglob('*'):
            if path.is_file(): self.capture(path,'final_inventory')
        result = dict(schema_version='office-artifact-revisions-v1', events=self.events, gaps=self.gaps,
            scope='Workspace generated files plus script/config/text/document/transformed-data files under /tmp. close-write/move observations and final inventory; filesystem timing is not process read/exec provenance. Fast overwrite/delete races may produce gaps. Full tool arguments/results remain in tool_events.',
            replay_ready=False)
        write_json(self.destination/'revisions.json',result)
        return result
