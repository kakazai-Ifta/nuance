"""
app.py - the Nuance screen (built with Streamlit).

Run it with:   streamlit run app.py
"""

import html
import json
import os
import textwrap
import altair as alt
import pandas as pd
import streamlit as st

from report import make_pdf
from agents import (DEFAULT_TOPICS, suggest_topics, analyse_review, make_priority_table, make_briefing, baseline_counts)

st.set_page_config(page_title="Nuance", layout="wide")

# ---------------------------------------------------------------
# Look and feel: the same plum / rose / gold colours as the slides and the PDF
# ---------------------------------------------------------------
PLUM, ROSE, GOLD, BLUSH, LINE = "#4A2545", "#B5476B", "#C9A24B", "#F7EEF1", "#E8B4C0"

st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Lora:wght@600;700&display=swap');

h1, h2, h3 {{ font-family: 'Lora', Georgia, serif !important; color: {PLUM} !important; }}
h1 {{ border-bottom: 3px solid {GOLD}; padding-bottom: 0.2rem; display: inline-block; }}

/* sidebar: plum background, light text */
[data-testid="stSidebar"] {{ background-color: {PLUM}; }}
[data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3,
[data-testid="stSidebar"] label, [data-testid="stSidebar"] p,
[data-testid="stSidebar"] span, [data-testid="stSidebar"] small {{ color: {BLUSH} !important; }}
[data-testid="stSidebar"] h2 {{ color: {GOLD} !important; }}
[data-testid="stSidebar"] input, [data-testid="stSidebar"] textarea {{ color: #2B1B2A !important; }}

/* buttons */
.stButton > button[kind="primary"], .stDownloadButton > button {{
    background-color: {ROSE}; color: white; border: none; border-radius: 8px;
}}
.stButton > button[kind="primary"]:hover, .stDownloadButton > button:hover {{
    background-color: {PLUM}; color: white;
}}

/* metric tiles and cards */
[data-testid="stMetric"] {{
    background-color: {BLUSH}; border-left: 5px solid {ROSE};
    border-radius: 8px; padding: 0.8rem 1rem;
}}
[data-testid="stMetricValue"] {{ color: {PLUM}; font-family: 'Lora', Georgia, serif; }}
[data-testid="stVerticalBlockBorderWrapper"] {{ border-color: {LINE} !important; border-radius: 10px; }}

/* bigger text inside the "How Nuance works" pop-up */
[role="dialog"] [data-testid="stMarkdownContainer"] p {{ font-size: 1.15rem; }}
[role="dialog"] code {{ font-size: 1.05rem !important; line-height: 1.6; }}
[role="dialog"] [data-testid="stCaptionContainer"] {{ font-size: 1.05rem; }}
</style>
""", unsafe_allow_html=True)

st.title("Nuance")
st.caption("Reads between the lines of customer reviews, and tells you what to fix first.")
button_slot = st.container()     # the "How Nuance works" button goes here (filled at the end)

# ---------------------------------------------------------------
# Left side: inputs
# ---------------------------------------------------------------

# ---------------------------------------------------------------
# Example settings (you can edit every box after choosing one)
# ---------------------------------------------------------------
PRESETS = {
    "Skincare (Dior on Sephora)": {
        "product": "Dior skincare sold at Sephora: Capture Totale Super Potent Eye Serum, Capture Totale Super Potent Rich Cream, Capture Totale firming cream, and Cica Recover Balm",
        "brand": "Brand: Dior, a French luxury house. Skincare lines: Capture Totale (anti-ageing, \"backed by over 40 years of stem cell research\") and Cica (repair for stressed skin). Sold at Sephora at premium prices.\n"
                 "Brand promises:\n"
                 "- Capture Totale Super Potent Eye Serum: eyes look younger, less puffiness from the first week, fewer dark circles and fine lines, firmer and brighter eye contour, hydration, a fresh cooling feel, applied with the 360 Cryo-Flex massaging applicator.\n"
                 "- Capture Totale Super Potent Rich Cream: rich texture, age-defying correction of wrinkles and firmness, \"seals in\" benefits.\n"
                 "- Capture Totale firming cream: firmer, more visibly revitalised skin.\n"
                 "- Cica Recover Balm: regenerating multi-use balm for face and body, long-lasting hydration, soothes discomfort, suitable even for the most sensitive skin, no oily or sticky film, no synthetic fragrance.\n"
                 "Audience: adults who buy premium anti-ageing skincare and expect luxury-level, visible results for the price.",
        "topics": "results: visible effect on wrinkles, firmness, dark circles, puffiness, glow, or no visible effect\n"
                  "hydration: moisture, nourishment, dryness\n"
                  "texture: how it feels on the skin, rich, heavy, greasy, sticky or light\n"
                  "scent: smell or fragrance, too strong, perfume-like, fragrance-free expectations\n"
                  "irritation: breakouts, burning, redness, allergic reactions\n"
                  "packaging: jar, pump, bottle, applicator, hygiene, leaking\n"
                  "price: cost and value for money",
    },
    "Hair diffuser (Curly Co)": {
        "product": "Collapsible hair diffuser for curly hair, sold by a beauty brand",
        "brand": "Example brand that sells a travel hair diffuser.\n"
                 "Brand promises: fits most hair dryers, compact, durable.\n"
                 "Audience: people with curly hair.",
        "topics": DEFAULT_TOPICS,
    },
    "Skincare (LANEIGE on Sephora)": {
        "product": "Lip Sleeping Mask, an overnight lip treatment by LANEIGE, sold at Sephora",
        "brand": "Brand: LANEIGE, a Korean skincare and beauty brand sold at Sephora.\n"
                 "Brand promises: deep hydration, soft and smooth skin, gentle on sensitive skin, pleasant scent.\n"
                 "Audience: people looking for hydrating skincare, mostly dry or combination skin.",
        "topics": "hydration: dryness relief, moisture, softness\n"
                  "texture: how it feels on the skin, sticky, greasy, thick or light\n"
                  "scent: smell or flavour\n"
                  "irritation: breakouts, burning, allergic reactions\n"
                  "packaging: jar, tube, pump, hygiene, leaking\n"
                  "price: cost and value for money",
    },
    "Your own product (empty)": {"product": "", "brand": "", "topics": "quality: how good or bad the product is\nprice: cost and value for money"},
}

DEMO_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "demo", "dior_demo.json")
DEMO_AVAILABLE = os.path.exists(DEMO_FILE)
MODES = ["Demo: Dior results", "Analyse my own reviews"]

uploaded = None       # filled in only in "Analyse my own reviews" mode
run = False
brand_label = ""
n_products = 5        # how many products to analyse (the ones with most reviews)

with st.sidebar:
    mode = st.radio("Mode", MODES, index=0 if DEMO_AVAILABLE else 1)
    live_mode = (mode == MODES[1])

    if not live_mode:
        st.caption("You are looking at saved results from a real run of Nuance. "
                   "Switch to the second mode to analyse your own reviews (this needs Ollama on your computer).")
    else:
        st.header("1. Add your reviews")
        uploaded = st.file_uploader("Drag and drop a CSV or TXT file", type=["csv", "txt"])

        text_column = None
        rating_column = None
        product_column = None
        sample_texts = []
        only_three_star = False

        # If it is a CSV, let the user choose which column holds the review text
        if uploaded is not None and uploaded.name.lower().endswith(".csv"):
            table = pd.read_csv(uploaded)
            columns = list(table.columns)
            # Guess the review text column: a usual name, otherwise the text column with the longest entries
            usual_names = ["text", "review_text", "review", "reviews", "review_body", "body", "comment", "content"]
            found = [name for name in columns if name.lower() in usual_names]
            if found:
                default_index = columns.index(found[0])
            else:
                lengths = {name: table[name].astype(str).str.len().mean() for name in columns if not pd.api.types.is_numeric_dtype(table[name])}
                default_index = columns.index(max(lengths, key=lengths.get)) if lengths else 0
            text_column = st.selectbox("Which column has the review text?", columns, index=default_index)

            # Warn if the chosen column looks like titles instead of full reviews
            average_length = table[text_column].dropna().astype(str).str.len().mean()
            if average_length < 60:
                st.warning(f"The entries in this column are very short (about {round(average_length)} characters). "
                           "Is this the full review text, and not a title?")

            # Optional: keep only one brand (useful when the file has many brands)
            brand_options = ["(all brands)"] + columns
            brand_guess = brand_options.index("brand_name") if "brand_name" in columns else 0
            brand_column = st.selectbox("Which column says the brand? (optional)", brand_options, index=brand_guess)
            if brand_column != brand_options[0]:
                brand_counts = table[brand_column].astype(str).value_counts()
                brand_names = [f"{name}  ({count} reviews)" for name, count in brand_counts.items()]
                picked = st.selectbox("Analyse which brand?", brand_names)
                brand_label = picked.rsplit("  (", 1)[0]
                table = table[table[brand_column].astype(str) == brand_label]

            product_options = ["(none - one product)"] + columns
            chosen = st.selectbox("Which column says the product? (optional)", product_options)
            if chosen != product_options[0]:
                product_column = chosen
                n_products = st.slider("How many products? (the ones with the most reviews)", 1, 5, 5)
                st.caption("The slider in step 3 counts reviews PER product.")

            if "rating" in columns:
                rating_column = "rating"
                only_three_star = st.checkbox("Only analyse 3-star reviews", value=True)

            # A random sample of reviews, used to suggest topics
            sample_data = table
            if rating_column is not None and only_three_star:
                sample_data = table[table[rating_column] == 3]
            sample_texts = sample_data[text_column].dropna().astype(str)
            sample_texts = sample_texts.sample(min(30, len(sample_texts)), random_state=0).tolist()

        st.header("2. Describe the product and brand")
        preset = st.selectbox("Start from an example", list(PRESETS.keys()))
        chosen_preset = PRESETS[preset]
        # the key changes with the preset, so the boxes refill when you switch example
        product_info = st.text_input("Product", value=chosen_preset["product"], key="product_" + preset)
        brand_context = st.text_area("Brand context", value=chosen_preset["brand"], height=130, key="brand_" + preset)
        topics_text = st.text_area(
            "Topics to look for (one per line: name: definition)",
            value=chosen_preset["topics"], height=150, key="topics_" + preset,
        )
        st.caption('The topic "other" is added automatically.')

        # Let Llama read a sample of the reviews and propose the topics
        def fill_topics(texts, info, box_key):
            suggestion = suggest_topics(texts, info)
            if suggestion != "":
                st.session_state[box_key] = suggestion

        st.button(
            "Suggest topics from my reviews",
            on_click=fill_topics,
            args=(sample_texts, product_info, "topics_" + preset),
            disabled=(len(sample_texts) == 0),
        )
        st.caption("Llama reads up to 30 reviews (about a minute) and fills the box above. You can then edit it.")

        st.header("3. Analyse")
        max_reviews = st.slider("How many reviews to analyse", 5, 50, 10)
        st.caption("Each review takes about 20 to 30 seconds on a laptop.")
        run = st.button("Analyse reviews", type="primary")


# ---------------------------------------------------------------
# Read the reviews from the uploaded file
# Returns a dictionary: product name -> list of review texts
# ---------------------------------------------------------------
def read_reviews():
    """Returns: (product -> list of reviews, product -> reviews in the file, number of products in the file)."""
    if uploaded is None:
        return {}, {}, 0

    if uploaded.name.lower().endswith(".csv"):
        data = table.copy()
        if rating_column is not None and only_three_star:
            data = data[data[rating_column] == 3]
        data = data.dropna(subset=[text_column])

        if product_column is None:
            return {"All reviews": data[text_column].astype(str).tolist()[:max_reviews]}, {}, 0

        data = data.dropna(subset=[product_column])
        data = data.assign(_product=data[product_column].astype(str))
        all_counts = data["_product"].value_counts()               # reviews per product, biggest first
        chosen_counts = all_counts.head(n_products)                # the products with the most reviews

        groups = {}
        for name in chosen_counts.index:
            part = data[data["_product"] == name]
            groups[name] = part[text_column].astype(str).tolist()[:max_reviews]
        return groups, {name: int(count) for name, count in chosen_counts.items()}, len(all_counts)

    uploaded.seek(0)
    lines = uploaded.read().decode("utf-8", errors="ignore").splitlines()
    texts = [line.strip() for line in lines if line.strip()]
    return {"All reviews": texts[:max_reviews]}, {}, 0


# ---------------------------------------------------------------
# When the button is pressed: run the agents, one product at a time
# ---------------------------------------------------------------
if run:
    groups, product_counts, products_in_file = read_reviews()
    total = sum(len(texts) for texts in groups.values())

    if total == 0:
        st.warning("Please add a file with reviews first.")
    else:
        progress = st.progress(0, text="Starting...")
        runs = {}
        done = 0

        for name, reviews in groups.items():
            # With several products, the product name is what the agents are told about
            info = product_info if name == "All reviews" else name
            results = []

            for review in reviews:
                progress.progress(done / total, text=f"{name[:40]}: review {len(results) + 1} of {len(reviews)}...")
                try:   # if one review causes an error, skip it instead of stopping everything
                    results.append(analyse_review(review, info, brand_context, topics_text))
                except Exception as error:
                    st.caption(f"Skipped a review: {error}")
                done += 1

            priority_table = make_priority_table(results)
            briefing = []
            if len(priority_table) > 0:
                briefing = make_briefing(priority_table, info, brand_context, topics_text=topics_text)

            runs[name] = {"reviews": reviews, "results": results,
                          "priority_table": priority_table, "briefing": briefing}

        st.session_state["runs"] = runs     # Streamlit re-runs the page on every click
        st.session_state["meta"] = {"brand": brand_label, "product": product_info,
                                    "brand_context": brand_context, "topics": topics_text,
                                    "model": "llama3.1:8b (local, Ollama)",
                                    "product_counts": product_counts,
                                    "products_requested": n_products,
                                    "products_in_file": products_in_file,
                                    "reviews_per_product": max_reviews,
                                    "filters": ", ".join(
                                        (["brand " + brand_label] if brand_label else [])
                                        + (["3-star reviews"] if only_three_star else []))}
        progress.empty()

        if sum(len(r["results"]) for r in runs.values()) == 0:
            st.error("No review could be analysed. Is Ollama installed and open on this computer? "
                     "(A hosted page can only show the demo results.)")


# ---------------------------------------------------------------
# The results screen for ONE product
# ---------------------------------------------------------------
def show_product(name, run_data):
    reviews = run_data["reviews"]
    results = run_data["results"]
    priority_table = run_data["priority_table"]
    briefing = run_data["briefing"]
    key = name                                  # makes widget names unique per product

    flagged = [r for r in results if r["needs_human_review"]]
    low_confidence = [b for b in briefing if b["needs_human_review"]]

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Reviews analysed", len(results))
    col2.metric("Topics found", len(priority_table))
    col3.metric("Reviews flagged for a human", len(flagged))
    col4.metric("Advice with low confidence", len(low_confidence))

    # Sentiment analysis next to the topics found by Nuance
    st.subheader("Detailed analysis")
    counts = baseline_counts(reviews)
    left, right = st.columns(2)

    with left:
        st.markdown("**Normal sentiment analysis:**")
        st.bar_chart(pd.DataFrame({"reviews": counts}), color=LINE)
        positive_share = round(100 * counts["positive"] / max(len(reviews), 1))
        st.info(f"**Result:** {positive_share}% of reviews are labelled positive.")

    with right:
        st.markdown("**Nuance analysis (topics behind the reviews):**")
        if len(priority_table) > 0:
            st.bar_chart(priority_table.set_index("topic")[["reviews"]], color=ROSE)
        else:
            st.write("No topics found.")

        if len(briefing) > 0:
            top = briefing[0]
            st.success(
                f"**Result:** the biggest issue is **{top['topic']}** "
                f"({top['reviews']} of {len(results)} reviews, priority {top['priority']}).\n\n"
                f"**Recommended action:** {top['action']}\n\n"
                f"**Confidence:** {top['confidence']}"
            )

    # Ranked topics
    st.subheader("What to fix first")
    if len(priority_table) > 0:
        st.dataframe(
            priority_table[["topic", "reviews", "share_%", "priority", "risk_of_losing_customer"]],
            hide_index=True,
            width="stretch",
        )

    # The briefing: one card per topic, with a human decision
    if len(briefing) > 0:
        st.caption("Suggested actions are ideas for a human to review. Any detail in them that the customers did not write is the AI's suggestion, not a finding.")
    for item in briefing:
        with st.container(border=True):
            st.markdown(f"### {item['topic'].capitalize()}")
            st.write(
                f"**Priority:** {item['priority']}  |  "
                f"**Risk of losing customers:** {item['risk']}  |  "
                f"**Confidence:** {item['confidence']}  |  "
                f"**Reviews:** {item['reviews']}"
            )
            if item.get("risk") == "Unclear":
                st.caption("Risk is unclear: fewer than 3 customers said clearly whether they would buy again.")
            elif item.get("decided") is not None:
                st.caption(f"Risk is based on {item['decided']} guesses where the customer's plan was clear.")
            st.write(f"**What customers believe:** {item['mindset']}")
            st.write(f"**Recommended action:** {item['action']}")
            if item.get("quotes"):
                with st.expander("What customers wrote"):
                    for quote in item["quotes"]:
                        st.write(f"- \u201c{quote}\u201d")
            st.caption(f"Validation check: {item['comment']}")

            if item["needs_human_review"]:
                st.warning("Low confidence. Please review this advice carefully.")

            decision = st.radio(
                "Your decision",
                ["Waiting", "Accept", "Edit", "Reject"],
                horizontal=True,
                key=f"decision_{key}_{item['topic']}",
            )
            if decision == "Edit":
                st.text_area("Edit the action", value=item["action"], key=f"edit_{key}_{item['topic']}")

    # Reviews the agents were not sure about
    if len(flagged) > 0:
        with st.expander(f"Reviews flagged for a human ({len(flagged)})"):
            for r in flagged:
                st.write("- " + r["review"][:300])

    st.download_button(
        "Download the briefing (JSON)",
        data=json.dumps(briefing, indent=2),
        file_name="nuance_briefing.json",
        mime="application/json",
        key=f"download_{key}",
    )


# ---------------------------------------------------------------
# Show the results: one product directly, several products as tabs
# ---------------------------------------------------------------
# ---------------------------------------------------------------
# Demo results saved from a real run (so nobody needs Ollama to look)
# ---------------------------------------------------------------
@st.cache_data
def load_demo():
    with open(DEMO_FILE, encoding="utf-8") as f:
        data = json.load(f)
    columns = ["topic", "reviews", "share_%", "priority", "risk_of_losing_customer", "examples"]
    runs = {}
    for name, r in data["runs"].items():
        runs[name] = {"reviews": r["reviews"], "results": r["results"],
                      "priority_table": pd.DataFrame(r["priority_table"], columns=columns),
                      "briefing": r["briefing"]}
    return runs, data.get("meta", {})


def runs_to_json(runs, meta):
    data = {"meta": meta, "runs": {}}
    for name, r in runs.items():
        data["runs"][name] = {"reviews": r["reviews"], "results": r["results"],
                              "priority_table": r["priority_table"].to_dict("records"),
                              "briefing": r["briefing"]}
    return json.dumps(data, indent=1, default=lambda o: o.item() if hasattr(o, "item") else str(o))


# ---------------------------------------------------------------
# The flow chart: how Nuance works (hover over a box to see an example)
# ---------------------------------------------------------------
FLOW_STEPS = [
    {"kind": "pale", "title": "Customer reviews", "sub": "a CSV file with a text column",
     "tip": [("What it is", "Any CSV or text file of reviews. Optional columns for rating, brand and product unlock filters."),
             ("Example", "\u201cThe cream feels lovely and rich, but after two months I cannot see any change in my wrinkles. For this price I expected more. Probably will not repurchase.\u201d")]},
    {"kind": "rose", "title": "1. Theory-of-Mind", "sub": "guesses what the customer believes, feels and intends",
     "tip": [("Uses", "Llama (the AI)"),
             ("What it does", "Reads one review and gives 2 different explanations, each with a belief, a feeling and an intention."),
             ("Example output", "Guess 1: \u201cNo visible results for the price\u201d, disappointed, stop buying.  Guess 2: \u201cPleasant but not worth the money\u201d, mixed, undecided.")]},
    {"kind": "rose", "title": "2. Domain", "sub": "checks each guess against the review and the brand",
     "tip": [("Uses", "Llama answers yes/no questions, Python decides keep or drop"),
             ("What it does", "Asks: do the customer's own words support the belief? Does the intention contradict something they said?"),
             ("Example", "Guess 1 is kept (topic: results). Guess 2 is dropped, because the customer says they will not repurchase, not \u201cundecided\u201d. If every guess is dropped, the review is flagged for a human.")]},
    {"kind": "pale", "title": "3. Prioritiser", "sub": "counts topics and ranks them",
     "tip": [("Uses", "Plain Python, no AI"),
             ("What it does", "Counts how many reviews mention each topic and ranks the topics."),
             ("Rule", "25% of reviews or more = High priority, 10% or more = Medium, otherwise Low."),
             ("Example", "12 of 30 reviews mention results = 40% = High priority.")]},
    {"kind": "rose", "title": "4. Validation", "sub": "checks the advice and scores the confidence",
     "tip": [("Uses", "Llama writes and checks the advice, Python adds up the points"),
             ("What it does", "Writes advice for each top topic, then answers two yes/no questions about it."),
             ("Example", "Advice is about the topic (+1), specific and doable (+1), many reviews support it (+1) = 3 points = High confidence. Low confidence is flagged for a human.")]},
    {"kind": "gold", "title": "Human decision", "sub": "Accept, Edit or Reject",
     "tip": [("What it does", "A person reads the advice with its priority and confidence, then decides."),
             ("Why", "The AI can be wrong, so a person stays in control. Nuance never acts on its own.")]},
]

FLOW_CSS = """
<style>
.flow { display:flex; justify-content:center; align-items:stretch; gap:14px; margin:8px 0; font-family:'Source Sans Pro',Helvetica,Arial,sans-serif; }
.step { position:relative; flex:1 1 0; min-width:0; padding:26px 18px; border-radius:16px; border:3px solid; text-align:center; cursor:help; outline:none; transition:transform .15s; }
.step:hover, .step:focus { transform:translateY(-4px); z-index:60; }
.step .t { font-size:1.55rem; font-weight:700; line-height:1.2; }
.step .s { font-size:1.2rem; margin-top:8px; line-height:1.35; }
.step.rose { background:#B5476B; border-color:#B5476B; color:#fff; }
.step.pale { background:#F7EEF1; border-color:#4A2545; color:#4A2545; }
.step.gold { background:#C9A24B; border-color:#C9A24B; color:#2B1B2A; }
.arrow { align-self:center; font-size:2.4rem; color:#7A4B78; }
.down { text-align:center; font-size:2.4rem; color:#7A4B78; line-height:1; margin:4px 0 8px; }
.tip { display:none; position:absolute; top:100%; left:50%; transform:translateX(-50%); margin-top:12px; width:420px; max-width:85vw;
       background:#fff; color:#2B1B2A; border:3px solid #4A2545; border-radius:14px; padding:16px 18px; text-align:left;
       font-size:1.15rem; line-height:1.45; box-shadow:0 12px 32px rgba(0,0,0,.28); z-index:100; cursor:default; }
.tip b { color:#B5476B; }
.tip p { margin:0 0 9px; }
.step:hover .tip, .step:focus .tip { display:block; }
.step.first .tip { left:0; transform:none; }
.step.last .tip { left:auto; right:0; transform:none; }
.hint { text-align:center; color:#7A4B78; font-size:1.05rem; margin:-4px 0 6px; }
</style>
"""


def flow_html():
    boxes = []
    for i, step in enumerate(FLOW_STEPS):
        tip = "".join(f"<p><b>{html.escape(label)}:</b> {html.escape(text)}</p>" for label, text in step["tip"])
        place = ["first", "", "last"][i % 3]          # keeps the pop-up inside the window
        boxes.append(f'<div class="step {step["kind"]} {place}" tabindex="0">'
                     f'<div class="t">{html.escape(step["title"])}</div>'
                     f'<div class="s">{html.escape(step["sub"])}</div>'
                     f'<div class="tip">{tip}</div></div>')

    rows = []
    for start in range(0, len(boxes), 3):               # three boxes per row
        row = boxes[start:start + 3]
        rows.append('<div class="flow">' + '<div class="arrow">&rarr;</div>'.join(row) + "</div>")
    between = '<div class="down">&darr;</div>'
    return (FLOW_CSS + '<div class="hint">Hover over a box to see what it does, with an example.</div>'
            + between.join(rows))


@st.dialog("How Nuance works", width="large")
def show_flow():
    st.html(flow_html())
    st.caption("Rose boxes use Llama (the AI). Pale boxes are plain Python. Gold is the person who decides.")

    st.subheader("Follow one review through the pipeline")
    st.caption("This example review was written for this explanation. Real outputs are in the Results tab.")

    with st.container(border=True):
        st.markdown("**The review**")
        st.markdown("> The cream feels lovely and rich, but after two months I cannot see any change in my "
                    "wrinkles. For this price I expected more. Probably will not repurchase.")
        st.markdown("Normal sentiment analysis reads the nice words and says **positive**. Nuance reads the meaning.")

    with st.container(border=True):
        st.markdown("**Step 1. Theory-of-Mind (Llama)** guesses two different explanations")
        st.code('1. belief: "The cream does not give visible results for its price"\n'
                '   feeling: disappointed   intention: stop buying\n'
                '2. belief: "The cream feels pleasant but is not worth the money"\n'
                '   feeling: mixed          intention: undecided', language=None)

    with st.container(border=True):
        st.markdown("**Step 2. Domain (Llama answers yes/no, Python decides)** checks each guess on its own")
        st.code('Guess 1: supported by the review = yes, contradicts the intention = no  ->  KEEP\n'
                '         topic: results   evidence: "cannot see any change in my wrinkles"\n'
                'Guess 2: supported = yes, contradicts the intention = YES  ->  DROP\n'
                '         (the customer says "probably will not repurchase", not "undecided")', language=None)
        st.caption("If both guesses were dropped, the review would be flagged for a human instead.")

    with st.container(border=True):
        st.markdown("**Step 3. Prioritiser (plain Python)** counts across all reviews")
        st.code("If 12 of 30 reviews mention 'results' -> 40% of reviews\n"
                "40% is at least 25%  ->  priority HIGH\n"
                "(rule: 25% or more = High, 10% or more = Medium, otherwise Low)", language=None)

    with st.container(border=True):
        st.markdown("**Step 4. Validation (Llama) and confidence (Python)**")
        st.code('Advice: "Add clinical before/after evidence and a 4-week results guide to the product page."\n'
                "Is the advice about the topic?  yes   (+1 point)\n"
                "Is it specific and doable?      yes   (+1 point)\n"
                "Do many reviews support it?     yes   (+1 point)\n"
                "3 points  ->  confidence HIGH   (2 = Medium, 0 or 1 = Low and flagged)", language=None)

    with st.container(border=True):
        st.markdown("**Step 5. A person decides**")
        st.markdown("The brand manager sees the advice with its confidence level and presses "
                    "**Accept**, **Edit** or **Reject**. Nuance never acts on its own.")


def show_product_choice(meta, runs):
    """Say which products were chosen (the ones with the most reviews) and show their review counts."""
    counts = meta.get("product_counts") or {}
    if len(counts) == 0:
        return
    n = len(counts)
    plural = n > 1
    requested = meta.get("products_requested", n)
    in_file = meta.get("products_in_file", n)
    filters = meta.get("filters", "")
    where = f" (counting {filters})" if filters else ""
    names = ", ".join(f"**{name}**" for name in counts)

    st.info(f"**{n} product{'s' if plural else ''} analysed:** the {n} product{'s' if plural else ''} "
            f"with the most reviews{where} {'were' if plural else 'was'} chosen: {names}.")
    if requested > in_file:
        st.caption(f"You asked for {requested} products, but this file only has {in_file}, so all of them are analysed.")

    chart_data = pd.DataFrame({"Product": list(counts.keys()), "Number of reviews": list(counts.values())})
    chart_data["Label"] = ["\n".join(textwrap.wrap(name, 20, break_on_hyphens=False)) for name in chart_data["Product"]]   # wrap long names
    bars = (alt.Chart(chart_data)
            .mark_bar(color=ROSE, cornerRadiusTopLeft=5, cornerRadiusTopRight=5)
            .encode(x=alt.X("Label:N", sort=None, title="Product", axis=alt.Axis(labelAngle=0, labelLimit=400, labelFontSize=12, labelExpr="split(datum.label, '\\n')")),
                    y=alt.Y("Number of reviews:Q", title="Number of reviews"),
                    tooltip=["Product", "Number of reviews"]))
    numbers = bars.mark_text(dy=-8, fontSize=14, color=PLUM).encode(text="Number of reviews:Q")
    st.altair_chart((bars + numbers).properties(height=380), width="stretch")
    per_product = meta.get("reviews_per_product")
    if per_product:
        st.caption(f"The bars show all reviews available for each product. Nuance read up to {per_product} of them per product.")


# ---------------------------------------------------------------
# The results (the flow chart opens in a pop-up from the button at the top)
# ---------------------------------------------------------------
with button_slot:
    if st.button("How Nuance works", icon=":material/account_tree:"):
        show_flow()

meta = {}
if live_mode:
    runs = st.session_state.get("runs")
    meta = st.session_state.get("meta", {})
elif DEMO_AVAILABLE:
    runs, meta = load_demo()
    st.info("These are saved results from a real run of Nuance on Dior skincare reviews "
            f"(AI: {meta.get('model', 'Llama 3.1 8B')}). Nothing is being computed live.")
    with st.expander("What was analysed (brand context and topics)"):
        st.text(meta.get("brand_context", ""))
        st.text("Topics:\n" + meta.get("topics", ""))
else:
    runs = None
    st.warning("The demo file demo/dior_demo.json was not found. Switch to the second mode to analyse reviews.")

if runs is None:
    if live_mode:
        st.info("Add a file of reviews on the left, then press **Analyse reviews**.")
else:
    # Downloads: the PDF report (always) and the demo file (only when you analysed your own reviews)
    decisions = {}
    for run_name, run_data in runs.items():
        for item in run_data["briefing"]:
            decisions[(run_name, item["topic"])] = {
                "decision": st.session_state.get(f"decision_{run_name}_{item['topic']}", "Waiting"),
                "edit": st.session_state.get(f"edit_{run_name}_{item['topic']}", ""),
            }

    # What to download: the whole analysis or just one product's page
    whole_label = f"Whole analysis ({len(runs)} products)" if len(runs) > 1 else "Whole analysis"
    scope_options = [whole_label] + (list(runs.keys()) if len(runs) > 1 else [])
    scope = st.selectbox("What do you want to download?", scope_options, key="download_scope",
                         help="Choose the whole analysis, or only the page of one product.")
    if scope == whole_label:
        scope_runs, scope_meta, file_tag = runs, meta, "full"
    else:
        scope_runs = {scope: runs[scope]}
        scope_meta = dict(meta)
        scope_meta["product_counts"] = {k: v for k, v in meta.get("product_counts", {}).items() if k == scope}
        scope_meta["products_requested"] = 1
        file_tag = "".join(c if c.isalnum() else "_" for c in scope)[:40].strip("_").lower()

    download_pdf, download_json = st.columns(2)
    with download_pdf:
        try:
            baseline = {run_name: baseline_counts(run_data["reviews"]) for run_name, run_data in scope_runs.items()}
            pdf_bytes = make_pdf(scope_runs, scope_meta, decisions, baseline)
            st.download_button("Download the report (PDF)", data=pdf_bytes,
                               file_name=f"nuance_report_{file_tag}.pdf",
                               mime="application/pdf", key="pdf_report", type="primary")
        except Exception as error:
            st.caption(f"The PDF report could not be made: {error}")
    with download_json:
        st.download_button(
            "Save these results for demo mode (JSON)" if live_mode else "Download the results (JSON)",
            data=runs_to_json(scope_runs, scope_meta),
            file_name="dior_demo.json" if (live_mode and file_tag == "full") else f"nuance_results_{file_tag}.json",
            mime="application/json",
            key="save_demo",
        )

    show_product_choice(meta, runs)

    if len(runs) == 1:
        name = list(runs.keys())[0]
        show_product(name, runs[name])
    else:
        # Comparison table: share of reviews (%) per topic and per product
        st.subheader("Products side by side")
        compare = {}
        for name, run_data in runs.items():
            table_p = run_data["priority_table"]
            compare[name[:40]] = {row["topic"]: row["share_%"] for _, row in table_p.iterrows()}
        st.dataframe(pd.DataFrame(compare).fillna(0).astype(int), width="stretch")
        st.caption("Share of each product's reviews (%) that mention each topic.")

        tabs = st.tabs([name[:30] for name in runs.keys()])
        for tab, (name, run_data) in zip(tabs, runs.items()):
            with tab:
                st.markdown(f"## {name}")
                show_product(name, run_data)
