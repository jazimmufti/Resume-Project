import os
import json
import time
import re
import threading
import logging
from dotenv import load_dotenv
from google import genai
from datetime import datetime
import streamlit as st

# Configure logger
logger = logging.getLogger("ResumeScreener.Gemini")
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(
        logging.Formatter("[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s")
    )
    logger.addHandler(handler)
logger.setLevel(logging.INFO)

load_dotenv()

# Get API key from local .env first
api_key = os.getenv("GEMINI_API_KEY")

# If running on Streamlit Cloud, try Streamlit secrets
if not api_key:
    try:
        api_key = st.secrets["GEMINI_API_KEY"]
    except (FileNotFoundError, KeyError):
        pass

if not api_key:
    raise ValueError("GEMINI_API_KEY is not configured.")

client = genai.Client(api_key=api_key)

# Concurrency and Rate Limiting Controls
_gemini_lock = threading.Lock()
_last_request_time = 0.0
_MIN_REQUEST_INTERVAL = 1.0  # 1.0s sequential pacing between requests

# Exponential backoff schedule: 5s, 10s, 20s, 40s, 60s
BACKOFF_DELAYS = [5, 10, 20, 40, 60]

# Primary and configured fallback models
PRIMARY_MODEL = "gemini-3.6-flash"
FALLBACK_MODEL = "gemini-3.5-flash-lite"


def _redact(msg: object) -> str:
    """Sanitize message to ensure API keys are never exposed in logs or UI."""
    if not msg:
        return ""
    text = str(msg)
    for k in (api_key, os.getenv("GEMINI_API_KEY"), os.getenv("MISTRAL_API_KEY")):
        if k and k in text:
            text = text.replace(k, "[REDACTED_API_KEY]")
    text = re.sub(r'AIza[0-9A-Za-z-_]{35}', '[REDACTED_API_KEY]', text)
    text = re.sub(r'AQ\.[0-9A-Za-z-_]{40,}', '[REDACTED_API_KEY]', text)
    return text


def is_retryable_error(error: Exception) -> bool:
    """
    Check whether an error is retryable.
    Retryable: 429 RESOURCE_EXHAUSTED / rate limit, 503 UNAVAILABLE / high demand.
    Non-retryable: 400 invalid argument, 401/403 authentication/permission, 404 not found.
    """
    code = getattr(error, "code", None)
    status = str(getattr(error, "status", "") or "").upper()
    msg = str(error).upper()

    # Explicit non-retryable errors
    if code in (400, 401, 403, 404):
        return False
    if any(term in status for term in ["INVALID_ARGUMENT", "PERMISSION_DENIED", "UNAUTHENTICATED", "NOT_FOUND"]):
        return False

    # Retryable errors
    if code in (429, 503):
        return True
    if "RESOURCE_EXHAUSTED" in status or "RESOURCE_EXHAUSTED" in msg:
        return True
    if "UNAVAILABLE" in status or "UNAVAILABLE" in msg:
        return True
    if "429" in msg or "503" in msg:
        return True

    return False


def get_retry_delay(error: Exception, default_delay: float) -> float:
    """
    Determine wait time, respecting any Retry-After header or RetryInfo
    returned by the API when available.
    """
    # 1. Check HTTP response headers for Retry-After
    response = getattr(error, "response", None)
    if response is not None and hasattr(response, "headers"):
        headers = response.headers
        ra = headers.get("retry-after") or headers.get("Retry-After")
        if ra:
            try:
                val = float(ra)
                if val > 0:
                    return max(val, default_delay)
            except (ValueError, TypeError):
                pass

    # 2. Check error.details for Google RPC RetryInfo
    details = getattr(error, "details", None)
    if isinstance(details, dict):
        err_body = details.get("error", details)
        if isinstance(err_body, dict):
            detail_items = err_body.get("details", [])
            if isinstance(detail_items, list):
                for item in detail_items:
                    if isinstance(item, dict) and "retryDelay" in item:
                        rd = str(item["retryDelay"])
                        if rd.endswith("s"):
                            rd = rd[:-1]
                        try:
                            val = float(rd)
                            if val > 0:
                                return max(val, default_delay)
                        except ValueError:
                            pass

    # 3. Check error text for regex match (e.g. 'retry after 12s')
    msg = str(error).lower()
    match = re.search(r"retry\s+after\s+(\d+(?:\.\d+)?)\s*s", msg)
    if match:
        try:
            return max(float(match.group(1)), default_delay)
        except ValueError:
            pass

    return default_delay


def get_error_type(error: Exception) -> str:
    """Format clear, readable error string with code and status."""
    code = getattr(error, "code", None)
    status = getattr(error, "status", None)
    type_name = type(error).__name__
    parts = [type_name]
    if code:
        parts.append(f"HTTP {code}")
    if status:
        parts.append(str(status))
    return " / ".join(parts)






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

def extract_candidate_details(resume_text, filename="Unknown"):

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

    global _last_request_time

    models_to_try = [PRIMARY_MODEL, FALLBACK_MODEL]
    max_retries = len(BACKOFF_DELAYS)

    for model_idx, model_name in enumerate(models_to_try):
        is_fallback = (model_idx > 0)
        if is_fallback:
            logger.warning(
                f"[Gemini Fallback] File: {filename} | Primary model {PRIMARY_MODEL} exhausted. "
                f"Attempting fallback model: {model_name}"
            )

        for attempt in range(1, max_retries + 2):  # 1 initial attempt + 5 retries
            # Concurrency control and pacing
            with _gemini_lock:
                now = time.time()
                elapsed = now - _last_request_time
                if elapsed < _MIN_REQUEST_INTERVAL:
                    time.sleep(_MIN_REQUEST_INTERVAL - elapsed)
                _last_request_time = time.time()

            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                    config={
                        "response_mime_type": "application/json"
                    }
                )

                candidate = json.loads(
                    response.text
                )

                # Convert structured education into final string
                education = candidate.get(
                    "highest_education"
                )

                candidate["highest_education"] = normalize_education(
                    education
                )

                return candidate

            except Exception as e:
                error_type_str = get_error_type(e)
                sanitized_err = _redact(e)

                if not is_retryable_error(e):
                    logger.error(
                        f"[Gemini Non-Retryable Error] File: {filename} | Model: {model_name} | "
                        f"Error: {error_type_str} | Details: {sanitized_err}"
                    )
                    return {
                        "full_name": None,
                        "location": None,
                        "highest_education": None,
                        "experience_periods": []
                    }

                if attempt <= max_retries:
                    base_delay = BACKOFF_DELAYS[attempt - 1]
                    delay = get_retry_delay(e, base_delay)
                    logger.warning(
                        f"[Gemini Retry] File: {filename} | Model: {model_name} | "
                        f"Attempt {attempt}/{max_retries} failed ({error_type_str}). "
                        f"Retrying in {delay:.1f}s... | Details: {sanitized_err}"
                    )
                    time.sleep(delay)
                else:
                    logger.warning(
                        f"[Gemini Retries Exhausted] File: {filename} | Model: {model_name} | "
                        f"All {max_retries} retries exhausted for this model."
                    )

    # If all models and retries exhausted, gracefully fail without crashing
    logger.error(
        f"[Gemini Final Failure] File: {filename} | All Gemini models and retries exhausted. "
        f"Gracefully continuing with partial extraction."
    )

    return {
        "full_name": None,
        "location": None,
        "highest_education": None,
        "experience_periods": []
    }


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