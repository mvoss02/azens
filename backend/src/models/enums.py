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


class SessionType(enum.Enum):
    CV_SCREEN = 'cv_screen'
    KNOWLEDGE_DRILL = 'knowledge_drill'
    CASE_STUDY = 'case_study'


class SessionStatus(enum.Enum):
    PENDING = 'pending'  # room created, waiting for user to join
    ACTIVE = 'active'  # interview in progress
    COMPLETED = 'completed'  # interview finished normally
    ERROR = 'error'  # something went wrong


class FeedbackStatus(enum.Enum):
    PENDING = 'pending'
    GENERATED = 'generated'
    FAILED = 'failed'
    SKIPPED = 'skipped'


class SessionDuration(enum.Enum):
    SHORT = 15
    MEDIUM = 30
    LONG = 45
    EXTENDED = 60
    SUPERDAY = 90
