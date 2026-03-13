export interface Course {
  id: number;
  name: string;
  short_name: string;
  professor: string;
  url: string;
}

export interface Deadline {
  title: string;
  course_name: string | null;
  due_at: string;
  source: string;
  d_day: number;
  url: string;
}

export interface Notice {
  title: string;
  board_name: string;
  course_name: string;
  author: string;
  date: string;
  url: string;
  source_site: string;
}

export interface AttendanceRecord {
  course_name: string;
  week: number;
  date: string;
  period: string;
  status: string;
}

export interface GradeItem {
  course_name: string;
  category: string;
  item_name: string;
  score: string;
  weight: string;
  range: string;
}

export interface MaterialItem {
  filename: string;
  name: string;
  size_kb: number;
  downloaded_at: string;
}

export interface Syllabus {
  course_name: string;
  professor: string;
  email: string;
  classroom: string;
  overview: string;
  objectives: string;
  textbooks: { type: string; title: string }[];
  weekly_plan: { week: number; topic: string }[];
}

export interface CourseDetail extends Course {
  syllabus: Syllabus | null;
  grades: GradeItem[];
  attendance: AttendanceRecord[];
  notices: Notice[];
  assignments: { course_name: string; title: string; activity_type: string; url: string }[];
  deadlines: Deadline[];
  materials: MaterialItem[];
}

export type Permission = "dashboard" | "courses" | "grades" | "materials" | "notices" | "ask" | "sync";

export interface UserInfo {
  username: string;
  role: string;
  permissions: Permission[];
}

export interface DashboardData {
  today: string;
  weekday: string;
  today_classes: { course_name: string; schedule: string; room: string }[];
  upcoming_deadlines: Deadline[];
  recent_notices: Notice[];
  new_notice_courses: string[];
  last_run: { last_run: string; sites: string[] } | null;
}
