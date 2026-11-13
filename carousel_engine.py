import base64, io, json, os, re, zipfile
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageOps
from openai import OpenAI

BASE = Path(__file__).parent
OUTPUTS = BASE / "outputs"
OUTPUTS.mkdir(exist_ok=True)

SLIDE_SPECS = [
    {"number":1,"role":"Accroche","style":"UGC","visual":"Photo smartphone spontanée et crédible dans une situation du quotidien. Composition naturelle, lumière ambiante, rendu créateur non publicitaire."},
    {"number":2,"role":"Hero produit","style":"Studio","visual":"Photo produit studio professionnelle, produit entier bien lisible, fond neutre, ombres douces, détails exacts."},
    {"number":3,"role":"Bénéfice vérifié","style":"Lifestyle","visual":"Mise en situation réaliste qui illustre uniquement le bénéfice fourni, sans exagération ni promesse nouvelle."},
    {"number":4,"role":"Détails","style":"Studio macro","visual":"Gros plan photographique sur les détails réellement visibles et confirmés : texture, couture, fermeture, matière ou finition."},
    {"number":5,"role":"Moment créateur","style":"UGC","visual":"Photo smartphone lifestyle prise sur le vif, posture et décor naturels, sans faux témoignage ni avis client inventé."},
    {"number":6,"role":"Variantes","style":"Studio","visual":"Présentation claire des variantes réellement fournies en référence. Ne pas inventer de coloris, tailles ou options."},
    {"number":7,"role":"Récapitulatif","style":"Lifestyle","visual":"Image finale claire du produit exact dans un décor simple, composition équilibrée et espace négatif pour un texte court."},
]

def safe_slug(value):
    return re.sub(r"[^a-zA-Z0-9_-]+","-", value).strip("-").lower()[:64] or "produit"

def _mime(name, fallback="image/jpeg"):
    ext = Path(name).suffix.lower()
    return {".png":"image/png",".jpg":"image/jpeg",".jpeg":"image/jpeg",".webp":"image/webp"}.get(ext,fallback)

def analyze_product_images(api_key, text_model, references):
    client = OpenAI(api_key=api_key)
    content = [{
        "type":"input_text",
        "text": (
            "Analyse ces photos de référence pour préparer une fiche visuelle de produit e-commerce. "
            "Réponds en JSON valide avec les clés: product_type, visible_colors, visible_shape, "
            "visible_material_texture, visible_details, visible_packaging, consistency_warnings. "
            "Décris uniquement ce qui est visuellement observable. N'infère jamais composition textile, "
            "matière exacte, performances, certification, taille, compatibilité ou bénéfice non prouvé. "
            "Si incertain, indique 'à confirmer'."
        )
    }]
    for name, data, mime in references[:8]:
        b64 = base64.b64encode(data).decode("ascii")
        content.append({"type":"input_image","image_url":f"data:{mime or _mime(name)};base64,{b64}","detail":"high"})
    response = client.responses.create(
        model=text_model,
        input=[{"role":"user","content":content}]
    )
    raw = response.output_text.strip()
    raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.I)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"raw_visual_analysis":raw,"warning":"JSON non structuré ; vérifier les informations."}

def create_carousel_plan(api_key, text_model, product, analysis):
    client = OpenAI(api_key=api_key)
    instructions = {
        "task":"Créer un plan de carrousel TikTok Shop de 7 slides en français.",
        "product_facts":product,
        "visual_analysis":analysis,
        "slide_structure":SLIDE_SPECS,
        "rules":[
            "N'invente aucun fait produit, bénéfice, matière, certification, avis, résultat, prix ou garantie.",
            "Les photos ne prouvent pas les caractéristiques techniques ; les champs fournis font foi.",
            "Ne jamais créer de faux témoignage client ni présenter une scène UGC comme un vrai avis.",
            "Une seule idée courte par slide ; formulation naturelle, mobile-first.",
            "Le produit doit rester reconnaissable et conforme aux photos source.",
            "Si une donnée manque, ne pas la combler : omettre le claim."
        ],
        "required_json":{"slides":[{"number":"1-7","role":"...","style":"...","headline":"...","support_copy":"...","overlay_text":"...","visual_direction":"..."}]}
    }
    response = client.responses.create(
        model=text_model,
        input=[{"role":"user","content":[{"type":"input_text","text":json.dumps(instructions,ensure_ascii=False)}]}]
    )
    raw=response.output_text.strip()
    raw=re.sub(r"^```(?:json)?\s*|\s*```$","",raw,flags=re.I)
    data=json.loads(raw)
    slides=data.get("slides",[])
    if len(slides)!=7:
        raise ValueError("Le modèle n'a pas retourné exactement 7 diapositives.")
    for i,s in enumerate(slides,1):
        s["number"]=i
        # Pin style and role to the approved mix.
        s["role"]=SLIDE_SPECS[i-1]["role"]
        s["style"]=SLIDE_SPECS[i-1]["style"]
    return {"slides":slides}

def _build_prompt(product, analysis, slide):
    facts = {
        "nom":product.get("product_name",""),
        "bénéfice confirmé":product.get("primary_benefit",""),
        "caractéristiques confirmées":product.get("features",[]),
        "matière confirmée":product.get("materials",""),
        "variantes disponibles":product.get("variants",""),
        "éléments inclus":product.get("included_items",""),
        "à éviter":product.get("forbidden_claims",""),
        "analyse visuelle":analysis
    }
    return f"""
Create ONE photorealistic vertical TikTok Shop carousel image, 9:16 portrait.
VISUAL DIRECTION: {slide.get('visual_direction','')}
STYLE: {slide.get('style','')} — {SLIDE_SPECS[slide['number']-1]['visual']}
PRODUCT IDENTITY LOCK:
- Use the supplied reference images as the authoritative source for the exact SKU.
- Preserve silhouette, proportions, construction, panel layout, seams, stitching, closures, hardware, labels, logo placement, colors and all visible details.
- Do not redesign, simplify, embellish, recolor or add accessories to the product.
- Do not create extra products, extra variants, fake logos, fake labels or legible invented packaging text.
- The product must remain the clear subject and match the reference photos.
VERIFIED PRODUCT CONTEXT (for scene selection only; do not turn unknowns into claims):
{json.dumps(facts,ensure_ascii=False)}
COMPOSITION:
- Natural believable camera perspective, realistic lighting, true-to-life materials and shadows.
- Vertical portrait framing with key subject safely inside frame.
- No platform UI, carousel arrows, pagination dots, borders, watermarks or decorative badges.
- No text, captions, typography or prices in the generated image; editable copy is added separately.
- Avoid impossible hands, distorted anatomy, warped objects and floating product details.
""".strip()

def _fit_9x16(img):
    # Crop to exact 9:16 without stretching; final export size 1080x1920.
    return ImageOps.fit(img.convert("RGB"), (1080,1920), method=Image.Resampling.LANCZOS, centering=(0.5,0.5))

def _font(size):
    candidates=[
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/Library/Fonts/Arial Bold.ttf",
        "C:/Windows/Fonts/arialbd.ttf"
    ]
    for p in candidates:
        if Path(p).exists():
            return ImageFont.truetype(p,size)
    return ImageFont.load_default()

def _wrap(draw, text, font, max_width):
    words=(text or "").split()
    lines=[]; current=""
    for word in words:
        test=(current+" "+word).strip()
        if draw.textbbox((0,0),test,font=font)[2] <= max_width:
            current=test
        else:
            if current: lines.append(current)
            current=word
    if current: lines.append(current)
    return lines

def _add_overlay(img, text):
    if not text or not text.strip():
        return img
    img=img.convert("RGBA")
    # Subtle dark translucent top panel keeps text legible; avoids TikTok UI safe zones.
    overlay=Image.new("RGBA",img.size,(0,0,0,0))
    d=ImageDraw.Draw(overlay)
    font=_font(54)
    lines=_wrap(d,text.strip(),font,900)
    lines=lines[:3]
    if not lines: return img.convert("RGB")
    line_h=68
    panel_h=70+len(lines)*line_h
    d.rounded_rectangle((54,110,1026,110+panel_h),radius=28,fill=(0,0,0,135))
    y=142
    for line in lines:
        d.text((88,y),line,font=font,fill=(255,255,255,255),stroke_width=0)
        y+=line_h
    return Image.alpha_composite(img,overlay).convert("RGB")

def generate_carousel(api_key, image_model, quality, product, analysis, plan, references, job_id, progress_callback=None):
    client=OpenAI(api_key=api_key)
    folder=OUTPUTS/job_id
    folder.mkdir(parents=True,exist_ok=True)
    # Save references in job folder for reproducibility.
    ref_paths=[]
    for idx,(name,data,mime) in enumerate(references[:8],1):
        ext=Path(name).suffix.lower() or ".jpg"
        p=folder/f"reference_{idx:02d}{ext}"
        p.write_bytes(data); ref_paths.append(p)
    result_slides=[]
    for idx,slide in enumerate(plan["slides"],1):
        if progress_callback: progress_callback(idx-1,7,f"Génération {idx}/7 • {slide['role']} ({slide['style']})")
        handles=[]
        try:
            for p in ref_paths:
                handles.append(open(p,"rb"))
            response=client.images.edit(
                model=image_model,
                image=handles,
                prompt=_build_prompt(product,analysis,slide),
                size="1088x1920",
                quality=quality,
                output_format="png"
            )
            image_bytes=base64.b64decode(response.data[0].b64_json)
        finally:
            for h in handles:
                try: h.close()
                except Exception: pass
        image=Image.open(io.BytesIO(image_bytes))
        image=_fit_9x16(image)
        image=_add_overlay(image,slide.get("overlay_text",""))
        out=folder/f"{idx:02d}_{safe_slug(slide['role'])}.png"
        image.save(out,"PNG",optimize=True)
        result_slides.append({"number":idx,"role":slide["role"],"style":slide["style"],"path":str(out)})
        if progress_callback: progress_callback(idx,7,f"Terminé {idx}/7 • {slide['role']}")
    manifest={
        "job_id":job_id,"product":product,"visual_analysis":analysis,
        "plan":plan,"slides":result_slides,"format":{"width":1080,"height":1920,"ratio":"9:16"},
        "engine":image_model,"quality":quality,"created_at":__import__("datetime").datetime.utcnow().isoformat()+"Z",
        "publication_status":"not_published"
    }
    (folder/"manifest.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding="utf-8")
    return {"job_id":job_id,"folder":str(folder),"slides":result_slides,"manifest":manifest}

def create_export_zip(folder):
    folder=Path(folder)
    buf=io.BytesIO()
    with zipfile.ZipFile(buf,"w",zipfile.ZIP_DEFLATED) as z:
        for p in folder.rglob("*"):
            if p.is_file() and not p.name.startswith("reference_"):
                z.write(p,p.relative_to(folder))
    buf.seek(0)
    return buf.getvalue()
