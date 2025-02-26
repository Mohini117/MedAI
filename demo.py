import streamlit as st
import base64
import json
import re
import pandas as pd
from pathlib import Path
from together import Together
from dotenv import load_dotenv
import os
import speech_recognition as sr
from gtts import gTTS
import tempfile
import time
import threading
import io

# Load environment variables
load_dotenv()

# User authentication system
USER_FILE = "users.json"

def load_users():
    if not os.path.exists(USER_FILE):
        return {}
    with open(USER_FILE, "r") as f:
        return json.load(f)

def save_users(users):
    with open(USER_FILE, "w") as f:
        json.dump(users, f)

def authenticate_user(username, password):
    users = load_users()
    return users.get(username) == password

def register_user(username, password):
    users = load_users()
    if username in users:
        return False  # User already exists
    users[username] = password
    save_users(users)
    return True

def login_page():
    st.title("🔐 Login to Medical Image Analysis")
    choice = st.radio("Select an option", ["Login", "Register"])
    
    if choice == "Login":
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        login_button = st.button("Login")
        
        if login_button:
            if authenticate_user(username, password):
                st.session_state["authenticated"] = True
                st.session_state["username"] = username
                st.rerun()
            else:
                st.error("Invalid username or password")
    else:
        username = st.text_input("Choose a username")
        password = st.text_input("Choose a password", type="password")
        register_button = st.button("Register")
        
        if register_button:
            if register_user(username, password):
                st.success("Registration successful! You can now log in.")
            else:
                st.error("Username already exists. Choose a different one.")

if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False

if not st.session_state["authenticated"]:
    login_page()
    st.stop()

# Add custom CSS loader
def load_css():
    with open('styles.css') as f:
        st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)

class ImageAnalyzer:
    def __init__(self):
        self.api_key = os.getenv("TOGETHER_API_KEY")
        if not self.api_key:
            st.error("API key not found. Please check your .env file.")
            return
        self.client = Together(api_key=self.api_key)
        
    def encode_image(self, image_file):
        try:
            return base64.b64encode(image_file.read()).decode("utf-8")
        except Exception as e:
            st.error(f"Error encoding image: {str(e)}")
            return None

    def analyze_prescription(self, image_file):
        prompt = """You are a highly accurate AI specialized in extracting structured information from medical prescriptions.  
Your task is to analyze the provided prescription image and return the details in the following strict JSON format:  

{  
    "Date": "<Extracted Date>",  
    "Patient": {  
        "Name": "<Extracted Name>",  
        "Age": "<Extracted Age>"  
    },  
    "Medicines": [  
        {  
            "Type": "<Tablet/Capsule/Syrup/etc.>",  
            "Medicine": "<Medicine Name>",  
            "Dosage": "<Dosage Instructions>",  
            "Timings": [<If `X` is 1, replace it with a morning time (e.g., 8 AM, 9 AM, etc.)>, <If `Y` is 1, replace it with an afternoon time (e.g., 1 PM, 2 PM, etc.)>, <If `Z` is 1, replace it with a night/evening time (e.g., 7 PM, 8 PM, etc.).>]  # Extract exact timings as per prescription  
        }  
    ]  
}  

Timings Extraction Rules:  
- If the dosage format is in "X-Y-Z" (e.g., "1-0-1"):  
  - If `X` is 1, replace it with a morning time (e.g., 8 AM, 9 AM, etc.).  
  - If `Y` is 1, replace it with an afternoon time (e.g., 1 PM, 2 PM, etc.).  
  - If `Z` is 1, replace it with a night/evening time (e.g., 7 PM, 8 PM, etc.).  
  - If any of these are 0, do not include a time for that slot.  
- Ensure "Timings" always contains integers only.  
  

Return only the JSON output, without additional text or explanations."""  


        base64_image = self.encode_image(image_file)
        if not base64_image:
            return None

        try:
            response = self.client.chat.completions.create(
                model="meta-llama/Llama-3.2-11B-Vision-Instruct-Turbo",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}},
                        ],
                    }
                ],
                stream=False
            )

            full_response = response.choices[0].message.content
            json_match = re.search(r"\{.*\}", full_response, re.DOTALL)
            if json_match:
                extracted_data = json.loads(json_match.group(0))
                return extracted_data
            return None

        except Exception as e:
            st.error(f"Error analyzing prescription: {str(e)}")
            return None

    def analyze_diagnostic_image(self, image_file):
        prompt = """Analyze the provided medical image and provide analysis in this JSON format:
        {
            "Predicted_Disease": "<Predict accurate name of the Disease/Condition Name>",
            "Confidence_Score": "<AI Confidence Level (0-100%)>",
            "Description": "<Brief explanation of the disease>",
            "Possible_Causes": ["<Cause 1>", "<Cause 2>", "<Cause 3>"],
            "Recommended_Actions": ["<Action 1>", "<Action 2>", "<Action 3>"]
        }
        Ensure the response is accurate and useful for a medical specialist also you are expert in the feild of diagnosis analysis and you can detect things which human diagnostic analyzer can not detect. If the image is unclear, specify that in the Description field."""

        base64_image = self.encode_image(image_file)
        if not base64_image:
            return None

        try:
            response = self.client.chat.completions.create(
                model="meta-llama/Llama-3.2-11B-Vision-Instruct-Turbo",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}},
                        ],
                    }
                ],
                stream=False
            )

            full_response = response.choices[0].message.content
            json_match = re.search(r"\{.*\}", full_response, re.DOTALL)
            if json_match:
                extracted_data = json.loads(json_match.group(0))
                return extracted_data
            return None

        except Exception as e:
            st.error(f"Error analyzing diagnostic image: {str(e)}")
            return None


class VoiceAssistant:
    def __init__(self, llm_client):
        self.recognizer = sr.Recognizer()
        self.client = llm_client  # Store the Together API client correctly
        
        # Initialize session state for voice conversation
        if "voice_conversation" not in st.session_state:
            st.session_state["voice_conversation"] = []
        
    def listen(self):
        with sr.Microphone() as source:
            st.write("🎤 Listening...")
            # Adjust for ambient noise
            self.recognizer.adjust_for_ambient_noise(source)
            audio = self.recognizer.listen(source)
            st.write("Processing...")
            
        try:
            text = self.recognizer.recognize_google(audio)
            return text
        except sr.UnknownValueError:
            return "Sorry, I couldn't understand what you said."
        except sr.RequestError:
            return "Sorry, speech recognition service is unavailable."
    
    def speak(self, text):
        # Using Google Text-to-Speech (gTTS) - a simple TTS solution
        tts = gTTS(text=text, lang='en', slow=False)
        
        # Save the audio to a temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix='.mp3') as fp:
            tts.save(fp.name)
            st.audio(fp.name, format='audio/mp3')
    
    def get_llm_response(self, user_query):
        try:
            conversation_history = ""
            for entry in st.session_state.voice_conversation[-5:]:  # Use last 5 entries for context
                role = "user" if entry["role"] == "user" else "assistant"
                conversation_history += f"{role}: {entry['content']}\n"
            
            prompt = f"""You are a helpful medical assistant for a user as well as image diagnostic specialist. 
            The user is asking a question related to medical images, diagnoses, or the application itself.
            Previous conversation:
            {conversation_history}
            
            User: {user_query}
            
            Provide a clear, concise, and helpful response. If the user is asking about uploading or analyzing images,
            guide them on using the application features. Keep your response under 3 sentences unless detailed medical
            information is required.
            """
            
            response = self.client.chat.completions.create(
                model="meta-llama/Llama-3.2-11B-Instruct",
                messages=[
                    {"role": "system", "content": "You are a helpful, concise medical assistant."},
                    {"role": "user", "content": prompt}
                ],
                stream=False
            )
            
            return response.choices[0].message.content
        except Exception as e:
            st.error(f"Error getting LLM response: {str(e)}")
            return "I'm having trouble connecting to my knowledge base right now. Please try again in a moment."

def voice_assistant_page(analyzer):
    st.markdown('<div class="section-header">', unsafe_allow_html=True)
    st.title("🎙️ Voice Assistant")
    st.write("Ask medical questions using your voice, and get spoken responses")
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Initialize voice assistant
    voice_assistant = VoiceAssistant(analyzer.client)
    
    # Initialize conversation display
    if "voice_conversation" not in st.session_state:
        st.session_state.voice_conversation = []
    
    # Set up a session state for recording
    if "is_listening" not in st.session_state:
        st.session_state.is_listening = False
    
    if "temp_text" not in st.session_state:
        st.session_state.temp_text = ""
    
    # Display conversation history
    with st.container():
        for message in st.session_state.voice_conversation:
            if message["role"] == "user":
                st.markdown(f'<div class="user-message"><strong>You:</strong> {message["content"]}</div>', unsafe_allow_html=True)
            else:
                st.markdown(f'<div class="assistant-message"><strong>Assistant:</strong> {message["content"]}</div>', unsafe_allow_html=True)
    
    # Voice input section
    col1, col2, col3 = st.columns([3, 1, 1])
    
    # Use the session state to control the text value
    # Store any voice recognition results in session_state.temp_text
    # then use that to set the default value of the text_input
    with col1:
        user_text = st.text_input("Type or speak your question:", value=st.session_state.temp_text, key="voice_text_input")
    
    # Function to handle listening
    def start_listening():
        st.session_state.is_listening = True
        st.session_state.temp_text = voice_assistant.listen()
        st.session_state.is_listening = False
    
    with col2:
        listen_button = st.button("🎤 Listen", key="listen_button", on_click=start_listening)
    
    # Process the submission without modifying session state after instantiation
    def submit_message():
        if user_text:
            # Add user message to conversation
            st.session_state.voice_conversation.append({"role": "user", "content": user_text})
            
            # Get response from LLM
            assistant_response = voice_assistant.get_llm_response(user_text)
            
            # Add assistant response to conversation
            st.session_state.voice_conversation.append({"role": "assistant", "content": assistant_response})
            
            # Clear the temporary text for next input
            st.session_state.temp_text = ""
            
            # Speak the response (will happen on rerun)
            st.session_state.speak_response = assistant_response
    
    with col3:
        submit_button = st.button("🔊 Submit", key="submit_button", on_click=submit_message)
    
    # Handle text-to-speech after rerun
    if "speak_response" in st.session_state and st.session_state.speak_response:
        with st.spinner("Speaking..."):
            voice_assistant.speak(st.session_state.speak_response)
        st.session_state.speak_response = None
    
    # Function to clear conversation
    def clear_conversation():
        st.session_state.voice_conversation = []
        st.session_state.temp_text = ""
    
    # Add clear conversation button
    st.button("🗑️ Clear Conversation", on_click=clear_conversation)

    # Add helpful usage tips
    with st.expander("How to use the Voice Assistant"):
        st.write("""
        1. Click the **Listen** button and speak your question clearly
        2. Review the transcribed text to ensure accuracy
        3. Click **Submit** to get a response
        4. The assistant will answer your question both in text and speech
        5. You can also type your question directly in the text input field
        
        Try asking about:
        - How to use the prescription analysis feature
        - What kinds of medical images the system can analyze
        - Common medical conditions and their symptoms
        - How to interpret diagnostic results
        """)

def main():
    st.set_page_config(
        page_title="Medical Image Analysis",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    # Load custom CSS
    load_css()
    
    # Custom styled header
    st.markdown("""
        <div class="main-header">
            <h1>🏥 Medical Image Analysis System</h1>
            <p class="subtitle">AI-Powered Medical Image Analysis</p>
        </div>
    """, unsafe_allow_html=True)
    
    st.sidebar.markdown("""
        <div class="sidebar-header">
            <h3>Navigation</h3>
        </div>
    """, unsafe_allow_html=True)
    
    page = st.sidebar.radio("", ["Prescription Analysis", "Diagnostic Image Analysis", "Voice Assistant"])
    
    analyzer = ImageAnalyzer()

    if page == "Prescription Analysis":
        st.markdown('<div class="section-header">', unsafe_allow_html=True)
        st.title("Prescription Analysis")
        st.write("Upload a prescription image to extract details")
        st.markdown('</div>', unsafe_allow_html=True)
        
        uploaded_file = st.file_uploader("Choose a prescription image", type=["jpg", "jpeg", "png"])
        
        if uploaded_file:
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown('<div class="image-container">', unsafe_allow_html=True)
                st.image(uploaded_file, use_container_width=True, caption="Uploaded Prescription")
                st.markdown('</div>', unsafe_allow_html=True)
            
            with col2:
                if st.button("🔍 Analyze Prescription", type="primary"):
                    with st.spinner("🔄 Processing prescription..."):
                        results = analyzer.analyze_prescription(uploaded_file)
                        
                        if results:
                            st.success("✅ Analysis Complete!")
                            
                            st.markdown('<div class="results-card">', unsafe_allow_html=True)
                            st.subheader("Patient Information")
                            patient_data = results.get('Patient', {})
                            st.write(f"Name: {patient_data.get('Name', 'N/A')}")
                            st.write(f"Age: {patient_data.get('Age', 'N/A')}")
                            st.write(f"Date: {results.get('Date', 'N/A')}")
                            st.markdown('</div>', unsafe_allow_html=True)
                            
                            if results.get('Medicines'):
                                st.markdown('<div class="results-card">', unsafe_allow_html=True)
                                st.subheader("Prescribed Medicines")
                                df = pd.DataFrame(results['Medicines'])
                                st.table(df)
                                st.markdown('</div>', unsafe_allow_html=True)
                            
                            st.download_button(
                                label="⬇️ Download Analysis Report",
                                data=json.dumps(results, indent=4),
                                file_name="prescription_analysis.json",
                                mime="application/json"
                            )
                        else:
                            st.error("❌ Analysis failed. Please try again with a clearer image.")

    elif page == "Diagnostic Image Analysis":
        st.markdown('<div class="section-header">', unsafe_allow_html=True)
        st.title("Diagnostic Image Analysis")
        st.write("Upload a diagnostic image for detailed analysis")
        st.markdown('</div>', unsafe_allow_html=True)
        
        uploaded_file = st.file_uploader("Choose a diagnostic image", type=["jpg", "jpeg", "png"])
        
        if uploaded_file:
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown('<div class="image-container">', unsafe_allow_html=True)
                st.image(uploaded_file, use_container_width=True, caption="Uploaded Diagnostic Image")
                st.markdown('</div>', unsafe_allow_html=True)
            
            with col2:
                if st.button("🔬 Analyze Image", type="primary"):
                    with st.spinner("🔄 Analyzing image..."):
                        results = analyzer.analyze_diagnostic_image(uploaded_file)
                        
                        if results:
                            st.success("✅ Analysis Complete!")
                            
                            st.markdown('<div class="results-card">', unsafe_allow_html=True)
                            st.subheader("Disease Prediction")
                            st.write(f"Predicted Disease: {results.get('Predicted_Disease', 'N/A')}")
                            st.write(f"Confidence Score: {results.get('Confidence_Score', 'N/A')}")
                            st.markdown('</div>', unsafe_allow_html=True)
                            
                            st.markdown('<div class="results-card">', unsafe_allow_html=True)
                            st.subheader("Description")
                            st.write(results.get('Description', 'N/A'))
       
                            st.markdown('</div>', unsafe_allow_html=True)
                            
                            st.markdown('<div class="results-card">', unsafe_allow_html=True)
                            st.subheader("Possible Causes")
                            for cause in results.get('Possible_Causes', []):
                                st.write(f"• {cause}")
                            st.markdown('</div>', unsafe_allow_html=True)
                            
                            st.markdown('<div class="results-card">', unsafe_allow_html=True)
                            st.subheader("Recommended Actions")
                            for action in results.get('Recommended_Actions', []):
                                st.write(f"• {action}")
                            st.markdown('</div>', unsafe_allow_html=True)
                            
                            st.download_button(
                                label="⬇️ Download Analysis Report",
                                data=json.dumps(results, indent=4),
                                file_name="diagnostic_analysis.json",
                                mime="application/json"
                            )
                        else:
                            st.error("❌ Analysis failed. Please try again with a clearer image.")
    
    else:  # Voice Assistant
        voice_assistant_page(analyzer)

if __name__ == "__main__":
    main()  