import requests
import json
import re
from urllib.parse import quote

def extract_between_tags(text, start_tag, end_tag):
    start_index = text.find(start_tag)
    end_index = text.find(end_tag, start_index)
    return text[start_index+len(start_tag):end_index-len(end_tag)]

class CitationNormalizer():

    def __init__(self, responses, docs):
        self.docs = docs
        self.responses = responses
        self.refs = []

    def normalize_citations(self, summary):
        start_tag = "%START_SNIPPET%"
        end_tag = "%END_SNIPPET%"

        # find all references in the summary
        pattern = r'\[\d{1,2}\]'
        matches = [match.span() for match in re.finditer(pattern, summary)]

        # figure out unique list of references
        for match in matches:
            start, end = match
            response_num = int(summary[start+1:end-1])
            doc_num = self.responses[response_num-1]['documentIndex']
            metadata = {item['name']: item['value'] for item in self.docs[doc_num]['metadata']}
            text = extract_between_tags(self.responses[response_num-1]['text'], start_tag, end_tag)
            if 'url' in metadata.keys():
                url = f"{metadata['url']}#:~:text={quote(text)}"
                if url not in self.refs:
                    self.refs.append(url)

        # replace references with markdown links
        refs_dict = {url:(inx+1) for inx,url in enumerate(self.refs)}
        for match in reversed(matches):
            start, end = match
            response_num = int(summary[start+1:end-1])
            doc_num = self.responses[response_num-1]['documentIndex']
            metadata = {item['name']: item['value'] for item in self.docs[doc_num]['metadata']}
            text = extract_between_tags(self.responses[response_num-1]['text'], start_tag, end_tag)
            if 'url' in metadata.keys():
                url = f"{metadata['url']}#:~:text={quote(text)}"
                citation_inx = refs_dict[url]
                summary = summary[:start] + f'[\[{citation_inx}\]]({url})' + summary[end:]
            else:
                summary = summary[:start] + summary[end:]

        return summary

class VectaraQuery():
    def __init__(self, api_key: str, customer_id: str, corpus_ids: list[str], prompt_name: str = None):
        self.customer_id = customer_id
        self.corpus_ids = corpus_ids
        self.api_key = api_key
        self.prompt_name = prompt_name if prompt_name else "vectara-experimental-summary-ext-2023-12-11-sml"
        self.conv_id = None

    def get_body(self, query_str: str):
        corpora_key_list = [{
                'customer_id': self.customer_id, 'corpus_id': corpus_id, 'lexical_interpolation_config': {'lambda': 0.025}
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
                        'rerankerId': 272725718,
                        'mmrConfig': {
                            'diversityBias': 0.3
                        }
                    },
                    'summary': [
                        {
                            'responseLang': 'eng',
                            'maxSummarizedResults': 5,
                            'summarizerPromptName': self.prompt_name,
                            'chat': {
                                'store': True,
                                'conversationId': self.conv_id
                            },
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

        top_k = 10
        summary = res['responseSet'][0]['summary'][0]['text']
        responses = res['responseSet'][0]['response'][:top_k]
        docs = res['responseSet'][0]['document']
        chat = res['responseSet'][0]['summary'][0].get('chat', None)

        if chat and chat['status'] is not None:
            st_code = chat['status']
            print(f"Chat query failed with code {st_code}")
            if st_code == 'RESOURCE_EXHAUSTED':
                self.conv_id = None
                return 'Sorry, Vectara chat turns exceeds plan limit.'
            return 'Sorry, something went wrong in my brain. Please try again later.'
        
        self.conv_id = chat['conversationId'] if chat else None
        summary = CitationNormalizer(responses, docs).normalize_citations(summary)        
        return summary

    def submit_query_streaming(self, query_str: str):

        endpoint = f"https://api.vectara.io/v1/stream-query"
        body = self.get_body(query_str)

        response = requests.post(endpoint, data=json.dumps(body), verify=True, headers=self.get_headers(), stream=True) 
        if response.status_code != 200:
            print(f"Query failed with code {response.status_code}, reason {response.reason}, text {response.text}")
            return "Sorry, something went wrong in my brain. Please try again later."

        chunks = []
        accumulated_text = ""  # Initialize text accumulation
        pattern_max_length = 50  # Example heuristic
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
                    accumulated_text += chunk  # Append current chunk to accumulation
                    if len(accumulated_text) > pattern_max_length:
                        accumulated_text = re.sub(r"\[\d+\]", "", accumulated_text)
                        accumulated_text = re.sub(r"\s+\.", ".", accumulated_text)
                        out_chunk = accumulated_text[:-pattern_max_length]
                        chunks.append(out_chunk)
                        yield out_chunk
                        accumulated_text = accumulated_text[-pattern_max_length:]

                    if summary['done']:
                        break

        # yield the last piece
        if len(accumulated_text) > 0:
            accumulated_text = re.sub(r" \[\d+\]\.", ".", accumulated_text)
            chunks.append(accumulated_text)
            yield accumulated_text        
        
        return ''.join(chunks)
