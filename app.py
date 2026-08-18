from flask import Flask, request, jsonify, send_from_directory
from dotenv import load_dotenv
from google import genai
import firebase_admin
from firebase_admin import credentials, firestore
import os
import json


# ==========================================
# LOAD ENVIRONMENT VARIABLES
# ==========================================

load_dotenv()


# ==========================================
# PROJECT PATH
# ==========================================

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# ==========================================
# FLASK APP
# ==========================================

app = Flask(__name__)


# ==========================================
# GEMINI API
# ==========================================

api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    raise ValueError("GEMINI_API_KEY not found")

client = genai.Client(api_key=api_key)

# You can change this from Render Environment Variables
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")


# ==========================================
# FIREBASE / FIRESTORE
# ==========================================

db = None

firebase_json = os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON")

try:

    if not firebase_admin._apps:

        # ------------------------------------------
        # OPTION 1: Render Environment Variable
        # ------------------------------------------

        if firebase_json:

            firebase_info = json.loads(firebase_json)

            cred = credentials.Certificate(firebase_info)

            firebase_admin.initialize_app(cred)

        # ------------------------------------------
        # OPTION 2: Local JSON file
        # ------------------------------------------

        else:

            firebase_key = os.path.join(
                BASE_DIR,
                "backend",
                "firebase-service-account.json"
            )

            if os.path.exists(firebase_key):

                cred = credentials.Certificate(firebase_key)

                firebase_admin.initialize_app(cred)

            else:

                print("WARNING: Firebase credentials not found.")

    db = firestore.client()

except Exception as e:

    print("Firebase initialization warning:", e)

    db = None


# ==========================================
# FRONTEND ROUTES
# ==========================================

@app.route("/")
def home():

    return send_from_directory(
        BASE_DIR,
        "index.html"
    )


@app.route("/style.css")
def css():

    return send_from_directory(
        BASE_DIR,
        "style.css"
    )


@app.route("/script.js")
def javascript():

    return send_from_directory(
        BASE_DIR,
        "script.js"
    )


# ==========================================
# AI ANALYSIS
# ==========================================

@app.route("/analyze", methods=["POST"])
def analyze():

    data = request.get_json()

    if not data:

        return jsonify({
            "error": "Invalid request."
        }), 400

    text = data.get("text", "").strip()

    if not text:

        return jsonify({
            "error": "Please enter some content."
        }), 400


    prompt = f"""
You are TruthLens AI, a digital safety assistant.

Analyze the following news, social media post,
SMS, WhatsApp message, or online content.

IMPORTANT:

Do NOT claim with certainty that the content is
true or false based only on the text.

Classify it as one of:

- Likely Credible
- Needs Verification
- Potentially Misleading

Give a risk/credibility score from 0 to 100.

Identify warning signs such as:

- urgency
- emotional manipulation
- unsupported claims
- missing sources
- suspicious requests
- financial scams
- phishing-style language

Return ONLY valid JSON.

Use exactly this format:

{{
    "classification": "Needs Verification",
    "score": 50,
    "explanation": "Short explanation",
    "warning_signs": [
        "Warning sign 1",
        "Warning sign 2"
    ],
    "recommendation": "What the user should do"
}}

Content to analyze:

{text}
"""


    try:

        # ==========================================
        # GEMINI AI
        # ==========================================

        response = client.models.generate_content(

            model=GEMINI_MODEL,

            contents=prompt
        )


        result_text = response.text.strip()


        # ==========================================
        # REMOVE MARKDOWN CODE BLOCK
        # ==========================================

        if result_text.startswith("```"):

            result_text = result_text.replace(
                "```json",
                ""
            )

            result_text = result_text.replace(
                "```",
                ""
            )

            result_text = result_text.strip()


        # ==========================================
        # CONVERT AI RESPONSE TO JSON
        # ==========================================

        result = json.loads(result_text)


        # ==========================================
        # SAVE RESULT TO FIRESTORE
        # ==========================================

        if db is not None:

            try:

                db.collection("analyses").add({

                    "content": text,

                    "classification": result.get(
                        "classification"
                    ),

                    "score": result.get(
                        "score"
                    ),

                    "explanation": result.get(
                        "explanation"
                    ),

                    "warning_signs": result.get(
                        "warning_signs",
                        []
                    ),

                    "recommendation": result.get(
                        "recommendation"
                    )

                })

            except Exception as firebase_error:

                print(
                    "Firestore save error:",
                    firebase_error
                )


        # ==========================================
        # SEND RESULT TO WEBSITE
        # ==========================================

        return jsonify(result)


    except Exception as e:

        print("AI ANALYSIS ERROR:", e)

        return jsonify({

            "error": "AI analysis failed. Please try again."

        }), 500


# ==========================================
# START FLASK SERVER
# ==========================================

if __name__ == "__main__":

    app.run(

        host="0.0.0.0",

        port=int(
            os.environ.get(
                "PORT",
                5000
            )
        )

    )