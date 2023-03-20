"""THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE

For Demo use only - not to be used in production

Created by Douglas Copas, Azure Core CSA
"""

import logging
import os
from dotenv import load_dotenv
from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
from azure.identity import ManagedIdentityCredential
from azure.keyvault.secrets import SecretClient
import azure.functions as func
import base64

AZURE_SEARCH_SERVICE_ENDPOINT = 'CHANGEME'
AZURE_SEARCH_INDEX_NAME = 'CHANGEME'
AZURE_KEYVAULT_URL = 'CHANGEME'
AZURE_FUNCTION_FQDN = 'CHANGEME'

PAGE_SIZE = 500

SECRETS = dict()

USE_LOCALHOST = True

if USE_LOCALHOST:
    REDIRECT_FQDN = 'http://localhost:7071'
else:
    REDIRECT_FQDN = AZURE_FUNCTION_FQDN

def get_input_form() -> str:
    input_form = f"""<!DOCTYPE html>
    <html>
    <body>
    <h1>Cognitive Search Simple UI Demo</h1>
    <h3>Demo use only</h3>
    <br>    
    <p>Use + for AND operation. For example, ocean + pool stipulates that a document must contain both terms.</p>
    <p>Use | for OR operation. For example, ocean | pool finds documents containing either ocean or pool or both. Omitting the | symbol has the same result.</p>
    <p>Use quotes to search for a phrase. For example "ocean pool" (with the quotation marks) finds documents containing the phrase 'ocean pool'.</p>
    <form action="{REDIRECT_FQDN}/api/cogsearch" method="POST">
        Search term<br>
        <input type="text" name="term">
        <br><br>
        <button type="submit">Submit</button>
        <br><br><br><br>
    </form>
    </body>
    </html>"""
    return input_form

def get_secrets():
    if USE_LOCALHOST:
        load_dotenv()
        AZURE_SEARCH_API_KEY = os.getenv("AZURE_SEARCH_API_KEY")  
        AZURE_SEARCH_SERVICE_ENDPOINT = os.getenv("AZURE_SEARCH_SERVICE_ENDPOINT")
        AZURE_SEARCH_INDEX_NAME = os.getenv("AZURE_SEARCH_INDEX_NAME")
    else:
        identity = ManagedIdentityCredential()
        secretClient = SecretClient(vault_url=AZURE_KEYVAULT_URL, credential=identity)
        AZURE_SEARCH_API_KEY = secretClient.get_secret('AZURE-SEARCH-API-KEY').value  
    
    SECRETS['AZURE_SEARCH_API_KEY'] = AZURE_SEARCH_API_KEY
    SECRETS['AZURE_SEARCH_SERVICE_ENDPOINT'] = AZURE_SEARCH_SERVICE_ENDPOINT
    SECRETS['AZURE_SEARCH_INDEX_NAME'] = AZURE_SEARCH_INDEX_NAME
    return SECRETS

def simple_text_query(str):
    service_endpoint = SECRETS['AZURE_SEARCH_SERVICE_ENDPOINT']
    index_name = SECRETS['AZURE_SEARCH_INDEX_NAME']
    key = SECRETS['AZURE_SEARCH_API_KEY']
    search_client = SearchClient(service_endpoint, index_name, AzureKeyCredential(key))

    search_done = False
    skip_from = 0

    while not search_done:

        results = search_client.search(search_text=str, top=PAGE_SIZE, include_total_count=True, skip=skip_from, order_by='search.score() desc')

        if results.get_count() <= skip_from + PAGE_SIZE:
            search_done = True
        else:
            skip_from += PAGE_SIZE

        result_dict = dict()
        result_list = []
        undecoded_list = []

        for result in results:
            file_path = result['metadata_storage_path']
            path_decoded = file_path

            if file_path[-1] == '0':
                file_path = file_path[:-1]
            elif file_path[-1] == '1':
                file_path = file_path[:-1] + '='
            elif file_path[-1] == '2':
                file_path = file_path[:-1] + '=='

            try:
                path_decoded = base64.b64decode(file_path).decode("utf-8").rstrip()
            except Exception:
                pass

            if path_decoded == file_path:
                undecoded_list.append(file_path + ';\n')

            metadata_storage_name = result['metadata_storage_name']  + ';'
            metadata_storage_path = path_decoded + ';'
            metadata_creation_date =  result['metadata_creation_date'] + ';' if result['metadata_creation_date'] is not None else '' + ';'
            metadata_last_modified = result['metadata_last_modified'] + ';\n' if result['metadata_last_modified'] is not None else '' + ';\n' 
            
            if metadata_storage_path in result_dict:
                continue
            else:
                result_list.append([metadata_storage_name, metadata_storage_path, metadata_creation_date, metadata_last_modified])
                result_dict[metadata_storage_path] = 1
    return result_list, undecoded_list

def main(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Python HTTP trigger function processed a request.')

    term = req.params.get('term')
    if not term:
        try:
            req_body = req.get_json()
        except ValueError:
            try:
                term = req.form['term']
            except:
                pass
        else:
            term = req_body.get('term')     
        
    if term:
        get_secrets()
        result_list, undecoded_list = simple_text_query(term)
        if len(result_list) == 0:
            return func.HttpResponse(f"No results found matching search term")

        csv_string = ''

        for result in result_list:
            csv_string += result[0]
            csv_string += result[1]
            csv_string += result[2]
            csv_string += result[3]

        for item in undecoded_list:
            csv_string += 'undecoded;'
            csv_string += item
        
        fbytes = bytes(csv_string, 'utf-8')
        headers = {
            "Content-Disposition": "attachment; filename=results.csv"
        }
        return func.HttpResponse(body=fbytes, status_code=200, headers=headers, mimetype='application/octet-stream')
    else:
        return func.HttpResponse(body=get_input_form(), mimetype="text/html")
