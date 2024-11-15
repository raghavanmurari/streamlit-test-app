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
if 'show_main' not in st.session_state:
    st.session_state.show_main = False  # Control when the main page appears

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
            st.success(f"File '{file_name}' successfully uploaded to Google Cloud Storage.")
            return True
    except Exception as e:
        st.error(f"Failed to upload file '{file_name}': {str(e)}")
        return False

# Page 1: Login Page
if st.session_state["page"] == "login":
    st.title("Student Login")
    with st.form("login_form"):
        name = st.text_input("Student Name")
        email = st.text_input("Email ID")
        student_class = st.selectbox("Class", [9, 10, 11, 12])
        test_number = st.selectbox("Test Number", ["Test1", "Test2", "Test3"])
        
        submit = st.form_submit_button("Submit")
        if submit:
            if not name:
                st.error("Please enter your name")
            if not email:
                st.error("Please enter your email ID")
            
            # Only proceed if all required fields are filled
            if name and email and student_class:
                st.session_state["name"] = name
                st.session_state["email"] = email
                st.session_state["class"] = f"Grade{student_class}"
                st.session_state["test"] = test_number
                st.session_state["page"] = "main"
                st.session_state.show_main = True
                st.rerun()

# Page 2: Main Page
elif st.session_state.get("page") == "main" and st.session_state.show_main:
    st.title("Test Page")
    
    main_col, _, timer_col = st.columns([2, 1, 1])
    
    with main_col:
        # Question Paper Download
        st.subheader("Download Question Paper")
        question_path = save_folder / st.session_state["class"] / st.session_state["test"] / "QuestionPaper" / "QuestionPaper.pdf"
        if question_path.exists():
            if st.download_button(
                label="DOWNLOAD QUESTION PAPER",
                data=question_path.read_bytes(),
                file_name="QuestionPaper.pdf",
                mime="application/pdf",
                disabled=st.session_state.download_question_clicked
            ):
                st.session_state.download_question_clicked = True
                st.session_state.question_downloaded = True
                start_timer()
        else:
            st.error("Question paper not available.")

        # Calculate remaining time outside the display block
        remaining_time = max(st.session_state.exam_duration - st.session_state.elapsed_time, 0)
        if remaining_time <= 0:
            st.session_state.time_up = True
            if st.session_state.timer_running:
                stop_timer()

        # Answer Sheet Upload
        if not st.session_state.solution_downloaded:
            st.subheader("Upload Your Answer Sheet")
            upload_disabled = st.session_state.time_up or remaining_time <= 0 or st.session_state.upload_answer_clicked
            uploaded_file = st.file_uploader(
                "Choose a PDF file to upload your answer sheet",
                type="pdf",
                key="answer_upload",
                disabled=upload_disabled
            )
    
            if upload_disabled and not st.session_state.answer_uploaded:
                st.error("Time's up! Answer sheet uploads are no longer accepted.")
            # Check to ensure only one upload occurs
            if uploaded_file and not upload_disabled and not st.session_state.get("answer_uploaded", False):
                student_name = st.session_state["name"].replace(" ", "_")
                filename = f"{student_name}_{st.session_state['class']}.pdf"
                folder_path = f"{st.session_state['class']}/{st.session_state['test']}/AnswerSheets"
                if upload_to_gcs(uploaded_file, filename, folder_path):
                    st.session_state.timer_running = False  # Explicitly stop timer
                    st.session_state.elapsed_time = time.time() - st.session_state.start_time
                    st.session_state.answer_uploaded = True  # Set the flag to prevent re-upload
                    st.session_state.upload_answer_clicked = True
                    st.session_state.page = "main"  # Ensure we stay on main page
                    st.rerun()  # Force page refresh

        # Download Solutions
        if st.session_state.answer_uploaded:
            st.subheader("Download Solutions")
            solution_path = save_folder / st.session_state["class"] / st.session_state["test"] / "Solutions" / "Solutions.pdf"
            if solution_path.exists():
                if st.download_button(
                    label="DOWNLOAD SOLUTIONS",
                    data=solution_path.read_bytes(),
                    file_name="Solutions.pdf",
                    mime="application/pdf",
                    disabled=st.session_state.download_solution_clicked
                ):
                    st.session_state.solution_downloaded = True
                    st.session_state.download_solution_clicked = True
                    st.session_state["page"] = "thank_you"
                    st.rerun()

    # Timer display
    if st.session_state.question_downloaded and not st.session_state.answer_uploaded and not st.session_state.solution_downloaded:
        with timer_col:
            st.subheader("Exam Timer")
            if st.session_state.timer_running:
                st.session_state.elapsed_time = time.time() - st.session_state.start_time
            remaining_time = max(st.session_state.exam_duration - st.session_state.elapsed_time, 0)
            minutes = int(remaining_time // 60)
            seconds = int(remaining_time % 60)
            time_str = f"{minutes:02d}:{seconds:02d}"
            if remaining_time <= 10:
                st.markdown(f"<h2 style='color: red;'>⏱️ {time_str}</h2>", unsafe_allow_html=True)
            elif remaining_time <= 30:
                st.markdown(f"<h2 style='color: orange;'>⏱️ {time_str}</h2>", unsafe_allow_html=True)
            else:
                st.markdown(f"<h2>⏱️ {time_str}</h2>", unsafe_allow_html=True)
            if remaining_time <= 10 and st.session_state.timer_running:
                st.warning("⚠️ Less than 10 seconds remaining!")
            if remaining_time <= 0 and st.session_state.timer_running:
                stop_timer()
                st.error("Time's up! Answer sheet uploads are no longer accepted.")
    
    # Timer refresh control
    if st.session_state.timer_running and not st.session_state.answer_uploaded and not uploaded_file:
        st_autorefresh(interval=1000)

# Page 3: Thank You Page
elif st.session_state.get("page") == "thank_you":
    st.title("THANK YOU")
    st.header(f"Thank you {st.session_state['name']} for completing the test!")
    st.success("Your answer sheet has been submitted and solutions have been downloaded successfully.")