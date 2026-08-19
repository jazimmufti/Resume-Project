import os
import pandas as pd

from extractor import (
    extract_text,
    extract_email,
    extract_phone
)

from llm_extractor import extract_candidate_details


RESUME_FOLDER = "resumes"

results = []


for filename in os.listdir(RESUME_FOLDER):

    if not filename.lower().endswith((".pdf", ".docx")):
        continue

    file_path = os.path.join(
        RESUME_FOLDER,
        filename
    )

    print(f"\nProcessing: {filename}")

    try:

        # --------------------------------
        # 1. Extract resume text
        # --------------------------------

        resume_text = extract_text(file_path)

        if not resume_text or len(resume_text.strip()) < 50:

            print(
                f"Could not extract readable text from {filename}"
            )

            continue


        # --------------------------------
        # 2. Python extracts email
        # --------------------------------

        email = extract_email(resume_text)


        # --------------------------------
        # 3. Python extracts phone
        # --------------------------------

        phone = extract_phone(resume_text)


        # --------------------------------
        # 4. Gemini extracts difficult fields
        # --------------------------------

        candidate = extract_candidate_details(
            resume_text
        )


        # --------------------------------
        # 5. Combine everything
        # --------------------------------

        candidate["email"] = email
        candidate["phone"] = phone
        candidate["resume_file"] = filename

        results.append(candidate)

        print("Successfully processed:", filename)
        print(candidate)


    except Exception as e:

        print(
            f"Error processing {filename}: {e}"
        )


# --------------------------------
# Create DataFrame
# --------------------------------

df = pd.DataFrame(results)


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