from datetime import datetime
from enum import Enum

from sqlmodel import Field, SQLModel


class EmploymentType(str, Enum):
    FULL_TIME = "full"
    PART_TIME = "part"
    PROJECT = "project"
    VOLUNTEER = "volunteer"
    PROBATION = "probation"


class Experience(str, Enum):
    NO_EXPERIENCE = "noExperience"
    BETWEEN_1_AND_3 = "between1And3"
    BETWEEN_3_AND_6 = "between3And6"
    MORE_THAN_6 = "moreThan6"


class Schedule(str, Enum):
    FULL_DAY = "fullDay"
    SHIFT = "shift"
    FLEXIBLE = "flexible"
    REMOTE = "remote"
    FLY_IN_FLY_OUT = "flyInFlyOut"


class VacancyBase(SQLModel):
    title: str = Field(max_length=255)
    description: str
    key_skills: str | None = None
    employment_type: EmploymentType
    experience: Experience
    schedule: Schedule
    salary_from: int | None = None
    salary_to: int | None = None
    salary_currency: str | None = Field(default="RUR", max_length=3)
    gross_salary: bool | None = False
    company_name: str | None = Field(default=None, max_length=255)
    company_description: str | None = None
    area_name: str | None = Field(default=None, max_length=255)
    metro_stations: str | None = None
    address: str | None = None
    professional_roles: str | None = None
    contacts_name: str | None = Field(default=None, max_length=255)
    contacts_email: str | None = Field(default=None, max_length=255)
    contacts_phone: str | None = Field(default=None, max_length=50)
    is_archived: bool = Field(default=False)
    premium: bool = Field(default=False)
    published_at: datetime | None = Field(default_factory=datetime.utcnow)
    url: str | None = None


class Vacancy(VacancyBase, table=True):
    id: int | None = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class VacancyCreate(VacancyBase):
    pass


class VacancyUpdate(SQLModel):
    title: str | None = None
    description: str | None = None
    key_skills: str | None = None
    employment_type: EmploymentType | None = None
    experience: Experience | None = None
    schedule: Schedule | None = None
    salary_from: int | None = None
    salary_to: int | None = None
    salary_currency: str | None = None
    gross_salary: bool | None = None
    company_name: str | None = None
    company_description: str | None = None
    area_name: str | None = None
    metro_stations: str | None = None
    address: str | None = None
    professional_roles: str | None = None
    contacts_name: str | None = None
    contacts_email: str | None = None
    contacts_phone: str | None = None
    is_archived: bool | None = None
    premium: bool | None = None
    published_at: datetime | None = None
    url: str | None = None


class VacancyRead(VacancyBase):
    id: int
    created_at: datetime
    updated_at: datetime
