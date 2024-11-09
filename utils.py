import os
import requests
import json
import re

import streamlit as st

headers = {
    'Content-Type': 'application/json',
    'Accept': '*/*'
}

def thumbs_feedback(feedback, **kwargs):
    """
    Sends feedback to Amplitude Analytics
    """
    
    send_amplitude_data(
        user_query=kwargs.get("user_query", "No user input"),
        chat_response=kwargs.get("chat_response", "No bot response"),
        demo_name=kwargs.get("demo_name", "Unknown"),
        language = kwargs.get("response_language", "Unknown"),
        feedback=feedback["score"],
    )    
    st.session_state.feedback_key += 1

def send_amplitude_data(user_query, chat_response, demo_name, language, feedback=None):
    amplitude_api_key = os.getenv('AMPLITUDE_TOKEN')
    if not amplitude_api_key:
        return
    data = {
        "api_key": amplitude_api_key,
        "events": [{
            "device_id": st.session_state.device_id,
            "event_type": "submitted_query",
            "event_properties": {
                "Space Name": demo_name,
                "Demo Type": "chatbot",
                "query": user_query,
                "response": chat_response,
                "Response Language": language
            }
        }]
    }
    if feedback:
        data["events"][0]["event_properties"]["feedback"] = feedback

    response = requests.post('https://api2.amplitude.com/2/httpapi', headers=headers, data=json.dumps(data))
    if response.status_code != 200:
        print(f"Amplitude request failed with status code {response.status_code}. Response Text: {response.text}")

def escape_dollars_outside_latex(text):
    # Define a regex pattern to find LaTeX equations (either single $ or double $$)
    pattern = re.compile(r'(\$\$.*?\$\$|\$.*?\$)')
    latex_matches = pattern.findall(text)
    
    # Placeholder to temporarily store LaTeX equations
    placeholders = {}
    for i, match in enumerate(latex_matches):
        placeholder = f'__LATEX_PLACEHOLDER_{i}__'
        placeholders[placeholder] = match
        text = text.replace(match, placeholder)
    
    # Escape dollar signs in the rest of the text
    text = text.replace('$', '\\$')
    
    # Replace placeholders with the original LaTeX equations
    for placeholder, original in placeholders.items():
        text = text.replace(placeholder, original)
    return text