"""브리핑 마크다운 생성 — 오늘 기준 요약 정보."""

from datetime import date, timedelta
from pathlib import Path

from config import OUTPUT_DIR
from models import NormalizedOutput

NORM_DIR = OUTPUT_DIR / "normalized"


def generate_briefing(output: NormalizedOutput) -> None:
    """오늘 기준 브리핑 마크다운을 생성한다."""
    today = date.today()
    lines = [f"# school_sync 브리핑 — {today}", ""]

    lines.append("## 마감 임박")
    upcoming = [d for d in output.deadlines if 0 <= d.d_day <= 7]
    if upcoming:
        lines.append("| 과목 | 과제 | D-day | 링크 |")
        lines.append("|------|------|-------|------|")
        for d in upcoming:
            lines.append(f"| {d.course_name or '-'} | {d.title} | D-{d.d_day} | [링크]({d.url}) |")
    else:
        lines.append("임박한 마감 없음")
    lines.append("")

    lines.append("## 진행 중인 학사일정")
    today_str = today.isoformat()
    active_schedule = []
    for s in output.academic_schedule:
        if s.end_date:
            if s.start_date <= today_str <= s.end_date:
                active_schedule.append(s)
        elif s.start_date == today_str:
            active_schedule.append(s)
    if active_schedule:
        for s in active_schedule:
            period = f"{s.start_date} ~ {s.end_date}" if s.end_date else s.start_date
            lines.append(f"- {s.title} ({period})")
    else:
        lines.append("오늘 해당하는 학사일정 없음")
    lines.append("")

    lines.append("## 최근 공지 (48시간 이내)")
    recent_notices = [n for n in output.notices if n.date and n.date >= (today - timedelta(days=2)).isoformat()]
    if recent_notices:
        for n in recent_notices[:15]:
            source = {"eclass": "eclass", "portal": "포탈", "department": "학과"}.get(n.source_site, n.source_site)
            prefix = f"[{source}/{n.category}]" if n.category else f"[{source}]"
            lines.append(f"- {prefix} {n.title} ({n.date})")
    else:
        lines.append("최근 공지 없음")
    lines.append("")

    lines.append("## 출석 주의")
    absences = [a for a in output.attendance if a.status == "결석"]
    if absences:
        for a in absences:
            lines.append(f"- {a.course_name} {a.week}주차 {a.period} ({a.date}): **결석**")
    else:
        lines.append("결석 기록 없음")
    lines.append("")

    if output.student_profile:
        p = output.student_profile
        lines.append("## 프로필")
        lines.append(f"- {p.name} | {p.department}")
        lines.append(f"- {p.grade}학년 | 평점 {p.gpa} | 이수 {p.total_credits}학점 / 졸업소요 {p.graduation_semesters}학기")
        lines.append("")

    briefing_path = NORM_DIR / "briefing.md"
    briefing_path.write_text("\n".join(lines), encoding="utf-8")


def print_summary(output: NormalizedOutput) -> None:
    """정규화 결과 요약을 콘솔에 출력한다."""
    print(f"\n{'='*60}")
    print(f"  정규화 완료 — {output.semester}")
    print(f"{'='*60}")
    print(f"  과목: {len(output.courses)}개")
    print(f"  강의계획서: {len(output.syllabus)}개")
    print(f"  마감: {len(output.deadlines)}개 (D-day 기준 정렬)")
    if output.deadlines:
        upcoming = [d for d in output.deadlines if d.d_day >= 0]
        if upcoming:
            nearest = upcoming[0]
            print(f"    → 가장 가까운: [{nearest.course_name}] {nearest.title} (D-{nearest.d_day})")
    print(f"  과제/활동: {len(output.assignments)}개")
    print(f"  캘린더: {len(output.calendar)}개")
    print(f"  공지: {len(output.notices)}개")
    print(f"  출석: {len(output.attendance)}개 기록")
    print(f"  성적: {len(output.grades)}개 항목")
    print(f"  학사일정: {len(output.academic_schedule)}개")
    if output.student_profile:
        p = output.student_profile
        print(f"  프로필: {p.name} | {p.major} {p.grade}학년 | 평점 {p.gpa} | {p.total_credits}학점")
    print(f"  출력: {NORM_DIR}/")
    print(f"{'='*60}")
