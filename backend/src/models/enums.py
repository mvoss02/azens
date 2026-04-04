import enum


class SeniorityLevel(enum.Enum):
    INTERN = 'intern'
    ANALYST = 'analyst'
    ASSOCIATE = 'associate'
    VPANDABOVE = 'vp+'

class Language(enum.Enum):
    DE = 'german'
    ES = 'spanish'
    EN = 'english'
    IT = 'italian'
    NL = 'dutch'
