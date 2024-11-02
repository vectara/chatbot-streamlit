import requests
import json


class VectaraQuery():
    def __init__(self, api_key: str, corpus_keys: list[str], prompt_name: str = None):
        self.corpus_keys = corpus_keys
        self.api_key = api_key
        self.prompt_name = prompt_name if prompt_name else "vectara-summary-ext-24-05-sml"
        self.conv_id = None

    
    def get_body(self, query_str: str, response_lang: str, stream: False):
        corpora_list = [{
                'corpus_key': corpus_key, 'lexical_interpolation': 0.005
            } for corpus_key in self.corpus_keys
        ]

        return {
            'query': query_str,
            'search':
            {
                'corpora': corpora_list,
                'offset': 0,
                'limit': 50,
                'context_configuration':
                {
                    'sentences_before': 2,
                    'sentences_after': 2,
                    'start_tag': "%START_SNIPPET%",
                    'end_tag': "%END_SNIPPET%",
                },
                'reranker':
                {
                    "type": "chain",
                    "rerankers": [
                        {
                            "type": "customer_reranker",
                            "reranker_name": "Rerank_Multilingual_v1"
                        },
                        {
                            "type": "mmr",
                            "diversity_bias": 0.05
                        }
                    ]
                },
            },
            'generation':
            {
                'generation_preset_name': self.prompt_name,
                'max_used_search_results': 7,
                'response_language': response_lang,
                'citations':
                {
                    'style': 'markdown',
                    'url_pattern': '{doc.url}'
                },
                'enable_factual_consistency_score': True
            },
            'chat':
            {
                'store': True
            },
            'stream_response': stream
        }
    

    def get_headers(self):
        return {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "x-api-key": self.api_key,
            "grpc-timeout": "60S"
        }
    
    def get_stream_headers(self):
        return {
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
            "x-api-key": self.api_key,
            "grpc-timeout": "60S"
        }

    def submit_query(self, query_str: str, language: str):

        if self.conv_id:
            endpoint = f"https://api.vectara.io/v2/chats/{self.conv_id}/turns"
        else:
            endpoint = "https://api.vectara.io/v2/chats"

        body = self.get_body(query_str, language, stream=False)
        response = requests.post(endpoint, data=json.dumps(body), verify=True, headers=self.get_headers())

        if response.status_code != 200:
            print(f"Query failed with code {response.status_code}, reason {response.reason}, text {response.text}")
            if response.status_code == 429:
                return "Sorry, Vectara chat turns exceeds plan limit."
            return "Sorry, something went wrong in my brain. Please try again later."

        res = response.json()

        if self.conv_id is None:
            self.conv_id = res['chat_id']

        summary = res['answer']
        
        return summary

    def submit_query_streaming(self, query_str: str, language: str):

        if self.conv_id:
            endpoint = f"https://api.vectara.io/v2/chats/{self.conv_id}/turns"
        else:
            endpoint = "https://api.vectara.io/v2/chats"

        body = self.get_body(query_str, language, stream=True)

        response = requests.post(endpoint, data=json.dumps(body), verify=True, headers=self.get_stream_headers(), stream=True) 

        if response.status_code != 200:
            print(f"Query failed with code {response.status_code}, reason {response.reason}, text {response.text}")
            if response.status_code == 429:
                return "Sorry, Vectara chat turns exceeds plan limit."
            return "Sorry, something went wrong in my brain. Please try again later."        

        chunks = []
        for line in response.iter_lines():
            line = line.decode('utf-8')
            if line:  # filter out keep-alive new lines
                key, value = line.split(':', 1)
                if key == 'data':
                    line = json.loads(value)
                    if line['type'] == 'generation_chunk':
                        chunk = line['generation_chunk']
                        chunks.append(chunk)
                        yield chunk
                    elif line['type'] == 'chat_info':
                        self.conv_id = line['chat_id']

        return ''.join(chunks)