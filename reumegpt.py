import streamlit as st
import time
import datetime
from io import BytesIO
from xhtml2pdf import pisa
from jinja2 import Template
import requests # Used for making HTTP requests to Gemini API
import json # Used for JSON parsing and serialization
import markdown # Used to convert AI-generated Markdown to HTML for PDF

st.set_page_config(page_title="ResumeForge AI", page_icon="🧠", layout='wide')
st.title("AI-Powered Job-Winning Resume Builder")

# --- Global Configuration and Session State Initialization ---
# Gemini API URL
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key="
# API key will be automatically provided by the Canvas environment, so we leave it empty here
API_KEY = "AIzaSyCOfQTnMDO5AM-17L-3YErL0t3PZP-FaSE" 

# Initialize session state variables for all dynamic entries and new features
if 'job_entries' not in st.session_state:
    st.session_state.job_entries = []
if 'edu_entries' not in st.session_state:
    st.session_state.edu_entries = []
if 'cert_entries' not in st.session_state:
    st.session_state.cert_entries = []
if 'prof_affl' not in st.session_state:
    st.session_state.prof_affl = []
if 'generated_resume_content' not in st.session_state: # Will store Markdown string from AI
    st.session_state.generated_resume_content = ""
if 'generated_cover_letter_content' not in st.session_state:
    st.session_state.generated_cover_letter_content = ""
if 'suggested_skills' not in st.session_state:
    st.session_state.suggested_skills = []
if 'edit_job_idx' not in st.session_state:
    st.session_state.edit_job_idx = None
if 'edit_edu_idx' not in st.session_state:
    st.session_state.edit_edu_idx = None
if 'edit_cert_idx' not in st.session_state:
    st.session_state.edit_cert_idx = None
if 'edit_prof_affl_idx' not in st.session_state:
    st.session_state.edit_prof_affl_idx = None
# Initialize text area specific session state keys for direct manipulation
if 'tech_textarea' not in st.session_state:
    st.session_state['tech_textarea'] = ""
if 'summary_textarea' not in st.session_state: # Added for summary manipulation
    st.session_state['summary_textarea'] = ""
if 'position_input' not in st.session_state:
    st.session_state['position_input'] = ""
if 'ai_temperature_slider' not in st.session_state:
    st.session_state['ai_temperature_slider'] = 0.7 # Default temperature


# --- Helper Functions for AI API Calls ---

def _call_gemini_api(prompt_text, temperature=0.7, response_mime_type="text/plain"):
    """
    Makes a call to the Gemini API with the given prompt and temperature.
    Handles loading spinner and basic error messages.
    """
    
    generation_config = {
        "temperature": temperature,
        "topP": 0.95,
        "topK": 60,
        "maxOutputTokens": 2048,
        "responseMimeType": response_mime_type, # Use the provided mime type
    }

    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [{"text": prompt_text}]
            }
        ],
        "generationConfig": generation_config
    }
    
    api_url = f"{GEMINI_API_URL}{API_KEY}"

    try:
        with st.spinner("Talking to AI... Please wait."):
            response = requests.post(api_url, headers={'Content-Type': 'application/json'}, json=payload)
            response.raise_for_status() # Raise an exception for HTTP errors
            result = response.json()

            if result.get('candidates') and len(result['candidates']) > 0 and \
               result['candidates'][0].get('content') and \
               result['candidates'][0]['content'].get('parts') and \
               len(result['candidates'][0]['content']['parts']) > 0:
                return result['candidates'][0]['content']['parts'][0]['text']
            else:
                st.error("AI response format was unexpected. Please try again.")
                print(f"Unexpected AI response: {result}")
                return None
    except requests.exceptions.RequestException as e:
        st.error(f"Failed to connect to AI: {e}. Please check your network or try again.")
        # Print the response content for debugging Bad Request errors
        if response.status_code == 400:
            print(f"Bad Request Details: {response.text}")
        return None
    except Exception as e:
        st.error(f"An error occurred during AI processing: {e}")
        return None

# --- Data Management Functions (Save/Load) ---

def save_user_data(data, file_name="resume_data.json"):
    """Saves current session state data to a JSON file."""
    # Convert dates to strings for JSON serialization
    serializable_data = json.loads(json.dumps(data, default=str)) 
    
    json_data = json.dumps(serializable_data, indent=4)
    st.download_button(
        label="Download All Data",
        data=json_data,
        file_name=file_name,
        mime="application/json",
        help="Saves your current form data so you can load it later."
    )

def load_user_data(uploaded_file):
    """Loads user data from an uploaded JSON file."""
    if uploaded_file is not None:
        try:
            data = json.load(uploaded_file)
            st.session_state.job_entries = data.get('work experience', [])
            st.session_state.edu_entries = data.get('Educational Experience', [])
            st.session_state.cert_entries = data.get('Certifications', [])
            st.session_state.prof_affl = data.get('Professional Affiliations', [])
            
            # Update main text inputs by setting session_state values directly
            # These keys match the `key` arguments in st.text_input/st.selectbox/st.text_area
            st.session_state['full_name_input'] = data.get('name', '')
            st.session_state['email_address_input'] = data.get('mail', '')
            st.session_state['linkedin_input'] = data.get('linkedin', '')
            st.session_state['portfolio_link_website_input'] = data.get('portfolio_link_website', '')
            st.session_state['location_select'] = data.get('location', 'Work from Home')
            st.session_state['position_input'] = data.get('position', '')
            st.session_state['description_textarea'] = data.get('description', '')
            st.session_state['summary_textarea'] = data.get('summary', '') # Load summary
            st.session_state['tech_textarea'] = data.get('tech', '') # Load tech skills

            st.success("Data loaded successfully! Please check the fields below.")
            st.rerun() # Rerun to refresh the displayed inputs
        except json.JSONDecodeError:
            st.error("Invalid JSON file. Please upload a valid data file.")
        except Exception as e:
            st.error(f"An error occurred while loading data: {e}")

# --- Resume Template Definitions (Reinstated for user choice) ---
RESUME_TEMPLATES = {
    "Modern Professional": Template("""
        <html>
        <head>
            <style>
                body { font-family: 'Inter', sans-serif; padding: 20px; line-height: 1.3; color: #333; }
                h1 { color: #2a4d69; text-align: center; margin-bottom: 5px; font-size: 2.2em; }
                .contact-info-line { text-align: center; margin-top: -5px; margin-bottom: 20px; font-size: 0.9em; color: #555; } /* Explicit class for centering contact info */
                h2 { color: #2a4d69; border-bottom: 2px solid #ddd; padding-bottom: 8px; margin-top: 30px; margin-bottom: 15px; font-size: 1.5em; }
                p { margin-bottom: 1em; }
                ul { list-style-type: disc; padding-left: 25px; margin-bottom: 15px; line-height: 1.3; }
                ol { list-style-type: decimal; padding-left: 25px; margin-bottom: 15px; line-height: 1.3; }
                li { margin-bottom: 0.5em; }
                b, strong { font-weight: bold; }
                i, em { font-style: italic; }
                a { color: #2a4d69; text-decoration: none; }
                .job-title { font-size: 1.1em; font-weight: bold; }
                .company-info { font-size: 0.95em; color: #666; margin-top: 2px; margin-bottom: 5px; }
                .date-range { float: right; font-style: italic; color: #777; }
                .clear { clear: both; }
            </style>
        </head>
        <body>
            {# The AI-generated markdown, converted to HTML, will be inserted here #}
            {{ html_content | safe }} 
        </body>
        </html>
    """),
    "Classic Clean": Template("""
        <html>
        <head>
            <style>
                body { font-family: 'Times New Roman', serif; padding: 25px; line-height: 1.3; color: #000; }
                h1 { text-align: center; margin-bottom: 5px; font-size: 2.5em; }
                .contact-info-line { text-align: center; margin-top: -5px; margin-bottom: 25px; font-size: 1em; } /* Explicit class for centering contact info */
                h2 { border-bottom: 1px solid #000; padding-bottom: 5px; margin-top: 30px; margin-bottom: 15px; font-size: 1.6em; }
                p { margin-bottom: 1em; }
                ul { list-style-type: square; padding-left: 20px; margin-bottom: 10px; line-height: 1.3; }
                ol { list-style-type: decimal; padding-left: 20px; margin-bottom: 10px; line-height: 1.3; }
                li { margin-bottom: 0.5em; }
                strong { font-weight: bold; }
                i, em { font-style: italic; }
                a { color: #000; text-decoration: underline; }
                .job-details { margin-bottom: 10px; }
                .job-title { font-weight: bold; }
                .company-name { font-style: italic; }
                .date-location { float: right; }
                .clear { clear: both; }
            </style>
        </head>
        <body>
            {# The AI-generated markdown, converted to HTML, will be inserted here #}
            {{ html_content | safe }}
        </body>
        </html>
    """)
}


# --- PDF Conversion Function ---
def convert_html_to_pdf(source_html):
    """Converts HTML string to a PDF byte stream."""
    result_file = BytesIO()
    pisa_status = pisa.CreatePDF(source_html, dest=result_file)
    if pisa_status.err:
        st.error(f"PDF creation error: {pisa_status.err}")
        return None
    return result_file.getvalue()


# --- Dynamic Entry Management Functions ---

def display_and_manage_entries(entry_type, entries_list, edit_idx_key):
    """Generic function to display, edit, and delete entries."""
    if entries_list:
        st.subheader(f"Your Added {entry_type} Entries:")
        for i, entry in enumerate(entries_list):
            col1, col2, col3 = st.columns([0.7, 0.15, 0.15])
            with col1:
                if entry_type == "Work Experience":
                    st.markdown(f"**{entry['job']}** at {entry['organization']} ({entry['start_date']} - {entry['end_date']})")
                elif entry_type == "Education":
                    st.markdown(f"**{entry['degree']}** in {entry['course']} from {entry['school']} ({entry['grad_date']})")
                elif entry_type == "Certifications":
                    st.markdown(f"**{entry['title']}** ({entry['date']})")
                elif entry_type == "Professional Affiliations":
                    st.markdown(f"**{entry['body']}** (Joined: {entry['date']})")
            
            with col2:
                if col2.button("Edit", key=f"edit_{entry_type}_{i}"):
                    st.session_state[edit_idx_key] = i
                    st.rerun() # Rerun to populate fields for editing
            with col3:
                if col3.button("Delete", key=f"delete_{entry_type}_{i}"):
                    entries_list.pop(i)
                    st.toast(f"{entry_type} Entry Deleted", icon="🗑️")
                    st.rerun() # Rerun to refresh the list

# --- Callback for enhancing job responsibilities/projects ---
def enhance_job_description_callback(responsibilities_key, projects_key, target_position, temperature_value):
    """
    Callback function to enhance job responsibilities and projects using AI.
    Updates the respective session state keys.
    """
    current_responsibilities = st.session_state.get(responsibilities_key, "")
    current_projects = st.session_state.get(projects_key, "")

    if not current_responsibilities and not current_projects:
        st.warning("Please enter some responsibilities or projects to enhance.")
        return

    enhance_prompt = f"""
    You are an expert resume bullet point writer. Take the following raw job responsibilities and projects
    and rewrite them into 3-5 concise, **achievement-oriented bullet points**.
    **Crucially, incorporate quantifiable results and metrics where appropriate. If specific numbers are not available, invent plausible but realistic numbers/percentages (e.g., 'increased X by 15%', 'reduced Y by 20%', 'managed $10K budget').**
    Use strong action verbs and focus on impact and results.
    The target position is "{target_position}".

    Responsibilities:
    {current_responsibilities}

    Projects:
    {current_projects}

    Return only the bullet points, formatted as a markdown unordered list.
    Example:
    - Spearheaded content strategy for social media platforms, resulting in a **25% growth in followers** and a **15% increase in engagement**.
    - Managed the end-to-end content creation and distribution process for the Nigerian 2023 elections, ensuring timely and accurate information dissemination to **over 1 million viewers**.
    """
    # Call AI without schema for this text enhancement
    enhanced_text = _call_gemini_api(enhance_prompt, temperature=temperature_value, response_mime_type="text/plain")
    if enhanced_text:
        st.session_state[responsibilities_key] = enhanced_text
        st.session_state[projects_key] = "" # Clear projects after combining/enhancing
        st.toast("Responsibilities/Projects enhanced!", icon="✨")
        st.rerun() # Rerun to display the updated text areas


def add_edit_job_experience():
    """Form for adding/editing work experience."""
    is_editing = st.session_state.edit_job_idx is not None
    current_entry = st.session_state.job_entries[st.session_state.edit_job_idx] if is_editing else {}

    # Define unique keys for text areas based on whether editing or adding
    responsibility_input_key = f"responsibility_input_{st.session_state.edit_job_idx}"
    project_input_key = f"project_input_{st.session_state.edit_job_idx}"

    st.subheader(f"{'Edit' if is_editing else 'Add'} Work Experience")
    with st.container(border=True):
        col_job, col_org, col_loc = st.columns(3)
        job_title = col_job.text_input("Job Title", value=current_entry.get('job', ''), key=f"job_title_input_{st.session_state.edit_job_idx}")
        organization = col_org.text_input("Organization", value=current_entry.get('organization', ''), key=f"org_input_{st.session_state.edit_job_idx}")
        location = col_loc.selectbox("Location", ("Onsite", 'Remote', 'Hybrid'), index=["Onsite", 'Remote', 'Hybrid'].index(current_entry.get('location', 'Onsite')), key=f"loc_select_{st.session_state.edit_job_idx}")

        col_stdate, col_enddate, col_current = st.columns([1, 1, 0.5])
        start_date = col_stdate.date_input("Role Start Date", value=datetime.date.fromisoformat(current_entry['start_date']) if 'start_date' in current_entry else datetime.date.today(), key=f"start_date_input_{st.session_state.edit_job_idx}")
        
        # "Currently Working Here" checkbox logic
        is_current_role = col_current.checkbox("Current Role?", value=("Present" in current_entry.get('end_date', '')), key=f"current_role_checkbox_{st.session_state.edit_job_idx}")
        
        end_date_value = datetime.date.fromisoformat(current_entry['end_date']) if 'end_date' in current_entry and current_entry['end_date'] != "Present" else datetime.date.today()
        end_date = col_enddate.date_input("Role End Date", value=end_date_value, disabled=is_current_role, key=f"end_date_input_{st.session_state.edit_job_idx}")
        
        if is_current_role:
            final_end_date = "Present"
        else:
            final_end_date = str(end_date)

        # Initialize text area values in session state if they don't exist
        if responsibility_input_key not in st.session_state:
            st.session_state[responsibility_input_key] = current_entry.get('responsibilities', '')
        if project_input_key not in st.session_state:
            st.session_state[project_input_key] = current_entry.get('projects', '')

        responsibilities = st.text_area("Key Responsibilities (Use bullet points for clarity)", value=st.session_state[responsibility_input_key], height=100, key=responsibility_input_key)
        projects = st.text_area("Projects (Separate with new lines, use bullet points)", value=st.session_state[project_input_key], height=100, key=project_input_key)

        col_buttons = st.columns(3)
        if col_buttons[0].button(f"{'Update' if is_editing else 'Add'} Role", key=f"add_update_job_btn_{st.session_state.edit_job_idx}"):
            new_job_entry = {
                'job': job_title,
                'organization': organization,
                'location': location,
                'start_date': str(start_date),
                'end_date': final_end_date,
                'responsibilities': st.session_state[responsibility_input_key], # Use value from session state
                'projects': st.session_state[project_input_key], # Use value from session state
            }
            if is_editing:
                st.session_state.job_entries[st.session_state.edit_job_idx] = new_job_entry
                st.session_state.edit_job_idx = None
                st.toast("Work Experience Updated Successfully", icon="✅")
            else:
                st.session_state.job_entries.append(new_job_entry)
                st.toast("Work Experience Added Successfully", icon="✅")
            st.rerun() # Rerun after adding/updating to clear form or refresh list
        
        # Use on_click for the "Enhance with AI" button
        if col_buttons[1].button(
            "Enhance with AI (Add Quantifiers)",
            key=f"enhance_job_btn_{st.session_state.edit_job_idx}",
            on_click=enhance_job_description_callback,
            args=(
                responsibility_input_key,
                project_input_key,
                st.session_state.get('position_input', 'General Role'), # Get target position from session state
                st.session_state.get('ai_temperature_slider', 0.7) # Get AI temperature from session state
            )
        ):
            pass # Logic is now in the callback


        if is_editing and col_buttons[2].button("Cancel Edit", key=f"cancel_job_edit_btn_{st.session_state.edit_job_idx}"):
            st.session_state.edit_job_idx = None
            st.rerun()

def add_edit_edu_experience():
    """Form for adding/editing education."""
    is_editing = st.session_state.edit_edu_idx is not None
    current_entry = st.session_state.edu_entries[st.session_state.edit_edu_idx] if is_editing else {}

    st.subheader(f"{'Edit' if is_editing else 'Add'} Education")
    with st.container(border=True):
        col_school, col_course, col_deg = st.columns(3)
        school = col_school.text_input("Institution", value=current_entry.get('school', ''), key=f"school_input_{st.session_state.edit_edu_idx}")
        course = col_course.text_input("Course Studied", value=current_entry.get('course', ''), key=f'course_input_{st.session_state.edit_edu_idx}')
        degree = col_deg.selectbox("Degree Awarded", ("BSc", "ND", "HND", "MSc", "PhD", "Other"), index=["BSc", "ND", "HND", "MSc", "PhD", "Other"].index(current_entry.get('degree', 'BSc')), key=f"degree_select_{st.session_state.edit_edu_idx}")
        
        col_grad, col_gpa = st.columns(2)
        graduation_date = col_grad.date_input("Convocation Date", value=datetime.date.fromisoformat(current_entry['grad_date']) if 'grad_date' in current_entry else datetime.date.today(), key=f"graduation_date_input_{st.session_state.edit_edu_idx}")
        gpa = col_gpa.number_input("Grade Point Average (e.g., 3.50)", value=float(current_entry.get('GPA', 0.0)) if 'GPA' in current_entry else 0.0, format="%0.2f", key=f'gpa_input_{st.session_state.edit_edu_idx}')

        col_buttons = st.columns(2)
        if col_buttons[0].button(f"{'Update' if is_editing else 'Add'} Education", key=f"add_update_edu_btn_{st.session_state.edit_edu_idx}"):
            new_edu_entry = {
                'school': school,
                'grad_date': str(graduation_date),
                'degree': degree,
                'course': course,
                'GPA': gpa
            }
            if is_editing:
                st.session_state.edu_entries[st.session_state.edit_edu_idx] = new_edu_entry
                st.session_state.edit_edu_idx = None
                st.toast("Education Updated Successfully", icon="✅")
            else:
                st.session_state.edu_entries.append(new_edu_entry)
                st.toast("Education Added Successfully", icon="✅")
            st.rerun()
        
        if is_editing and col_buttons[1].button("Cancel Edit", key=f"cancel_edu_edit_btn_{st.session_state.edit_edu_idx}"):
            st.session_state.edit_edu_idx = None
            st.rerun()

def add_edit_certifications():
    """Form for adding/editing certifications."""
    is_editing = st.session_state.edit_cert_idx is not None
    current_entry = st.session_state.cert_entries[st.session_state.edit_cert_idx] if is_editing else {}

    st.subheader(f"{'Edit' if is_editing else 'Add'} Certification")
    with st.container(border=True):
        col_title, col_link, col_date = st.columns(3)
        title = col_title.text_input("Certificate Name", value=current_entry.get('title', ''), key=f'title_input_{st.session_state.edit_cert_idx}')
        link = col_link.text_input("Link to Certificate", value=current_entry.get('link', ''), key=f'link_input_{st.session_state.edit_cert_idx}')
        date = col_date.date_input("Date Issued", value=datetime.date.fromisoformat(current_entry['date']) if 'date' in current_entry else datetime.date.today(), key=f'cert_date_input_{st.session_state.edit_cert_idx}')
        
        desc = st.text_area("Description", value=current_entry.get('description', ''), height=80, key=f'des_input_{st.session_state.edit_cert_idx}')

        col_buttons = st.columns(2)
        if col_buttons[0].button(f"{'Update' if is_editing else 'Add'} Certification", key=f"add_update_cert_btn_{st.session_state.edit_cert_idx}"):
            new_cert_entry = {
                'title': title,
                'link': link,
                'date': str(date),
                'description': desc
            }
            if is_editing:
                st.session_state.cert_entries[st.session_state.edit_cert_idx] = new_cert_entry
                st.session_state.edit_cert_idx = None
                st.toast("Certification Updated Successfully", icon="✅")
            else:
                st.session_state.cert_entries.append(new_cert_entry)
                st.toast("Certification Added Successfully", icon="✅")
            st.rerun()
        
        if is_editing and col_buttons[1].button("Cancel Edit", key=f"cancel_cert_edit_btn_{st.session_state.edit_cert_idx}"):
            st.session_state.edit_cert_idx = None
            st.rerun()

def add_edit_prof_affiliations():
    """Form for adding/editing professional affiliations."""
    is_editing = st.session_state.edit_prof_affl_idx is not None
    current_entry = st.session_state.prof_affl[st.session_state.edit_prof_affl_idx] if is_editing else {}

    st.subheader(f"{'Edit' if is_editing else 'Add'} Professional Affiliation")
    with st.container(border=True):
        col_body, col_date = st.columns(2)
        body = col_body.text_input("Association Name", value=current_entry.get('body', ''), key=f'body_input_{st.session_state.edit_prof_affl_idx}')
        date = col_date.date_input("Date Joined", value=datetime.date.fromisoformat(current_entry['date']) if 'date' in current_entry else datetime.date.today(), key=f'date_input_{st.session_state.edit_prof_affl_idx}')

        col_buttons = st.columns(2)
        if col_buttons[0].button(f"{'Update' if is_editing else 'Add'} Association", key=f"add_update_prof_btn_{st.session_state.edit_prof_affl_idx}"):
            new_entry = {
                'body': body,
                'date': str(date)
            }
            if is_editing:
                st.session_state.prof_affl[st.session_state.edit_prof_affl_idx] = new_entry
                st.session_state.edit_prof_affl_idx = None
                st.toast("Association Updated Successfully", icon="✅")
            else:
                st.session_state.prof_affl.append(new_entry)
                st.toast("Association Added Successfully", icon="✅")
            st.rerun()
        
        if is_editing and col_buttons[1].button("Cancel Edit", key=f"cancel_prof_edit_btn_{st.session_state.edit_prof_affl_idx}"):
            st.session_state.edit_prof_affl_idx = None
            st.rerun()

# --- Callback for adding suggested skills ---
def add_selected_skills_to_tech_callback():
    """
    Callback function to add selected skills to the technical skills text area.
    This function is called when the 'Add Selected Skills' button is clicked.
    """
    current_tech_skills = [s.strip() for s in st.session_state.tech_textarea.split(',') if s.strip()]
    selected_new_skills = st.session_state.suggested_skills_multiselect
    new_tech_skills = list(set(current_tech_skills + selected_new_skills)) 
    st.session_state.tech_textarea = ", ".join(new_tech_skills)
    st.session_state.suggested_skills = [] # Clear suggestions after adding
    st.toast("Skills added!", icon="✔️")

# --- Callback for enhancing career summary ---
def enhance_summary_callback(summary_key, description_key, position_key, temperature_value):
    """
    Callback function to enhance the career summary using AI, making it job-specific.
    """
    current_summary = st.session_state.get(summary_key, "")
    job_description = st.session_state.get(description_key, "")
    target_position = st.session_state.get(position_key, "")

    if not current_summary or not job_description or not target_position:
        st.warning("Please provide a current Career Goal/Summary, Job Description, and Target Position to enhance the summary.")
        return

    summary_prompt = f"""
    You are an expert resume writer. Refine the following career summary to be highly
    tailored and impactful for a "{target_position}" role, based on the provided job description.
    Focus on aligning the summary with key requirements and keywords from the job description.
    Keep it concise (2-4 sentences).

    Current Career Summary:
    {current_summary}

    Target Position: {target_position}

    Job Description:
    {job_description}

    Provide only the refined career summary.
    """
    refined_summary = _call_gemini_api(summary_prompt, temperature=temperature_value, response_mime_type="text/plain")
    if refined_summary:
        st.session_state[summary_key] = refined_summary
        st.toast("Career Summary enhanced!", icon="✨")
        st.rerun()


# --- Main Application Layout ---
tab1, tab2 = st.tabs(["📝 Enter Your Details", "✨ Generate & Download"])

with tab1:
    st.header("Personal Information")
    with st.container(border=True):
        # Use session state to persist input values across reruns
        full_name = st.text_input("Full Name", placeholder="e.g. Ayomide Stephen", key='full_name_input')
        email_address = st.text_input("Email Address", key='email_address_input')
        linkedin = st.text_input("Link to LinkedIn Profile", key='linkedin_input')
        portfolio_link_website = st.text_input("Portfolio Link (if applicable)", key='portfolio_link_website_input')
        location = st.selectbox("Preferred Mode of Work", ("Work from Home", "Onsite", "Hybrid"), key='location_select')
        positon = st.text_input("Position Applying For", key='position_input')
        description = st.text_area("Job Description (Paste from Job Posting)", height=150, key='description_textarea')
        
        # Career Summary with AI Enhancement button
        summary = st.text_area(
            "Career Goal / Summary (A brief statement summarizing your career goals or personal branding.)",
            height=100,
            key='summary_textarea',
            value=st.session_state.get('summary_textarea', '')
        )
        if st.button(
            "Enhance Summary with AI",
            on_click=enhance_summary_callback,
            args=(
                'summary_textarea',
                'description_textarea',
                'position_input',
                st.session_state.get('ai_temperature_slider', 0.7)
            )
        ):
            pass

        tech = st.text_area(
            "Technical Skills (Comma-separated, e.g., Python, SQL, AWS, Machine Learning)",
            height=80,
            key='tech_textarea', 
            value=st.session_state.get('tech_textarea', '') 
        )
    
    # AI-Powered Skill Suggestions
    st.header("Skill Suggestions")
    with st.container(border=True):
        if st.button("Get AI Skill Suggestions (Based on Job Description)"):
            if description:
                skills_prompt = f"""
                Based on the following job description for a {positon} role, suggest a list of 10-15 highly relevant
                technical and soft skills. Provide them as a comma-separated list.

                Job Description:
                {description}
                """
                suggested_skills_text = _call_gemini_api(skills_prompt, temperature=st.session_state.get('ai_temperature_slider', 0.7), response_mime_type="text/plain") 
                if suggested_skills_text:
                    st.session_state.suggested_skills = [s.strip() for s in suggested_skills_text.split(',') if s.strip()]
                    st.toast("Skills suggested!", icon="💡")
            else:
                st.warning("Please provide a Job Description to get skill suggestions.")

        if st.session_state.suggested_skills:
            st.write("Select skills to add to your Technical Skills:")
            selected_new_skills_multiselect = st.multiselect(
                "Suggested Skills",
                options=[s for s in st.session_state.suggested_skills if s not in [t.strip() for t in st.session_state.tech_textarea.split(',')]], 
                key='suggested_skills_multiselect'
            )
            if st.button("Add Selected Skills to Technical Skills", on_click=add_selected_skills_to_tech_callback):
                pass 


    st.header("Work Experience")
    with st.expander("Add New Work Experience", expanded=(st.session_state.edit_job_idx is not None)):
        add_edit_job_experience()
    display_and_manage_entries("Work Experience", st.session_state.job_entries, 'edit_job_idx')

    st.header("Education")
    with st.expander("Add New Education", expanded=(st.session_state.edit_edu_idx is not None)):
        add_edit_edu_experience()
    display_and_manage_entries("Education", st.session_state.edu_entries, 'edit_edu_idx')

    st.header("Certifications")
    with st.expander("Add New Certification", expanded=(st.session_state.edit_cert_idx is not None)):
        add_edit_certifications()
    display_and_manage_entries("Certifications", st.session_state.cert_entries, 'edit_cert_idx')

    st.header("Professional Affiliations")
    with st.expander("Add New Professional Affiliation", expanded=(st.session_state.edit_prof_affl_idx is not None)):
        add_edit_prof_affiliations()
    display_and_manage_entries("Professional Affiliations", st.session_state.prof_affl, 'edit_prof_affl_idx')

    st.markdown("---")
    st.header("Data Management")
    col_save, col_load = st.columns(2)
    with col_save:
        # Consolidate all user inputs for saving
        current_data = {
            'name': full_name,
            'mail': email_address,
            'linkedin': linkedin,
            'portfolio_link_website': portfolio_link_website,
            'location': location,
            'position': positon,
            'description': description,
            'summary': st.session_state.summary_textarea, # Get value from session state
            'tech': st.session_state.tech_textarea, # Get value from session state
            'work experience': st.session_state.job_entries,
            'Educational Experience': st.session_state.edu_entries,
            'Certifications': st.session_state.cert_entries,
            'Professional Affiliations': st.session_state.prof_affl
        }
        save_user_data(current_data, f"{full_name.replace(' ', '_') if full_name else 'my_resume_data'}.json")
    with col_load:
        uploaded_file = st.file_uploader("Upload Data (JSON)", type="json", help="Upload a previously saved .json file to restore your data.")
        load_user_data(uploaded_file)


with tab2:
    st.header("Generate Your Documents")
    
    # Consolidate all user inputs for AI prompt
    # Ensure all data is pulled from session_state for consistency
    var_for_ai = {
        'name': st.session_state.get('full_name_input', ''),
        'mail': st.session_state.get('email_address_input', ''),
        'linkedin': st.session_state.get('linkedin_input', ''),
        'portfolio_link_website': st.session_state.get('portfolio_link_website_input', ''),
        'location': st.session_state.get('location_select', 'Work from Home'),
        'position': st.session_state.get('position_input', ''),
        'description': st.session_state.get('description_textarea', ''),
        'summary': st.session_state.get('summary_textarea', ''), # Get value from session state
        'tech': st.session_state.get('tech_textarea', ''), # Get value from session state
        'work experience': st.session_state.job_entries,
        'Educational Experience': st.session_state.edu_entries,
        'Certifications': st.session_state.cert_entries,
        'Professional Affiliations': st.session_state.prof_affl
    }

    # AI Temperature Slider
    ai_temperature = st.slider(
        "AI Creativity (Temperature)",
        min_value=0.0,
        max_value=1.0,
        value=0.7,
        step=0.05,
        key='ai_temperature_slider', 
        help="Higher values (e.g., 1.0) make the AI's output more creative/random. Lower values (e.g., 0.2) make it more focused and deterministic."
    )

    # --- Resume Generation ---
    st.subheader("Generate Resume")
    if st.button("Generate Resume", key="generate_resume_main_btn"):
        # Basic validation for essential fields
        missing_fields = []
        if not var_for_ai['name']: missing_fields.append("Full Name")
        if not var_for_ai['mail']: missing_fields.append("Email Address")
        if not var_for_ai['position']: missing_fields.append("Position Applying For")
        if not var_for_ai['description']: missing_fields.append("Job Description")
        if not var_for_ai['summary']: missing_fields.append("Career Goal/Summary")
        if not var_for_ai['tech']: missing_fields.append("Technical Skills")
        
        if not st.session_state.job_entries: missing_fields.append("at least one Work Experience")
        if not st.session_state.edu_entries: missing_fields.append("at least one Education entry")

        if missing_fields:
            st.warning(f"Please fill in the following required fields before generating: {', '.join(missing_fields)}")
        else:
            resume_prompt = f"""
            You are a seasoned and master resume creator with expert-level knowledge of modern hiring trends and resume formatting.
            Based on the provided user data and job description, generate a tailored, ATS-compliant, job-specific resume.

            **Crucially, output the entire resume content using professional Markdown syntax.**
            Do not include any conversational text, explanations, or Markdown code block fences (```markdown).
            Just provide the Markdown content of the resume.

            Use appropriate Markdown:
            - **Name:** Start with `# {var_for_ai['name']}`.
            - **Contact Info Line (IMPORTANT):** Immediately after the name, output this specific HTML structure for contact info:
                `<div class="contact-info-line">{var_for_ai['mail']} | <a href="{var_for_ai['linkedin']}">LinkedIn</a> {var_for_ai['portfolio_link_website']}  | <a href="{var_for_ai['portfolio_link_website']}">Portfolio</a> | {var_for_ai['location']}</div>`
                Ensure all user data is directly injected into this HTML string, and the `<a>` tags are correct.
            - **Major Sections:** Use `##` for sections like "Summary", "Skills", "Experience", "Education", "Certifications", "Professional Affiliations".
            - **Sub-headings:** Use `###` for job titles/degrees.
            - **Bullet points:** Use `-` for responsibilities, projects, and list items.
            - **Bold text:** Use `**text**` for emphasis (e.g., skill categories, company names in bold where appropriate).
            - **Consistent formatting for dates:** (e.g., "Jan 2020 – Present", "May 2022").

            **MANDATORY QUANTIFIERS IN EXPERIENCE SECTION**:
            For each responsibility or achievement in the Experience section, **invent plausible but realistic numbers, percentages, or metrics if none are explicitly provided by the user.** These should demonstrate impact and results.
            Example for a responsibility: `- Developed and maintained scalable web applications using Python and Django, leading to a **15% improvement in application performance** and **processing over 10,000 transactions daily**.`

            User Information:
            Name: {var_for_ai['name']}
            Email: {var_for_ai['mail']}
            LinkedIn: {var_for_ai['linkedin']}
            Portfolio: {var_for_ai['portfolio_link_website']}
            Location: {var_for_ai['location']}
            Target Position: {var_for_ai['position']}
            Job Description: {var_for_ai['description']}
            Career Summary: {var_for_ai['summary']}
            Technical Skills (from user): {var_for_ai['tech']}
            Work Experience (from user, summarize key points for AI to expand): {json.dumps(var_for_ai['work experience'], indent=2)}
            Education (from user): {json.dumps(var_for_ai['Educational Experience'], indent=2)}
            Certifications (from user): {json.dumps(var_for_ai['Certifications'], indent=2)}
            Professional Affiliations (from user): {json.dumps(var_for_ai['Professional Affiliations'], indent=2)}

            **BEGIN RESUME MARKDOWN OUTPUT**
            """
            generated_text = _call_gemini_api(resume_prompt, temperature=ai_temperature, response_mime_type="text/plain")
            if generated_text:
                st.session_state.generated_resume_content = generated_text
                st.toast("Resume Generated Successfully!", icon="📄")
            else:
                st.error("Failed to generate resume. Please check the API response or try again.")
    
    if st.session_state.generated_resume_content:
        # Display the Markdown output directly in a text area
        st.text_area("Your Generated Resume", value=st.session_state.generated_resume_content, height=500, key="generated_resume_display")

        st.subheader("Refine Resume (Optional)")
        refinement_request = st.text_input(
            "Enter your refinement request (e.g., 'Make the summary more concise', 'Expand on the data analysis skills')",
            key="refinement_input"
        )
        if st.button("Refine Resume"):
            if refinement_request:
                refine_prompt = f"""
                You are an expert resume writer. Please refine the following resume content based on the user's request.
                Maintain a professional, **Markdown** format.
                Do not include any conversational text or Markdown code block fences (```markdown).

                Original Resume Content:
                {st.session_state.generated_resume_content}

                Refinement Request:
                {refinement_request}

                Provide the refined resume content in Markdown, ensuring continued use of quantifiable results where appropriate.
                """
                refined_text = _call_gemini_api(refine_prompt, temperature=ai_temperature, response_mime_type="text/plain")
                if refined_text:
                    st.session_state.generated_resume_content = refined_text
                    st.toast("Resume Refined!", icon="✏️")
                    st.rerun()
            else:
                st.warning("Please enter a refinement request.")
        
        st.subheader("Download Resume as PDF or Plain Text for Editing")
        
        # Resume template selector (reinstated)
        selected_template_name = st.selectbox(
            "Choose Resume Layout/Style (for PDF)",
            list(RESUME_TEMPLATES.keys()),
            key="resume_template_select"
        )

        col_pdf, col_txt = st.columns(2)
        with col_pdf:
            if st.button("Download PDF", key="download_resume_pdf_btn"):
                if st.session_state.generated_resume_content:
                    # Convert AI-generated Markdown to HTML
                    # Note: The 'markdown' library will parse the HTML <div> we asked the AI to output correctly.
                    html_from_markdown = markdown.markdown(st.session_state.generated_resume_content)
                    
                    # Render the final HTML for PDF using the chosen Jinja2 template
                    selected_template = RESUME_TEMPLATES[selected_template_name]
                    rendered_html = selected_template.render(html_content=html_from_markdown) # Pass the converted HTML

                    pdf_file_bytes = convert_html_to_pdf(rendered_html)
                    if pdf_file_bytes:
                        st.download_button(
                            "Download Resume PDF",
                            data=pdf_file_bytes,
                            file_name=f"{var_for_ai['name'].replace(' ', '_') if var_for_ai['name'] else 'resume'}_{selected_template_name.lower().replace(' ', '_')}.pdf",
                            mime="application/pdf"
                        )
                    else:
                        st.error("Failed to generate PDF from AI content.")
                else:
                    st.warning("Please generate a resume first before downloading.")
        with col_txt:
            # New button for downloading as plain text
            if st.button("Download as Text File (for Word/Docs)", key="download_resume_txt_btn"):
                if st.session_state.generated_resume_content:
                    # The AI-generated content is already Markdown, which is essentially plain text
                    text_content = st.session_state.generated_resume_content.replace('**', '').replace('*', '').replace('[', '').replace(']', '') # Remove markdown bolding/links for cleaner plain text
                    
                    st.download_button(
                        "Download Resume Text",
                        data=text_content.encode("utf-8"),
                        file_name=f"{var_for_ai['name'].replace(' ', '_') if var_for_ai['name'] else 'resume'}_for_editing.txt",
                        mime="text/plain"
                    )
                    st.info("You can open this `.txt` file in Microsoft Word, Google Docs, or LibreOffice Writer and then save it as a `.docx` file for further editing and formatting.")
                else:
                    st.warning("Please generate a resume first before downloading.")


    # --- Cover Letter Generation ---
    st.subheader("Generate Cover Letter")
    if st.button("Generate Cover Letter", key="generate_cover_letter_btn"):
        # Basic validation for essential fields for cover letter
        cl_missing_fields = []
        if not var_for_ai['name']: cl_missing_fields.append("Full Name")
        if not var_for_ai['mail']: cl_missing_fields.append("Email Address")
        if not var_for_ai['position']: cl_missing_fields.append("Position Applying For")
        if not var_for_ai['description']: cl_missing_fields.append("Job Description")
        if not var_for_ai['summary']: cl_missing_fields.append("Career Goal/Summary")
        
        if cl_missing_fields:
            st.warning(f"Please fill in the following required fields for the cover letter: {', '.join(cl_missing_fields)}")
        else:
            cover_letter_prompt = f"""
            You are an expert cover letter writer. Draft a professional, compelling cover letter for the following job application.
            Tailor it to the job description and highlight how the user's experience and skills are a perfect match.

            User Information:
            Name: {var_for_ai['name']}
            Email: {var_for_ai['mail']}
            LinkedIn: {var_for_ai['linkedin']}
            Portfolio: {var_for_ai['portfolio_link_website']}
            Location: {var_for_ai['location']}
            Target Position: {var_for_ai['position']}
            Job Description: {var_for_ai['description']}
            Career Summary: {var_for_ai['summary']}
            Technical Skills: {var_for_ai['tech']}
            Work Experience (brief summary for context): {', '.join([f"{exp['job']} at {exp['organization']}" for exp in var_for_ai['work experience'][:2]]) if var_for_ai['work experience'] else 'N/A'}
            Education (brief summary for context): {', '.join([f"{edu['degree']} from {edu['school']}" for edu in var_for_ai['Educational Experience'][:1]]) if var_for_ai['Educational Experience'] else 'N/A'}

            Structure the letter with:
            1.  Your Contact Information
            2.  Date
            3.  Hiring Manager/Company Address (use placeholders if not provided, e.g., "Hiring Manager" "Company Name")
            4.  Salutation
            5.  Opening Paragraph: State the position you're applying for and where you saw it, expressing enthusiasm.
            6.  Body Paragraphs (2-3): Connect your key skills and experiences (especially from job description) to the job requirements. Use specific examples.
            7.  Closing Paragraph: Reiterate interest, mention enclosed resume, and express eagerness for an interview.
            8.  Professional Closing and Your Name.
            """
            generated_cl_text = _call_gemini_api(cover_letter_prompt, temperature=ai_temperature, response_mime_type="text/plain")
            if generated_cl_text:
                st.session_state.generated_cover_letter_content = generated_cl_text
                st.toast("Cover Letter Generated Successfully!", icon="✉️")

    if st.session_state.generated_cover_letter_content:
        st.text_area("Your Generated Cover Letter", value=st.session_state.generated_cover_letter_content, height=500, key="generated_cover_letter_display")
        
        if st.download_button(
            "Download Cover Letter (Text File)",
            data=st.session_state.generated_cover_letter_content.encode("utf-8"),
            file_name=f"{var_for_ai['name'].replace(' ', '_') if var_for_ai['name'] else 'cover_letter'}_generated.txt",
            mime="text/plain"
        ):
            st.toast("Cover Letter Downloaded!", icon="📩")

