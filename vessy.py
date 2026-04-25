import streamlit as st
from groq import Groq
import requests
from PIL import Image, ImageDraw
import json
from gtts import gTTS
from moviepy.editor import ImageClip, AudioFileClip
import tempfile
import os

# ================= CONFIG =================

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
UNSPLASH_KEY = os.getenv("UNSPLASH_KEY")

if not GROQ_API_KEY:
    st.error("Missing GROQ_API_KEY in secrets.")
    st.stop()

if not UNSPLASH_KEY:
    st.error("Missing UNSPLASH_KEY in secrets.")
    st.stop()

llm = Groq(api_key=GROQ_API_KEY)

st.set_page_config(page_title="Veesy AI", layout="centered")
st.title("Veesy — Visual Teaching AI 🧠🎬")

question = st.text_input("Ask anything:")

# ================= SMART DIAGRAM QUERY GENERATION =================

def extract_visual_keywords(question):

    prompt = f"""
    Convert this question into 3 diagram-style image search phrases.

    IMPORTANT RULES:
    - Prefer scientific diagrams
    - Prefer labeled illustrations
    - Prefer educational visuals
    - Avoid stock photography
    - Avoid people, laptops, desks, offices

    Example:

    Question: What is a black hole?

    Output:
    [
      "black hole spacetime curvature diagram labeled",
      "event horizon black hole structure illustration",
      "black hole gravity bending light diagram"
    ]

    Return ONLY valid JSON array.

    Question: {question}
    """

    res = llm.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[{"role": "user", "content": prompt}]
    )

    try:
        queries = json.loads(res.choices[0].message.content)

        # enforce diagram bias automatically
        return [
            q + " diagram labeled illustration"
            for q in queries
        ]

    except:
        return [question + " diagram labeled illustration"]


# ================= IMAGE SEARCH =================

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


# ================= FILTER BAD STOCK IMAGES =================

def get_best_image(question):

    queries = extract_visual_keywords(question)

    for q in queries:

        results = search_images(q, 3)

        for url in results:

            if any(
                bad in url.lower()
                for bad in [
                    "person",
                    "office",
                    "desk",
                    "workspace",
                    "laptop",
                    "portrait",
                    "team",
                    "meeting",
                    "people"
                ]
            ):
                continue

            return url

    return None


# ================= VISUAL POINTER GENERATION =================

def get_visual_points(question):

    prompt = f"""
    You are Vessy, a visual teacher explaining with diagrams.

    For this question:
    "{question}"

    Return 3 teaching pointer labels with coordinates.

    Format ONLY valid JSON:

    [
      {{"label": "Explanation phrase", "x": 0.3, "y": 0.4}},
      {{"label": "Explanation phrase", "x": 0.6, "y": 0.5}},
      {{"label": "Explanation phrase", "x": 0.5, "y": 0.7}}
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

    for idx, p in enumerate(points, start=1):

        x = int(p.get("x", 0.5) * width)
        y = int(p.get("y", 0.5) * height)

        label = f"{idx}. {p.get('label','')}"

        sx, sy = x - 80, y - 80

        draw.line((sx, sy, x, y), fill=arrow_color, width=8)

        draw.polygon(
            [(x, y), (x-20, y-20), (x+20, y-20)],
            fill=arrow_color
        )

        box_w = len(label) * 12 + 20

        draw.rectangle(
            (sx-10, sy-40, sx-10 + box_w, sy),
            fill=bg_color,
            outline=arrow_color,
            width=3
        )

        draw.text((sx, sy-32), label, fill=(0, 0, 0))

    return image


# ================= TEACHING SCRIPT =================

def build_teaching_script(points_json):

    try:
        points = json.loads(points_json)
    except:
        return ""

    lines = []

    for p in points:
        if "label" in p:
            lines.append(p["label"])

    return ". ".join(lines)


# ================= VOICE =================

def generate_voice(text):

    if not text.strip():
        text = "Let me explain this visually step by step."

    temp_audio = tempfile.NamedTemporaryFile(
        delete=False,
        suffix=".mp3"
    )

    audio_path = temp_audio.name
    temp_audio.close()

    gTTS(text=text, lang="en").save(audio_path)

    return audio_path


# ================= VIDEO =================

def create_video(image, audio_path):

    temp_img = tempfile.NamedTemporaryFile(
        delete=False,
        suffix=".png"
    )

    img_path = temp_img.name
    temp_img.close()

    image.save(img_path)

    audio_clip = AudioFileClip(audio_path)

    temp_video = tempfile.NamedTemporaryFile(
        delete=False,
        suffix=".mp4"
    )

    video_path = temp_video.name
    temp_video.close()

    clip = ImageClip(img_path, duration=audio_clip.duration)

    clip = clip.set_audio(audio_clip)

    clip.write_videofile(
        video_path,
        fps=24,
        codec="libx264",
        audio_codec="aac"
    )

    return video_path


# ================= MAIN EXECUTION =================

if st.button("Teach Me"):

    if not question.strip():
        st.warning("Ask something first.")
        st.stop()

    # TEXT EXPLANATION

    with st.spinner("Planning lesson..."):

        chat = llm.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {
                    "role": "system",
                    "content":
                    "Explain visually in 3–5 short teaching bullet points."
                },
                {"role": "user", "content": question}
            ]
        )

        answer = chat.choices[0].message.content

    st.subheader("Veesy explains")
    st.write(answer)

    # IMAGE SELECTION

    with st.spinner("Finding best diagram..."):

        img_url = get_best_image(question)

        if not img_url:
            st.error("No suitable diagram found.")
            st.stop()

        base_img = Image.open(
            requests.get(img_url, stream=True).raw
        ).convert("RGB")

        points_json = get_visual_points(question)

        annotated = annotate_image(base_img, points_json)

    # AUDIO

    with st.spinner("Generating teaching voice..."):

        teaching_text = build_teaching_script(points_json)

        audio_path = generate_voice(teaching_text)

    # VIDEO

    with st.spinner("Creating teaching video..."):

        video_path = create_video(annotated, audio_path)

    st.video(video_path)






