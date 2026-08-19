import json

from extractor import (
    extract_text,
    extract_email,
    extract_phone,
    extract_name
)

from llm_extractor import (
    extract_candidate_details,
    calculate_experience,
    calculate_relevant_experience,

)

# =========================================================
# RESUME
# =========================================================

file_path = "resumes/Mufti Jazim.pdf"


# =========================================================
# EXTRACT TEXT
# =========================================================

resume_text = extract_text(
    file_path
)



if not resume_text or len(
    resume_text.strip()
) < 50:

    print(
        "ERROR: Could not extract readable text "
        "from this resume."
    )

    exit()


# =========================================================
# PYTHON EXTRACTION
# =========================================================

email = extract_email(resume_text)

phone = extract_phone(
    resume_text
)

python_name = extract_name(
    resume_text
)


# =========================================================
# GEMINI EXTRACTION
# =========================================================

candidate = extract_candidate_details(
    resume_text
)


experience_periods = candidate.get(
    "experience_periods",
    []
)

print("\n========== EXPERIENCE PERIODS ==========\n")
print(experience_periods)
# =========================================================
# NAME FALLBACK
# =========================================================

if not candidate.get("full_name"):

    candidate["full_name"] = python_name


# =========================================================
# EXPERIENCE
# =========================================================

experience_periods = candidate.get(
    "experience_periods",
    []
)

print("\n========== EXPERIENCE PERIODS ==========\n")

print(
    json.dumps(
        experience_periods,
        indent=4
    )
)


total_experience = calculate_experience(
    experience_periods
)


relevant_experience = calculate_relevant_experience(
    experience_periods
)


# =========================================================
# REMOVE INTERMEDIATE FIELD
# =========================================================

candidate.pop(
    "experience_periods",
    None
)


# =========================================================
# FINAL FIELDS
# =========================================================

candidate["total_experience"] = (
    total_experience
)

candidate["relevant_experience"] = (
    relevant_experience
)

candidate["email"] = email

candidate["phone"] = phone


# =========================================================
# RESULT
# =========================================================

print(
    "\n========== FINAL RESULT ==========\n"
)

for key, value in candidate.items():

    print(
        f"{key}: {value}"
    )