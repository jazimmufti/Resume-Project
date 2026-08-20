import pymupdf
import re
import phonenumbers
import pytesseract

from PIL import Image
from docx import Document


# =========================================================
# TESSERACT
# =========================================================

if os.name == "nt":
    pytesseract.pytesseract.tesseract_cmd = (
        r"C:\Program Files\Tesseract-OCR\tesseract.exe"
    )


# =========================================================
# NAME
# =========================================================

def extract_name(text):

    lines = [
        line.strip()
        for line in text.splitlines()
        if line.strip()
    ]

    headings = {
        "resume",
        "curriculum vitae",
        "cv",
        "profile",
        "about me",
        "personal details",
        "summary",
        "skills",
        "education",
        "experience",
        "work experience",
        "professional experience",
        "projects",
        "certifications",
        "contact",
        "objective",
        "languages",
        "references",
        "interest",
        "interests",
    }

    # Look at more lines because OCR can insert
    # unwanted lines before the actual name.
    for line in lines[:15]:

        clean_line = line.strip()

        if clean_line.lower() in headings:
            continue

        # Email
        if "@" in clean_line:
            continue

        # URLs
        if "linkedin" in clean_line.lower():
            continue

        if "http://" in clean_line.lower():
            continue

        if "www." in clean_line.lower():
            continue

        # Phone / numbers
        if re.search(r"\d", clean_line):
            continue

        # Too long to be a normal name
        if len(clean_line.split()) > 5:
            continue

        # Must contain letters
        if not re.search(r"[A-Za-z]", clean_line):
            continue

        words = clean_line.split()

        if 2 <= len(words) <= 5:

            bad_phrases = {
                "effective communication",
                "problem solving",
                "time management",
                "team collaboration",
                "leadership",
                "data analysis",
                "machine learning",
                "python developer",
                "computer operator",
                "data entry",
            }

            if clean_line.lower() in bad_phrases:
                continue

            return clean_line

    return None


# =========================================================
# PDF EXTRACTION
# =========================================================

def extract_pdf(file_path):

    text = ""

    document = pymupdf.open(file_path)

    for page_number, page in enumerate(document):

        # -----------------------------------------
        # Normal PDF text
        # -----------------------------------------

        page_text = page.get_text()

        text += page_text + "\n"


        # -----------------------------------------
        # PDF email links
        # -----------------------------------------

        links = page.get_links()

        for link in links:

            uri = link.get("uri", "")

            if uri.lower().startswith("mailto:"):

                email = uri[7:].split("?")[0]

                text += email + "\n"


        # -----------------------------------------
        # OCR
        # -----------------------------------------

        pix = page.get_pixmap(
            matrix=pymupdf.Matrix(3, 3),
            alpha=False
        )

        img = Image.frombytes(
            "RGB",
            [pix.width, pix.height],
            pix.samples
        )


        # OCR pass 1
        ocr_text = pytesseract.image_to_string(
            img,
            config="--psm 6"
        )

        text += "\n" + ocr_text


        # OCR pass 2
        ocr_text = pytesseract.image_to_string(
            img,
            config="--psm 11"
        )

        text += "\n" + ocr_text


        # OCR pass 3
        ocr_text = pytesseract.image_to_string(
            img,
            config=(
                "--psm 11 "
                "-c tessedit_char_whitelist="
                "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
                "abcdefghijklmnopqrstuvwxyz"
                "0123456789"
                "@._+-"
            )
        )

        text += "\n" + ocr_text


    document.close()

    return text


# =========================================================
# DOCX
# =========================================================

def extract_docx(file_path):

    document = Document(file_path)

    text = ""

    for paragraph in document.paragraphs:

        text += paragraph.text + "\n"

    return text


# =========================================================
# GENERAL TEXT EXTRACTION
# =========================================================

def extract_text(file_path):

    if file_path.lower().endswith(".pdf"):

        return extract_pdf(file_path)

    elif file_path.lower().endswith(".docx"):

        return extract_docx(file_path)

    return ""


# =========================================================
# EMAIL
# =========================================================
def extract_email(text):

    # -----------------------------------------
    # Remove invisible characters
    # -----------------------------------------

    text = re.sub(
        r'[\u200b-\u200f\uFEFF]',
        '',
        text
    )

    # -----------------------------------------
    # Process LINE BY LINE
    #
    # This prevents the regex from combining
    # text from different OCR lines.
    # -----------------------------------------

    lines = text.splitlines()

    candidates = []

    for line in lines:

        line = line.strip()

        if not line:
            continue

        # -------------------------------------
        # Normalize spaces around @ and .
        # -------------------------------------

        line = re.sub(
            r'\s*@\s*',
            '@',
            line
        )

        line = re.sub(
            r'\s*\.\s*',
            '.',
            line
        )

        # -------------------------------------
        # OCR domain corrections
        # -------------------------------------

        line = re.sub(
            r'\.corn\b',
            '.com',
            line,
            flags=re.IGNORECASE
        )

        line = re.sub(
            r'\.c0m\b',
            '.com',
            line,
            flags=re.IGNORECASE
        )

        line = re.sub(
            r'\.con\b',
            '.com',
            line,
            flags=re.IGNORECASE
        )

        # -------------------------------------
        # Extract normal email
        #
        # '?' is allowed here because OCR may
        # have replaced an unknown character.
        # -------------------------------------

        pattern = (
            r'[A-Za-z0-9._%+\-?]+'
            r'@'
            r'[A-Za-z0-9.-]+'
            r'\.'
            r'(?:com|in|org|net|co\.in)'
            r'\b'
        )

        matches = re.findall(
            pattern,
            line,
            flags=re.IGNORECASE
        )

        for match in matches:

            email = match.strip(
                ' .,;:'
            ).lower()

            if email not in candidates:

                candidates.append(email)


    # -----------------------------------------
    # Prefer a completely recognized email
    # -----------------------------------------

    clean_candidates = [
        email
        for email in candidates
        if '?' not in email
    ]

    if clean_candidates:

        return clean_candidates[0]


    # -----------------------------------------
    # If OCR only produced an ambiguous email,
    # return it rather than inventing a character.
    # -----------------------------------------

    if candidates:

        return candidates[0]


    return None


# =========================================================
# PHONE
# =========================================================

def extract_phone(text):

    # -----------------------------------------
    # Clean text
    # -----------------------------------------

    text = re.sub(
        r'[\u200b-\u200f\uFEFF]',
        '',
        text
    )


    # -----------------------------------------
    # First try phonenumbers
    # -----------------------------------------

    try:

        for match in phonenumbers.PhoneNumberMatcher(
            text,
            "IN"
        ):

            number = str(
                match.number.national_number
            )

            if len(number) == 10:

                return number

    except Exception:

        pass


    # -----------------------------------------
    # Normalize common OCR separators
    # -----------------------------------------

    text = text.replace(
        '-',
        ' '
    )

    text = text.replace(
        '.',
        ' '
    )


    # -----------------------------------------
    # Indian mobile number
    # -----------------------------------------

    matches = re.findall(
        r'(?<!\d)([6-9]\d{9})(?!\d)',
        text
    )

    if matches:

        return matches[0]


    # -----------------------------------------
    # Number split by spaces
    #
    # Example:
    # 6262 774 688
    # -----------------------------------------

    matches = re.findall(
        r'(?<!\d)'
        r'([6-9]\d{2,3})\s+'
        r'(\d{3})\s+'
        r'(\d{3,4})'
        r'(?!\d)',
        text
    )

    for match in matches:

        number = ''.join(match)

        if len(number) == 10:

            return number


    # -----------------------------------------
    # Last fallback:
    # collect nearby digit groups
    # -----------------------------------------

    groups = re.findall(
        r'\d+',
        text
    )

    for i in range(len(groups)):

        combined = ''

        for j in range(
            i,
            min(i + 4, len(groups))
        ):

            combined += groups[j]

            if len(combined) == 10:

                if combined[0] in '6789':

                    return combined

                break

            if len(combined) > 10:

                break


    return None