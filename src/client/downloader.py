#    Copyright (C) 2011 Aaron Lindsay <aaron@aclindsay.com>
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 2 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.

import threading
import Queue
from tempfile import mkstemp
from shutil import copy2, move
from os import path, remove, makedirs, close

from shared import events
from config import Config

class Downloader(threading.Thread):
    stopped = False
    def stop(self):
        self.stopped = True
        self.rd_queue.put(None)
    def run(self):
        while not self.stopped:
            event = self.rd_queue.get(True)
            if event:
                self.handle_event(event)

    def handle_event(self, event):
        dst = path.join(Config().get("core", "syncdir"), event.path)
        cachepath = path.join(Config().get("core", "cachedir"), event.hash)

        #TODO downloaded files should probably be cached locally
        #TODO make sure deleted files are cached locally if they're not yet
            #stored online
        if event.type & events.EventType.DELETE != 0:
            if path.exists(dst):
                try:
                    remove(dst)
                except: #OSError from file not existing
                    print "error removing ", event.path
            return

        #ensure file isn't already cached
        if not path.exists(cachepath):
            try:
                #create temporary file to download it to
                handle, tmppath = mkstemp(dir=Config().get("core", "cachedir"))
                close(handle) #we don't really want it open, we just want a good name

                self.storage.get(tmppath, event.hash, event.storagekey)
                #TODO handle failure of storage.get (will throw exception if fails)

                #move temp file to hashed cache file
                move(tmppath, cachepath)
            except:
                print "Error downloading file:"
                print event

        #move file from cache directory to actual file system
        #by way of another tmp file
        handle, tmppath = mkstemp(dir=Config().get("core", "cachedir"))
        close(handle) #we don't really want it open, we just want a good name
        copy2(cachepath, tmppath)

        #make sure directory exists first
        dirname = path.dirname(dst)
        if not path.isdir(dirname):
            makedirs(dirname)

        move(tmppath, dst)
