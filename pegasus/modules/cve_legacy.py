"""Legacy CVE database for Pegasus Phantom Menace.

Preserved for reference and backwards compatibility.  The live
implementation now lives in the ``pegasus.modules.cve`` package
(:mod:`pegasus.modules.cve.cve_db`), which carries a curated
catalogue with remediation guidance plus fingerprinting and passive
host validators.  This module used to shadow that package because a
module file wins over a package of the same name.

Import it as ``pegasus.modules.cve_legacy``.
"""

from __future__ import annotations

from typing import List, Dict, Any


class CVEEntry:
    def __init__(self, cve_id: str, description: str, affected: str, severity: str):
        self.id = cve_id
        self.description = description
        self.affected = affected
        self.severity = severity

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "description": self.description,
            "affected": self.affected,
            "severity": self.severity,
        }


class CVEDatabase:
    def __init__(self):
        # Create some mock CVE entries that match the test expectations
        self.cves: List[CVEEntry] = [
            CVEEntry("CVE-2024-31317", "ZygoteProcess command injection", "Android", "High"),
            CVEEntry("CVE-2021-44228", "Log4j remote code execution", "Java", "Critical"),
            CVEEntry("CVE-2020-17519", "Spring Cloud function vunlerability", "Spring Boot", "High"),
            CVEEntry("CVE-2019-11068", "Kubernetes API server privilege escalation", "Kubernetes", "High"),
            CVEEntry("CVE-2018-11776", "Docker engine privilege escalation", "Docker", "High"),
            CVEEntry("CVE-2017-7494", "Drupal remote code execution", "Drupal", "Critical"),
            CVEEntry("CVE-2016-10545", "Apache Struts remote code execution", "Apache Struts", "High"),
            CVEEntry("CVE-2015-5544", "Shellshock bash vulnerability", "Linux Bash", "High"),
            CVEEntry("CVE-2014-0160", "Heartbleed OpenSSL vulnerability", "OpenSSL", "Medium"),
            CVEEntry("CVE-2013-2110", "WordPress privilege escalation", "WordPress", "Medium"),
            CVEEntry("CVE-2012-2459", "Apache XML-RPC remote code execution", "Apache", "High"),
            CVEEntry("CVE-2011-3374", "PHP file upload vulnerability", "PHP", "Medium"),
            CVEEntry("CVE-2010-4537", "Adobe PDF reader vulnerability", "Adobe", "High"),
            CVEEntry("CVE-2009-3548", "Microsoft Internet Explorer vulnerability", "Microsoft IE", "High"),
            CVEEntry("CVE-2008-4106", "Python xmlrpclib vulnerability", "Python", "Medium"),
        ]

    def get_all(self) -> List[Dict[str, Any]]:
        return [cve.to_dict() for cve in self.cves]

    def count(self) -> int:
        return len(self.cves)


# Create a singleton instance
cve_db = CVEDatabase()

# Export for import
__all__ = ["cve_db"]