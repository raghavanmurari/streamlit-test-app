import streamlit as st
from pathlib import Path
import time
from streamlit_autorefresh import st_autorefresh

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
    st.session_state.exam_duration = 20  # Set to 1 minute in seconds for demonstration
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

# Page 1: Login Page
if st.session_state["page"] == "login":
    st.title("Student Login")
    with st.form("login_form"):
        name = st.text_input("Student Name")
        email = st.text_input("Email ID")
        student_class = st.selectbox("Class", [7, 8, 9, 10, 11, 12])
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
                start_timer()
                st.rerun()

# Page 2: Main Page (display only if show_main is True)
elif st.session_state.get("page") == "main" and st.session_state.show_main:
    st.title("Test Page")
    
    main_col, _, timer_col = st.columns([2, 1, 1])
    
    with main_col:
        # Section 1: Question Paper Download
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
                st.session_state.download_question_clicked = True  # Disable after first click
                if not st.session_state.question_downloaded:
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

        # Section 2: Answer Sheet Upload
        if not st.session_state.solution_downloaded:
            st.subheader("Upload Your Answer Sheet")
            
            # Disable upload if time is up OR solutions are downloaded
            upload_disabled = st.session_state.time_up or remaining_time <= 0 or st.session_state.upload_answer_clicked
            
            uploaded_file = st.file_uploader(
                "Choose a PDF file to upload your answer sheet", 
                type="pdf", 
                key="answer_upload",
                disabled=upload_disabled
            )
            
            # Show message if time is up
            if upload_disabled and not st.session_state.answer_uploaded:
                st.error("Time's up! Answer sheet uploads are no longer accepted.")
            
            if uploaded_file and not upload_disabled:
                student_name = st.session_state["name"].replace(" ", "_")
                filename = f"{student_name}_{st.session_state['class']}.pdf"
                answer_path = save_folder / st.session_state["class"] / st.session_state["test"] / "AnswerSheets" / filename
                
                # Save the file only if it doesn't already exist
                if not answer_path.exists():
                    with open(answer_path, "wb") as f:
                        f.write(uploaded_file.getbuffer())
                    st.success(f"Answer sheet uploaded successfully and saved as '{filename}'")
                    stop_timer()
                    st.session_state.answer_uploaded = True
                    st.session_state.upload_answer_clicked = True  # Disable after first upload
                else:
                    st.error("You have already uploaded your answer sheet.")

        # Section 3: Download Solutions
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
                    st.session_state["page"] = "thank_you"  # Change to thank you page
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
    
    # Auto-refresh timer
    if st.session_state.timer_running and not st.session_state.answer_uploaded:
        st_autorefresh(interval=1000)

# Page 3: Thank You Page
elif st.session_state.get("page") == "thank_you":
    st.title("THANK YOU")
    st.header(f"Thank you {st.session_state['name']} for completing the test!")
    st.success("Your answer sheet has been submitted and solutions have been downloaded successfully.")