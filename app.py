import io, os, json, zipfile, textwrap
from pathlib import Path
from datetime import datetime
import streamlit as st
from PIL import Image
from carousel_engine import (
    analyze_product_images, create_carousel_plan, generate_carousel,
    create_export_zip, safe_slug
)

st.set_page_config(page_title="TikTok Shop Carousel Factory", page_icon="🛍️", layout="wide")
st.title("TikTok Shop Carousel Factory")
st.caption("V2 • OpenAI Image API • Import de photos • 7 visuels verticaux par produit")

with st.sidebar:
    st.subheader("Configuration OpenAI")
    api_key = st.text_input("Clé API OpenAI", type="password",
        value=os.getenv("OPENAI_API_KEY", ""), help="La clé est utilisée uniquement côté serveur local. Ne la partage pas.")
    text_model = st.text_input("Modèle d'analyse", value=os.getenv("OPENAI_TEXT_MODEL", "gpt-6.1-terra"))
    image_model = st.text_input("Modèle image", value=os.getenv("OPENAI_IMAGE_MODEL", "gpt-image-2.5-sunburst"))
    image_quality = st.selectbox("Qualité image", ["medium", "high"], index=1)
    st.markdown("---")
    st.caption("Les appels API sont facturés séparément de l'abonnement ChatGPT.")

left, right = st.columns([1.05, 0.95], gap="large")
with left:
    st.subheader("1. Importer le produit")
    files = st.file_uploader(
        "Photos de référence du produit",
        type=["png", "jpg", "jpeg", "webp"],
        accept_multiple_files=True,
        help="Importe plusieurs angles et, si nécessaire, les photos de chaque coloris."
    )
    product_name = st.text_input("Nom du produit", placeholder="Ex. Sweat gaufré à capuche")
    market = st.selectbox("Marché", ["France", "Belgique", "Portugal", "Espagne", "Royaume-Uni", "Autre"])
    language = st.selectbox("Langue des textes", ["Français", "English", "Português", "Español"])
    category = st.text_input("Catégorie", placeholder="Mode, beauté, maison…")
    audience = st.text_input("Client cible", placeholder="Ex. Femmes 25–45 ans")
    price = st.text_input("Prix (facultatif)", placeholder="Ex. 39,90 €")
    main_problem = st.text_area("Besoin auquel le produit répond", height=70)
    benefit = st.text_area("Bénéfice principal confirmé", height=70)
    features = st.text_area("Caractéristiques confirmées (une par ligne)", height=100,
        placeholder="Capuche avec cordons\nPoche zippée sur la poitrine\nMaille gaufrée")
    materials = st.text_input("Matière / composition (uniquement si connue)")
    variants = st.text_input("Coloris / tailles réellement disponibles")
    included = st.text_input("Contenu du colis")
    approved_claims = st.text_area("Promesses / affirmations autorisées", height=65,
        placeholder="Laisser vide si aucune promesse particulière n'est justifiée.")
    forbidden_claims = st.text_area("À ne jamais affirmer", height=65,
        placeholder="Ex. imperméable, hypoallergénique, 100 % coton si non prouvé.")
    tone = st.selectbox("Ton éditorial", ["Naturel et direct", "Premium et sobre", "Dynamique et tendance", "Expert et pédagogique"])

with right:
    st.subheader("2. Aperçu des références")
    if files:
        cols = st.columns(2)
        for i, f in enumerate(files):
            try:
                img = Image.open(io.BytesIO(f.getvalue())).convert("RGB")
                with cols[i % 2]:
                    st.image(img, caption=f.name, use_container_width=True)
            except Exception:
                st.warning(f"Fichier illisible : {f.name}")
        st.info(f"{len(files)} photo(s) importée(s). Les références seront transmises à OpenAI uniquement au lancement de l'analyse/génération.")
    else:
        st.info("Ajoute les photos fournisseur ou tes propres photos produit. Plusieurs angles améliorent la fidélité visuelle.")
    st.subheader("3. Mix créatif")
    st.markdown("""
    - **2 UGC** : scènes smartphone naturelles, non présentées comme de faux avis.
    - **3 studio** : hero produit, macro détails, variantes.
    - **2 lifestyle** : mise en situation et image finale.
    """)
    st.subheader("4. Format de sortie")
    st.metric("Images par carrousel", "7")
    st.metric("Format export", "1080 × 1920 px")
    st.metric("Ratio", "9:16")

st.divider()
col_a, col_b, col_c = st.columns([1,1,1])
with col_a:
    analyze_btn = st.button("Analyser les photos", type="secondary", use_container_width=True)
with col_b:
    plan_btn = st.button("Créer le plan du carrousel", type="secondary", use_container_width=True)
with col_c:
    generate_btn = st.button("Générer les 7 visuels", type="primary", use_container_width=True)

def product_payload():
    return {
        "product_name": product_name.strip(),
        "market": market,
        "language": language,
        "category": category.strip(),
        "audience": audience.strip(),
        "price": price.strip(),
        "main_problem": main_problem.strip(),
        "primary_benefit": benefit.strip(),
        "features": [x.strip() for x in features.splitlines() if x.strip()],
        "materials": materials.strip(),
        "variants": variants.strip(),
        "included_items": included.strip(),
        "approved_claims": approved_claims.strip(),
        "forbidden_claims": forbidden_claims.strip(),
        "tone": tone
    }

def validate():
    if not api_key:
        st.error("Ajoute ta clé API OpenAI dans la barre latérale.")
        return False
    if not files:
        st.error("Ajoute au moins une photo de référence.")
        return False
    if not product_name.strip():
        st.error("Renseigne le nom du produit.")
        return False
    return True

if "analysis" not in st.session_state: st.session_state.analysis = None
if "plan" not in st.session_state: st.session_state.plan = None
if "generated" not in st.session_state: st.session_state.generated = None

if analyze_btn and validate():
    with st.spinner("Analyse visuelle des photos…"):
        try:
            st.session_state.analysis = analyze_product_images(
                api_key, text_model, [(f.name, f.getvalue(), f.type) for f in files]
            )
            st.success("Analyse terminée. Les caractéristiques visuelles restent à vérifier.")
        except Exception as e:
            st.error(f"Analyse impossible : {e}")

if st.session_state.analysis:
    with st.expander("Analyse visuelle détectée", expanded=True):
        st.json(st.session_state.analysis)

if plan_btn and validate():
    with st.spinner("Construction du scénario et des textes…"):
        try:
            if st.session_state.analysis is None:
                st.session_state.analysis = analyze_product_images(
                    api_key, text_model, [(f.name, f.getvalue(), f.type) for f in files]
                )
            st.session_state.plan = create_carousel_plan(api_key, text_model, product_payload(), st.session_state.analysis)
            st.success("Plan du carrousel prêt.")
        except Exception as e:
            st.error(f"Création du plan impossible : {e}")

if st.session_state.plan:
    st.subheader("Plan éditorial généré")
    for slide in st.session_state.plan.get("slides", []):
        with st.expander(f"{slide['number']:02d} • {slide['role']} • {slide['style']}"):
            st.markdown(f"**Accroche :** {slide.get('headline','')}")
            st.write(slide.get("support_copy",""))
            st.caption(slide.get("visual_direction",""))
            st.text_area("Texte affiché", value=slide.get("overlay_text",""), key=f"copy_{slide['number']}")

if generate_btn and validate():
    try:
        if st.session_state.analysis is None:
            with st.spinner("Analyse des photos…"):
                st.session_state.analysis = analyze_product_images(
                    api_key, text_model, [(f.name, f.getvalue(), f.type) for f in files]
                )
        if st.session_state.plan is None:
            with st.spinner("Préparation du scénario…"):
                st.session_state.plan = create_carousel_plan(api_key, text_model, product_payload(), st.session_state.analysis)
        # Respect any text edits made in the plan expander.
        for slide in st.session_state.plan.get("slides", []):
            k = f"copy_{slide['number']}"
            if k in st.session_state:
                slide["overlay_text"] = st.session_state[k]
        product = product_payload()
        job_id = datetime.now().strftime("%Y%m%d_%H%M%S") + "_" + safe_slug(product_name)
        progress = st.progress(0, text="Préparation…")
        status = st.empty()
        def on_progress(i, total, message):
            progress.progress(int(i/total*100), text=f"{i}/{total} visuels")
            status.write(message)
        result = generate_carousel(
            api_key=api_key,
            image_model=image_model,
            quality=image_quality,
            product=product,
            analysis=st.session_state.analysis,
            plan=st.session_state.plan,
            references=[(f.name, f.getvalue(), f.type) for f in files],
            job_id=job_id,
            progress_callback=on_progress
        )
        st.session_state.generated = result
        st.success("Les 7 visuels ont été générés et exportés.")
    except Exception as e:
        st.error(f"Génération interrompue : {e}")

if st.session_state.generated:
    result = st.session_state.generated
    st.subheader("Carrousel généré")
    grid = st.columns(2)
    for i, item in enumerate(result["slides"]):
        with grid[i % 2]:
            st.image(item["path"], caption=f"{item['number']:02d} • {item['role']}", use_container_width=True)
    zip_bytes = create_export_zip(result["folder"])
    st.download_button(
        "Télécharger le carrousel complet (.ZIP)",
        data=zip_bytes,
        file_name=f"{result['job_id']}_TikTokShop_9x16.zip",
        mime="application/zip",
        type="primary"
    )
    st.caption("Chaque visuel est exporté séparément en PNG 1080 × 1920, avec le texte intégré en calque raster et le plan en JSON.")
    st.warning("Vérifie manuellement la fidélité du produit, les variantes, les claims et le rendu final avant toute publication.")


# Optional Google Drive / Sheets integration for cloud deployments
try:
    from cloud_integrations import save_job_to_google, upload_folder_to_drive, google_configured
    if st.session_state.generated:
        st.divider()
        st.subheader("Synchronisation cloud")
        if google_configured():
            if st.button("Archiver les visuels dans Google Drive et enregistrer le suivi dans Sheets"):
                with st.spinner("Synchronisation Google…"):
                    drive_url = upload_folder_to_drive(
                        st.session_state.generated["folder"],
                        st.session_state.generated["job_id"]
                    )
                    save_job_to_google(
                        st.session_state.generated["manifest"],
                        drive_url
                    )
                st.success("Carrousel archivé et suivi synchronisé.")
                if drive_url:
                    st.markdown(f"[Ouvrir le dossier Google Drive]({drive_url})")
        else:
            st.info("Google Drive / Sheets non configurés. Ajoute les secrets Google dans les paramètres de déploiement pour activer la synchronisation.")
except Exception as e:
    st.warning(f"Module de synchronisation indisponible : {e}")
