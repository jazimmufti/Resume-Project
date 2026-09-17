import os
import pandas as pd

from concurrent.futures import ThreadPoolExecutor, as_completed
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
    calculate_no_of_companies,
    _redact
)


RESUME_FOLDER = "resumes"


def process_file(filename, target_role="Customer Service"):
    file_path = os.path.join(RESUME_FOLDER, filename)
    print(f"Processing: {filename}")

    try:
        resume_text = extract_text(file_path)

        if not resume_text or len(resume_text.strip()) < 50:
            print(f"Could not extract readable text from {filename}")
            return None

        email = extract_email(resume_text)
        phone = extract_phone(resume_text)

        candidate = extract_candidate_details(
            resume_text,
            filename=filename,
            target_role=target_role
        )

        if not candidate.get("full_name"):
            python_name = extract_name(resume_text)
            if python_name:
                candidate["full_name"] = python_name

        experience_periods = candidate.get("experience_periods", [])
        companies_list = candidate.get("companies", [])
        candidate["total_experience"] = calculate_experience(experience_periods)
        candidate["relevant_experience"] = calculate_relevant_experience(experience_periods)
        candidate["no_of_companies"] = calculate_no_of_companies(experience_periods, companies_list)
        candidate.pop("experience_periods", None)
        candidate.pop("companies", None)

        candidate["phone"] = phone
        candidate["email"] = email
        candidate["resume_file"] = filename

        print(f"Successfully processed: {filename}")
        return candidate

    except Exception as e:
        print(f"Error processing {filename}: {_redact(str(e))}")
        return None


if __name__ == "__main__":
    target_role = input("Enter target hiring role (default: Customer Service): ").strip()
    if not target_role:
        target_role = "Customer Service"
    print(f"Evaluating relevant experience for role: '{target_role}'\n")

    results = []

    valid_files = [
        f for f in os.listdir(RESUME_FOLDER)
        if f.lower().endswith((".pdf", ".docx"))
    ]

    max_workers = min(len(valid_files), 3) if valid_files else 1
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_file = {
            executor.submit(process_file, f, target_role): f for f in valid_files
        }
        for future in as_completed(future_to_file):
            candidate_data = future.result()
            if candidate_data:
                results.append(candidate_data)


    # --------------------------------
    # Create DataFrame
    # --------------------------------

    df = pd.DataFrame(results)

    columns = [
        "full_name",
        "phone",
        "email",
        "location",
        "highest_education",
        "total_experience",
        "relevant_experience",
        "no_of_companies",
        "resume_file"
    ]

    df = df[[col for col in columns if col in df.columns]]


    # --------------------------------
    # Create output folder
    # --------------------------------

    os.makedirs(
        "output",
        exist_ok=True
    )


    # --------------------------------
    # Save CSV
    # --------------------------------

    df.to_csv(
        "output/candidate_data.csv",
        index=False
    )


    print("\nProcessing completed!")

    print(
        f"Total resumes processed: {len(results)}"
    )

    print(
        "CSV saved to: output/candidate_data.csv"
    )