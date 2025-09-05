# streamlit_app.py
import streamlit as st
import asyncio
import pandas as pd
import json
from typing import Dict, Any
from dotenv import load_dotenv

# Importer kjernekomponentene fra prosjektet ditt
from src.agents.oslomodell_agent import OslomodellAgent
from src.models.base_models import BaseProcurementInput
from src.models.enums import ProcurementCategory, ProcurementSubCategory
from src.utils.csv_manager import CSVManager

# --- SIDEKONFIGURASJON ---
st.set_page_config(
    page_title="Anskaffelsesassistenten",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- NYTT: Egendefinert CSS for finjustering ---
def load_custom_css():
    """Laster inn egendefinert CSS for å matche Oslo Kommunes profil."""
    st.markdown("""
        <style>
            /* Endre fargen på hovedtittelen (h1) */
            h1 {
                color: #2A2859; /* Oslo mørk blå */
            }
            /* Styling for metrikk-kortene på dashboardet */
            .stMetric {
                background-color: #F8F0DD; /* Oslo lys beige */
                border: 1px solid #D0BFAE; /* Oslo mørk beige */
                padding: 15px;
                border-radius: 10px;
            }
        </style>
    """, unsafe_allow_html=True)

# Kall funksjonen for å laste CSS
load_custom_css()

# --- INITIALISERING & CACHING ---
# Bruk Streamlits caching for å unngå å laste tunge objekter på hver re-run.
# `allow_output_mutation=True` er nødvendig for komplekse objekter som agenten.
@st.cache_resource
def load_agent_and_config():
    """Laster konfigurasjon og initialiserer agenten én gang."""
    print("--- Laster konfigurasjon og initialiserer agent ---")
    # Antar at config-filen ligger i en 'config'-mappe
    load_dotenv()
    import yaml
    with open("config/oslomodell_config.yaml", 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    agent = OslomodellAgent(config)
    return agent, agent.csv_manager

agent, csv_manager = load_agent_and_config()

# --- STATE MANAGEMENT ---
# Initialiser session state for å holde på data mellom interaksjoner
if 'assessment_result' not in st.session_state:
    st.session_state.assessment_result = None
if 'procurement_input' not in st.session_state:
    st.session_state.procurement_input = None
if 'running' not in st.session_state:
    st.session_state.running = False

# --- ASYNC HELPER ---
# Streamlit kjører synkront, så vi trenger en hjelper for å kjøre vår async-agent
def run_async_assessment(proc_input):
    return asyncio.run(agent.assess(proc_input))

# ======================================================================================
#                                    SIDEBAR (INPUT)
# ======================================================================================
with st.sidebar:
    st.title("📋 Ny Vurdering")
    st.write("Fyll ut detaljene for anskaffelsen og start en ny vurdering.")

    with st.form("procurement_form"):
        st.subheader("Grunndata")
        name = st.text_input("Navn på anskaffelsen", "Rehabilitering av Storgata Skole")
        value = st.number_input("Estimert verdi (NOK eks. mva)", min_value=0, value=25000000, step=10000)
        category = st.selectbox(
            "Kategori",
            options=[cat.value for cat in ProcurementCategory],
            format_func=lambda x: x.capitalize()
        )
        # Vis subkategori kun hvis relevant
        subcategory_options = [sub.value for sub in ProcurementSubCategory]
        subcategory = st.selectbox(
            "Underkategori (valgfritt)",
            options=[""] + subcategory_options,
            format_func=lambda x: x.capitalize() if x else "Ingen"
        )
        duration_months = st.number_input("Varighet (måneder)", min_value=0, value=18, step=1)
        description = st.text_area("Kort beskrivelse", "Totalrehabilitering av skolebygg. Omfatter tømrer, rørlegger, og elektrikerarbeid.")

        st.subheader("Leverandør (valgfritt)")
        supplier_name = st.text_input("Navn på leverandør som skal sjekkes", "AF Gruppen ASA")

        submitted = st.form_submit_button("🚀 Start Vurdering", type="primary", width='stretch')

    if submitted:
        if not name or value is None:
            st.error("Navn og verdi må fylles ut.")
        else:
            # Bygg input-objektet
            procurement_input = BaseProcurementInput(
                name=name,
                value=value,
                category=ProcurementCategory(category),
                subcategory=ProcurementSubCategory(subcategory) if subcategory else None,
                duration_months=duration_months,
                description=description,
                supplier_name_to_verify=supplier_name if supplier_name else None,
                requested_by="Streamlit User" # Hardkodet for nå
            )
            st.session_state.procurement_input = procurement_input
            st.session_state.assessment_result = None # Nullstill gammelt resultat
            st.session_state.running = True
            st.rerun() # Kjør appen på nytt for å vise spinner og starte prosessering

# ======================================================================================
#                                    HOVEDINNHOLD
# ======================================================================================

st.title("Anskaffelsesassistenten")
st.markdown("Et verktøy for automatisert vurdering av anskaffelser mot Oslomodellen.")

# --- FANER FOR ORGANISERING ---
tab_assessment, tab_dashboard, tab_details = st.tabs(["Vurderingsresultat", "Dashboard", "Detaljert Logg"])

# --- FANE 1: VURDERINGSRESULTAT ---
with tab_assessment:
    if st.session_state.running:
        with st.spinner("Agenten jobber... Dette kan ta et øyeblikk."):
            try:
                result = run_async_assessment(st.session_state.procurement_input)
                st.session_state.assessment_result = result
            except Exception as e:
                st.error(f"En feil oppstod under vurderingen: {e}")
                st.exception(e)
            finally:
                st.session_state.running = False
                st.rerun() # Kjør på nytt for å vise resultatet

    if st.session_state.assessment_result:
        res = st.session_state.assessment_result
        st.header(f"Resultat for: {res.procurement_name}")

        col1, col2, col3 = st.columns(3)
        col1.metric("Anbefalte Krav", len(res.applicable_requirements))
        col2.metric("Utløste Regler", len(res.triggered_rules))
        col3.metric("Advarsler", len(res.warnings), delta_color="inverse")

        st.subheader("Oppsummering")
        summary = res.summary_prose or "Ingen oppsummering generert."
        st.info(summary)

        with st.expander("📜 Anbefalte krav", expanded=True):
            if res.applicable_requirements:
                req_data = [
                    {"Kode": req.code, "Navn": req.name, "Kategori": req.category.value.capitalize()}
                    for req in res.applicable_requirements
                ]
                st.dataframe(pd.DataFrame(req_data), width='stretch')
            else:
                st.write("Ingen krav ble aktivert for denne anskaffelsen.")

        with st.expander("⚠️ Advarsler og Anbefalinger"):
            if res.warnings:
                st.warning("Advarsler:")
                for warning in res.warnings:
                    st.write(f"- {warning}")
            if res.recommendations:
                st.success("Anbefalinger:")
                for rec in res.recommendations:
                    st.write(f"- {rec}")
            if not res.warnings and not res.recommendations:
                st.write("Ingen spesifikke advarsler eller anbefalinger.")

    else:
        st.info("Fyll ut skjemaet i sidebaren og trykk 'Start Vurdering' for å se resultater her.")


# --- FANE 2: DASHBOARD ---
with tab_dashboard:
    st.header("📊 Dashboard & Oversikt")

    # Hent data fra CSV-filene
    avtale_data = csv_manager.read_csv('avtaleoversikt')
    cost_data = csv_manager.read_csv('llm_costs')

    if not avtale_data:
        st.warning("Ingen data funnet. Kjør en vurdering for å populere dashboardet.")
    else:
        # Konverter til Pandas DataFrame for enklere analyse
        avtale_df = pd.DataFrame(avtale_data)
        cost_df = pd.DataFrame(cost_data)

        # Konverter kolonner til riktig type for analyse
        avtale_df['verdi'] = pd.to_numeric(avtale_df['verdi'], errors='coerce')
        avtale_df['antall_risikoer'] = pd.to_numeric(avtale_df['antall_risikoer'], errors='coerce')
        cost_df['estimated_cost_usd'] = pd.to_numeric(cost_df['estimated_cost_usd'], errors='coerce')

        # Vis KPI-er
        col1, col2, col3 = st.columns(3)
        col1.metric("Totalt antall vurderinger", len(avtale_df))
        col2.metric("Total LLM-kostnad", f"${cost_df['estimated_cost_usd'].sum():.4f}")
        col3.metric("Gj.snitt. verdi", f"{avtale_df['verdi'].mean():,.0f} NOK".replace(",", " "))

        # Vis graf
        st.subheader("Vurderinger per kategori")
        category_counts = avtale_df['kategori'].value_counts()
        st.bar_chart(category_counts)

        # Vis tabell med siste vurderinger
        st.subheader("Siste vurderinger")
        st.dataframe(avtale_df.tail(10), width='stretch')


# --- FANE 3: DETALJERT LOGG ---
with tab_details:
    st.header("🔍 Detaljert Logg")
    
    avtaleoversikt = csv_manager.read_csv('avtaleoversikt')
    if not avtaleoversikt:
        st.warning("Ingen vurderinger å vise. Kjør en vurdering først.")
    else:
        # Lag en penere visning for selectboxen
        options = {f"{row['navn']} ({row['procurement_id']})": row['procurement_id'] for row in avtaleoversikt}
        selected_display = st.selectbox("Velg en anskaffelse for å se detaljer", options.keys())

        if selected_display:
            selected_proc_id = options[selected_display]
            st.subheader(f"Logger for anskaffelse: `{selected_proc_id}`")

            # Vis risikovurderinger
            with st.expander("Risikovurderinger"):
                risk_data = csv_manager.read_csv('risk_assessments', filters={'procurement_id': selected_proc_id})
                if risk_data:
                    st.dataframe(risk_data, width='stretch')
                else:
                    st.write("Ingen risikovurderinger logget.")

            # Vis LLM-kostnader
            with st.expander("LLM Kostnader"):
                cost_data = csv_manager.read_csv('llm_costs', filters={'procurement_id': selected_proc_id})
                if cost_data:
                    st.dataframe(cost_data, width='stretch')
                else:
                    st.write("Ingen LLM-kostnader logget.")

            # Vis LLM-tanker
            with st.expander("LLM Tankeprosess (Thoughts)"):
                thought_data = csv_manager.read_csv('llm_thoughts', filters={'procurement_id': selected_proc_id})
                if thought_data:
                    for thought in thought_data:
                        st.text_area(
                            label=f"**Agent:** {thought['agent_name']} | **Modell:** {thought['model']}",
                            value=thought['thought_content'],
                            height=200,
                            disabled=True
                        )
                else:
                    st.write("Ingen LLM-tanker logget.")