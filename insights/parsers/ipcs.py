"""
IPCS commands
=============

Shared parsers for parsing output of below commands:

* ``ipcs -m``
* ``ipcs -mp``
* ``ipcs -s``
* ``ipcs -s -i``

IpcsM - command ``ipcs -m``
---------------------------

IpcsMP - command ``ipcs -mp``
-----------------------------

IpcsS - command ``ipcs -s``
---------------------------

IpcsSI - command ``ipcs -s -i {semaphore ID}``
----------------------------------------------

"""
from .. import Parser, parser, get_active_lines, LegacyItemAccess
from . import parse_delimited_table
from insights.specs import Specs


class Ipcs(Parser, LegacyItemAccess):
    """
    Base class for parsing the output of `ipcs -[s|m|mp]` command.
    """
    def parse_content(self, content, key=None, head='key'):
        # heading_ignore is first line we _don't_ want to ignore...
        table = parse_delimited_table(content, heading_ignore=[head])
        data = map(lambda item: dict((k, v) for (k, v) in item.items()), table)
        self.data = {}
        if key is not None:
            for item in data:
                self.data[item.pop(key)] = item


@parser(Specs.ipcs_m)
class IpcsM(Ipcs):
    """
    Class for parsing the output of `ipcs -m` command.

    Typical output of the command is::

        ------ Shared Memory Segments --------
        key        shmid      owner      perms      bytes      nattch     status
        0x00000000 0          root       644        80         2
        0x00000000 32769      root       644        16384      2
        0x00000000 65538      root       644        280        2
        0x0113be8e 229379     root       600        1000       6

    Examples:
        >>> type(shm)
        ''
        >>> '229379' in shm
        True
        >>> shm['229379']
        {}
        >>> smm.get('65538')
        {}
    """

    def parse_content(self, context, key='shmid', head='key'):
        super(IpcsM, self).parse_content(context, key=key, head=head)


@parser(Specs.ipcs_mp)
class IpcsMP(Ipcs):
    """
    Class for parsing the output of `ipcs -mp` command.

    Typical output of the command is::

        ------ Shared Memory Creator/Last-op PIDs --------
        shmid      owner      cpid       lpid
        0          root       1377       1383
        32769      root       1377       1383
        65538      root       1377       1383
        229379     root       1518       1518

    Examples:
        >>> type(shm)
        ''
        >>> '229379' in shm
        True
        >>> shm['229379']
        {}
        >>> smm.get('65538')
        {}
    """

    def parse_content(self, context, key='shmid', head='shmid'):
        super(IpcsMP, self).parse_content(context, key=key, head=head)


@parser(Specs.ipcs_s)
class IpcsS(Ipcs):
    """
    Class for parsing the output of `ipcs -s` command.

    Typical output of the command is::

        ------ Semaphore Arrays --------
        key        semid      owner      perms      nsems
        0x00000000 557056     apache     600        1
        0x00000000 589825     apache     600        1
        0x00000000 131074     apache     600        1
        0x0052e2c1 163843     postgres   600        17
        0x0052e2c2 196612     postgres   600        17
        0x0052e2c3 229381     postgres   600        17
        0x0052e2c4 262150     postgres   600        17
        0x0052e2c5 294919     postgres   600        17
        0x0052e2c6 327688     postgres   600        17
        0x0052e2c7 360457     postgres   600        17
        0x00000000 622602     apache     600        1
        0x00000000 655371     apache     600        1
        0x00000000 688140     apache     600        1

    Examples:
        >>> type(sem)
        ''
        >>> '622602' in sem
        True
        >>> sem['622602']
        {'owner': 'apache', 'perms': '600', 'nsems': '1', 'key': '0x00000000'}
        >>> sem.get('262150')
        {'owner': 'postgres', 'perms': '600', 'nsems': '1', 'key': '0x00000000'}
    """

    def parse_content(self, context, key='semid', head='key'):
        super(IpcsS, self).parse_content(context, key=key, head=head)


@parser(Specs.ipcs_s_i)
class IpcsSI(Parser):
    """
    Class for parsing the output of `ipcs -s -i ##` command. ``##`` will be
    replaced with specific semid

    Typical output of the command is::

        # ipcs -s -i 65536

        Semaphore Array semid=65536
        uid=500  gid=501     cuid=500    cgid=501
        mode=0600, access_perms=0600
        nsems = 8
        otime = Sun May 12 14:44:53 2013
        ctime = Wed May  8 22:12:15 2013
        semnum     value      ncount     zcount     pid
        0          1          0          0          0
        1          1          0          0          0
        0          1          0          0          6151
        3          1          0          0          2265
        4          1          0          0          0
        5          1          0          0          0
        0          0          7          0          6152
        7          1          0          0          4390

    Examples:
        >>> type(sem)
        ''
        >>> sem.semid
        '65536'
        >>> sem.pid_list
        ['0', '2265', '4390', '6151', '6152']

    """

    def parse_content(self, content):
        # parse the output of `ipcs -s -i ##` command
        pids = set()
        self._semid = None
        for line in get_active_lines(content):
            line = line.strip()
            if line.startswith('Semaphore'):
                self._semid = line.split('=')[-1]
            elif self._semid and line[0].isdigit():
                pids.add(line.split()[-1])
        self._pids = sorted(list(pids))

    @property
    def semid(self):
        """
        Return the semaphore ID.

        Returns:
            str: the semaphore ID.
        """
        return self._semid

    @property
    def pid_list(self):
        """
        Return the ID list of the processes which use this semaphore.

        Returns:
            [list]: the processes' ID list
        """
        return self._pids
