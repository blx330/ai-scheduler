from enum import Enum


class ParticipantRole(str, Enum):
    REQUIRED = "required"
    OPTIONAL = "optional"


class Weekday(str, Enum):
    MON = "MON"
    TUE = "TUE"
    WED = "WED"
    THU = "THU"
    FRI = "FRI"
    SAT = "SAT"
    SUN = "SUN"
