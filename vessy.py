import streamlit as st
from groq import Groq
import requests
from PIL import Image, ImageDraw
import json
from gtts import gTTS


from moviepy import ImageClip, AudioFileClip

import tempfile

# ================= CONFIG =================
import os

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
UNSPLASH_KEY = os.getenv("UNSPLASH_KEY")


llm = Groq(api_key=GROQ_API_KEY)

st.set_page_config(page_title="Vessy AI", layout="centered")
st.title("Vessy — Visual Teaching AI 🧠🎬")

question = st.text_input("Ask anything:")

# ================= IMAGE SEARCH =================
def extract_visual_keyword(question):
    prompt = f"""
    Convert this question into ONE concrete visual search phrase.
    Use nouns only. No explanation.
    Question: {question}
    """
    res = llm.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[{"role": "user", "content": prompt}]
    )
    return res.choices[0].message.content.strip()


def search_images(query, count=3):
    url = "https://api.unsplash.com/search/photos"
    params = {
        "query": query,
        "per_page": count,
        "client_id": UNSPLASH_KEY
    }
    res = requests.get(url, params=params).json()

    images = []
    if res.get("results"):
        for r in res["results"]:
            images.append(r["urls"]["regular"])

    return images


# ================= VISUAL POINTS =================
def get_visual_points(question):
    prompt = f"""
    You are Vessy, a visual teacher who explains by pointing at images.

    For the question:
    "{question}"

    Decide 3 important things a teacher would POINT TO
    while explaining this concept visually.

    VERY IMPORTANT RULES FOR LABELS:
    - Do NOT use abstract technical words like:
      data, algorithm, model, system, process
    - Labels must describe WHAT IS HAPPENING, not what it is
    - Labels should sound like spoken teaching, not metadata

    Good examples:
    - "Information flows through this part"
    - "A decision is made here"
    - "This step transforms the input"
    - "Energy is absorbed at this point"

    Bad examples:
    - "Data"
    - "Algorithm"
    - "Processing unit"

    Return ONLY valid JSON in this exact format:

    [
      {{"label": "Teaching action phrase", "x": 0.3, "y": 0.4}},
      {{"label": "Teaching action phrase", "x": 0.6, "y": 0.5}},
      {{"label": "Teaching action phrase", "x": 0.5, "y": 0.7}}
    ]
    """

    res = llm.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[{"role": "user", "content": prompt}]
    )

    return res.choices[0].message.content



# ================= DRAW ARROWS =================
def annotate_image(image, points_json):
    draw = ImageDraw.Draw(image)
    width, height = image.size

    try:
        points = json.loads(points_json)
    except:
        return image

    arrow_color = (0, 180, 255)
    bg_color = (180, 240, 255)
    text_color = (0, 0, 0)

    for idx, p in enumerate(points, start=1):
        if "label" not in p:
            continue

        x = int(p.get("x", 0.5) * width)
        y = int(p.get("y", 0.5) * height)
        label = f"{idx}. {p['label']}"

        sx, sy = x - 80, y - 80

        draw.line((sx, sy, x, y), fill=arrow_color, width=8)
        draw.polygon([(x, y), (x-20, y-20), (x+20, y-20)], fill=arrow_color)

        box_w = len(label) * 12 + 20
        draw.rectangle(
            (sx-10, sy-40, sx-10+box_w, sy),
            fill=bg_color,
            outline=arrow_color,
            width=3
        )
        draw.text((sx, sy-32), label, fill=text_color)

    return image


# ================= TEACHING SCRIPT (SAFE) =================
def build_teaching_script(points_json):
    try:
        points = json.loads(points_json)
    except:
        return ""

    lines = []
    for p in points:
        label = p.get("label", "").strip()
        if label:
            lines.append(label)

    return ". ".join(lines)


# ================= VOICE (SAFE) =================
def generate_voice(text):
    if not text or not text.strip():
        text = (
            "Let me explain this visually step by step. "
            "Focus on the highlighted parts as I explain."
        )

    temp_audio = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
    audio_path = temp_audio.name
    temp_audio.close()

    tts = gTTS(text=text, lang="en")
    tts.save(audio_path)

    return audio_path




# ================= VIDEO =================
def create_video(image, audio_path):
    temp_img = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
    img_path = temp_img.name
    temp_img.close()
    image.save(img_path)

    audio_clip = AudioFileClip(audio_path)

    temp_video = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4")
    video_path = temp_video.name
    temp_video.close()

    clip = ImageClip(img_path, duration=audio_clip.duration)
    clip = clip.with_audio(audio_clip)

    clip.write_videofile(
        video_path,
        fps=24,
        codec="libx264",
        audio_codec="aac"
    )

    return video_path


# ================= ACTION =================
if st.button("Teach Me"):
    if not question.strip():
        st.warning("Ask something first.")
        st.stop()

    # ---- Teaching text ----
    with st.spinner("Planning lesson..."):
        chat = llm.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are Vessy, a calm visual teaching assistant. "
                        "Start with one short guiding sentence. "
                        "Then explain in 3–5 short bullet points. "
                        "Use teaching language like 'Look here' or 'Notice this'. "
                        "Keep it short and clear."
                    )
                },
                {"role": "user", "content": question}
            ]
        )
        answer = chat.choices[0].message.content

    st.subheader("Vessy explains")
    st.write(answer)

    # ---- Visual creation (NO STATIC IMAGE SHOWN) ----
    with st.spinner("Preparing visual lesson..."):
        visual_query = extract_visual_keyword(question)
        img_urls = search_images(visual_query, count=3)

        if not img_urls:
            st.error("No visuals found.")
            st.stop()

        base_img = Image.open(
            requests.get(img_urls[0], stream=True).raw
        ).convert("RGB")

        points_json = get_visual_points(question)
        annotated = annotate_image(base_img, points_json)

    # ---- Voice + Video ----
    with st.spinner("Teaching with voice..."):
        teaching_text = build_teaching_script(points_json)
        audio_path = generate_voice(teaching_text)

    with st.spinner("Creating teaching video..."):
        video_path = create_video(annotated, audio_path)

    st.video(video_path)












