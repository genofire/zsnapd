# Copyright (c) 2014-2017 Kenneth Henderick <kenneth@ketronic.be>
# Copyright (c) 2019 Matthew Grant <matt@mattgrant.net.nz>
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
Provides basic ZFS functionality
"""

import time
import re
from collections import OrderedDict

from magcode.core.globals_ import log_debug, log_info, log_error

from scripts.globals_ import SNAPSHOTNAME_REGEX
from scripts.globals_ import SNAPSHOTNAME_FMTSPEC
from scripts.helper import Helper


class ZFS(object):
    """
    Contains generic ZFS functionality
    """

    @staticmethod
    def get_snapshots(dataset='', endpoint='', all_snapshots=True):
        """
        Retreives a list of snapshots
        """

        if endpoint == '':
            command = 'zfs list -pH -s creation -o name,creation -t snapshot{0}{1} || true'
        else:
            command = '{0} \'zfs list -pH -s creation -o name,creation -t snapshot{1} || true\''
        if dataset == '':
            dataset_filter = ''
        else:
            dataset_filter = ' | grep ^{0}@'.format(dataset)
        output = Helper.run_command(command.format(endpoint, dataset_filter), '/')
        snapshots = {}
        for line in filter(len, output.split('\n')):
            parts = list(filter(len, line.split('\t')))
            datasetname = parts[0].split('@')[0]
            creation = int(parts[1])
            snapshot = time.strftime(SNAPSHOTNAME_FMTSPEC, time.localtime(creation))
            snapshotname = parts[0].split('@')[1]
            if (not all_snapshots and re.match(SNAPSHOTNAME_REGEX, snapshotname) is None):
                # If required, only read in zsnapd snapshots
                continue
            if datasetname not in snapshots:
                snapshots[datasetname] = OrderedDict()
            snapshots[datasetname].update({snapshot:{'name': snapshotname, 'creation': creation}})
        return snapshots

    @staticmethod
    def get_datasets(endpoint=''):
        """
        Retreives all datasets
        """
        if endpoint == '':
            command = 'zfs list -H'
        else
            command = "{0} 'zfs list -H'"
        output = Helper.run_command(command.format(endpoint), '/')
        datasets = []
        for line in filter(len, output.split('\n')):
            parts = list(filter(len, line.split('\t')))
            datasets.append(parts[0])
        return datasets

    @staticmethod
    def snapshot(dataset, name, endpoint=''):
        """
        Takes a snapshot
        """
        if endpoint == '':
            command = 'zfs snapshot {0}@{1}'.format(dataset, name)
        else:
            command = "{0} 'zfs snapshot {1}@{2}'".format(endpoint, dataset, name)
        Helper.run_command(command, '/')

    @staticmethod
    def replicate(dataset, base_snapshot, last_snapshot, target, endpoint='', direction='push', compression=None):
        """
        Replicates a dataset towards a given endpoint/target (push)
        Replicates a dataset from a given endpoint to a local target (pull)
        """

        delta = ''
        if base_snapshot is not None:
            delta = '-i {0}@{1} '.format(dataset, base_snapshot)

        if compression is not None:
            compress = '| {0} -c'.format(compression)
            decompress = '| {0} -cd'.format(compression)
        else:
            compress = ''
            decompress = ''

        if endpoint == '':
            # We're replicating to a local target
            command = 'zfs send {0}{1}@{2} | zfs receive -F {3}'
            command = command.format(delta, dataset, last_snapshot, target)
            Helper.run_command(command, '/')
        else:
            if direction == 'push':
                # We're replicating to a remote server
                command = 'zfs send {0}{1}@{2} {3} | mbuffer -q -v 0 -s 128k -m 512M | {4} \'mbuffer -s 128k -m 512M {5} | zfs receive -F {6}\''
                command = command.format(delta, dataset, last_snapshot, compress, endpoint, decompress, target)
                Helper.run_command(command, '/')
            elif direction == 'pull':
                # We're pulling from a remote server
                command = '{4} \'zfs send {0}{1}@{2} {3} | mbuffer -q -v 0 -s 128k -m 512M\' | mbuffer -s 128k -m 512M {5} | zfs receive -F {6}'
                command = command.format(delta, dataset, last_snapshot, compress, endpoint, decompress, target)
                Helper.run_command(command, '/')

    @staticmethod
    def is_held(target, snapshot, endpoint=''):
        if endpoint == '':
            command = 'zfs holds {0}@{1}'.format(target, snapshot)
            return 'zsm' in Helper.run_command(command, '/')
        command = '{0} \'zfs holds {1}@{2}\''.format(endpoint, target, snapshot)
        return 'zsm' in Helper.run_command(command, '/')

    @staticmethod
    def hold(target, snapshot, endpoint=''):
        if endpoint == '':
            command = 'zfs hold zsm {0}@{1}'.format(target, snapshot)
            Helper.run_command(command, '/')
        else:
            command = '{0} \'zfs hold zsm {1}@{2}\''.format(endpoint, target, snapshot)
            Helper.run_command(command, '/')

    @staticmethod
    def release(target, snapshot, endpoint=''):
        if endpoint == '':
            command = 'zfs release zsm {0}@{1} || true'.format(target, snapshot)
            Helper.run_command(command, '/')
        else:
            command = '{0} \'zfs release zsm {1}@{2} || true\''.format(endpoint, target, snapshot)
            Helper.run_command(command, '/')

    @staticmethod
    def get_size(dataset, base_snapshot, last_snapshot, endpoint=''):
        """
        Executes a dry-run zfs send to calculate the size of the delta.
        """
        delta = ''
        if base_snapshot is not None:
            delta = '-i {0}@{1} '.format(dataset, base_snapshot)

        if endpoint == '':
            command = 'zfs send -nv {0}{1}@{2}'
            command = command.format(delta, dataset, last_snapshot)
        else:
            command = '{0} \'zfs send -nv {1}{2}@{3}\''
            command = command.format(endpoint, delta, dataset, last_snapshot)
        command = '{0} 2>&1 | grep \'total estimated size is\''.format(command)
        output = Helper.run_command(command, '/')
        size = output.strip().split(' ')[-1]
        if size[-1].isdigit():
            return '{0}B'.format(size)
        return '{0}iB'.format(size)

    @staticmethod
    def destroy(dataset, snapshot, endpoint=''):
        """
        Destroyes a dataset
        """
        if endpoint == '':
            command = 'zfs destroy {0}@{1}'.format(dataset, snapshot)
        else:
            command = "{0} 'zfs destroy {1}@{2}'".format(endpoint, dataset, snapshot)
        Helper.run_command(command, '/')
