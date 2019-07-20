"""
 ****************************************************************************
 Filename:          enclosure.py
 Description:       Base classes for monitoring & management targets
 Creation Date:     07/03/2019
 Author:            Chetan S. Deshmukh

 Do NOT modify or remove this copyright and confidentiality notice!
 Copyright (c) 2001 - $Date: 2015/01/14 $ Seagate Technology, LLC.
 The code contained herein is CONFIDENTIAL to Seagate Technology, LLC.
 Portions are also trade secret. Any use, duplication, derivation, distribution
 or disclosure of this code, for any reason, not expressly authorized is
 prohibited. All other rights are expressly reserved by Seagate Technology, LLC.
 ****************************************************************************
"""

import os
import sys
import errno
import threading

from framework.utils.config_reader import ConfigReader
from framework.utils.service_logging import logger

class StorageEnclosure(object):

    CONF_FILE = "/etc/sspl_ll.conf"

    ENCL_FAMILY = "enclosure-family"
    EES_ENCL = "Realstor 5U84"

    EXTENDED_INFO = "extended_info"

    # SSPL Data path
    SYSINFO = "SYSTEM_INFORMATION"
    DEFAULT_RAS_VOL = "/var/sspl/data/"

    # RAS FRU alert types
    FRU_MISSING = "missing"
    FRU_INSERTION = "insertion"
    FRU_FAULT = "fault"
    FRU_FAULT_RESOLVED = "resolved"

    fru_alerts = [FRU_MISSING, FRU_INSERTION, FRU_FAULT, FRU_FAULT_RESOLVED]

    # Management user & passwd
    user = ""
    passwd = ""

    encl = {}
    enclosures = {}
    memcache_frus = {}
    memcache_system = {}
    memcache_faults = {}

    # encl instance
    encl_inst = -1

    def __init__(self):

        #ECS Requirement - multiple enclosure cache
        self.encl_inst += 1
        #self.enclosures.update({self.encl_inst:self.encl})

        # Validate configuration file for required valid values
        try:
            self.conf_reader = ConfigReader(self.CONF_FILE)

        except (IOError, ConfigReader.Error) as err:
            logger.error("[ Error ] when validating the config file {0} - {1}"\
                 .format(self.CONF_FILE, err))

        self.vol_ras = self.conf_reader._get_value_with_default(\
            self.SYSINFO, "data_path", self.DEFAULT_RAS_VOL)

        self.encl_cache = self.vol_ras + "encl_" + str(self.encl_inst) + "/"
        self.frus = self.encl_cache + "frus/"

        self.encl.update({"frus":self.memcache_frus})
        self.encl.update({"system":self.memcache_system})

        self._check_ras_vol()

    def _check_ras_vol(self):
        """ Check for RAS volume """
        available = os.path.exists(self.vol_ras)

        if not available:
            logger.warn("Missing RAS volume, creating ...")

            try:
                orig_umask = os.umask(0)
                os.makedirs(self.vol_ras)
            except OSError as exc:
                if exc.errno == errno.EACCES:
                    logger.warn("Permission denied to create configured sspl"
                    " datapath {0}, defaulting to {1}".format(self.vol_ras,\
                    self.DEFAULT_RAS_VOL))

                    #Configured sspl data path creation failed
                    #defaulting data path to available default dir
                    self.vol_ras = self.DEFAULT_RAS_VOL

                elif exc.errno != errno.EEXIST:
                    logger.warn("%s creation failed, alerts may get missed on "
                    "sspl restart or failover!!" % (self.vol_ras))
            except Exception as err:
                logger.error("makedirs {0} failed with error {1}".format(
                    self.vol_ras, err))
            finally:
                os.umask(orig_umask)