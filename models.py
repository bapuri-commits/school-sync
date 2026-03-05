"""정규화 스키마 — 사이트별 raw 데이터를 통합하는 Pydantic 모델."""

from __future__ import annotations

import re
from datetime import date, datetime, time
from pydantic import BaseModel, computed_field


class Course(BaseModel):
    id: int
    name: str
    short_name: str
    professor: str
    url: str

    @staticmethod
    def make_short_name(raw_name: str) -> str:
        """'자료구조 - 2분반 [컴퓨터·AI학부] (1학기)' → '자료구조'"""
        name = re.sub(r'\s*-\s*\d+분반.*$', '', raw_name)
        name = re.sub(r'\s*\[.*?\]\s*', '', name)
        name = re.sub(r'\s*\(.*?학기\)\s*', '', name)
        return name.strip()


class CalendarEvent(BaseModel):
    id: int | None = None
    title: str
    course_name: str | None = None
    start_at: datetime
    end_at: datetime | None = None
    event_type: str
    url: str = ""
    source_site: str = "eclass"


class Deadline(BaseModel):
    title: str
    course_name: str | None = None
    due_at: datetime
    source: str                     # "calendar" | "assignment" | "notice"
    source_site: str = "eclass"
    url: str = ""

    @computed_field
    @property
    def d_day(self) -> int:
        delta = self.due_at.date() - date.today()
        return delta.days


class Assignment(BaseModel):
    course_name: str
    title: str
    activity_type: str              # "assign" | "quiz" | "ubboard" | ...
    deadline: datetime | None = None
    url: str = ""
    info: str = ""


class Notice(BaseModel):
    title: str
    board_name: str
    course_name: str
    author: str = ""
    date: str = ""
    url: str = ""
    category: str = ""              # 포탈 공지 카테고리 ("수업/성적", "등록" 등)
    source_site: str = "eclass"


class AttendanceRecord(BaseModel):
    course_name: str
    week: int
    date: str                       # "2026-03-04"
    period: str                     # "1교시"
    status: str                     # "출석" | "결석" | "지각" | "조퇴" | "유고결석" | "미기록"


class GradeItem(BaseModel):
    course_name: str
    category: str                   # "출석" | "중간고사" | "기말고사" | "과제" | ...
    item_name: str
    score: str = "-"
    weight: str = "-"
    range: str = ""
    feedback: str = ""


class TimetableEntry(BaseModel):
    course_name: str
    day_of_week: int                # 0=월 ~ 4=금
    start_time: time
    end_time: time
    location: str
    professor: str


class StudentProfile(BaseModel):
    student_id: str                 # "2023112470"
    name: str                       # "김세윤"
    name_en: str = ""               # "KIM SEYUN"
    department: str = ""            # "AI융합대학 AI소프트웨어융합학부 데이터사이언스전공"
    college: str = ""               # "AI융합대학"
    major: str = ""                 # "데이터사이언스전공"
    grade: int = 0                  # 4
    enrollment_status: str = ""     # "재학"
    admission_year: str = ""        # "2023"
    admission_type: str = ""        # "신입학"
    total_credits: str = ""         # "34"
    gpa: str = ""                   # "2.29"
    registered_semesters: str = ""  # "6/5/1"
    graduation_semesters: int = 0   # 8
    campus: str = ""                # "서울"
    email: str = ""
    phone: str = ""


class AcademicSchedule(BaseModel):
    title: str
    start_date: str                 # "2026-03-01"
    end_date: str = ""              # "2026-03-09" (범위가 있을 때)
    department: str = ""
    source_site: str = "portal"


class NormalizedOutput(BaseModel):
    """정규화 파이프라인의 최종 출력 컨테이너."""
    semester: str
    normalized_at: str
    courses: list[Course] = []
    deadlines: list[Deadline] = []
    assignments: list[Assignment] = []
    calendar: list[CalendarEvent] = []
    notices: list[Notice] = []
    attendance: list[AttendanceRecord] = []
    grades: list[GradeItem] = []
    academic_schedule: list[AcademicSchedule] = []
    student_profile: StudentProfile | None = None
