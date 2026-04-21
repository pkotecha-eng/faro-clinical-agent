"""
FARO Clinical Agent - Data Tools
Handles PubMed and ClinicalTrials.gov API calls
"""

import requests
import xmltodict
from typing import Any


def search_pubmed(query: str, max_results: int = 5) -> list[dict]:
    """Search PubMed for peer-reviewed biomedical literature."""
    try:
        # Search for IDs
        search_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
        search_params = {
            "db": "pubmed",
            "term": query,
            "retmax": max_results,
            "retmode": "json",
        }
        search_resp = requests.get(search_url, params=search_params, timeout=10)
        ids = search_resp.json().get("esearchresult", {}).get("idlist", [])

        if not ids:
            return []

        # Fetch details
        fetch_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
        fetch_params = {
            "db": "pubmed",
            "id": ",".join(ids),
            "retmode": "xml",
        }
        fetch_resp = requests.get(fetch_url, params=fetch_params, timeout=10)
        data = xmltodict.parse(fetch_resp.text)

        articles = data.get("PubmedArticleSet", {}).get("PubmedArticle", [])
        if isinstance(articles, dict):
            articles = [articles]

        results = []
        for article in articles:
            medline = article.get("MedlineCitation", {})
            article_data = medline.get("Article", {})
            abstract = article_data.get("Abstract", {})
            abstract_text = abstract.get("AbstractText", "")
            if isinstance(abstract_text, list):
                abstract_text = " ".join(
                    t if isinstance(t, str) else t.get("#text", "")
                    for t in abstract_text
                )
            elif isinstance(abstract_text, dict):
                abstract_text = abstract_text.get("#text", "")

            authors_list = article_data.get("AuthorList", {}).get("Author", [])
            if isinstance(authors_list, dict):
                authors_list = [authors_list]
            authors = []
            for a in authors_list[:3]:
                last = a.get("LastName", "")
                first = a.get("ForeName", "")
                if last:
                    authors.append(f"{last} {first}".strip())

            pmid = str(medline.get("PMID", {}).get("#text", ""))
            journal = article_data.get("Journal", {})
            journal_title = journal.get("Title", "")
            pub_date = journal.get("JournalIssue", {}).get("PubDate", {})
            year = pub_date.get("Year", pub_date.get("MedlineDate", ""))[:4] if pub_date else ""

            results.append({
                "title": article_data.get("ArticleTitle", "Untitled"),
                "authors": authors,
                "journal": journal_title,
                "year": year,
                "abstract": abstract_text,
                "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
            })

        return results

    except Exception as e:
        return [{"error": str(e)}]


def search_clinical_trials(
    condition: str,
    status: str = "RECRUITING",
    intervention: str = "",
    max_results: int = 5,
) -> list[dict]:
    """Search ClinicalTrials.gov for clinical studies."""
    try:
        url = "https://clinicaltrials.gov/api/v2/studies"
        params = {
            "query.cond": condition,
            "query.intr": intervention,
            "filter.overallStatus": status,
            "pageSize": max_results,
            "format": "json",
        }
        resp = requests.get(url, params=params, timeout=10)
        data = resp.json()
        studies = data.get("studies", [])

        results = []
        for study in studies:
            protocol = study.get("protocolSection", {})
            id_module = protocol.get("identificationModule", {})
            status_module = protocol.get("statusModule", {})
            desc_module = protocol.get("descriptionModule", {})
            conditions_module = protocol.get("conditionsModule", {})
            design_module = protocol.get("designModule", {})
            eligibility_module = protocol.get("eligibilityModule", {})
            contacts_module = protocol.get("contactsLocationsModule", {})
            sponsor_module = protocol.get("sponsorCollaboratorsModule", {})

            nct_id = id_module.get("nctId", "")
            phases = design_module.get("phases", [])
            phase = ", ".join(phases) if phases else "N/A"
            locations = contacts_module.get("locations", [])
            location_names = [
                f"{loc.get('city', '')}, {loc.get('country', '')}"
                for loc in locations[:3]
            ]

            results.append({
                "nct_id": nct_id,
                "title": id_module.get("briefTitle", "Untitled"),
                "status": status_module.get("overallStatus", "N/A"),
                "phase": phase,
                "sponsor": sponsor_module.get("leadSponsor", {}).get("name", "N/A"),
                "conditions": ", ".join(conditions_module.get("conditions", [])),
                "brief_summary": desc_module.get("briefSummary", ""),
                "eligibility_criteria": eligibility_module.get("eligibilityCriteria", ""),
                "min_age": eligibility_module.get("minimumAge", "N/A"),
                "max_age": eligibility_module.get("maximumAge", "N/A"),
                "locations": location_names,
                "url": f"https://clinicaltrials.gov/study/{nct_id}",
            })

        return results

    except Exception as e:
        return [{"error": str(e)}]