"""THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE

For Demo use only - not to be used in production
"""

import logging
import os
from dotenv import load_dotenv
from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
from azure.identity import ManagedIdentityCredential
from azure.keyvault.secrets import SecretClient
import azure.functions as func

AZURE_SEARCH_SERVICE_ENDPOINT = 'CHANGEME'
AZURE_SEARCH_INDEX_NAME = 'CHANGEME'
AZURE_KEYVAULT_URL = 'CHANGEME'
AZURE_FUNCTION_FQDN = 'CHANGEME'

SECRETS = dict()

USE_LOCALHOST = False

if USE_LOCALHOST:
    REDIRECT_FQDN = 'http://localhost:7071'
else:
    REDIRECT_FQDN = AZURE_FUNCTION_FQDN

def get_input_form() -> str:
    input_form = f"""<!DOCTYPE html>
    <html>
    <body>
    <h1>Cognitive Search Simple UI Demo</h1>
    <h3>by Douglas Copas, Azure Core CSA</h3>
    <h3>Demo use only</h3>
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
    else:
        identity = ManagedIdentityCredential()
        secretClient = SecretClient(vault_url=AZURE_KEYVAULT_URL, credential=identity)
        AZURE_SEARCH_API_KEY = secretClient.get_secret('AZURE-SEARCH-API-KEY').value  
    
    SECRETS['AZURE_SEARCH_API_KEY'] = AZURE_SEARCH_API_KEY
    return SECRETS

def simple_text_query(str):
    service_endpoint = AZURE_SEARCH_SERVICE_ENDPOINT
    index_name = AZURE_SEARCH_INDEX_NAME
    key = SECRETS['AZURE_SEARCH_API_KEY']
    search_client = SearchClient(service_endpoint, index_name, AzureKeyCredential(key))
    results = search_client.search(search_text=str, top=1000)
    # TODO get next 1000 if there are 1000 results
    result_dict = dict()
    result_list = []
    for result in results:
        metadata_storage_name = result['metadata_storage_name']  + ';'
        metadata_storage_path = result['metadata_storage_path'] + ';\n'

        if metadata_storage_path in result_dict:
            continue
        else:
            result_list.append([metadata_storage_name, metadata_storage_path])
            result_dict[metadata_storage_path] = 1
    return result_list

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
        results = simple_text_query(term)
        if len(results) == 0:
            return func.HttpResponse(f"No results found matching search term")

        csv_string = ''
        for pair in results:
            csv_string += pair[0]
            csv_string += pair[1]
        fbytes = bytes(csv_string, 'utf-8')
        headers = {
            "Content-Disposition": "attachment; filename=results.csv"
        }
        return func.HttpResponse(body=fbytes, status_code=200, headers=headers, mimetype='application/octet-stream')
    else:
        return func.HttpResponse(body=get_input_form(), mimetype="text/html")
