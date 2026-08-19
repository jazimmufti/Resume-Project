import streamlit as st
import pandas as pd
import tempfile
import os
from io import BytesIO

from extractor import (
    extract_text,
    extract_email,
    extract_phone
)

from llm_extractor import (
    extract_candidate_details,
    calculate_experience,
    calculate_relevant_experience
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


        # -----------------------------------------
        # Process each resume
        # -----------------------------------------

        for i, uploaded_file in enumerate(uploaded_files):

            status.write(
                f"Processing: {uploaded_file.name}"
            )

            temp_path = None

            try:

                # -----------------------------------------
                # Save uploaded file temporarily
                # -----------------------------------------

                suffix = os.path.splitext(
                    uploaded_file.name
                )[1]

                with tempfile.NamedTemporaryFile(
                    delete=False,
                    suffix=suffix
                ) as temp_file:

                    temp_file.write(
                        uploaded_file.getbuffer()
                    )

                    temp_path = temp_file.name


                # -----------------------------------------
                # Extract resume text
                # -----------------------------------------

                resume_text = extract_text(
                    temp_path
                )


                # -----------------------------------------
                # Check extracted text
                # -----------------------------------------

                if not resume_text or len(
                    resume_text.strip()
                ) < 50:

                    st.warning(
                        f"Could not extract readable text "
                        f"from {uploaded_file.name}"
                    )

                    continue


                # -----------------------------------------
                # Extract email and phone using Python
                # -----------------------------------------

                email = extract_email(
                    resume_text
                )

                phone = extract_phone(
                    resume_text )


                # -----------------------------------------
                # Clean extracted contact information
                # -----------------------------------------

                if email:

                    email = email.strip().lower()

                else:

                    email = None


                if phone:

                    phone = phone.strip()

                else:

                    phone = None


                # -----------------------------------------
                # Extract candidate information using Gemini
                # -----------------------------------------

                candidate = extract_candidate_details(
                    resume_text
                )


                # -----------------------------------------
                # Get experience periods
                # -----------------------------------------

                experience_periods = candidate.get(
                    "experience_periods",
                    []
                )


                # -----------------------------------------
                # Calculate total experience
                # -----------------------------------------

                candidate["total_experience"] = (
                    calculate_experience(
                        experience_periods
                    )
                )


                # -----------------------------------------
                # Calculate relevant experience
                # -----------------------------------------

                candidate["relevant_experience"] = (
                    calculate_relevant_experience(
                        experience_periods
                    )
                )


                # -----------------------------------------
                # Remove intermediate Gemini field
                # -----------------------------------------

                candidate.pop(
                    "experience_periods",
                    None
                )


                # -----------------------------------------
                # Add Python extracted fields
                # -----------------------------------------

                candidate["email"] = email

                candidate["phone"] = phone

                candidate["resume_file"] = (
                    uploaded_file.name
                )


                # -----------------------------------------
                # Add candidate to results
                # -----------------------------------------

                results.append(
                    candidate
                )


            except Exception as e:

                st.error(
                    f"Error processing "
                    f"{uploaded_file.name}: {e}"
                )


            finally:

                # -----------------------------------------
                # Delete temporary file
                # -----------------------------------------

                if temp_path and os.path.exists(
                    temp_path
                ):

                    os.remove(temp_path)


            # -----------------------------------------
            # Update progress
            # -----------------------------------------

            progress_bar.progress(
                (i + 1) / len(uploaded_files)
            )


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
                "email",
                "phone",
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