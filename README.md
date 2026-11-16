# Nuance

**Reads between the lines of customer reviews, and tells you what to fix first.**

Star ratings and sentiment scores say *how* customers feel. Nuance explains *why*: what customers believe, feel and
intend, which problems matter most, and what the brand should do about them. Every piece of advice comes with a
visible confidence level and waits for a person's decision (Accept, Edit or Reject).

Built for the M2 Quantitative Marketing & Applications course (Topic 3, MetaMind: Reading Between the Lines of Consumer
Feedback). The agent design follows Zhang et al. (2025), *MetaMind*.

## Try it without installing anything
Open the hosted demo: **<ADD YOUR STREAMLIT LINK HERE>**

It starts in **Demo mode**: saved results from a real run of Nuance on Dior skincare reviews (Sephora). You can explore the
charts, the ranked topics, the advice with confidence levels, press Accept / Edit / Reject, open the **How Nuance works**
pop-up (hover over each box), and download a PDF report. Nothing is computed live, so no AI and no API key are needed.

## How it works
| Step | Agent | What it does | Uses |
|---|---|---|---|
| 1 | Theory-of-Mind | Guesses what the customer believes, feels and intends (two different explanations per review) | Llama |
| 2 | Domain | Checks each guess against the review and the brand context, then keeps or drops it | Llama answers yes/no, Python decides |
| 3 | Prioritiser | Counts how many reviews mention each topic and ranks them (25% or more = High, 10% or more = Medium) | Python |
| 4 | Validation | Writes advice for each top topic, checks it, and gives a confidence level | Llama + Python |
| 5 | Human decision | Accept, Edit or Reject | Person |

Design choices: a small model gets small tasks (one guess per call, yes/no questions, one worked example per prompt), and plain
Python makes the decisions (keep or drop, counting, ranking, confidence score). Reviews where no guess survives are flagged for a human.

## Features
- Upload any CSV or TXT file of reviews. Optional filters for rating (3-star only), brand and product.
- Analyses the products with the most reviews (you choose 1 to 5) and shows a bar chart of their review counts.
- Topics are editable. Press **Suggest topics from my reviews** and Llama proposes them from your data.
- Normal sentiment analysis (VADER) shown next to Nuance's topics.
- One-click **PDF report** with the full analysis, including your decisions.
- Works for any product category (examples built in: hair diffuser, skincare).

## Run it yourself on your own reviews (needs Ollama)
The AI is **Llama 3.1 8B running locally with Ollama**, so there is no API key and no cloud account. Allow about 10 minutes
(mostly the model download) and a laptop with 8 GB of RAM or more.

1. **Install Ollama** from https://ollama.com/download and open it once.
2. **Download the model** (about 5 GB, once):
   ```
   ollama pull llama3.1:8b
   ```
3. **Get the code and install the packages** (Python 3.10 or newer):
   ```
   git clone <this repository's URL>
   cd <repository folder>
   python3 -m venv venv
   source venv/bin/activate          # Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```
4. **Start the app:**
   ```
   streamlit run app.py
   ```
5. In the sidebar choose **Analyse my own reviews**, drag in `sample_reviews.csv`, set the text column to `text`, the brand column to `brand_name` and the
   product column to `product_name`, and press **Analyse reviews**.

Speed: about 20 to 30 seconds per review. Use the slider (for example 5 reviews per product) for a quick test.

## Files
- `app.py`: the Streamlit screen.
- `agents.py`: the agents and the ranking.
- `report.py`: builds the PDF report.
- `sample_reviews.csv`: 40 three-star Dior reviews (10 per product) from the Sephora review dataset, for testing.
- `demo/dior_demo.json`: saved Dior results shown in Demo mode.
- `.streamlit/config.toml`: colour theme.
- `requirements.txt`: Python packages.

## Data
Sephora product and skincare reviews (Kaggle). The full dataset is not included because it is over 100 MB. Any CSV with a
review text column works.

## Limits
Nuance uses a small local model and a limited sample of reviews. A customer's intention (buy again or stop buying) is the
least reliable guess, so the ranking relies mostly on how often a topic appears. Treat the output as decision support,
not as a verdict: a person approves every recommendation.

## Team
<ADD TEAM MEMBER NAMES HERE>
