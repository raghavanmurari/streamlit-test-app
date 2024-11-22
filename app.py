import streamlit as st
import time
from streamlit_autorefresh import st_autorefresh
from google.oauth2 import service_account
from google.cloud import storage
import mimetypes
import io
from openpyxl import load_workbook
from io import BytesIO
from datetime import datetime
import logging
import traceback

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize session state variables
def init_session_state():
    if 'timer_running' not in st.session_state:
        st.session_state.timer_running = False
    if 'start_time' not in st.session_state:
        st.session_state.start_time = None
    if 'elapsed_time' not in st.session_state:
        st.session_state.elapsed_time = 0
    if 'exam_duration' not in st.session_state:
        st.session_state.exam_duration = 6000  # 100 minutes in seconds
    if 'answer_uploaded' not in st.session_state:
        st.session_state.answer_uploaded = False
    if 'question_downloaded' not in st.session_state:
        st.session_state.question_downloaded = False
    if 'solution_downloaded' not in st.session_state:
        st.session_state.solution_downloaded = False
    if 'time_up' not in st.session_state:
        st.session_state.time_up = False
    if 'download_question_clicked' not in st.session_state:
        st.session_state.download_question_clicked = False
    if 'upload_answer_clicked' not in st.session_state:
        st.session_state.upload_answer_clicked = False
    if 'download_solution_clicked' not in st.session_state:
        st.session_state.download_solution_clicked = False
    if "page" not in st.session_state:
        st.session_state["page"] = "login"
    if "login_time" not in st.session_state:
        st.session_state.login_time = None
    if "upload_progress" not in st.session_state:
        st.session_state.upload_progress = 0

init_session_state()

def start_timer():
    st.session_state.timer_running = True
    st.session_state.start_time = time.time() - st.session_state.elapsed_time

def stop_timer():
    if st.session_state.timer_running:
        st.session_state.timer_running = False
        st.session_state.elapsed_time = time.time() - st.session_state.start_time
        if st.session_state.elapsed_time >= st.session_state.exam_duration:
            st.session_state.time_up = True

# GCS Operations with retry mechanism
def initialize_gcs_client():
    """Initialize Google Cloud Storage client with credentials from Streamlit secrets."""
    max_retries = 3
    retry_delay = 1  # seconds
    
    for attempt in range(max_retries):
        try:
            credentials = service_account.Credentials.from_service_account_info(
                st.secrets["gcp_service_account"]
            )
            return storage.Client(credentials=credentials)
        except Exception as e:
            if attempt == max_retries - 1:
                logger.error(f"Failed to initialize GCS client: {str(e)}")
                st.error(f"Failed to initialize storage client. Please try again.")
                return None
            time.sleep(retry_delay)
    return None

def download_from_gcs(folder_path, filename):
    """Download a file from Google Cloud Storage with retry mechanism."""
    max_retries = 3
    retry_delay = 1  # seconds
    
    for attempt in range(max_retries):
        try:
            bucket_name = st.secrets["gcs"]["bucket_name"]
            client = initialize_gcs_client()
            if not client:
                return None
                
            bucket = client.bucket(bucket_name)
            blob_path = f"{folder_path}/{filename}"
            blob = bucket.blob(blob_path)
            
            if not blob.exists():
                logger.warning(f"File not found: {blob_path}")
                return None
                
            return blob.download_as_bytes()
        except Exception as e:
            if attempt == max_retries - 1:
                logger.error(f"Failed to download file '{filename}': {str(e)}")
                st.error(f"Failed to download file. Please try again.")
                return None
            time.sleep(retry_delay)
    return None

def upload_to_gcs(file_data, file_name, folder_path):
    """Upload file to GCS with retry mechanism and progress tracking."""
    max_retries = 3
    retry_delay = 1  # seconds
    
    for attempt in range(max_retries):
        try:
            bucket_name = st.secrets["gcs"]["bucket_name"]
            client = initialize_gcs_client()
            if not client:
                return False
                
            bucket = client.bucket(bucket_name)
            blob_path = f"{folder_path}/{file_name}"
            blob = bucket.blob(blob_path)
            
            # Reset file pointer
            file_data.seek(0)
            
            # Set content type
            content_type = mimetypes.guess_type(file_name)[0]
            if content_type:
                blob.content_type = content_type
            
            # Upload with progress
            blob.upload_from_file(file_data)
            return True
            
        except Exception as e:
            if attempt == max_retries - 1:
                logger.error(f"Failed to upload file '{file_name}': {str(e)}")
                st.error(f"Upload failed. Please try again.")
                return False
            time.sleep(retry_delay)
    return False

def log_student_login(name, email, class_name, test_number):
    """Log student login information to Excel with retry mechanism."""
    max_retries = 3
    retry_delay = 1
    
    for attempt in range(max_retries):
        try:
            # Download existing log file
            log_content = download_from_gcs("logs", "student_logs.xlsx")
            if log_content is None:
                logger.error("Could not access student logs")
                return False
                
            # Load workbook
            wb = load_workbook(BytesIO(log_content))
            ws = wb.active
            
            # Get next row number
            next_row = ws.max_row + 1
            
            # Add new record
            login_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            st.session_state.login_time = login_time
            
            # Add data to Excel
            ws.cell(row=next_row, column=1, value=next_row-1)  # SNO
            ws.cell(row=next_row, column=2, value=name)  # StudentName
            ws.cell(row=next_row, column=3, value=email)  # EmailID
            ws.cell(row=next_row, column=4, value=class_name)  # Class
            ws.cell(row=next_row, column=5, value=test_number)  # TestNumber
            ws.cell(row=next_row, column=6, value=login_time)  # LoginTimestamp
            
            # Save and upload
            excel_bytes = BytesIO()
            wb.save(excel_bytes)
            excel_bytes.seek(0)
            
            # Upload updated file
            if not upload_to_gcs(excel_bytes, "student_logs.xlsx", "logs"):
                raise Exception("Failed to upload updated log file")
            
            return True
            
        except Exception as e:
            if attempt == max_retries - 1:
                logger.error(f"Failed to log student login: {str(e)}")
                return False
            time.sleep(retry_delay)
    return False

def log_student_logout(name, email, class_name, test_number):
    """Update student logout information with retry mechanism."""
    max_retries = 3
    retry_delay = 1
    
    for attempt in range(max_retries):
        try:
            # Download existing log file
            log_content = download_from_gcs("logs", "student_logs.xlsx")
            if log_content is None:
                logger.error("Could not access student logs")
                return False
                
            # Load workbook
            wb = load_workbook(BytesIO(log_content))
            ws = wb.active
            
            # Find matching row
            login_time = st.session_state.login_time
            row_found = None
            for row in range(2, ws.max_row + 1):
                if (ws.cell(row=row, column=2).value == name and 
                    ws.cell(row=row, column=3).value == email and
                    ws.cell(row=row, column=4).value == class_name and
                    ws.cell(row=row, column=5).value == test_number and
                    ws.cell(row=row, column=6).value == login_time):
                    row_found = row
                    break
            
            if row_found:
                logout_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                ws.cell(row=row_found, column=7, value=logout_time)  # LogoutTimestamp
                
                # Calculate time taken
                login_dt = datetime.strptime(login_time, "%Y-%m-%d %H:%M:%S")
                logout_dt = datetime.strptime(logout_time, "%Y-%m-%d %H:%M:%S")
                time_taken = str(logout_dt - login_dt)
                ws.cell(row=row_found, column=8, value=time_taken)  # TimeTaken
                
                # Save and upload
                excel_bytes = BytesIO()
                wb.save(excel_bytes)
                excel_bytes.seek(0)
                
                if not upload_to_gcs(excel_bytes, "student_logs.xlsx", "logs"):
                    raise Exception("Failed to upload updated log file")
                
                return True
                
        except Exception as e:
            if attempt == max_retries - 1:
                logger.error(f"Failed to log student logout: {str(e)}")
                return False
            time.sleep(retry_delay)
    return False

# Handler functions with progress tracking
def handle_login_submit():
    name = st.session_state.get("student_name", "").strip()
    email = st.session_state.get("student_email", "").strip()
    
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
    
    with st.spinner('Logging in...'):
        if log_student_login(name, email, st.session_state["class"], st.session_state["test"]):
            st.session_state["page"] = "download_questions"
        else:
            st.error("Failed to log student information. Please try again.")

def handle_question_download():
    st.session_state.download_question_clicked = True
    st.session_state.question_downloaded = True
    st.session_state["page"] = "upload_answer_sheet"

def handle_answer_upload():
    """Handle answer upload with progress tracking and error handling."""
    try:
        if not st.session_state.get("answer_upload"):
            st.error("Please select a file to upload")
            return False
        
        file = st.session_state.answer_upload
        student_name = st.session_state["name"].replace(" ", "_")
        filename = f"{student_name}_{st.session_state['class']}.pdf"
        folder_path = f"{st.session_state['class']}/{st.session_state['test']}/AnswerSheets"
        
        return upload_to_gcs(file, filename, folder_path)
        
    except Exception as e:
        logger.error(f"Error in handle_answer_upload: {str(e)}")
        st.error("Failed to process answer upload. Please try again.")
        return False

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
    
    # Get question paper from GCS
    question_folder = f"{st.session_state['class']}/{st.session_state['test']}/QuestionPaper"
    question_content = download_from_gcs(question_folder, "QuestionPaper.pdf")
    
    if question_content is not None:
        if not st.session_state.download_question_clicked:
            st.download_button(
                label="DOWNLOAD QUESTION PAPER",
                data=question_content,
                file_name="QuestionPaper.pdf",
                mime="application/pdf",
                on_click=handle_question_download
            )
    else:
        st.error("Question paper not available in Google Cloud Storage. Please contact your administrator.")

# Page 3: UPLOAD ANSWER SHEET Page
elif st.session_state["page"] == "upload_answer_sheet":
    st.title("Upload Answer Sheet")
    
    if not st.session_state.timer_running:
        start_timer()
    
    if st.session_state.timer_running:
        st.session_state.elapsed_time = time.time() - st.session_state.start_time
    
    remaining_time = max(st.session_state.exam_duration - st.session_state.elapsed_time, 0)
    if remaining_time <= 0:
        st.session_state.time_up = True
        stop_timer()
    
    minutes = int(remaining_time // 60)
    seconds = int(remaining_time % 60)
    time_str = f"{minutes:02d}:{seconds:02d}"
    st.subheader(f"Time Remaining: ⏱️ {time_str}")
    
    upload_disabled = st.session_state.time_up or st.session_state.upload_answer_clicked
    
    uploaded_file = st.file_uploader(
        "Choose a PDF file to upload your answer sheet",
        type="pdf",
        key="answer_upload",
        disabled=upload_disabled
    )
    
    if st.button("Submit Answer Sheet", disabled=upload_disabled):
        if uploaded_file:
            # Create placeholder for progress bar and status
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            try:
                # Step 1: Pre-upload checks and timer stop
                status_text.text('Preparing submission...')
                stop_timer()
                progress_bar.progress(20)
                
                # Step 2: Upload answer sheet
                status_text.text('Uploading your answer sheet...')
                if handle_answer_upload():
                    progress_bar.progress(60)
                    # Step 3: Log completion
                    status_text.text('Updating records...')
                    if log_student_logout(
                        st.session_state["name"], 
                        st.session_state["email"],
                        st.session_state["class"], 
                        st.session_state["test"]
                    ):
                        progress_bar.progress(90)
                        
                        # Step 4: Complete process
                        status_text.text('Finalizing...')
                        st.session_state.answer_uploaded = True
                        st.session_state.upload_answer_clicked = True
                        progress_bar.progress(100)
                        status_text.text('Complete!')
                        st.success("Answer sheet uploaded successfully!")
                        time.sleep(1)  # Brief pause to show completion
                        st.session_state["page"] = "thank_you"
                        st.rerun()
                    else:
                        st.error("Failed to update records. Please try again.")
                else:
                    st.error("Failed to upload answer sheet. Please try again.")
            except Exception as e:
                logger.error(f"Error during submission process: {str(e)}")
                st.error("An error occurred during submission. Please try again.")
        else:
            st.error("Please select a file to upload")
    
    if st.session_state.timer_running and not st.session_state.answer_uploaded:
        st_autorefresh(interval=1000, key="timer_refresh")

# Page 4: THANK YOU Page
elif st.session_state.get("page") == "thank_you":
    st.title("THANK YOU")
    st.header(f"Thank you {st.session_state['name']} for completing the test!")
    st.success("Your answer sheet has been submitted successfully.")
    
    # Get solutions from GCS
    solutions_folder = f"{st.session_state['class']}/{st.session_state['test']}/Solutions"
    solution_content = download_from_gcs(solutions_folder, "Solutions.pdf")
    
    if solution_content is not None and not st.session_state.download_solution_clicked:
        if st.download_button(
            label="DOWNLOAD SOLUTIONS",
            data=solution_content,
            file_name="Solutions.pdf",
            mime="application/pdf"
        ):
            st.session_state.solution_downloaded = True
            st.session_state.download_solution_clicked = True
            st.success("Solutions downloaded successfully!")
    else:
        st.error("Solutions not available in Google Cloud Storage. Please contact your administrator.")