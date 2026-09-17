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
    calculate_no_of_companies
)

# =========================================================
# RESUME
# =========================================================

file_path = "resumes/Mufti Jazim.pdf"
target_role = "Software Engineer"


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
# LLAMA EXTRACTION
# =========================================================

print(f"Extracting candidate details with target role: '{target_role}'...")
candidate = extract_candidate_details(
    resume_text,
    filename=file_path,
    target_role=target_role
)


# =========================================================
# NAME FALLBACK
# =========================================================

if not candidate.get("full_name"):

    candidate["full_name"] = python_name


# =========================================================
# EXPERIENCE & COMPANIES
# =========================================================

experience_periods = candidate.get(
    "experience_periods",
    []
)

companies_list = candidate.get(
    "companies",
    []
)

print("\n========== EXPERIENCE PERIODS ==========\n")
print(
    json.dumps(
        experience_periods,
        indent=4
    )
)

print("\n========== COMPANIES EXTRACTED ==========\n")
print(companies_list)

total_experience = calculate_experience(
    experience_periods
)

relevant_experience = calculate_relevant_experience(
    experience_periods
)

no_of_companies = calculate_no_of_companies(
    experience_periods,
    companies_list
)


# =========================================================
# REMOVE INTERMEDIATE FIELDS
# =========================================================

candidate.pop(
    "experience_periods",
    None
)
candidate.pop(
    "companies",
    None
)


# =========================================================
# FINAL FIELDS
# =========================================================

candidate["total_experience"] = total_experience
candidate["relevant_experience"] = relevant_experience
candidate["no_of_companies"] = no_of_companies
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