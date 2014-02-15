#!/usr/bin/python2
# Copyright (c) 2014 Kenneth Henderick <kenneth@ketronic.be>
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.

"""
Provides the overal functionality
"""

import ConfigParser
import time
import os
from datetime import datetime

from zfs import ZFS
from clean import Cleaner
from toolbox import Toolbox


class Manager(object):
    """
    Manages the ZFS snapshotting process
    """

    @staticmethod
    def run(settings):
        """
        Executes a single run where certain volumes might or might not be snapshotted
        """

        now = datetime.now()
        today = '{0:04d}{1:02d}{2:02d}'.format(now.year, now.month, now.day)

        snapshots = ZFS.get_snapshots()
        volumes = ZFS.get_volumes()
        for volume in volumes:
            if volume in settings:
                try:
                    volume_settings = settings[volume]
                    volume_snapshots = snapshots.get(volume, [])

                    # Decide whether we need to handle this volume
                    execute = False
                    if volume_settings['time'] == 'trigger':
                        # We wait until we find a trigger file in the filesystem
                        trigger_filename = '{0}/.trigger'.format(volume_settings['mountpoint'])
                        if os.path.exists(trigger_filename) and today not in volume_snapshots:
                            Toolbox.log('Trigger found on {0}'.format(volume))
                            os.remove(trigger_filename)
                            execute = True
                    else:
                        trigger_time = volume_settings['time'].split(':')
                        hour = int(trigger_time[0])
                        minutes = int(trigger_time[1])
                        if (now.hour > hour or (now.hour == hour and now.minute >= minutes)) and today not in volume_snapshots:
                            Toolbox.log('Time passed for {0}'.format(volume))
                            execute = True

                    if execute is True:
                        if volume_settings['snapshot'] is True:
                            # Take today's snapshotzfs
                            Toolbox.log('Taking snapshot {0}@{1}'.format(volume, today))
                            ZFS.snapshot(volume, today)
                            volume_snapshots.append(today)

                        # Replicating, if required
                        if volume_settings['replicate'] is not None:
                            Toolbox.log('Replicating {0}'.format(volume))
                            replicate_settings = volume_settings['replicate']
                            remote_snapshots = ZFS.get_snapshots(replicate_settings['endpoint'], replicate_settings['target'])
                            previous_snapshot = None
                            for snapshot in volume_snapshots:
                                if snapshot in remote_snapshots[replicate_settings['target']]:
                                    previous_snapshot = snapshot
                                elif previous_snapshot is not None:
                                    # There is a snapshot on this host that is not yet on the other side.
                                    ZFS.replicate(volume, previous_snapshot, snapshot, replicate_settings['target'], replicate_settings['endpoint'])
                                    previous_snapshot = snapshot

                        # Cleaning the snapshots (cleaning is mandatory)
                        Toolbox.log('Cleaning {0}'.format(volume))
                        Cleaner.clean(volume, volume_snapshots, volume_settings['schema'])
                except Exception as ex:
                    Toolbox.log('Exception: {0}'.format(str(ex)))

    @staticmethod
    def start():
        """
        Main entry point
        """

        settings = {}
        config = ConfigParser.ConfigParser()
        config.read('/etc/zfssnapmanager.cfg')
        for volume in config.sections():
            settings[volume] = {'mountpoint': config.get(volume, 'mountpoint'),
                                'time': config.get(volume, 'time'),
                                'snapshot': config.getboolean(volume, 'snapshot'),
                                'replicate': None,
                                'clean': config.getboolean(volume, 'clean'),
                                'schema': config.get(volume, 'schema')}
            if config.has_option(volume, 'replicate_endpoint') and config.has_option(volume, 'replicate_target'):
                settings[volume]['replicate'] = {'endpoint': config.get(volume, 'replicate_endpoint'),
                                                 'target': config.get(volume, 'replicate_target')}

        while True:
            Manager.run(settings)
            time.sleep(5 * 60)


if __name__ == '__main__':
    import daemon
    import daemon.pidfile

    pidfile = daemon.pidfile.PIDLockFile("/var/run/zfs-snap-manager.pid")
    with daemon.DaemonContext(pidfile=pidfile):
        Manager.start()