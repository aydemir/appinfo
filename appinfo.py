#!/usr/bin/python
# -*- coding: utf-8 -*-
#
# Copyright (C) 2010, TUBITAK/UEKAE
#
# This program is free software; you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free
# Software Foundation; either version 2 of the License, or (at your option)
# any later version.
#
# Please read the COPYING file.
#

# Python Libs
import os
import math
import sqlite3

# AppInfo Libs
import config
import backends
import database

class AppInfo(object):
    """ AppInfo
        -------
        Package Management System indepented, package metadata
        information management system.

        Notes:
        ------
        - All methods returns a tuple which contains state of operation and
          state message (Boolean, Unicode)
        - Whole DB is built on sqlite3
        - Default database scheme described in database.py

    """

    def __getattribute__(self, name):
        if object.__getattribute__(self, '_sq') or \
                name in ('createDB', 'initializeDB'):
            return object.__getattribute__(self, name)
        return lambda:(False, 'Initialize a DB first')

    def __init__(self, pm):
        """ Initialize with given PMS (Package Management System) """

        if not pm in backends.known_pms:
            raise Exception('Selected PMS (%s) is not available yet.' % pm)

        self.config = config.Config()
        self._pm = backends.known_pms[pm]()
        self._sq = None
        self._db = None

    def initializeDB(self, db='appinfo.db'):
        """ Initialize given database """

        if os.path.exists(db):
            self._sq = sqlite3.connect(db)
            self._db = db
            return (True, 'DB Initialized sucessfuly.')

        self._sq = None

        return (False, 'No such DB (%s).' % db)

    def getPackagesFromDB(self, fields = '*', condition = ''):
        """ Internal method to get package list from database """

        if condition:
            condition = ' WHERE %s' % condition

        return self._sq.execute('SELECT %s FROM %s%s' % (fields, database.PKG_TABLE, condition)).fetchall()

    def commitDB(self):
        """ Commit changes to DB """

        self._sq.commit()

        if self.config.updateSignAfterEachCommit:
            os.system('md5sum %s' % self._db)

class AppInfoServer(AppInfo):
    """ AppInfoServer
        -------------
        Server-side operations for AppInfo

        Notes:
        ------
        - All methods returns a tuple which contains state of operation and
          state message (Boolean, Unicode)
        - Whole DB is built on sqlite3
        - Default database scheme described in database.py

    """

    def __init__(self, pm):
        AppInfo.__init__(self, pm)

    def createDB(self, db='appinfo.db', force=False):
        """ Create given database """

        if not force and os.path.exists(db):
            self.initializeDB(db)
            return (False, 'DB already exists.')

        if os.path.exists(db+'.backup'):
            os.unlink(db+'.backup')

        if os.path.exists(db):
            os.rename(db, db+'.backup')

        self._sq = sqlite3.connect(db)
        self._db = db
        self._sq.execute(database.DB_SCHEME)
        self.commitDB()

        return (True, 'DB created sucessfuly.')

    def updatePackageList(self):
        """ Merge packages in database with packages in PMS """

        packages_from_pms = self._pm.getPackageList()
        packages_from_db = [str(x[1]) for x in self.getPackagesFromDB()]
        new_packages = list(set(packages_from_pms) - set(packages_from_db))

        for package in new_packages:
            self._sq.execute('INSERT INTO %s (name, score, nose) VALUES (?,0,0)' % database.PKG_TABLE, (package,) )

        self.commitDB()

        return (True, '%s package insterted.' % len(new_packages))

    def updatePackageScore(self, package, score):
        """ Update given packages score """

        # We accept 1-5
        score = min(5, max(score, 1))

        info = self.getPackagesFromDB(condition = "name = '%s'" % package)
        if info:
            self._sq.execute("UPDATE %s SET score = score + ? WHERE name = ?" % \
                    database.PKG_TABLE, (score, package,))
            self._sq.execute("UPDATE %s SET nose = nose + 1 WHERE name = ?" % \
                    database.PKG_TABLE, (package,))
            self.commitDB()

            return (True, self.getPackagesFromDB(condition = "name = '%s'" % package))
        return (False, 'Package %s does not exists' % package)

    def resetPackageScores(self, package = ''):
        """ Resets package scores
            WARNING ! If no package given it will resets all package scores """

        if package:
            package = " WHERE name = '%s'" % package

        self._sq.execute("UPDATE %s SET score = 0, nose = 0 %s" % (database.PKG_TABLE, package,))
        self.commitDB()

        return (True, 'All scores reset.')

class AppInfoClient(AppInfo):
    """ AppInfoClient
        -------------
        Client-side operations for AppInfo

        Notes:
        ------
        - Whole DB is built on sqlite3
        - Default database scheme described in database.py

    """

    def __init__(self, pm):
        AppInfo.__init__(self, pm)

    def getPackageScore(self, package):
        """ Returns given package calculated score:
            Where score = score / nose """

        info = self.getPackagesFromDB(condition = "name = '%s'" % package)
        if info:
            return int(math.ceil(float(max(1,info[0][2])) / float(max(1,info[0][3]))))
        return 1

    def getPackageId(self, package):
        """ Returns given package db id """

        info = self.getPackagesFromDB("id", condition = "name = '%s'" % package)
        if info:
            return info[0][0]

