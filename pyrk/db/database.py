# Licensed under a 3-clause BSD style license - see LICENSE
import tables as tb
import descriptions as desc

import contextlib
import sys


@contextlib.contextmanager
def nostderr():
    """This context manager catches standard error output.
    It is used mostly to catch the unnecessary fileclosed warnings from
    pytables.
    """
    savestderr = sys.stderr

    class Devnull(object):
        def write(self, _): pass

        def flush(self): pass

    sys.stderr = Devnull()
    try:
        yield
    finally:
        sys.stderr = savestderr


class Database(object):
    """The Database class handles operations on the pyrk simulation backend and
    provides utilities for interacting with it.
    """

    def __init__(self, filepath='pyrk.h5',
                 mode='w',
                 title='PyRKDatabase'
                 ):
        """Creates an hdf5 database for simulation information

        :param filepath: the location of the h5 file. e.g. 'pyrk.h5'
        :type filepath: str
        :param mode: mode for file opening
        :type mode: str (a, w, and r are supported)
        :param title: The title of the database
        :type title: str
        """
        self.recorders = []
        self.tablehandles = {}
        self.mode = mode
        self.title = title
        self.filepath = filepath
        self.h5file = tb.File(filename=self.filepath,
                              title=self.title,
                              mode=self.mode)
        self.groups = self.set_up_groups()
        self.tables = self.set_up_tables()
        self.make_groups()
        self.make_tables()

    def add_group(self, groupname, grouptitle, path_to_group='/'):
        """Creates a new group in the file

        :param groupname: name of the group to add
        :type groupname: str
        :param grouptitle: metadata to store in plain english, a title
        :type grouptitle: str
        :param path_to_group: the database path, starts with '/'
        :type path_to_group: str
        """
        self.open_db()
        group = self.group_exists(path_to_group, groupname)
        if group is False:
            group = self.h5file.create_group(path_to_group, groupname,
                                             grouptitle)
        return group

    def add_table(self, groupname, tablename, description, tabletitle):
        """Creates a new table
        All groupnames must be directly under root

        :param groupname: name of the group to add
        :type groupname: str
        :param tablename: name of the table to add
        :type tablename: str
        :param description: metadata for the table
        :type : str
        :param tabletitle: metadata to store in plain english, a title
        :type tabletitle: str
        """
        self.open_db()
        p = self.get_tablepath(groupname, tablename)
        self.tablehandles[p] = self.h5file.create_table('/'+groupname,
                                                        tablename,
                                                        description,
                                                        tabletitle)
        return self.tablehandles[p]

    def add_row(self, table, row_dict):
        """Adds a row to the table

        :param table: handle to the table where the row will reside
        :type tablename: pytables Table object
        :param row_dict: metadata to store in plain english, a title
        :type row_dict: dictionary of row keys and values
        """
        self.open_db()
        for k, v in row_dict.iteritems():
            table.row[k] = v
        table.row.append()
        table.flush()

    def group_exists(self, path_to_group, groupname):
        self.open_db()
        try:
            group = self.h5file.get_node(path_to_group,
                                         name=groupname)
        except tb.NoSuchNodeError:
            group = False
        return group

    def open_db(self):
        """Returns a handle to the open db"""
        # if it is not open, open it.
        if self.h5file.isopen is True:
            return self.h5file
        else:
            self.h5file = tb.open_file(filename=self.filepath, mode='a')
            assert(self.h5file.isopen)
        return self.h5file

    def close_db(self):
        with nostderr():
            tb.file._open_files.close_all()

    def record_all(self):
        for i in self.recorders:
            t = i[0]
            r = i[1]
            self.add_row(t, r())

    def delete_db(self):
        """If the database exists, delete it"""
        import os.path
        os.remove(self.filepath)

    def make_groups(self):
        for g in self.groups:
            self.add_group(groupname=g['groupname'],
                           grouptitle=g['grouptitle'],
                           path_to_group=g['path'])

    def make_tables(self):
        for t in self.tables:
            self.add_table(groupname=t['groupname'],
                           tablename=t['tablename'],
                           description=t['description'],
                           tabletitle=t['tabletitle'])

    def set_up_groups(self):
        groups = []
        groups.append({'groupname': 'th',
                       'grouptitle': 'TH',
                       'path': '/'})
        groups.append({'groupname': 'neutronics',
                       'grouptitle': 'Neutronics',
                       'path': '/'})
        groups.append({'groupname': 'metadata',
                       'grouptitle': 'Simulation Metadata',
                       'path': '/'})
        return groups

    def set_up_tables(self):
        tables = []
        tables.append({'groupname': 'metadata',
                       'tablename': 'sim_info',
                       'description': desc.SimInfoRow,
                       'tabletitle': 'Simulation Information'})
        tables.append({'groupname': 'metadata',
                       'tablename': 'sim_input',
                       'description': desc.SimInputRow,
                       'tabletitle': 'Simulation Input Data'})
        tables.append({'groupname': 'th',
                       'tablename': 'th_params',
                       'description': desc.ThMetadataRow,
                       'tabletitle': 'TH Component Parameters'})
        tables.append({'groupname': 'th',
                       'tablename': 'th_timeseries',
                       'description': desc.ThTimeseriesRow,
                       'tabletitle': 'TH Timeseries'})
        tables.append({'groupname': 'neutronics',
                       'tablename': 'neutronics_timeseries',
                       'description': desc.NeutronicsTimeseriesRow,
                       'tabletitle': 'Neutronics Timeseries'})
        tables.append({'groupname': 'neutronics',
                       'tablename': 'neutronics_params',
                       'description': desc.NeutronicsParamsRow,
                       'tabletitle': 'Neutronics Metadata'})
        tables.append({'groupname': 'neutronics',
                       'tablename': 'zetas',
                       'description': desc.ZetasTimestepRow,
                       'tabletitle': 'Neutron Precursor Concentrations'})
        tables.append({'groupname': 'neutronics',
                       'tablename': 'omegas',
                       'description': desc.OmegasTimestepRow,
                       'tabletitle': 'Decay Heat Fractions'})
        return tables

    def register_recorder(self, groupname, tablename, recorder,
                          timeseries=False):
        self.open_db()
        tab = self.get_table(groupname, tablename)
        if timeseries is False:
            self.add_row(tab, recorder())
        else:
            self.recorders.append((tab, recorder))

    def get_tablepath(self, grp, tbl):
        return '/'+grp+'/'+tbl

    def get_table(self, grp, tbl):
        self.open_db()
        p = self.get_tablepath(grp, tbl)
        try:
            return self.tablehandles[p]
        except KeyError:
            msg = "table path " + p + " not found among table handles."
            raise KeyError(msg)
