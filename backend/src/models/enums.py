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


class Topic(enum.Enum):
    DCF = 'dcf'
    LBO = 'lbo' 
    MA = 'ma'
    ACCOUNTING = 'accounting'
    VALUATION = 'valuation'
    GENERAL = 'general'


class Difficulty(enum.Enum):
    EASY = 'easy'
    MEDIUM = 'medium'
    HARD = 'hard'


class SubscriptionPlan(enum.Enum):
    ANALYST = 'starter'
    ASSOCIATE = 'pro'
    MANAGING_DIRECTOR = 'elite'
