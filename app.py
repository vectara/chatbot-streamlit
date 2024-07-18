from omegaconf import OmegaConf
from query import VectaraQuery
import os

import streamlit as st
from streamlit_pills import pills

from PIL import Image

max_examples = 6

def isTrue(x) -> bool:
    if isinstance(x, bool):
        return x
    return x.strip().lower() == 'true'

def launch_bot():
    def generate_response(question):
        response = vq.submit_query(question)
        return response
    
    def generate_streaming_response(question):
        response = vq.submit_query_streaming(question)
        return response
    
    def show_example_questions():        
        if len(st.session_state.example_messages) > 0 and st.session_state.first_turn:            
            selected_example = pills("Queries to Try:", st.session_state.example_messages, index=None)
            if selected_example:
                st.session_state.ex_prompt = selected_example
                st.session_state.first_turn = False
                return True
        return False

    if 'cfg' not in st.session_state:
        corpus_keys = str(os.environ['corpus_keys']).split(',')
        cfg = OmegaConf.create({
            'corpus_keys': corpus_keys,
            'api_key': str(os.environ['api_key']),
            'title': os.environ['title'],
            'source_data_desc': os.environ['source_data_desc'],
            'streaming': isTrue(os.environ.get('streaming', False)),
            'prompt_name': os.environ.get('prompt_name', None),
            'examples': os.environ.get('examples', None)
        })
        st.session_state.cfg = cfg
        st.session_state.ex_prompt = None
        st.session_state.first_turn = True        
        example_messages = [example.strip() for example in cfg.examples.split(",")]
        st.session_state.example_messages = [em for em in example_messages if len(em)>0][:max_examples]
        
        st.session_state.vq = VectaraQuery(cfg.api_key, cfg.corpus_keys, cfg.prompt_name)

    cfg = st.session_state.cfg
    vq = st.session_state.vq
    st.set_page_config(page_title=cfg.title, layout="wide")

    # left side content
    with st.sidebar:
        image = Image.open('Vectara-logo.png')
        st.image(image, width=175)
        st.markdown(f"## About\n\n"
                    f"This demo uses Retrieval Augmented Generation to ask questions about {cfg.source_data_desc}\n\n")

        st.markdown("---")
        st.markdown(
            "## How this works?\n"
            "This app was built with [Vectara](https://vectara.com).\n"
            "Vectara's [Indexing API](https://docs.vectara.com/docs/api-reference/indexing-apis/indexing) was used to ingest the data into a Vectara corpus (or index).\n\n"
            "This app uses Vectara [Chat API](https://docs.vectara.com/docs/console-ui/vectara-chat-overview) to query the corpus and present the results to you, answering your question.\n\n"
        )
        st.markdown("---")
        

    st.markdown(f"<center> <h2> Vectara AI Assistant: {cfg.title} </h2> </center>", unsafe_allow_html=True)

    if "messages" not in st.session_state.keys():
        st.session_state.messages = [{"role": "assistant", "content": "How may I help you?"}]
                
    # Display chat messages
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.write(message["content"])

    example_container = st.empty()
    with example_container:
        if show_example_questions():
            example_container.empty()
            st.rerun()

    # select prompt from example question or user provided input
    if st.session_state.ex_prompt:
        prompt = st.session_state.ex_prompt
    else:
        prompt = st.chat_input()
    if prompt:
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.write(prompt)
        st.session_state.ex_prompt = None
        
    # Generate a new response if last message is not from assistant
    if st.session_state.messages[-1]["role"] != "assistant":
        with st.chat_message("assistant"):
            if cfg.streaming:
                stream = generate_streaming_response(prompt) 
                response = st.write_stream(stream) 
            else:
                with st.spinner("Thinking..."):
                    response = generate_response(prompt)
                    st.write(response)
            message = {"role": "assistant", "content": response}
            st.session_state.messages.append(message)
            st.rerun()
    
if __name__ == "__main__":
    launch_bot()