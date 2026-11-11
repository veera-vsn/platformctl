import os
import requests
import streamlit as st

API = os.getenv("PLATFORMCTL_API_URL", "http://localhost:8000").rstrip("/")
st.set_page_config(page_title="platformctl", page_icon="☸️", layout="wide")
st.title("platformctl — Application Platform")
st.caption("A thin status UI over the platformctl control-plane API")

try:
    response = requests.get(f"{API}/v1/apps", timeout=10)
    response.raise_for_status()
    apps = response.json().get("items", [])
except requests.RequestException as exc:
    st.error(f"Cannot reach the platform API: {exc}")
    st.stop()

if not apps:
    st.info("No applications registered yet. Use `platformctl app create` to register one.")
    st.stop()

rows = []
for item in apps:
    metadata = item.get("metadata", {})
    spec = item.get("spec", {})
    status = item.get("status", {})
    rows.append({
        "Application": metadata.get("name", ""),
        "Type": spec.get("type", ""),
        "Version": spec.get("version", ""),
        "Image": spec.get("image", ""),
        "Phase": status.get("phase", "Pending"),
        "Namespace": status.get("targetNamespace", "Pending"),
    })

st.metric("Registered applications", len(rows))
st.dataframe(rows, use_container_width=True, hide_index=True)
selected = st.selectbox("Inspect application", [row["Application"] for row in rows])
if st.button("Run diagnostics", type="primary"):
    try:
        result = requests.get(f"{API}/v1/apps/{selected}/diagnose", timeout=20)
        result.raise_for_status()
        report = result.json()["diagnostics"]
        if report["healthy"]:
            st.success(report["summary"])
        else:
            st.warning(report["summary"])
        st.json(report["findings"])
    except requests.RequestException as exc:
        st.error(f"Diagnostics failed: {exc}")
