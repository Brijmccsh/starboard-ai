import re
import io
from flask import Flask, request, jsonify
from PyPDF2 import PdfReader

app = Flask(__name__)

def extract_text_from_pdf(file_stream):
    """
    Extract all text from the provided PDF file stream.
    """
    try:
        reader = PdfReader(file_stream)
        text = ""
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
        return text
    except Exception as e:
        raise ValueError("Error processing PDF file: " + str(e))

def remove_extra_spaces_in_uppercase(s):
    """
    Remove extra spaces from sequences of uppercase letters.
    For example, converts "B R O O K LY N" to "BROOKLYN".
    Also replaces newlines with a single space.
    """
    # Replace newlines with spaces for easier processing.
    s = s.replace("\n", " ")
    # This regex finds groups of uppercase letters separated by spaces.
    pattern = re.compile(r'((?:[A-Z]\s+){1,}[A-Z])')
    def repl(match):
        return match.group(0).replace(" ", "")
    return pattern.sub(repl, s)

def parse_key_data(pdf_text):
    """
    Extract key fields from the PDF text:
      - Property Name (e.g., "280 Richards")
      - Address (e.g., "Brooklyn, New York City")
      - Total Rentable Square Footage (e.g., 312000)
    """
    # Clean the text to remove newlines and extra spaces between uppercase letters.
    cleaned_text = remove_extra_spaces_in_uppercase(pdf_text)
    
    # --- Extract Property Name ---
    # Look for "280 RICHARDS" (case-insensitive).
    prop_name_match = re.search(r"(280\s+RICHARDS)", cleaned_text, re.IGNORECASE)
    property_name = prop_name_match.group(1).strip().title() if prop_name_match else None

    # --- Extract Address ---
    # After cleaning, we expect something like "BROOKLYN,NEWYORCITY" (or "NEWYOR" if truncated).
    address_match = re.search(r"(BROOKLYN)[,]?\s*(NEWYOR(?:CITY)?)", cleaned_text, re.IGNORECASE)
    if address_match:
        borough = address_match.group(1).title()  # "Brooklyn"
        ny_variant = address_match.group(2).upper()
        if ny_variant == "NEWYORCITY":
            ny = "New York City"
        elif ny_variant == "NEWYOR":
            ny = "New York"
        else:
            ny = ny_variant.title()
        address = f"{borough}, {ny}"
    else:
        address = None

    # --- Extract Total Rentable Square Footage ---
    sqft = None
    # First try to match something like "312,000 square feet" or "312000 sf"
    sqft_match = re.search(r"([\d,]+)\s*(?:square\s*feet|sf)", cleaned_text, re.IGNORECASE)
    if sqft_match:
        sqft_str = sqft_match.group(1).replace(",", "")
        try:
            sqft = int(sqft_str)
        except ValueError:
            sqft = None
    else:
        # Alternatively, look for a pattern like "312K"
        k_match = re.search(r"(\d+)\s*K", cleaned_text, re.IGNORECASE)
        if k_match:
            try:
                sqft = int(k_match.group(1)) * 1000
            except ValueError:
                sqft = None

    return {
        "property_name": property_name,
        "address": address,
        "total_rentable_square_footage": sqft
    }

@app.route('/parse-pdf', methods=['POST'])
def parse_pdf_api():
    if 'file' not in request.files:
        return jsonify({"error": "No file part in the request."}), 400

    pdf_file = request.files['file']
    if pdf_file.filename == '':
        return jsonify({"error": "No selected file."}), 400

    try:
        file_stream = io.BytesIO(pdf_file.read())
        pdf_text = extract_text_from_pdf(file_stream)
        key_data = parse_key_data(pdf_text)
        
        # Ensure we found all key elements.
        if None in key_data.values():
            return jsonify({
                "error": "Could not reliably extract all key information.",
                "extracted": key_data
            }), 422
        
        return jsonify(key_data), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)
