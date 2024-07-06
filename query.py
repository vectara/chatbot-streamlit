import requests
import json


class VectaraQuery():
    def __init__(self, api_key: str, customer_id: str, corpus_ids: list[str], prompt_name: str = None):
        self.customer_id = customer_id
        self.corpus_ids = corpus_ids
        self.api_key = api_key
        self.prompt_name = prompt_name if prompt_name else "vectara-experimental-summary-ext-2023-12-11-sml"
        self.conv_id = None

    def get_body(self, query_str: str):
        corpora_key_list = [{
                'customer_id': self.customer_id, 'corpus_id': corpus_id, 'lexical_interpolation_config': {'lambda': 0.005}
            } for corpus_id in self.corpus_ids
        ]

        return {
            'query': [
                { 
                    'query': query_str,
                    'start': 0,
                    'numResults': 50,
                    'corpusKey': corpora_key_list,
                    'context_config': {
                        'sentences_before': 2,
                        'sentences_after': 2,
                        'start_tag': "%START_SNIPPET%",
                        'end_tag': "%END_SNIPPET%",
                    },
                    'rerankingConfig':
                    {
                        'rerankerId': 272725719,
                    },
                    'summary': [
                        {
                            'responseLang': 'eng',
                            'maxSummarizedResults': 10,
                            'summarizerPromptName': self.prompt_name,
                            'chat': {
                                'store': True,
                                'conversationId': self.conv_id
                            },
                            'citationParams': {
                                "style": "NONE",
                            }
                        }
                    ]
                } 
            ]
        }
    

    def get_headers(self):
        return {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "customer-id": self.customer_id,
            "x-api-key": self.api_key,
            "grpc-timeout": "60S"
        }

    def submit_query(self, query_str: str):

        endpoint = f"https://api.vectara.io/v1/query"
        body = self.get_body(query_str)

        response = requests.post(endpoint, data=json.dumps(body), verify=True, headers=self.get_headers())    
        if response.status_code != 200:
            print(f"Query failed with code {response.status_code}, reason {response.reason}, text {response.text}")
            return "Sorry, something went wrong in my brain. Please try again later."

        res = response.json()

        #top_k = 10
        summary = res['responseSet'][0]['summary'][0]['text']
        #responses = res['responseSet'][0]['response'][:top_k]
        #docs = res['responseSet'][0]['document']
        chat = res['responseSet'][0]['summary'][0].get('chat', None)

        if chat and chat['status'] is not None:
            st_code = chat['status']
            print(f"Chat query failed with code {st_code}")
            if st_code == 'RESOURCE_EXHAUSTED':
                self.conv_id = None
                return 'Sorry, Vectara chat turns exceeds plan limit.'
            return 'Sorry, something went wrong in my brain. Please try again later.'
        
        self.conv_id = chat['conversationId'] if chat else None
        return summary

    def submit_query_streaming(self, query_str: str):

        endpoint = "https://api.vectara.io/v1/stream-query"
        body = self.get_body(query_str)

        response = requests.post(endpoint, data=json.dumps(body), verify=True, headers=self.get_headers(), stream=True) 
        if response.status_code != 200:
            print(f"Query failed with code {response.status_code}, reason {response.reason}, text {response.text}")
            return "Sorry, something went wrong in my brain. Please try again later."

        chunks = []
        for line in response.iter_lines():
            if line:  # filter out keep-alive new lines
                data = json.loads(line.decode('utf-8'))
                res = data['result']
                response_set = res['responseSet']                
                if response_set is None:
                    # grab next chunk and yield it as output
                    summary = res.get('summary', None)
                    if summary is None or len(summary)==0:
                        continue
                    else:
                        chat = summary.get('chat', None)
                        if chat and chat.get('status', None):
                            st_code = chat['status']
                            print(f"Chat query failed with code {st_code}")
                            if st_code == 'RESOURCE_EXHAUSTED':
                                self.conv_id = None
                                return 'Sorry, Vectara chat turns exceeds plan limit.'
                            return 'Sorry, something went wrong in my brain. Please try again later.'
                        conv_id = chat.get('conversationId', None) if chat else None
                        if conv_id:
                            self.conv_id = conv_id
                        
                    chunk = summary['text']
                    chunks.append(chunk)
                    yield chunk

                    if summary['done']:
                        break
        
        return ''.join(chunks)
