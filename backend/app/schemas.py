from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


Role = Literal["student", "recruiter", "admin"]


class RegisterRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=8, max_length=128)
    role: Role = "student"
    student_id: str | None = None
    name: str | None = Field(default=None, min_length=1, max_length=200)
    degree: str | None = Field(default=None, max_length=200)
    department: str | None = Field(default=None, max_length=200)
    year: int | None = Field(default=None, ge=1, le=10)
    skills: str | None = Field(default=None, max_length=500)


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=128)


class UserResponse(BaseModel):
    id: int
    email: str
    role: Role
    is_active: bool
    student_id: str | None
    created_at: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class TargetRoleRequest(BaseModel):
    target_role: str = Field(min_length=1, max_length=200)


class AssessmentAnswerRequest(BaseModel):
    question_id: str
    answer: str


class AssessmentSubmitRequest(BaseModel):
    answers: list[AssessmentAnswerRequest] = Field(min_length=1)


class ProgressRequest(BaseModel):
    skill_id: int
    resource_id: int | None = None
    status: Literal["not_started", "in_progress", "completed"]
    week_number: int = Field(ge=1)


class StudentProfileUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    experience: str | None = Field(default=None, max_length=500)
    certifications: str | None = Field(default=None, max_length=500)


class RecruiterJobRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=10000)
    location: str = Field(min_length=1, max_length=200)
    company_display_name: str = Field(min_length=1, max_length=200)
    required_skills: list[str] = Field(min_length=1)
    preferred_skills: list[str] = Field(default_factory=list)
    status: Literal["open", "closed", "draft"] = "draft"


class RecruiterJobUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, min_length=1, max_length=10000)
    location: str | None = Field(default=None, min_length=1, max_length=200)
    company_display_name: str | None = Field(default=None, min_length=1, max_length=200)
    required_skills: list[str] | None = Field(default=None, min_length=1)
    preferred_skills: list[str] | None = None
    status: Literal["open", "closed", "draft"] | None = None


class CourseOutlineRequest(BaseModel):
    skill_id: int
    course_title_preference: str | None = Field(default=None, max_length=200)
    target_audience: str | None = Field(default=None, max_length=300)
    duration: str | None = Field(default=None, max_length=100)


class TryItRequest(BaseModel):
    text: str = Field(min_length=1, max_length=12000)
    target_role: str | None = Field(default=None, min_length=1, max_length=200)