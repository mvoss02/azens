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
    # Values match the plan slugs used across the public API (CheckoutRequest
    # and the subscription response). SQLAlchemy's Enum column stores the
    # NAMES (ANALYST / ASSOCIATE / MANAGING_DIRECTOR) in Postgres, so changing
    # the values here does not require a DB migration — only the wire format
    # changes (Pydantic serializes enums to their value).
    ANALYST = 'analyst'
    ASSOCIATE = 'associate'
    MANAGING_DIRECTOR = 'managing_director'


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
