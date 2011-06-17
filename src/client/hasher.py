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
import hashlib
from os import path, close
from tempfile import mkstemp
from shutil import copy2, move

from database import Database
from shared import events
from config import Config

hashfn = hashlib.sha256
blocksize = 2**15 #seems to be the fastest chunk size on my laptop

class Hasher(threading.Thread):
    stopped = False
    def stop(self):
        self.stopped = True
        self.wh_queue.put(None)
    def run(self):
        self.database = Database()
        while not self.stopped:
            event = self.wh_queue.get(True)
            if event:
                self.handle_event(event)

    def handle_event(self, event):
        try:
            filepath = path.join(Config().get("core", "syncdir"), event.path)

            #first, copy the file over to a temporary directory, get its hash,
            #and then move it to the filename with that hash value
            handle, tmppath = mkstemp(dir=Config().get("core", "cachedir"))
            close(handle) #we don't really want it open, we just want a good name
            copy2(filepath, tmppath)

            event.hash = hash(tmppath)
            print "HASHED", event

            cachepath = path.join(Config().get("core", "cachedir"), event.hash)

            #move tmp file to hash-named file in cache directory
            move(tmppath, cachepath)

            #make sure the most recent version of this file doesn't match this one
            #this protects against basically creating an infinite loop
            res = self.database.execute("""SELECT * FROM events WHERE localpath=?
                                        AND rev != 0 ORDER BY rev DESC LIMIT 1""", (event.path,))
            latest = next(res, None)
            if latest is not None:
                e = events.Event(0)
                e.fromseq(latest)
                if e.hash == event.hash:
                    #returning because hashes are equal
                    return

            res = self.database.execute("SELECT * FROM events WHERE hash=?",
                                       (event.hash,))
            needsUpload = not next(res, None)

            #add event to the database
            self.database.execute("INSERT INTO events VALUES (0,?,?,?,?,?,?,?)",
                                  event.totuple()[1:])

            if needsUpload:
                print "HASH_HU ", event
                self.hu_queue.put(event)
            else:
                print "HASH_WUHS ", event
                self.wuhs_queue.put(event) #TODO check to make sure files
                                           #match, not just hashes
        except Exception as e:
            print e.message
            print "Error hashing file:"
            print event

def hash(filename):
    fn = hashfn()
    with open(filename,'rb') as f:
        for chunk in iter(lambda: f.read(blocksize), ''):
             fn.update(chunk)
    return fn.hexdigest()
