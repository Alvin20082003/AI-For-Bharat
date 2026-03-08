from fastapi import FastAPI, UploadFile, File
import boto3
import pandas as pd
import uuid

app = FastAPI()

import os

# -----------------------------
# LOAD DATASET
# -----------------------------
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSV_PATH = os.path.join(BASE_DIR, "schemes.csv")

schemes = pd.read_csv(
    CSV_PATH,
    encoding="latin1",
    on_bad_lines="skip",
    engine="python"
)

print("Dataset loaded:", schemes.shape)

# -----------------------------
# AWS CLIENTS
# -----------------------------
s3 = boto3.client("s3")

bedrock = boto3.client(
    service_name="bedrock-runtime",
    region_name="ap-south-1"
)

dynamodb = boto3.resource("dynamodb")
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
    return {"message": "Sahayak AI backend running"}

# -----------------------------
# SCHEME RECOMMENDATION API
# -----------------------------
@app.get("/recommend")
def recommend(query: str):

    # convert dataset to string
    data = schemes.astype(str)

    # search dataset using query words
    filtered = data[
        data.apply(
            lambda row: any(word in row.str.lower().str.cat(sep=" ")
                            for word in query.lower().split()),
            axis=1
        )
    ]

    # fallback if nothing found
    if filtered.empty:
        filtered = data.head(5)

    # send small dataset sample to AI
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

    # extract scheme names from dataset (first column)
    scheme_names = filtered.head(5).iloc[:, 0].tolist()

    return {
        "query": query,
        "recommendations": result,
        "schemes": scheme_names
    }

# -----------------------------
# DOCUMENT UPLOAD API (S3)
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
# SUBMIT APPLICATION (DynamoDB)
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