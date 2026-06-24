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

            outcomes_mod = protocol.get("outcomesModule", {})

            primary_outcomes = outcomes_mod.get("primaryOutcomes") or []
            primary_outcome = primary_outcomes[0].get("measure", "") if primary_outcomes else ""
            if len(primary_outcome) > 300:
              primary_outcome = primary_outcome[:297] + "..."

            secondary_outcomes_list = outcomes_mod.get("secondaryOutcomes") or []
            secondary_outcome_strs = [
              o.get("measure", "") for o in secondary_outcomes_list[:3] if isinstance(o, dict)
            ]
            secondary_outcome = "; ".join(secondary_outcome_strs)
            if len(secondary_outcome) > 300:
              secondary_outcome = secondary_outcome[:297] + "..."

            nct_id = id_module.get("nctId", "")
            phases = design_module.get("phases", [])
            phase = ", ".join(phases) if phases else "N/A"
            locations = contacts_module.get("locations", [])
            location_names = [
                f"{loc.get('city', '')}, {loc.get('country', '')}"
                for loc in locations[:3]
            ]

            criteria_raw = eligibility_module.get("eligibilityCriteria", "")
            if "Exclusion Criteria:" in criteria_raw:
                parts = criteria_raw.split("Exclusion Criteria:")
                inclusion_criteria = parts[0].replace("Inclusion Criteria:", "").strip()[:400]
                exclusion_criteria = parts[1].strip()[:800]
            else:
                inclusion_criteria = criteria_raw[:400]
                exclusion_criteria = ""

            results.append({
                "nct_id": nct_id,
                "title": id_module.get("briefTitle", "Untitled"),
                "status": status_module.get("overallStatus", "N/A"),
                "phase": phase,
                "sponsor": sponsor_module.get("leadSponsor", {}).get("name", "N/A"),
                "conditions": ", ".join(conditions_module.get("conditions", [])),
                "brief_summary": desc_module.get("briefSummary", ""),
                "inclusion_criteria": inclusion_criteria,
                "exclusion_criteria": exclusion_criteria,
                "min_age": eligibility_module.get("minimumAge", "N/A"),
                "max_age": eligibility_module.get("maximumAge", "N/A"),
                "locations": location_names,
                "url": f"https://clinicaltrials.gov/study/{nct_id}",
                "primary_outcome": primary_outcome,
                "secondary_outcomes": secondary_outcome,
            })

        return results

    except Exception as e:
        return [{"error": str(e)}]


def search_isrctn(query: str, max_results: int = 5) -> list[dict]:
    """Search ISRCTN registry for UK and European clinical trials."""
    try:
        url = "https://www.isrctn.com/api/query/format/who"
        params = {"q": query, "limit": max_results * 2}  # fetch extra for relevance filtering
        resp = requests.get(url, params=params, timeout=15)
        data = xmltodict.parse(resp.content)

        trials_el = (data.get("trials") or {}).get("trial")
        if not trials_el:
            return []
        if isinstance(trials_el, dict):
            trials_el = [trials_el]

        # Relevance filter — all query terms must appear in title or condition
        query_words = set(query.lower().split())

        results = []
        for trial in trials_el:
            main = trial.get("main") or {}
            title = main.get("public_title") or ""
            condition = main.get("hc_freetext") or ""
            searchable = f"{title} {condition}".lower()

            significant_words = [w for w in query_words if len(w) > 3]
            if not significant_words or not any(word in searchable for word in significant_words):
                continue

            criteria = trial.get("criteria") or {}
            countries_el = trial.get("countries") or {}
            country_raw = countries_el.get("country2")
            if isinstance(country_raw, list):
                countries = [c for c in country_raw if c]
            elif country_raw:
                countries = [country_raw]
            else:
                countries = []

            primary_outcome_el = trial.get("primary_outcome") or {}
            primary_outcome = primary_outcome_el.get("prim_outcome") or ""

            results.append({
                "trial_id": main.get("trial_id", ""),
                "title": title,
                "status": main.get("recruitment_status", "N/A"),
                "phase": main.get("phase", "N/A"),
                "sponsor": main.get("primary_sponsor", "N/A"),
                "condition": condition,
                "primary_outcome": primary_outcome[:300] if primary_outcome else "",
                "countries": countries,
                "min_age": criteria.get("agemin", "N/A"),
                "max_age": criteria.get("agemax", "N/A"),
                "gender": criteria.get("gender", "N/A"),
                "inclusion_criteria": (criteria.get("inclusion_criteria") or "")[:400],
                "exclusion_criteria": (criteria.get("exclusion_criteria") or "")[:800],
                "url": main.get("url", ""),
            })

            if len(results) >= max_results:
                break

        return results

    except Exception as e:
        return [{"error": str(e)}]