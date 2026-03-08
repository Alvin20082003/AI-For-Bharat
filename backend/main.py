from fastapi import FastAPI, UploadFile, File
import boto3
import pandas as pd
import uuid
import os

app = FastAPI()

# -----------------------------
# LOAD DATASET
# -----------------------------

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSV_PATH = os.path.join(BASE_DIR, "schemes.csv")

print("Loading dataset from:", CSV_PATH)

schemes = pd.read_csv(
    CSV_PATH,
    encoding="latin1",
    on_bad_lines="skip",
    engine="python"
)

print("Dataset loaded:", schemes.shape)

# -----------------------------
# AWS CONFIG
# -----------------------------

AWS_ACCESS_KEY = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
AWS_REGION = os.getenv("AWS_DEFAULT_REGION")

# -----------------------------
# AWS CLIENTS
# -----------------------------

s3 = boto3.client(
    "s3",
    aws_access_key_id=AWS_ACCESS_KEY,
    aws_secret_access_key=AWS_SECRET_KEY,
    region_name=AWS_REGION
)

bedrock = boto3.client(
    "bedrock-runtime",
    aws_access_key_id=AWS_ACCESS_KEY,
    aws_secret_access_key=AWS_SECRET_KEY,
    region_name=AWS_REGION
)

dynamodb = boto3.resource(
    "dynamodb",
    aws_access_key_id=AWS_ACCESS_KEY,
    aws_secret_access_key=AWS_SECRET_KEY,
    region_name=AWS_REGION
)

table = dynamodb.Table("sahayak-applications")

# -----------------------------
# CONFIG
# -----------------------------

BUCKET_NAME = "sahayak-ai-documents-alvin"

MODEL_ID = "arn:aws:bedrock:ap-south-1:248189924710:application-inference-profile/dtkpg502t751"

# -----------------------------
# BEDROCK FUNCTION
# -----------------------------

def ask_bedrock(prompt):

    response = bedrock.converse(
        modelId=MODEL_ID,
        messages=[
            {
                "role": "user",
                "content": [{"text": prompt}]
            }
        ],
        inferenceConfig={
            "maxTokens": 800,
            "temperature": 0.5
        }
    )

    return response["output"]["message"]["content"][0]["text"]


# -----------------------------
# HOME API
# -----------------------------

@app.get("/")
def home():
    return {"message": "Sahayak AI backend running successfully 🚀"}


# -----------------------------
# SCHEME RECOMMENDATION
# -----------------------------

@app.get("/recommend")
def recommend(query: str):

    data = schemes.astype(str)

    filtered = data[
        data.apply(
            lambda row: any(
                word in row.str.lower().str.cat(sep=" ")
                for word in query.lower().split()
            ),
            axis=1
        )
    ]

    if filtered.empty:
        filtered = data.head(5)

    scheme_list = filtered.head(5).to_string()

    prompt = f"""
You are an AI assistant helping Indian citizens find government schemes.

User query:
{query}

Available schemes:
{scheme_list}

Return answer in this format:

1. Scheme Name
Description: short explanation
Benefits: key benefit

Only show 3 schemes maximum.
"""

    result = ask_bedrock(prompt)

    scheme_names = filtered.head(5).iloc[:, 0].tolist()

    return {
        "query": query,
        "recommendations": result,
        "schemes": scheme_names
    }


# -----------------------------
# DOCUMENT UPLOAD (S3)
# -----------------------------

@app.post("/upload-document")
async def upload_document(file: UploadFile = File(...)):

    file_content = await file.read()

    s3.put_object(
        Bucket=BUCKET_NAME,
        Key=file.filename,
        Body=file_content
    )

    return {
        "message": "Document uploaded successfully",
        "file_name": file.filename
    }


# -----------------------------
# SUBMIT APPLICATION
# -----------------------------

@app.post("/submit-application")
def submit_application(name: str, phone: str, scheme: str, document: str):

    reference_id = str(uuid.uuid4())

    table.put_item(
        Item={
            "reference_id": reference_id,
            "name": name,
            "phone": phone,
            "scheme": scheme,
            "document": document,
            "status": "submitted"
        }
    )

    return {
        "message": "Application submitted successfully",
        "reference_id": reference_id
    }


# -----------------------------
# CHECK APPLICATION STATUS
# -----------------------------

@app.get("/check-status")
def check_status(reference_id: str):

    response = table.get_item(
        Key={
            "reference_id": reference_id
        }
    )

    if "Item" not in response:
        return {"error": "Application not found"}

    item = response["Item"]

    return {
        "reference_id": item["reference_id"],
        "name": item["name"],
        "scheme": item["scheme"],
        "status": item["status"]
    }