import streamlit as st
import pandas as pd
import json
import time
import os
from openai import OpenAI
from datetime import datetime
from Bio import Entrez

# Streamlit UI Configuration
st.set_page_config(
    page_title="PubMed Analysis Tool",
    page_icon=":mag:",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Sidebar for Inputs
st.sidebar.header("PubMed Search Parameters")
query = st.sidebar.text_input("Search Query", "GIST")
max_results = st.sidebar.number_input("Max Results", min_value=1, max_value=500, value=100, step=10)

# Configure NCBI Search
Entrez.email = st.secrets["ncbi_email"]  # Use Streamlit secrets
Entrez.api_key = st.secrets["PM_Key"]  # Use Streamlit secrets

# Configure file name
filename = f"GIST Results {time.strftime('%y%m%d')}.xlsx"

# State Management
if 'analysis_results' not in st.session_state:
    st.session_state['analysis_results'] = []
if 'progress' not in st.session_state:
    st.session_state['progress'] = 0
if 'total_papers' not in st.session_state:
    st.session_state['total_papers'] = 0
if 'search_completed' not in st.session_state:
    st.session_state['search_completed'] = False

# Functions
def search_and_fetch_pubmed(query, max_results):
    """Search PubMed and fetch details in one function."""
    with Entrez.esearch(db="pubmed", term=query, retmax=max_results) as handle:
        record = Entrez.read(handle)
    
    id_list = record["IdList"]
    print(id_list)
    if not id_list:
        return []

    ids = ','.join(id_list)
    with Entrez.efetch(db="pubmed", id=ids, retmode="xml") as handle:
        records = Entrez.read(handle)
    
    return records

def add_to_excel(output_list, excel_file_path):
    """Add a list of dictionaries to an Excel sheet."""
    df = pd.DataFrame(output_list)
    df.to_excel(excel_file_path, index=False)
    return excel_file_path  # Return the file path

def analyze_paper(paper):
    """Call OpenAI to analyze the paper and return the results."""
    client = OpenAI(api_key=st.secrets["MGA_Key"], base_url="https://chat.int.bayer.com/api/v1")
    
    conversation = client.chat.completions.create(
        model='gpt-4o-mini',#gpt-4-turbo
        messages=[
            {
                "role": "system",
                "content": """
                You are a bot speaking with another program that takes JSON formatted text as an input. Only return results in JSON format, with NO PREAMBLE.
                The user will input the results from a PubMed search. Your job is to extract the exact information to return:              
                  'Title': The complete article title
                  'PMID': The Pubmed ID of the article
                  'Full Text Link' : If available, the DOI URL, otherwise, NA
                  'Subject of Study': The type of subject in the study. Human, Animal, In-Vitro, Other
                  'Disease State': Disease state studied, if any, or if the study is done on a healthy population. leave blank if disease state or healthy patients is not mentioned explicitly. 
                  'Number of Subjects Studied': If human, the total study population. Otherwise, leave blank. This field needs to be an integer or empty.
                  'Type of Study': Type of study done. Can be '3. RCT' for randomized controlled trial, '1. Meta-analysis','2. Systematic Review','4. Cohort Study', or '5. Other'. If it is '5. Other', append a short description
                  'Study Design': Brief and succinct details about study design, if applicable
                  'Intervention': Intervention(s) studied, if any. Intervention is the treatment applied to the group. List the interventions in broad language in bullet form.
                  'Intervention Dose': Go in detail here about the intervention's doses and treatment duration if available.
                  'Intervention Dosage Form': A brief description of the dosage form - ie. oral, topical, intranasal, if available.
                  'Control': Control or comarators, if any
                  'Primary Endpoint': What the primary endpoint of the study was, if available. Include how it was measured too if available.
                  'Primary Endpoint Result': The measurement for the primary endpoints
                  'Secondary Endpoints' If available
                  'Safety Endpoints' If available
                  'Results Available': Yes or No
                  'Primary Endpoint Met': Summarize from results whether or not the primary endpoint(s) was met: Yes or No or NA if results unavailable
                  'Statistical Significance': alpha-level and p-value for primary endpoint(s), if available
                  'Clinical Significance': Effect size, and Number needed to treat (NNT)/Number needed to harm (NNH), if available
                  'Main Author': Last name, First initials
                  'Other Authors': Last name, First initials; Last name First initials; ...
                  'Journal Name': Full journal name
                  'Date of Publication': YYYY-MM-DD
                  'Error': Error description, if any. Otherwise, leave emtpy
                """
            },
            {
                "role": "user",
                "content": str(paper)
            }
        ]
    )
    
    cleaned_str = conversation.choices[0].message.content.replace("```json", "").replace("```", "").strip()
    print(conversation)
    return json.loads(cleaned_str)

# Main Execution
if st.sidebar.button("Start Analysis"):
    st.session_state['analysis_results'] = []  # Reset results
    st.session_state['progress'] = 0
    st.session_state['search_completed'] = False

    with st.spinner(f"Searching PubMed for '{query}'..."):
        papers = search_and_fetch_pubmed(query, max_results)
        st.session_state['total_papers'] = len(papers['PubmedArticle'])
        st.write(f"Found {st.session_state['total_papers']} papers.")

    progress_bar = st.progress(0)

    for i, paper in enumerate(papers['PubmedArticle']):
        try:
            with st.spinner(f"Analyzing paper {i+1}/{st.session_state['total_papers']}..."):
                result = analyze_paper(paper)
                st.session_state['analysis_results'].append(result)
        except Exception as e:
            st.error(f"Error analyzing paper {i+1}: {e}")
        
        st.session_state['progress'] = (i + 1) / st.session_state['total_papers']
        progress_bar.progress(st.session_state['progress'])

    st.session_state['search_completed'] = True

# Display Results and Download Button
if st.session_state['search_completed']:
    st.success("Analysis Complete!")

    if st.session_state['analysis_results']:
        df = pd.DataFrame(st.session_state['analysis_results'])
        st.dataframe(df)

        excel_file = add_to_excel(st.session_state['analysis_results'], filename)
        with open(excel_file, "rb") as f:
            st.download_button(
                label="Download Excel File",
                data=f,
                file_name=filename,
                mime="application/vnd.ms-excel",
            )
    else:
        st.info("No results to display.")