import json
import random

COURSES = 10
DAYS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
HOURS = ['9:00-10:00', '10:00-11:00', '11:00-12:00', '1:00-2:00', '2:00-3:00', '3:00-4:00']

def pick_random(days, hours):

    schedule = []
    for day in days:
        if random.random() <= 0.5:
            hour = random.choice(hours)
            schedule.append(f"{day} {hour}")
    return schedule


def generate_course_data():

    course_data = []

    for i in range(COURSES):

        course = {
            "id": i + 1,
            "name": f"Course {i + 1}",
            "schedule": pick_random(DAYS,HOURS)
        }
        course_data.append(course)

    with open('course_data.json', 'w') as f:
        json.dump(course_data, f, indent=4)


if __name__ == "__main__":
    generate_course_data()
