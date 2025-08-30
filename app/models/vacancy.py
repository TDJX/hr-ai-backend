from sqlmodel import SQLModel, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum


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
    key_skills: Optional[str] = None
    employment_type: EmploymentType
    experience: Experience
    schedule: Schedule
    salary_from: Optional[int] = None
    salary_to: Optional[int] = None
    salary_currency: Optional[str] = Field(default="RUR", max_length=3)
    gross_salary: Optional[bool] = False
    company_name: str = Field(max_length=255)
    company_description: Optional[str] = None
    area_name: str = Field(max_length=255)
    metro_stations: Optional[str] = None
    address: Optional[str] = None
    professional_roles: Optional[str] = None
    contacts_name: Optional[str] = Field(max_length=255)
    contacts_email: Optional[str] = Field(max_length=255)
    contacts_phone: Optional[str] = Field(max_length=50)
    is_archived: bool = Field(default=False)
    premium: bool = Field(default=False)
    published_at: Optional[datetime] = Field(default_factory=datetime.utcnow)
    url: Optional[str] = None


class Vacancy(VacancyBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class VacancyCreate(VacancyBase):
    pass


class VacancyUpdate(SQLModel):
    title: Optional[str] = None
    description: Optional[str] = None
    key_skills: Optional[str] = None
    employment_type: Optional[EmploymentType] = None
    experience: Optional[Experience] = None
    schedule: Optional[Schedule] = None
    salary_from: Optional[int] = None
    salary_to: Optional[int] = None
    salary_currency: Optional[str] = None
    gross_salary: Optional[bool] = None
    company_name: Optional[str] = None
    company_description: Optional[str] = None
    area_name: Optional[str] = None
    metro_stations: Optional[str] = None
    address: Optional[str] = None
    professional_roles: Optional[str] = None
    contacts_name: Optional[str] = None
    contacts_email: Optional[str] = None
    contacts_phone: Optional[str] = None
    is_archived: Optional[bool] = None
    premium: Optional[bool] = None
    published_at: Optional[datetime] = None
    url: Optional[str] = None


class VacancyRead(VacancyBase):
    id: int
    created_at: datetime
    updated_at: datetime