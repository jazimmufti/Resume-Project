import streamlit as st
import pandas as pd
import tempfile
import os
from io import BytesIO

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
    _redact
)


# -----------------------------------------
# Page configuration
# -----------------------------------------

st.set_page_config(
    page_title="Resume Screener",
    page_icon="📄",
    layout="wide"
)


# -----------------------------------------
# Title
# -----------------------------------------

st.title("📄 AI Resume Information Extractor")

st.write(
    "Upload multiple resumes and extract candidate information automatically."
)


# -----------------------------------------
# File uploader
# -----------------------------------------

uploaded_files = st.file_uploader(
    "Upload Resumes",
    type=["pdf", "docx"],
    accept_multiple_files=True
)


# -----------------------------------------
# Process button
# -----------------------------------------

if st.button("🚀 Process Resumes"):

    if not uploaded_files:

        st.warning(
            "Please upload at least one resume."
        )

    else:

        results = []

        progress_bar = st.progress(0)

        status = st.empty()


        from concurrent.futures import ThreadPoolExecutor, as_completed

        def process_resume(file_bytes, filename):
            try:
                resume_text = extract_text(file_bytes, filename=filename)

                if not resume_text or len(resume_text.strip()) < 50:
                    return None, f"Could not extract readable text from {filename}"

                email = extract_email(resume_text)
                phone = extract_phone(resume_text)

                email = email.strip().lower() if email else None
                phone = phone.strip() if phone else None

                candidate = extract_candidate_details(
                    resume_text,
                    filename=filename
                )

                if not candidate.get("full_name"):
                    python_name = extract_name(resume_text)
                    if python_name:
                        candidate["full_name"] = python_name

                experience_periods = candidate.get("experience_periods", [])
                candidate["total_experience"] = calculate_experience(experience_periods)
                candidate["relevant_experience"] = calculate_relevant_experience(experience_periods)
                candidate.pop("experience_periods", None)

                candidate["email"] = email
                candidate["phone"] = phone
                candidate["resume_file"] = filename

                return candidate, None

            except Exception as e:
                return None, f"Error processing {filename}: {_redact(str(e))}"

        # -----------------------------------------
        # Process resumes concurrently (up to 4 in parallel)
        # -----------------------------------------
        total_files = len(uploaded_files)
        completed_count = 0

        # Read buffers into memory
        file_payloads = [
            (f.getvalue(), f.name) for f in uploaded_files
        ]

        max_workers = min(total_files, 3)
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_name = {
                executor.submit(process_resume, b, name): name
                for b, name in file_payloads
            }

            for future in as_completed(future_to_name):
                file_name = future_to_name[future]
                completed_count += 1

                candidate_res, error_msg = future.result()

                if error_msg:
                    if "Could not extract" in error_msg:
                        st.warning(error_msg)
                    else:
                        st.error(error_msg)
                elif candidate_res:
                    results.append(candidate_res)

                status.write(
                    f"Processed: {file_name} ({completed_count}/{total_files})"
                )
                progress_bar.progress(completed_count / total_files)

        # -----------------------------------------
        # Processing completed
        # -----------------------------------------

        status.success(
            "All resumes processed!"
        )


        # -----------------------------------------
        # Create DataFrame
        # -----------------------------------------

        if results:

            df = pd.DataFrame(
                results
            )


            # -----------------------------------------
            # Reorder columns
            # -----------------------------------------

            columns = [
                "full_name",
                "phone",
                "email",
                "location",
                "highest_education",
                "total_experience",
                "relevant_experience",
                "resume_file"
            ]

            df = df[
                [
                    column
                    for column in columns
                    if column in df.columns
                ]
            ]


            # -----------------------------------------
            # Display results
            # -----------------------------------------

            st.subheader(
                "Candidate Details"
            )

            st.dataframe(
                df,
                width="stretch"
            )


            # -----------------------------------------
            # Create Excel file
            # -----------------------------------------

            excel_file = BytesIO()

            with pd.ExcelWriter(
                excel_file,
                engine="openpyxl"
            ) as writer:

                df.to_excel(
                    writer,
                    index=False,
                    sheet_name="Candidates"
                )


            # -----------------------------------------
            # Download Excel
            # -----------------------------------------

            st.download_button(
                label="📥 Download Excel",
                data=excel_file.getvalue(),
                file_name="candidate_data.xlsx",
                mime=(
                    "application/vnd.openxmlformats-"
                    "officedocument.spreadsheetml.sheet"
                )
            )


        else:

            st.warning(
                "No resumes could be processed successfully."
            )