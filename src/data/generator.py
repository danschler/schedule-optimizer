"""Sample data generation for the schedule optimizer."""

from src.models import (
    Building,
    Course,
    Room,
    RoomType,
    ScheduleData,
    StudentGroup,
    Teacher,
)


def generate_sample_data() -> ScheduleData:
    """Generate a realistic sample dataset for schedule optimization."""

    # ── Buildings ──────────────────────────────────────────────────────
    buildings = [
        Building(
            id="b1", name="Main",
            travel_time_to={"b1": 0, "b2": 5, "b3": 10},
        ),
        Building(
            id="b2", name="Science",
            travel_time_to={"b1": 5, "b2": 0, "b3": 15},
        ),
        Building(
            id="b3", name="Arts",
            travel_time_to={"b1": 10, "b2": 15, "b3": 0},
        ),
    ]

    # ── Rooms ──────────────────────────────────────────────────────────
    rooms = [
        # Main building
        Room(id="r1",  name="LH-101",   building_id="b1", capacity=60,  room_type=RoomType.LECTURE_HALL),
        Room(id="r2",  name="LH-102",   building_id="b1", capacity=50,  room_type=RoomType.LECTURE_HALL),
        Room(id="r3",  name="LH-103",   building_id="b1", capacity=40,  room_type=RoomType.LECTURE_HALL),
        Room(id="r4",  name="SEM-101",  building_id="b1", capacity=20,  room_type=RoomType.SEMINAR),
        Room(id="r5",  name="SEM-102",  building_id="b1", capacity=20,  room_type=RoomType.SEMINAR),
        # Science building
        Room(id="r6",  name="LAB-201",  building_id="b2", capacity=40,  room_type=RoomType.LAB),
        Room(id="r7",  name="LAB-202",  building_id="b2", capacity=35,  room_type=RoomType.LAB),
        Room(id="r8",  name="LAB-203",  building_id="b2", capacity=40,  room_type=RoomType.LAB),
        Room(id="r9",  name="CLAB-201", building_id="b2", capacity=45,  room_type=RoomType.COMPUTER_LAB),
        # Arts building
        Room(id="r10", name="LH-301",   building_id="b3", capacity=50,  room_type=RoomType.LECTURE_HALL),
        Room(id="r11", name="LH-302",   building_id="b3", capacity=40,  room_type=RoomType.LECTURE_HALL),
        Room(id="r12", name="AUD-301",  building_id="b3", capacity=100, room_type=RoomType.AUDITORIUM),
    ]

    # ── Helpers for availability ───────────────────────────────────────
    all_periods = list(range(9))  # periods 0-8

    def full_time_availability() -> dict[int, list[int]]:
        return {d: list(all_periods) for d in range(5)}

    def part_time_availability(days: list[int]) -> dict[int, list[int]]:
        return {d: list(all_periods) for d in days}

    # ── Teachers ───────────────────────────────────────────────────────
    teachers = [
        # CS department (4 teachers, t2 and t4 part-time)
        Teacher(
            id="t1", name="Dr. Alice Chen", department="CS",
            subjects_can_teach=["programming", "algorithms", "databases"],
            availability=full_time_availability(),
            max_hours_week=20, max_hours_day=6,
            preferred_days_off=[4],  # Friday off
            preferred_time_slots=[0, 1, 2, 3],  # morning
        ),
        Teacher(
            id="t2", name="Dr. Bob Kumar", department="CS",
            subjects_can_teach=["programming", "networks", "databases"],
            availability=part_time_availability([0, 2, 4]),  # Mon, Wed, Fri
            max_hours_week=12, max_hours_day=4,
            preferred_time_slots=[0, 1, 2, 3],
        ),
        Teacher(
            id="t3", name="Dr. Carol Zhang", department="CS",
            subjects_can_teach=["algorithms", "networks", "programming"],
            availability=full_time_availability(),
            max_hours_week=20, max_hours_day=6,
            preferred_time_slots=[5, 6, 7, 8],  # afternoon
        ),
        Teacher(
            id="t4", name="Dr. Dan Rivera", department="CS",
            subjects_can_teach=["databases", "networks", "algorithms"],
            availability=part_time_availability([1, 3, 4]),  # Tue, Thu, Fri
            max_hours_week=12, max_hours_day=4,
        ),
        # Math department (4 teachers, t6 part-time)
        Teacher(
            id="t5", name="Dr. Eva Petrov", department="Math",
            subjects_can_teach=["calculus", "linear_algebra", "statistics"],
            availability=full_time_availability(),
            max_hours_week=20, max_hours_day=6,
            preferred_days_off=[4],
        ),
        Teacher(
            id="t6", name="Dr. Frank Osei", department="Math",
            subjects_can_teach=["calculus", "discrete_math", "statistics"],
            availability=part_time_availability([0, 1, 3]),  # Mon, Tue, Thu
            max_hours_week=12, max_hours_day=4,
            preferred_time_slots=[0, 1, 2, 3],
        ),
        Teacher(
            id="t7", name="Dr. Grace Tanaka", department="Math",
            subjects_can_teach=["linear_algebra", "discrete_math", "calculus"],
            availability=full_time_availability(),
            max_hours_week=20, max_hours_day=6,
        ),
        Teacher(
            id="t8", name="Dr. Hector Morales", department="Math",
            subjects_can_teach=["statistics", "linear_algebra", "discrete_math"],
            availability=full_time_availability(),
            max_hours_week=20, max_hours_day=6,
            preferred_time_slots=[0, 1, 2, 3],
        ),
        # Physics department (4 teachers, t10 part-time)
        Teacher(
            id="t9", name="Dr. Irene Volkov", department="Physics",
            subjects_can_teach=["mechanics", "electromagnetics", "thermodynamics"],
            availability=full_time_availability(),
            max_hours_week=20, max_hours_day=6,
            preferred_days_off=[4],
        ),
        Teacher(
            id="t10", name="Dr. James Park", department="Physics",
            subjects_can_teach=["mechanics", "optics", "thermodynamics"],
            availability=part_time_availability([0, 2, 3]),  # Mon, Wed, Thu
            max_hours_week=12, max_hours_day=4,
        ),
        Teacher(
            id="t11", name="Dr. Kira Johansson", department="Physics",
            subjects_can_teach=["electromagnetics", "optics", "mechanics"],
            availability=full_time_availability(),
            max_hours_week=20, max_hours_day=6,
        ),
        Teacher(
            id="t12", name="Dr. Leo Nguyen", department="Physics",
            subjects_can_teach=["thermodynamics", "optics", "electromagnetics"],
            availability=full_time_availability(),
            max_hours_week=20, max_hours_day=6,
            preferred_time_slots=[5, 6, 7, 8],
        ),
        # Languages department (3 teachers, t14 part-time)
        Teacher(
            id="t13", name="Dr. Maria Santos", department="Languages",
            subjects_can_teach=["english", "academic_writing", "communication"],
            availability=full_time_availability(),
            max_hours_week=20, max_hours_day=6,
            preferred_days_off=[4],
        ),
        Teacher(
            id="t14", name="Dr. Nils Eriksson", department="Languages",
            subjects_can_teach=["english", "communication"],
            availability=part_time_availability([1, 2, 4]),  # Tue, Wed, Fri
            max_hours_week=12, max_hours_day=4,
            preferred_time_slots=[0, 1, 2, 3],
        ),
        Teacher(
            id="t15", name="Dr. Olivia Brown", department="Languages",
            subjects_can_teach=["academic_writing", "communication", "english"],
            availability=full_time_availability(),
            max_hours_week=20, max_hours_day=6,
        ),
    ]

    # ── Student Groups ─────────────────────────────────────────────────
    student_groups = [
        StudentGroup(id="sg1", name="CS-Y1",      size=40, required_course_ids=[]),
        StudentGroup(id="sg2", name="CS-Y2",      size=35, required_course_ids=[]),
        StudentGroup(id="sg3", name="Math-Y1",    size=30, required_course_ids=[]),
        StudentGroup(id="sg4", name="Math-Y2",    size=25, required_course_ids=[]),
        StudentGroup(id="sg5", name="Physics-Y1", size=35, required_course_ids=[]),
        StudentGroup(id="sg6", name="Physics-Y2", size=30, required_course_ids=[]),
        StudentGroup(id="sg7", name="Lang-Y1",    size=45, required_course_ids=[]),
        StudentGroup(id="sg8", name="Lang-Y2",    size=20, required_course_ids=[]),
    ]

    # ── Courses ────────────────────────────────────────────────────────
    courses = [
        # CS courses (8)
        Course(
            id="c1", name="Intro to Programming", subject="programming",
            department="CS", sessions_per_week=1, session_duration_slots=1,
            required_room_type=RoomType.LECTURE_HALL, student_group_id="sg1",
            eligible_teacher_ids=["t1", "t2", "t3"],
        ),
        Course(
            id="c2", name="Programming Lab", subject="programming",
            department="CS", sessions_per_week=1, session_duration_slots=2,
            required_room_type=RoomType.COMPUTER_LAB, student_group_id="sg1",
            eligible_teacher_ids=["t1", "t2"],
        ),
        Course(
            id="c3", name="Algorithms", subject="algorithms",
            department="CS", sessions_per_week=1, session_duration_slots=1,
            required_room_type=RoomType.LECTURE_HALL, student_group_id="sg2",
            eligible_teacher_ids=["t1", "t3", "t4"],
        ),
        Course(
            id="c4", name="Database Systems", subject="databases",
            department="CS", sessions_per_week=1, session_duration_slots=1,
            required_room_type=RoomType.LECTURE_HALL, student_group_id="sg2",
            eligible_teacher_ids=["t1", "t2", "t4"],
        ),
        Course(
            id="c5", name="Database Lab", subject="databases",
            department="CS", sessions_per_week=1, session_duration_slots=2,
            required_room_type=RoomType.COMPUTER_LAB, student_group_id="sg2",
            eligible_teacher_ids=["t2", "t4"],
        ),
        Course(
            id="c6", name="Computer Networks", subject="networks",
            department="CS", sessions_per_week=1, session_duration_slots=1,
            required_room_type=RoomType.LECTURE_HALL, student_group_id="sg1",
            eligible_teacher_ids=["t2", "t3", "t4"],
        ),
        Course(
            id="c7", name="Networks Lab", subject="networks",
            department="CS", sessions_per_week=1, session_duration_slots=2,
            required_room_type=RoomType.COMPUTER_LAB, student_group_id="sg1",
            eligible_teacher_ids=["t3", "t4"],
        ),
        Course(
            id="c8", name="Advanced Algorithms", subject="algorithms",
            department="CS", sessions_per_week=1, session_duration_slots=1,
            required_room_type=RoomType.LECTURE_HALL, student_group_id="sg2",
            eligible_teacher_ids=["t1", "t3"],
            is_fixed=True, fixed_day=0, fixed_period=0,  # Monday 8:00
        ),
        # Math courses (8)
        Course(
            id="c9", name="Calculus I", subject="calculus",
            department="Math", sessions_per_week=1, session_duration_slots=1,
            required_room_type=RoomType.LECTURE_HALL, student_group_id="sg3",
            eligible_teacher_ids=["t5", "t6", "t7"],
        ),
        Course(
            id="c10", name="Calculus II", subject="calculus",
            department="Math", sessions_per_week=1, session_duration_slots=1,
            required_room_type=RoomType.LECTURE_HALL, student_group_id="sg4",
            eligible_teacher_ids=["t5", "t6"],
        ),
        Course(
            id="c11", name="Linear Algebra", subject="linear_algebra",
            department="Math", sessions_per_week=1, session_duration_slots=1,
            required_room_type=RoomType.LECTURE_HALL, student_group_id="sg3",
            eligible_teacher_ids=["t5", "t7", "t8"],
        ),
        Course(
            id="c12", name="Statistics", subject="statistics",
            department="Math", sessions_per_week=1, session_duration_slots=1,
            required_room_type=RoomType.LECTURE_HALL, student_group_id="sg4",
            eligible_teacher_ids=["t5", "t6", "t8"],
        ),
        Course(
            id="c13", name="Discrete Math", subject="discrete_math",
            department="Math", sessions_per_week=1, session_duration_slots=1,
            required_room_type=RoomType.LECTURE_HALL, student_group_id="sg3",
            eligible_teacher_ids=["t6", "t7", "t8"],
        ),
        Course(
            id="c14", name="Statistics Lab", subject="statistics",
            department="Math", sessions_per_week=1, session_duration_slots=2,
            required_room_type=RoomType.COMPUTER_LAB, student_group_id="sg4",
            eligible_teacher_ids=["t5", "t8"],
        ),
        Course(
            id="c15", name="Advanced Linear Algebra", subject="linear_algebra",
            department="Math", sessions_per_week=1, session_duration_slots=1,
            required_room_type=RoomType.LECTURE_HALL, student_group_id="sg4",
            eligible_teacher_ids=["t7", "t8"],
        ),
        Course(
            id="c16", name="Advanced Calculus", subject="calculus",
            department="Math", sessions_per_week=1, session_duration_slots=1,
            required_room_type=RoomType.LECTURE_HALL, student_group_id="sg4",
            eligible_teacher_ids=["t5", "t7"],
            is_fixed=True, fixed_day=1, fixed_period=2,  # Tuesday 10:00
        ),
        # Physics courses (7)
        Course(
            id="c17", name="Mechanics", subject="mechanics",
            department="Physics", sessions_per_week=1, session_duration_slots=1,
            required_room_type=RoomType.LECTURE_HALL, student_group_id="sg5",
            eligible_teacher_ids=["t9", "t10", "t11"],
        ),
        Course(
            id="c18", name="Mechanics Lab", subject="mechanics",
            department="Physics", sessions_per_week=1, session_duration_slots=2,
            required_room_type=RoomType.LAB, student_group_id="sg5",
            eligible_teacher_ids=["t9", "t10"],
        ),
        Course(
            id="c19", name="Electromagnetics", subject="electromagnetics",
            department="Physics", sessions_per_week=1, session_duration_slots=1,
            required_room_type=RoomType.LECTURE_HALL, student_group_id="sg6",
            eligible_teacher_ids=["t9", "t11", "t12"],
        ),
        Course(
            id="c20", name="Thermodynamics", subject="thermodynamics",
            department="Physics", sessions_per_week=1, session_duration_slots=1,
            required_room_type=RoomType.LECTURE_HALL, student_group_id="sg5",
            eligible_teacher_ids=["t9", "t10", "t12"],
        ),
        Course(
            id="c21", name="Optics", subject="optics",
            department="Physics", sessions_per_week=1, session_duration_slots=1,
            required_room_type=RoomType.LECTURE_HALL, student_group_id="sg6",
            eligible_teacher_ids=["t10", "t11", "t12"],
        ),
        Course(
            id="c22", name="Optics Lab", subject="optics",
            department="Physics", sessions_per_week=1, session_duration_slots=2,
            required_room_type=RoomType.LAB, student_group_id="sg6",
            eligible_teacher_ids=["t11", "t12"],
        ),
        Course(
            id="c23", name="Thermodynamics Lab", subject="thermodynamics",
            department="Physics", sessions_per_week=1, session_duration_slots=2,
            required_room_type=RoomType.LAB, student_group_id="sg6",
            eligible_teacher_ids=["t9", "t12"],
            is_fixed=True, fixed_day=3, fixed_period=5,  # Thursday 13:00
        ),
        # Languages courses (7)
        Course(
            id="c24", name="English Composition", subject="english",
            department="Languages", sessions_per_week=1, session_duration_slots=1,
            required_room_type=RoomType.LECTURE_HALL, student_group_id="sg7",
            eligible_teacher_ids=["t13", "t14", "t15"],
        ),
        Course(
            id="c25", name="Academic Writing", subject="academic_writing",
            department="Languages", sessions_per_week=1, session_duration_slots=1,
            required_room_type=RoomType.SEMINAR, student_group_id="sg8",
            eligible_teacher_ids=["t13", "t15"],
        ),
        Course(
            id="c26", name="Communication Skills", subject="communication",
            department="Languages", sessions_per_week=1, session_duration_slots=1,
            required_room_type=RoomType.LECTURE_HALL, student_group_id="sg7",
            eligible_teacher_ids=["t14", "t15"],
        ),
        Course(
            id="c27", name="Advanced English", subject="english",
            department="Languages", sessions_per_week=1, session_duration_slots=1,
            required_room_type=RoomType.LECTURE_HALL, student_group_id="sg8",
            eligible_teacher_ids=["t13", "t14"],
        ),
        Course(
            id="c28", name="Advanced Writing Workshop", subject="academic_writing",
            department="Languages", sessions_per_week=2, session_duration_slots=1,
            required_room_type=RoomType.SEMINAR, student_group_id="sg8",
            eligible_teacher_ids=["t13", "t15"],
        ),
        Course(
            id="c29", name="Public Speaking", subject="communication",
            department="Languages", sessions_per_week=1, session_duration_slots=1,
            required_room_type=RoomType.LECTURE_HALL, student_group_id="sg7",
            eligible_teacher_ids=["t14", "t15"],
        ),
        Course(
            id="c30", name="Business Communication", subject="communication",
            department="Languages", sessions_per_week=1, session_duration_slots=1,
            required_room_type=RoomType.SEMINAR, student_group_id="sg8",
            eligible_teacher_ids=["t13", "t14", "t15"],
        ),
    ]

    # ── Wire up required_course_ids on student groups ──────────────────
    group_courses: dict[str, list[str]] = {}
    for course in courses:
        group_courses.setdefault(course.student_group_id, []).append(course.id)
    for group in student_groups:
        group.required_course_ids = group_courses.get(group.id, [])

    return ScheduleData(
        teachers=teachers,
        courses=courses,
        rooms=rooms,
        buildings=buildings,
        student_groups=student_groups,
    )


if __name__ == "__main__":
    from src.data.loader import save_data

    data = generate_sample_data()
    save_data(data, "data/sample_data.json")
    print(
        f"Generated: {len(data.teachers)} teachers, "
        f"{len(data.courses)} courses, "
        f"{len(data.rooms)} rooms, "
        f"{len(data.student_groups)} groups"
    )
