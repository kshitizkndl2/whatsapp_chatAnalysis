import os
import traceback
from datetime import datetime, timezone

import streamlit as st

import feedback_store
import helper
import preprocessor

st.title("WhatsApp Chat Analysis By Kshitiz Kandel")
st.title("Note: This app is still in development and may not work as expected.")

_FEEDBACK_INSTRUCTIONS_AFTER_ERROR = """
**Next steps**

1. You can use the **Feedback** button below to send your notes and paste the error text.
2. Or copy **“Error details (copy this)”** below, then use **Feedback** → **Error details** field → **Send**.

Thank you.
"""


def _get_feedback_admin_key() -> str | None:
    k = os.environ.get("FEEDBACK_ADMIN_KEY", "").strip()
    if k:
        return k
    try:
        return str(st.secrets["FEEDBACK_ADMIN_KEY"]).strip()
    except Exception:
        return None


def _format_error_report(context: str, exc: BaseException) -> str:
    """Plain-text block suitable for copy-paste into a .txt file."""
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    tb = traceback.format_exc()
    lines = [
        "=== WhatsApp Chat Analysis — error report ===",
        f"Time (UTC): {ts}",
        f"Step: {context}",
        f"Exception type: {type(exc).__name__}",
        f"Exception message: {exc!r}",
        "",
        "=== Traceback ===",
        tb if tb.strip() else "(no traceback available)",
        "",
        "=== End of report ===",
    ]
    return "\n".join(lines)


def _show_error_and_feedback(context: str, exc: BaseException) -> None:
    st.error("Something went wrong while running the app. See the details below.")
    st.markdown(_FEEDBACK_INSTRUCTIONS_AFTER_ERROR)
    report = _format_error_report(context, exc)
    st.text_area(
        "Error details (copy this)",
        value=report,
        height=320,
        help="Select all text (Ctrl+A / Cmd+A), copy, paste into a text editor, and save as a .txt file.",
        key="whatsapp_analysis_error_report_copy_area",
    )


# --- User feedback (saved on server; developer reads via password section below) ---
if "feedback_form_open" not in st.session_state:
    st.session_state.feedback_form_open = False

with st.sidebar:
    st.caption("Problems? Use **Feedback** on the main page.")

st.markdown(
    "Use **Feedback** to send a message and optional error text. "
    "When you click **Send**, a report file is created on the server for the developer only."
)

c1, c2 = st.columns([1, 4])
with c1:
    if st.button("Feedback", type="primary", use_container_width=True):
        st.session_state.feedback_form_open = True

if st.session_state.pop("feedback_thanks", False):
    st.success("Thank you! Your feedback was saved for the developer.")

if st.session_state.feedback_form_open:
    with st.expander("Feedback form", expanded=True):
        with st.form("user_feedback_form", clear_on_submit=True):
            user_message = st.text_area(
                "Your message",
                height=120,
                placeholder="What were you doing? What should we improve?",
            )
            error_text = st.text_area(
                "Error details",
                height=200,
                placeholder="If the app showed an error, paste the full text here (or leave blank).",
            )
            send = st.form_submit_button("Send")
            if send:
                if not (user_message or "").strip() and not (error_text or "").strip():
                    st.warning("Please enter a message and/or paste error details, then click Send again.")
                else:
                    try:
                        feedback_store.save_feedback(user_message, error_text)
                        st.session_state.feedback_form_open = False
                        st.session_state.feedback_thanks = True
                        st.rerun()
                    except OSError as exc:
                        st.error(f"Could not save feedback on the server: {exc}")
        if st.button("Close feedback form"):
            st.session_state.feedback_form_open = False
            st.rerun()

# --- Developer inbox (key from env or Streamlit secrets; never shown to end users) ---
with st.expander("Developer — feedback inbox", expanded=False):
    admin_key = _get_feedback_admin_key()
    if not admin_key:
        st.warning(
            "**This panel is locked until an admin key is configured.**\n\n"
            "- **On Render (or any host):** open your service → **Environment** → add variable "
            "`FEEDBACK_ADMIN_KEY` with a long random value → **Save** → **Manual Deploy** (or wait for deploy). "
            "Render does **not** read `.streamlit/secrets.toml` from Git.\n\n"
            "- **On your computer only:** create or edit `.streamlit/secrets.toml` and set "
            "`FEEDBACK_ADMIN_KEY = \"...\"` (see `.streamlit/secrets.toml.example`)."
        )
    else:
        entered = st.text_input("Developer access key", type="password", key="dev_feedback_key")
        if entered == admin_key:
            files = feedback_store.list_feedback_files()
            st.info(
                "On **Render** (or similar hosts): attach a **persistent disk**, set environment variable "
                "`FEEDBACK_LOG_DIR` to a folder on that disk so feedback files survive redeploys. "
                "Otherwise files live on ephemeral disk and may disappear after restart."
            )
            if not files:
                st.info(f"No feedback files yet. They are stored under: `{feedback_store.feedback_dir()}`")
            else:
                st.caption(f"Directory: `{feedback_store.feedback_dir()}` — newest first.")
                labels = [f.name for f in files]
                choice = st.selectbox("Pick a file", options=labels, key="dev_pick_feedback")
                path = feedback_store.feedback_dir() / choice
                st.text_area("File contents", value=feedback_store.read_feedback(path), height=360, disabled=True)
                st.download_button(
                    "Download this .txt",
                    data=feedback_store.read_feedback(path),
                    file_name=choice,
                    mime="text/plain",
                    key=f"dl_{choice}",
                )
        elif entered:
            st.error("Incorrect key.")

uploaded_file = st.file_uploader("Upload your WhatsApp chat()", type="txt")

if uploaded_file is not None:
    try:
        data = uploaded_file.read().decode("utf-8")
    except UnicodeDecodeError as exc:
        _show_error_and_feedback("Decoding the uploaded file as UTF-8", exc)
        st.caption(
            "Tip: export the chat again from WhatsApp as **.txt**, or try saving the file as UTF-8 in your editor."
        )
        st.stop()
    except Exception as exc:
        _show_error_and_feedback("Reading the uploaded file", exc)
        st.stop()

    try:
        df = preprocessor.preprocess(data)
    except Exception as exc:
        _show_error_and_feedback("Parsing or preprocessing your WhatsApp export", exc)
        st.stop()

    try:
        st.dataframe(df)
        options = []
        options.extend(df["Name"].unique())
        options = [name for name in options if "," not in str(name)]

        options.sort()
        options.insert(0, "Overall")

        selected_user = st.selectbox("Select a user", options)
        stats, cleaned_df, links = helper.fetch_stats(selected_user, df)
    except Exception as exc:
        _show_error_and_feedback("Loading the chat preview or user list", exc)
        st.stop()

    if st.button("Show Analysis"):
        try:
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric(label="Total Messages", value=stats[0])
            with col2:
                st.metric(label="Total Words", value=stats[1])
            with col3:
                st.metric(label="Total Media Shared", value=stats[2])
            with col4:
                st.metric(label="Total Links Shared", value=stats[3])

            helper.fetch_wordcloud(cleaned_df, links)

            helper.fetch_most_busy_users(df)
            helper.most_common_words(cleaned_df, links)
            helper.fetch_emojis(cleaned_df)
        except Exception as exc:
            _show_error_and_feedback("Running “Show Analysis” (charts / word cloud)", exc)
