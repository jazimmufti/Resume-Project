import os
import json
from dotenv import load_dotenv
from google import genai
from datetime import datetime
import streamlit as st

load_dotenv()

try:
    api_key = st.secrets["GEMINI_API_KEY"]
except Exception:
    api_key = os.getenv("GEMINI_API_KEY")

client = genai.Client(api_key=api_key)


# =========================================================
# DATE PARSER
# =========================================================

def parse_date(date_string):

    if not date_string:
        return None

    date_string = str(
        date_string
    ).strip()

    formats = [
        "%m/%Y",
        "%Y",
        "%m/%d/%Y",
        "%d/%m/%Y",
        "%B %Y",
        "%b %Y"
    ]

    for fmt in formats:

        try:
            return datetime.strptime(
                date_string,
                fmt
            )

        except ValueError:
            continue

    return None


# =========================================================
# EDUCATION NORMALIZATION
# =========================================================

def normalize_education(education):

    if not education:
        return None

    if not isinstance(education, dict):
        return education

    qualification = education.get(
        "qualification"
    )

    if not qualification:
        return None

    qualification = str(
        qualification
    ).strip()

    status = str(
        education.get("status") or ""
    ).strip().lower()

    start_date = education.get(
        "start_date"
    )

    end_date = education.get(
        "end_date"
    )

    # -----------------------------------------------------
    # Explicit completed status
    # -----------------------------------------------------

    completed_statuses = {
        "completed",
        "complete",
        "graduated",
        "passed",
        "awarded"
    }

    if status in completed_statuses:

        return qualification


    # -----------------------------------------------------
    # Check education end date
    # -----------------------------------------------------

    parsed_end_date = parse_date(
        end_date
    )

    if parsed_end_date:

        current_date = datetime.now()

        # End date has already passed
        if parsed_end_date < current_date:

            return qualification

        # End date is today/future
        return f"{qualification} (pursuing)"


    # -----------------------------------------------------
    # Explicit pursuing status
    # -----------------------------------------------------

    pursuing_statuses = {
        "pursuing",
        "ongoing",
        "in progress",
        "currently studying",
        "current"
    }

    if status in pursuing_statuses:

        return f"{qualification} (pursuing)"


    # -----------------------------------------------------
    # Unknown status
    # -----------------------------------------------------

    # Do not incorrectly mark it as pursuing.
    return qualification


# =========================================================
# CANDIDATE EXTRACTION
# =========================================================

def extract_candidate_details(resume_text):

    current_year = datetime.now().year

    prompt = f"""
Extract candidate information from the resume and return ONLY
valid JSON.

The current date is {datetime.now().strftime("%d/%m/%Y")}.

FIELDS:

- full_name
- location
- highest_education
- experience_periods


=========================================================
FULL NAME
=========================================================

Extract the candidate's actual name.

Return null if it cannot be identified confidently.


# =========================================================
# LOCATION
# =========================================================

Extract the candidate's location from the resume.

Special city rules:

- If the candidate's own location/address explicitly mentions
  "Indore", return "Indore".
- If the candidate's own location/address explicitly mentions
  "Bhopal", return "Bhopal".

For ALL other cities, return only the state/UT.

Examples:

"Indore, Madhya Pradesh" → "Indore"
"Indore, MP" → "Indore"
"Patni Pura, Indore, MP" → "Indore"

"Bhopal, Madhya Pradesh" → "Bhopal"
"Bhopal, MP" → "Bhopal"

"Khargone, Madhya Pradesh" → "MP"
"Khargone, MP" → "MP"
"Gwalior, MP" → "MP"
"Jabalpur, Madhya Pradesh" → "MP"

"Madhya Pradesh" → "MP"
"MP" → "MP"

Use these state abbreviations:

Madhya Pradesh → MP
Uttar Pradesh → UP
Jammu and Kashmir → J&K
Uttarakhand → UK

Only use the candidate's own explicitly stated location/address.

Do NOT infer location from:

- college/university
- company
- school
- email
- phone number
- PIN code

Return null if no explicit candidate location is available.


# =========================================================
# HIGHEST EDUCATION
# =========================================================

Identify the candidate's highest educational qualification.

Return it as an object with:

- qualification
- status
- start_date
- end_date

IMPORTANT QUALIFICATION FORMAT RULES:

1. Preserve a standard qualification abbreviation when it is
   explicitly used in the resume.

Examples:

MA → MA
M.A. → MA
MBA → MBA
M.B.A. → MBA
MCA → MCA
M.C.A. → MCA
M.Com → M.Com
M.Com. → M.Com
M.Tech → M.Tech
M.Tech. → M.Tech
B.Tech → B.Tech
B.Tech. → B.Tech
B.Com → B.Com
BCA → BCA
B.Sc → B.Sc
B.A → B.A
M.Sc → M.Sc
Ph.D → Ph.D

2. Do NOT unnecessarily expand an abbreviation.

For example:

"MA" must NOT become "Master of Arts".

"MBA" must NOT become "Master of Business Administration".

"MCA" must NOT become "Master of Computer Applications".

3. If the resume gives the full qualification name instead of
an abbreviation, you may return the standard commonly used
abbreviation when it is unambiguous.

4. Do NOT invent or create non-standard abbreviations.

5. Do NOT change the qualification level.

6. If multiple qualifications exist, identify the highest-level
qualification.

7. Do not include "(pursuing)" in qualification itself.
Python will determine the final display value.

The status should describe what the resume explicitly indicates.

Possible status values include:

- completed
- pursuing
- ongoing
- in progress
- unknown

Extract education dates when present.

Do NOT invent dates.

If status cannot be determined, return "unknown".


=========================================================
EXPERIENCE PERIODS
=========================================================

Extract ALL professional employment periods.

For every job return:

- start
- end
- duration_months
- relevant

Use calendar dates when they are explicitly available.

Use MM/YYYY whenever possible.

Do NOT invent dates.


=========================================================
DURATION-BASED EXPERIENCE
=========================================================

If a job does not provide calendar dates but explicitly
states a duration, extract the duration as duration_months.

Examples of information that may indicate duration include
months or years of employment.

Convert explicit durations into months.

Examples:

6 months → 6

1 year → 12

1 year 6 months → 18

2 years 3 months → 27

Do not invent a duration when the resume does not provide one.


=========================================================
RELEVANT EXPERIENCE
=========================================================

"relevant": true ONLY when the employment is clearly
customer-facing.

Relevant roles include work involving:

- customer service
- customer support
- customer care
- call center
- client service
- customer-facing operations
- customer interaction
- closely related customer-facing responsibilities

Otherwise return false.

Do not infer customer-facing responsibilities merely
from a job title.


=========================================================
EXPERIENCE RESTRICTIONS
=========================================================

Include professional employment.

Do not include:

- education
- school
- college
- university
- projects
- certifications
- hobbies

Do not include internships unless explicitly described
as professional employment.

If a job has neither reliable dates nor an explicit
duration, exclude it.

Do not calculate total experience.


=========================================================
OUTPUT
=========================================================

Return ONLY valid JSON in exactly this structure:

{{
    "full_name": null,

    "location": null,

    "highest_education": {{
        "qualification": null,
        "status": null,
        "start_date": null,
        "end_date": null
    }},

    "experience_periods": []
}}


RESUME:

{resume_text}
"""

    response = client.models.generate_content(
        model="gemini-3.5-flash-lite",
        contents=prompt,
        config={
            "temperature": 0,
            "response_mime_type": "application/json"
        }
    )

    candidate = json.loads(
        response.text
    )

    # -----------------------------------------------------
    # Convert structured education into final string
    # -----------------------------------------------------

    education = candidate.get(
        "highest_education"
    )

    candidate["highest_education"] = normalize_education(
        education
    )

    return candidate


# =========================================================
# CALCULATE EXPERIENCE
# =========================================================

def calculate_experience(experience_periods):

    if not experience_periods:
        return None

    total_months = 0

    current_date = datetime.now()

    for period in experience_periods:

        if not isinstance(
            period,
            dict
        ):
            continue

        # -------------------------------------------------
        # Duration-based experience
        # -------------------------------------------------

        duration_months = period.get(
            "duration_months"
        )

        if duration_months is not None:

            try:

                duration_months = int(
                    duration_months
                )

                if duration_months > 0:

                    total_months += duration_months

                    continue

            except (
                ValueError,
                TypeError
            ):
                pass


        # -------------------------------------------------
        # Date-based experience
        # -------------------------------------------------

        start = period.get(
            "start"
        )

        end = period.get(
            "end"
        )

        start_date = parse_date(
            start
        )

        if not start_date:
            continue

        if not end:
            continue

        if str(end).strip().lower() == "present":

            end_date = current_date

        else:

            end_date = parse_date(
                end
            )

            if not end_date:
                continue

        months = (
            (end_date.year - start_date.year) * 12
            + (end_date.month - start_date.month)
            + 1
        )

        if months > 0:

            total_months += months


    if total_months == 0:
        return None

    years = total_months // 12
    months = total_months % 12

    if years == 0:
        return f"{months}m"

    if months == 0:
        return f"{years}y"

    return f"{years}.{months}y"


# =========================================================
# CALCULATE RELEVANT EXPERIENCE
# =========================================================

def calculate_relevant_experience(
    experience_periods
):

    if not experience_periods:
        return None

    relevant_periods = [
        period
        for period in experience_periods
        if (
            isinstance(period, dict)
            and period.get("relevant") is True
        )
    ]

    if not relevant_periods:
        return None

    return calculate_experience(
        relevant_periods
    )