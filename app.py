import streamlit as st
from pathlib import Path
import time
from streamlit_autorefresh import st_autorefresh
from google.oauth2 import service_account
from google.cloud import storage
import mimetypes

# Define the folder path where files will be saved
save_folder = Path("files")  # Change if your folder path is different
save_folder.mkdir(exist_ok=True)  # Create the folder if it doesn't exist

# Initialize session state variables
if 'timer_running' not in st.session_state:
    st.session_state.timer_running = False
if 'start_time' not in st.session_state:
    st.session_state.start_time = None
if 'elapsed_time' not in st.session_state:
    st.session_state.elapsed_time = 0
if 'exam_duration' not in st.session_state:
    st.session_state.exam_duration = 6000  # Set to 100 minutes in seconds 
if 'answer_uploaded' not in st.session_state:
    st.session_state.answer_uploaded = False
if 'question_downloaded' not in st.session_state:
    st.session_state.question_downloaded = False
if 'solution_downloaded' not in st.session_state:
    st.session_state.solution_downloaded = False
if 'time_up' not in st.session_state:
    st.session_state.time_up = False

# Track button clicks to disable after the first click
if 'download_question_clicked' not in st.session_state:
    st.session_state.download_question_clicked = False
if 'upload_answer_clicked' not in st.session_state:
    st.session_state.upload_answer_clicked = False
if 'download_solution_clicked' not in st.session_state:
    st.session_state.download_solution_clicked = False

# Page Navigation State
if "page" not in st.session_state:
    st.session_state["page"] = "login"

def start_timer():
    st.session_state.timer_running = True
    st.session_state.start_time = time.time() - st.session_state.elapsed_time

def stop_timer():
    st.session_state.timer_running = False
    st.session_state.elapsed_time = time.time() - st.session_state.start_time
    if st.session_state.elapsed_time >= st.session_state.exam_duration:
        st.session_state.time_up = True

def initialize_gcs_client():
    """Initialize Google Cloud Storage client with credentials from Streamlit secrets."""
    try:
        credentials = service_account.Credentials.from_service_account_info(
            st.secrets["gcp_service_account"]
        )
        return storage.Client(credentials=credentials)
    except Exception as e:
        st.error(f"Failed to initialize GCS client: {str(e)}")
        return None

def upload_to_gcs(file_data, file_name, folder_path=None):
    """Upload a file to Google Cloud Storage."""
    try:
        bucket_name = st.secrets["gcs"]["bucket_name"]
        client = initialize_gcs_client()
        if client:
            bucket = client.bucket(bucket_name)
            blob_path = f"{folder_path}/{file_name}" if folder_path else file_name
            blob = bucket.blob(blob_path)
            content_type = mimetypes.guess_type(file_name)[0]
            if content_type:
                blob.content_type = content_type
            blob.upload_from_file(file_data)
            return True
    except Exception as e:
        st.error(f"Failed to upload file '{file_name}': {str(e)}")
        return False

# Define navigation callbacks
def handle_login_submit():
    name = st.session_state.get("student_name", "")
    email = st.session_state.get("student_email", "")
    if not name:
        st.error("Please enter your name")
        return
    if not email:
        st.error("Please enter your email ID")
        return
    st.session_state["name"] = name
    st.session_state["email"] = email
    st.session_state["class"] = f"Grade{st.session_state.student_class}"
    st.session_state["test"] = st.session_state.test_number
    st.session_state["page"] = "download_questions"

def handle_question_download():
    st.session_state.download_question_clicked = True
    st.session_state.question_downloaded = True
    st.session_state["page"] = "upload_answer_sheet"

def handle_answer_upload():
    if not st.session_state.get("answer_upload"):
        st.error("Please select a file to upload")
        return False
    
    # First update states
    stop_timer()
    st.session_state.answer_uploaded = True
    st.session_state.upload_answer_clicked = True
    st.session_state["page"] = "thank_you"  # Set page before upload
    
    # Then upload file to GCS
    file = st.session_state.answer_upload
    student_name = st.session_state["name"].replace(" ", "_")
    filename = f"{student_name}_{st.session_state['class']}.pdf"
    folder_path = f"{st.session_state['class']}/{st.session_state['test']}/AnswerSheets"
    
    return upload_to_gcs(file, filename, folder_path)

# Page 1: LOGIN Page
if st.session_state["page"] == "login":
    st.title("Student Login")
    with st.form("login_form", clear_on_submit=False):
        st.text_input("Student Name", key="student_name")
        st.text_input("Email ID", key="student_email")
        st.selectbox("Class", [9, 10, 11, 12], key="student_class")
        st.selectbox("Test Number", ["Test1", "Test2", "Test3"], key="test_number")
        st.form_submit_button("Submit", on_click=handle_login_submit)

# Page 2: DOWNLOAD QUESTIONS Page
elif st.session_state["page"] == "download_questions":
    st.title("Download Questions")
    st.subheader("Download Question Paper")
    
    question_path = save_folder / st.session_state["class"] / st.session_state["test"] / "QuestionPaper" / "QuestionPaper.pdf"
    if question_path.exists():
        if not st.session_state.download_question_clicked:
            st.download_button(
                label="DOWNLOAD QUESTION PAPER",
                data=question_path.read_bytes(),
                file_name="QuestionPaper.pdf",
                mime="application/pdf",
                on_click=handle_question_download
            )
    else:
        st.error("Question paper not available.")

# Page 3: UPLOAD ANSWER SHEET Page
elif st.session_state["page"] == "upload_answer_sheet":
    st.title("Upload Answer Sheet")
    
    # Start the timer if not already started
    if not st.session_state.timer_running:
        start_timer()
    
    # Timer display
    if st.session_state.timer_running:
        st.session_state.elapsed_time = time.time() - st.session_state.start_time
    
    remaining_time = max(st.session_state.exam_duration - st.session_state.elapsed_time, 0)
    if remaining_time <= 0:
        st.session_state.time_up = True
        stop_timer()
    
    # Display the timer
    minutes = int(remaining_time // 60)
    seconds = int(remaining_time % 60)
    time_str = f"{minutes:02d}:{seconds:02d}"
    st.subheader(f"Time Remaining: ⏱️ {time_str}")
    
    # Upload form
    upload_disabled = st.session_state.time_up or st.session_state.upload_answer_clicked
    
    uploaded_file = st.file_uploader(
        "Choose a PDF file to upload your answer sheet",
        type="pdf",
        key="answer_upload",
        disabled=upload_disabled
    )
    
    if st.button("Submit Answer Sheet", disabled=upload_disabled):
        if uploaded_file:
            # First update all states
            st.session_state.timer_running = False
            stop_timer()
            st.session_state.answer_uploaded = True
            st.session_state.upload_answer_clicked = True
            st.session_state["page"] = "thank_you"
            
            # Then perform the upload
            student_name = st.session_state["name"].replace(" ", "_")
            filename = f"{student_name}_{st.session_state['class']}.pdf"
            folder_path = f"{st.session_state['class']}/{st.session_state['test']}/AnswerSheets"
            
            upload_to_gcs(uploaded_file, filename, folder_path)
            # Force page transition immediately
            st.rerun()
        else:
            st.error("Please select a file to upload")
    
    # Timer refresh control
    if st.session_state.timer_running and not st.session_state.answer_uploaded:
        st_autorefresh(interval=1000, key="timer_refresh")

# Page 4: THANK YOU Page
elif st.session_state.get("page") == "thank_you":
    st.title("THANK YOU")
    st.header(f"Thank you {st.session_state['name']} for completing the test!")
    st.success("Your answer sheet has been submitted successfully.")
    
    # Add solutions download button
    st.subheader("Download Solutions")
    solution_path = save_folder / st.session_state["class"] / st.session_state["test"] / "Solutions" / "Solutions.pdf"
    if solution_path.exists():
        if not st.session_state.download_solution_clicked:
            if st.download_button(
                label="DOWNLOAD SOLUTIONS",
                data=solution_path.read_bytes(),
                file_name="Solutions.pdf",
                mime="application/pdf"
            ):
                st.session_state.solution_downloaded = True
                st.session_state.download_solution_clicked = True
                st.success("Solutions downloaded successfully!")
