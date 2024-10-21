from .user import *
from .printer import *
from .managementgroup import *
from .project import *
from .device import *
from .schoolclass import *


DeviceWriter = LMNDeviceWriter()
MgmtGroupWriter = LMNMGMTGroupWriter()
PrinterWriter = LMNPrinterWriter()
ProjectWriter = LMNProjectWriter()
SchoolclassWriter = LMNSchoolclassWriter()
UserWriter  = LMNUserWriter()