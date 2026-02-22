from dataclasses import dataclass


@dataclass
class Partition:
    Bootable: bool
    Dev: str
    FSType: str
    Id: int
    Label: str
    Size: str

@dataclass
class OS:
    Append: str
    Autostart: bool
    AutostartTimeout: int
    BaseImage: str
    Boot: str
    DefaultAction: str
    Description: str
    Hidden: bool
    IconName: str
    Initrd: str
    Kernel: str
    NewEnabled: bool
    Root: str
    StartEnabled: bool
    SyncEnabled: bool
    Version: str

@dataclass
class Linbo:
    AutoFormat: bool
    AutoInitCache: bool
    AutoPartition: bool
    Cache: str
    DownloadType: str
    Group: str
    GuiDisabled: bool
    KernelOptions: str
    Locale: str
    RootTimeout: int
    Server: str
    SystemType: str
    UseMinimalLayout: bool

@dataclass
class LinboConfig:
    LINBO: Linbo
    Partitions: list
    OS: list