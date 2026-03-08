import streamlit as st
import requests

import os
API_URL = os.getenv("API_URL", "http://127.0.0.1:8000")

st.set_page_config(page_title="Sahayak AI", layout="centered")

st.title("🇮🇳 Sahayak AI – Government Benefits Assistant")
st.subheader("Government Scheme Finder")
st.progress(0)

st.markdown("### Application Process")

st.markdown("""
1️⃣ **Find Scheme**  
2️⃣ **Select Scheme**  
3️⃣ **Upload Documents**  
4️⃣ **Submit Application**  
5️⃣ **Track Status**
""")

# ------------------------
# SESSION STATE
# ------------------------

if "schemes" not in st.session_state:
    st.session_state["schemes"] = []

if "document" not in st.session_state:
    st.session_state["document"] = None

# ------------------------
# SEARCH SCHEMES
# ------------------------

query = st.text_input("Ask about schemes")

if st.button("Find Schemes"):

    response = requests.get(
        f"{API_URL}/recommend",
        params={"query": query}
    )

    data = response.json()

    st.success("Recommended Schemes")

    result_text = data["recommendations"]

    st.write(result_text)

    # Extract schemes from AI response
    schemes_list = []

    if "PM-KISAN" in result_text:
        schemes_list.append("PM-KISAN")

    if "PMFBY" in result_text:
        schemes_list.append("PMFBY")

    if "KCC" in result_text or "Kisan Credit" in result_text:
        schemes_list.append("Kisan Credit Card")

    if "PMKSY" in result_text:
        schemes_list.append("PMKSY")

    st.session_state["schemes"] = schemes_list
    st.progress(20)

# ------------------------
# SCHEME SELECTION
# ------------------------

selected_scheme = None

if st.session_state["schemes"]:

    st.subheader("Select Scheme")

    scheme_options = ["Select a scheme"] + st.session_state["schemes"]

    selected_scheme = st.selectbox(
        "Choose a scheme",
        scheme_options
    )

    if selected_scheme != "Select a scheme":
        st.success(f"Selected Scheme: {selected_scheme}")
        st.progress(40)

# ------------------------
# DOCUMENT UPLOAD
# ------------------------

st.subheader("Upload Document")

file = st.file_uploader(
    "Upload Aadhaar / PAN",
    type=["jpg","png","pdf"]
)

if st.button("Upload Document") and file:

    files = {"file": (file.name, file.getvalue())}

    res = requests.post(
        f"{API_URL}/upload-document",
        files=files
    )

    data = res.json()

    st.session_state["document"] = data["file_name"]

    st.success(f"Uploaded: {data['file_name']}")

if st.session_state["document"]:
    st.info(f"Document Uploaded: {st.session_state['document']}")
    st.progress(60)

# ------------------------
# APPLY FOR SCHEME
# ------------------------

st.subheader("Apply for Scheme")

name = st.text_input("Name")
phone = st.text_input("Phone")

if st.button("Submit Application"):

    if selected_scheme is None or selected_scheme == "Select a scheme":
        st.warning("Please select a scheme")

    elif st.session_state["document"] is None:
        st.warning("Please upload a document")

    else:

        res = requests.post(
            f"{API_URL}/submit-application",
            params={
                "name": name,
                "phone": phone,
                "scheme": selected_scheme,
                "document": st.session_state["document"]
            }
        )

        data = res.json()

        st.success("Application Submitted")

        st.write("Reference ID:", data["reference_id"])
        st.progress(100)

# ------------------------
# CHECK APPLICATION STATUS
# ------------------------

st.divider()

st.subheader("Check Application Status")

ref_id = st.text_input("Enter Reference ID")

if st.button("Check Status"):

    res = requests.get(
        f"{API_URL}/check-status",
        params={"reference_id": ref_id}
    )

    data = res.json()

    if "status" in data:

        st.success("Application Found")

        st.write("Name:", data["name"])
        st.write("Scheme:", data["scheme"])
        st.write("Status:", data["status"])

    else:
        st.error("Application not found")